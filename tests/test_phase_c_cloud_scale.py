"""
Phase C Cloud Scale Architecture Verification Suite (100% Offline, Zero Cloud Spend):
1. PostgreSQL 16 SQL dialect translator (quote-aware ? -> %s, INSERT OR IGNORE, REAL -> DOUBLE PRECISION, PRAGMA skip) + RLS DDL.
2. PostgreSQL adapter execution parity + DBIntegrityError normalization + Idempotent SQLite -> Postgres Migration CLI.
3. S3 / Cloudflare R2 Object Storage backend (sync_dir_up, sync_dir_down, presigned URLs, GDPR delete_prefix) + Parquet LRU Cache.
4. Redis / RQ multi-worker queue routing (high/default/bulk), Pub/Sub SSE streaming, atomic rate limiter, and worker_entry E2E + /tmp wipe.
5. FastAPI /api/v1/system/cloud-status introspection + docker-compose.cloud.yml & cloud runbook verification.
"""
import io
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient

from autonomous_engine import api_server
from autonomous_engine.action_ledger import ActionLedger
from autonomous_engine.billing_manager import TenantBillingManager
from autonomous_engine.db_adapter import (
    DBIntegrityError,
    DatabaseAdapter,
    TENANT_SCOPED_TABLES,
    generate_postgres_unified_schema_sql,
    sanitize_database_url,
    translate_sql_for_postgres,
)
from autonomous_engine.oauth_connectors import OAuthVaultAndScheduleManager
from autonomous_engine.queue_backend import (
    DistributedQueueBackend,
    DistributedRateLimiter,
    select_queue_name,
)
from autonomous_engine.storage_backend import (
    LocalParquetLRUCache,
    S3ObjectStorageBackend,
    sanitize_storage_key,
)
from autonomous_engine.tenant_auth import TenantAuthManager
from autonomous_engine.worker_entry import execute_pipeline_job_task
from scripts.migrate_sqlite_to_postgres import migrate_sqlite_to_postgres


# -----------------------------------------------------------------------------
# Deterministic Offline Fakes for PostgreSQL, S3/R2, and Redis/RQ
# -----------------------------------------------------------------------------
class _FakePGCursor:
    """Translates PostgreSQL %s back to SQLite ? so we prove real PostgreSQL dialect execution offline."""

    def __init__(self, sqlite_conn: sqlite3.Connection):
        self._conn = sqlite_conn
        self._cur = sqlite_conn.cursor()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def execute(self, pg_sql: str, params=None):
        sql = pg_sql.replace("%s", "?").replace("%%", "%")
        if params is not None:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class _FakePGConnection:
    def __init__(self, db_path: Path):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def cursor(self):
        return _FakePGCursor(self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class _FakeS3Client:
    def __init__(self):
        self.objects: Dict[str, Dict[str, Any]] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, **kwargs):
        self.objects[f"{Bucket}/{Key}"] = {"Body": bytes(Body), "Meta": kwargs}

    def get_object(self, Bucket: str, Key: str):
        rec = self.objects.get(f"{Bucket}/{Key}")
        if rec is None:
            raise KeyError(f"NoSuchKey: {Key}")
        return {"Body": io.BytesIO(rec["Body"])}

    def head_object(self, Bucket: str, Key: str):
        if f"{Bucket}/{Key}" not in self.objects:
            raise KeyError(f"404: {Key}")
        return {"ContentLength": len(self.objects[f"{Bucket}/{Key}"]["Body"])}

    def list_objects_v2(self, Bucket: str, Prefix: str = "", **kwargs):
        b_pref = f"{Bucket}/{Prefix}"
        matched = [{"Key": k[len(Bucket) + 1:]} for k in sorted(self.objects.keys()) if k.startswith(b_pref)]
        return {"Contents": matched, "IsTruncated": False}

    def delete_objects(self, Bucket: str, Delete: Dict[str, Any]):
        for obj in Delete.get("Objects", []):
            self.objects.pop(f"{Bucket}/{obj['Key']}", None)
        return {"Deleted": Delete.get("Objects", [])}

    def generate_presigned_url(self, ClientMethod: str, Params: Dict[str, Any], ExpiresIn: int = 900):
        return f"https://s3.mock.local/{Params['Bucket']}/{Params['Key']}?X-Amz-Expires={ExpiresIn}"


class _FakePubSub:
    def __init__(self, redis_store: "_FakeRedis"):
        self._r = redis_store
        self._channels: List[str] = []

    def subscribe(self, channel: str):
        self._channels.append(channel)

    def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 0.5):
        for ch in self._channels:
            q = self._r.channels.get(ch)
            if q:
                return {"type": "message", "channel": ch, "data": q.pop(0)}
        return None

    def unsubscribe(self, channel: str):
        if channel in self._channels:
            self._channels.remove(channel)

    def close(self):
        pass


class _FakeRedis:
    def __init__(self):
        self.kv: Dict[str, Any] = {}
        self.ttls: Dict[str, int] = {}
        self.channels: Dict[str, List[str]] = {}

    def set(self, key: str, value: str, ex: Optional[int] = None):
        self.kv[key] = value
        if ex:
            self.ttls[key] = ex

    def get(self, key: str):
        return self.kv.get(key)

    def publish(self, channel: str, message: str):
        self.channels.setdefault(channel, []).append(message)

    def pubsub(self):
        return _FakePubSub(self)

    def incr(self, key: str) -> int:
        val = int(self.kv.get(key, 0)) + 1
        self.kv[key] = val
        return val

    def expire(self, key: str, ttl: int):
        self.ttls[key] = ttl


class _FakeRQQueue:
    def __init__(self, name: str, enqueued_log: List[Dict[str, Any]]):
        self.name = name
        self.enqueued_log = enqueued_log

    def enqueue(self, func_path: str, *args, **kwargs):
        rec = {"queue": self.name, "func": func_path, "args": args, "kwargs": kwargs}
        self.enqueued_log.append(rec)
        return type("RQJob", (), {"id": kwargs.get("job_id", "rq_1")})()


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
def test_postgres_dialect_translator_and_unified_rls_schema():
    # PRAGMA skipped cleanly
    assert translate_sql_for_postgres("PRAGMA journal_mode=WAL;") is None

    # Quote-aware ? -> %s (preserves '?' inside string literals and escapes '%')
    pg_q = translate_sql_for_postgres("SELECT * FROM users WHERE note != 'why?' AND pct LIKE '10%' AND id = ?", has_params=True)
    assert pg_q == "SELECT * FROM users WHERE note != 'why?' AND pct LIKE '10%%' AND id = %s"

    # INSERT OR IGNORE -> ON CONFLICT DO NOTHING
    pg_ins = translate_sql_for_postgres("INSERT OR IGNORE INTO processed_webhook_events (event_id) VALUES (?)", has_params=True)
    assert pg_ins == "INSERT INTO processed_webhook_events (event_id) VALUES (%s) ON CONFLICT DO NOTHING"

    # REAL -> DOUBLE PRECISION in DDL
    pg_ddl = translate_sql_for_postgres("CREATE TABLE t (id TEXT PRIMARY KEY, val REAL NOT NULL)", has_params=False)
    assert "DOUBLE PRECISION" in (pg_ddl or "") and "REAL" not in (pg_ddl or "")

    # Credential masking never exposes password
    masked = sanitize_database_url("postgresql://admin:SuperSecretPass!@db.prod.internal:5432/dataxray")
    assert "SuperSecretPass" not in masked and "admin" not in masked
    assert "db.prod.internal:5432/dataxray" in masked

    # Unified PostgreSQL 16 DDL contains all 12 tables & RLS policies
    schema = generate_postgres_unified_schema_sql(enable_rls=True)
    for tbl in TENANT_SCOPED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {tbl}" in schema
        assert f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;" in schema
        assert f"CREATE POLICY tenant_isolation_{tbl}" in schema
    assert "CREATE TABLE IF NOT EXISTS processed_webhook_events" in schema
    assert "CREATE TABLE IF NOT EXISTS pipeline_runs" in schema


def test_postgres_adapter_mock_execution_and_sqlite_migration_cli(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    state_dir = runs_dir / "state"
    ledger_dir = runs_dir / "action_ledgers"

    # Seed realistic single-node SQLite WAL data across managers
    auth = TenantAuthManager(state_dir=state_dir)
    reg = auth.register_user("founder@cloudscale.io", "StrongPassword!123", "CloudScale Inc")
    tid = reg["user"]["tenant_id"]

    bm = TenantBillingManager(state_dir=state_dir)
    bm.set_tenant_plan(tid, "pro", provider="stripe")
    bm.record_run_usage(tid, rows_audited=2500)

    ov = OAuthVaultAndScheduleManager(state_dir=state_dir)
    ov.save_encrypted_connection(tid, "shopify", {"shop_domain": "cs.myshopify.com", "access_token": "tok_enc_1"})
    ov.create_digest_schedule(tid, "Monday Digest", "run_id", "hotel_booking_cancellation", channel="email", recipient="founder@cloudscale.io")

    ledger = ActionLedger(storage_dir=ledger_dir)
    ledger.record_action(
        tenant_id=tid,
        run_id="run_001",
        entity_id="CUST-901",
        action_type="CONTACTED",
        notes="Called CFO",
        monetary_exposure=12500.0,
        status="RESOLVED",
    )

    # 1. Dry-run reports exact source row counts without mutating anything
    dry = migrate_sqlite_to_postgres(runs_dir, database_url="postgresql://u:p@host:5432/dx", dry_run=True)
    assert dry["status"] == "dry_run_complete"
    assert dry["total_source_rows"] >= 6

    # 2. Execute migration through real PostgreSQL dialect mode (using FakePGConnection)
    pg_backing = tmp_path / "simulated_postgres.sqlite"
    pg_adapter = DatabaseAdapter(
        tmp_path / "unused.sqlite",
        database_url="postgresql://dx_user:dx_pass@pg.internal:5432/dataxray",
        pg_connect_fn=lambda _url: _FakePGConnection(pg_backing),
    )
    assert pg_adapter.is_postgres is True
    assert pg_adapter.backend_name == "postgresql"

    mig1 = migrate_sqlite_to_postgres(runs_dir, enable_rls=False, target_adapter=pg_adapter)
    assert mig1["status"] == "migrated_and_verified"
    assert mig1["all_tables_verified"] is True
    assert mig1["total_migrated_rows"] == dry["total_source_rows"]

    # 3. Re-running migration is 100% idempotent (0 duplicates, identical row counts)
    mig2 = migrate_sqlite_to_postgres(runs_dir, enable_rls=False, target_adapter=pg_adapter)
    assert mig2["status"] == "migrated_and_verified"
    with pg_adapter.connect() as conn:
        u_cnt = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        assert u_cnt == 1
        # Verify DBIntegrityError subclass compatibility on duplicate primary key
        try:
            conn.execute(
                "INSERT INTO tenant_subscriptions (tenant_id, plan_id, status, provider, updated_at) VALUES (?, ?, ?, ?, ?)",
                (tid, "pro", "active", "stripe", time.time()),
            )
            assert False, "Duplicate PK MUST raise DBIntegrityError"
        except DBIntegrityError:
            pass


def test_s3_r2_object_storage_backend_sync_presign_gdpr_purge_and_lru_cache(tmp_path: Path):
    fake_s3 = _FakeS3Client()
    store = S3ObjectStorageBackend(
        bucket="dataxray-prod-artifacts",
        prefix="eu-central",
        endpoint_url=None,
        region="eu-central-1",
        sse_mode="AES256",
        s3_client=fake_s3,
    )

    # Path traversal blocked
    try:
        sanitize_storage_key("../../etc/passwd")
        assert False, "Traversal must fail"
    except ValueError:
        pass

    # Sync directory up -> verifies AES256 SSE header applied
    src_dir = tmp_path / "local_out"
    (src_dir / "semantic_model").mkdir(parents=True)
    (src_dir / "bi_ready_fact.parquet").write_bytes(b"PAR1_FAKE_PARQUET_BYTES")
    (src_dir / "semantic_model" / "model.tmdl").write_text("model Model", encoding="utf-8")

    up_cnt = store.sync_dir_up(src_dir, "tenants/acme/runs/run_77/output")
    assert up_cnt == 2
    assert fake_s3.objects["dataxray-prod-artifacts/eu-central/tenants/acme/runs/run_77/output/bi_ready_fact.parquet"]["Meta"]["ServerSideEncryption"] == "AES256"

    # Presigned URL works
    url = store.presign_download_url("tenants/acme/runs/run_77/output/bi_ready_fact.parquet", expires_sec=600)
    assert url and "X-Amz-Expires=600" in url

    # Sync directory down into clean folder
    dl_dir = tmp_path / "downloaded"
    dl_cnt = store.sync_dir_down("tenants/acme/runs/run_77/output", dl_dir)
    assert dl_cnt == 2
    assert (dl_dir / "bi_ready_fact.parquet").read_bytes() == b"PAR1_FAKE_PARQUET_BYTES"
    assert (dl_dir / "semantic_model" / "model.tmdl").read_text(encoding="utf-8") == "model Model"

    # Parquet LRU Cache bounded eviction (max_entries=2)
    store.put_bytes("p/1.parquet", b"P1")
    store.put_bytes("p/2.parquet", b"P2")
    store.put_bytes("p/3.parquet", b"P3")
    lru = LocalParquetLRUCache(tmp_path / "lru_cache", max_entries=2)
    f1 = lru.get_or_fetch("t/1", store, "p/1.parquet")
    f2 = lru.get_or_fetch("t/2", store, "p/2.parquet")
    f3 = lru.get_or_fetch("t/3", store, "p/3.parquet")
    assert not f1.exists()  # Evicted cleanly!
    assert f2.exists() and f3.exists()

    # GDPR Art. 17 prefix purge wipes all run artifacts
    purged = store.delete_prefix("tenants/acme/runs/run_77")
    assert purged == 2
    assert store.list_prefix("tenants/acme/runs/run_77") == []


def test_redis_rq_queue_routing_pubsub_rate_limiter_and_worker_task(tmp_path: Path):
    # 1. Queue priority routing
    assert select_queue_name(payload_bytes=512_000) == "high"
    assert select_queue_name(payload_bytes=25 * 1024 * 1024) == "default"
    assert select_queue_name(payload_bytes=150 * 1024 * 1024) == "bulk"
    assert select_queue_name(payload_bytes=1024, is_scheduled=True) == "bulk"

    # 2. Redis/RQ enqueue + Pub/Sub streaming
    fake_redis = _FakeRedis()
    enqueued_log: List[Dict[str, Any]] = []
    q_backend = DistributedQueueBackend(
        redis_url="redis://:secretpass@redis.prod:6379/0",
        redis_client=fake_redis,
        rq_queue_factory=lambda name, _conn: _FakeRQQueue(name, enqueued_log),
    )
    assert q_backend.is_redis is True
    assert "secretpass" not in q_backend.get_backend_info()["target"]

    disp = q_backend.enqueue_pipeline_job(
        {"job_id": "job_cloud_01", "tenant_id": "acme"},
        payload_bytes=200_000,
    )
    assert disp["dispatched_via"] == "redis_rq"
    assert disp["queue"] == "high"
    assert len(enqueued_log) == 1

    # 3. Distributed atomic rate limiter
    rl = DistributedRateLimiter(redis_url="redis://redis.prod:6379/0", redis_client=fake_redis)
    assert rl.allow_request("ip_1", max_requests=2, window_sec=60, now_ts=1000.0) == (True, 1)
    assert rl.allow_request("ip_1", max_requests=2, window_sec=60, now_ts=1001.0) == (True, 2)
    assert rl.allow_request("ip_1", max_requests=2, window_sec=60, now_ts=1002.0) == (False, 3)

    # 4. Stateless Worker E2E: S3 download -> run pipeline -> S3 upload -> DB update -> Pub/Sub -> /tmp cleanup
    fake_s3 = _FakeS3Client()
    s3_store = S3ObjectStorageBackend(bucket="dx-worker-test", s3_client=fake_s3)
    s3_store.put_bytes("tenants/acme/runs/job_cloud_01/raw_data/orders.csv", b"order_id,amount,status\n1,100,Returned\n")

    jobs_db = DatabaseAdapter(tmp_path / "jobs.sqlite")
    with jobs_db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY, tenant_id TEXT, run_root TEXT, mode TEXT,
                region_profile TEXT, language TEXT, target_override TEXT, cost_override TEXT,
                status TEXT, current_stage TEXT, progress_pct INTEGER, created_at REAL,
                started_at REAL, completed_at REAL, error TEXT, result_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO jobs VALUES ('job_cloud_01','acme','/tmp','templated','US','en',NULL,NULL,'QUEUED','QUEUED',0,1.0,NULL,NULL,NULL,NULL)"
        )

    captured_scratch: List[Path] = []

    def _fake_pipeline(data_dir: str, output_dir: str, cache_dir: str, **kwargs) -> bool:
        captured_scratch.append(Path(data_dir).parent)
        assert (Path(data_dir) / "orders.csv").exists()
        (Path(output_dir) / "bi_ready_fact.parquet").write_bytes(b"PARQUET_VERIFIED")
        (Path(output_dir) / "bespoke_executive_dashboard.html").write_text("<html>OK</html>", encoding="utf-8")
        return True

    res = execute_pipeline_job_task(
        {"job_id": "job_cloud_01", "tenant_id": "acme", "mode": "templated", "region_profile": "US"},
        db_adapter=jobs_db,
        storage=s3_store,
        queue_backend=q_backend,
        pipeline_runner=_fake_pipeline,
    )
    assert res["status"] == "COMPLETED"
    assert res["uploaded_output_artifacts"] == 2
    assert s3_store.exists("tenants/acme/runs/job_cloud_01/output/bi_ready_fact.parquet")
    assert len(captured_scratch) == 1 and not captured_scratch[0].exists()  # /tmp wiped cleanly!

    with jobs_db.connect() as conn:
        row = conn.execute("SELECT status, progress_pct FROM jobs WHERE job_id = ?", ("job_cloud_01",)).fetchone()
        assert row["status"] == "COMPLETED" and int(row["progress_pct"]) == 100

    # Verify Pub/Sub received terminal COMPLETED event
    events = list(q_backend.iter_job_events("job_cloud_01", max_events=20, poll_timeout=0.05))
    assert any(ev.get("status") == "COMPLETED" for ev in events)


def test_api_cloud_status_endpoint_and_cloud_compose_hardening():
    client = TestClient(api_server.app)
    r = client.get("/api/v1/system/cloud-status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["backend"] in ("sqlite_wal", "postgresql")
    assert body["storage"]["backend"] in ("local_filesystem", "s3_r2_object_store")
    assert body["queue"]["backend"] in ("local_threadpool", "redis_rq")

    root = Path(__file__).resolve().parent.parent
    cloud_compose = (root / "docker-compose.cloud.yml").read_text(encoding="utf-8")
    req_cloud = (root / "requirements-cloud.txt").read_text(encoding="utf-8")
    env_ex = (root / ".env.production.example").read_text(encoding="utf-8")
    runbook = (root / "deploy" / "DEPLOYMENT_RUNBOOK.md").read_text(encoding="utf-8")

    assert "postgres:16-alpine" in cloud_compose
    assert "redis:7-alpine" in cloud_compose
    assert "autonomous_engine.worker_entry" in cloud_compose
    assert "psycopg" in req_cloud and "boto3" in req_cloud and "rq" in req_cloud
    assert "DATABASE_URL=" in env_ex and "REDIS_URL=" in env_ex and "DATAXRAY_S3_BUCKET=" in env_ex
    assert "migrate_sqlite_to_postgres.py" in runbook
