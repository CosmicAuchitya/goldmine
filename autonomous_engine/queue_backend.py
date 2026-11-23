"""
=============================================================================
DATAX-RAY PHASE C — REDIS / RQ MULTI-WORKER QUEUE, PUB/SUB & RATE LIMITER
=============================================================================
Provides horizontal multi-worker execution and cross-pod coordination:
- Local Single-Node (`REDIS_URL` unset): runs jobs on an in-process
  `ThreadPoolExecutor`, tracks SSE events in memory, and applies local IP
  sliding-window rate limits (zero external Redis required!).
- Cloud Scale (`REDIS_URL=redis://...`):
  1. Enqueues jobs onto prioritized RQ queues (`high`, `default`, `bulk`) so
     small interactive uploads stay fast while 500 MB / scheduled jobs isolate
     on dedicated workers.
  2. Broadcasts job progress via Redis Pub/Sub (`dx:job:{job_id}`) so ANY
     stateless API pod can stream `/api/v1/jobs/{job_id}/events` SSE seamlessly.
  3. Enforces distributed atomic rate limits (`INCR` + `EXPIRE`) across all
     horizontal FastAPI replicas.
=============================================================================
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Deque, Dict, Iterator, Optional, Tuple


HIGH_PRIORITY_THRESHOLD_BYTES = 10 * 1024 * 1024    # < 10 MB -> high
BULK_PRIORITY_THRESHOLD_BYTES = 100 * 1024 * 1024   # >= 100 MB -> bulk


def is_redis_url(url: Optional[str]) -> bool:
    u = str(url or "").strip().lower()
    return u.startswith(("redis://", "rediss://"))


def sanitize_redis_url(url: Optional[str]) -> str:
    raw = str(url or "").strip()
    if not raw:
        return "local_threadpool"
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.hostname or "localhost"
        port = f":{parsed.port}" if parsed.port else ""
        path = parsed.path or "/0"
        return f"{parsed.scheme}://***@{host}{port}{path}"
    except Exception:
        return "redis://***"


def select_queue_name(payload_bytes: int = 0, is_scheduled: bool = False) -> str:
    """Routes small interactive uploads to 'high', large/scheduled jobs to 'bulk', else 'default'."""
    if is_scheduled or int(payload_bytes or 0) >= BULK_PRIORITY_THRESHOLD_BYTES:
        return "bulk"
    if 0 < int(payload_bytes or 0) < HIGH_PRIORITY_THRESHOLD_BYTES:
        return "high"
    return "default"


class DistributedQueueBackend:
    """Dual-mode job dispatcher and cross-pod SSE Pub/Sub event bus."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        max_local_workers: int = 4,
        redis_client: Optional[Any] = None,
        rq_queue_factory: Optional[Callable[[str, Any], Any]] = None,
    ):
        env_url = os.environ.get("REDIS_URL", "").strip()
        resolved_url = (redis_url if redis_url is not None else env_url).strip()
        self.redis_url = resolved_url
        self.is_redis = is_redis_url(resolved_url) or (redis_client is not None)
        self._redis_client = redis_client
        self._rq_queue_factory = rq_queue_factory
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_local_workers)))
        self._local_lock = threading.Lock()
        self._local_latest: Dict[str, Dict[str, Any]] = {}

    @property
    def backend_name(self) -> str:
        return "redis_rq" if self.is_redis else "local_threadpool"

    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "target": sanitize_redis_url(self.redis_url) if self.is_redis else "in_process_threadpool",
            "queues": ["high", "default", "bulk"],
            "pubsub_sse_enabled": self.is_redis,
            "horizontal_multi_pod_ready": self.is_redis,
        }

    def _get_redis(self) -> Any:
        if self._redis_client is not None:
            return self._redis_client
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "REDIS_URL is configured, but 'redis' package is not installed. "
                "Install with: pip install redis rq"
            ) from exc
        self._redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client

    def _get_rq_queue(self, queue_name: str) -> Any:
        r_conn = self._get_redis()
        if self._rq_queue_factory is not None:
            return self._rq_queue_factory(queue_name, r_conn)
        try:
            from rq import Queue
        except ImportError as exc:
            raise RuntimeError(
                "REDIS_URL is configured, but 'rq' package is not installed. "
                "Install with: pip install redis rq"
            ) from exc
        return Queue(name=queue_name, connection=r_conn)

    def enqueue_pipeline_job(
        self,
        job_spec: Dict[str, Any],
        local_runner: Optional[Callable[[], None]] = None,
        payload_bytes: int = 0,
        is_scheduled: bool = False,
        job_timeout: int = 600,
    ) -> Dict[str, Any]:
        """Enqueues a pipeline job onto Redis/RQ in cloud mode or ThreadPoolExecutor locally."""
        q_name = select_queue_name(payload_bytes=payload_bytes, is_scheduled=is_scheduled)
        job_id = str(job_spec["job_id"])

        if self.is_redis:
            q = self._get_rq_queue(q_name)
            rq_job = q.enqueue(
                "autonomous_engine.worker_entry.execute_pipeline_job_task",
                job_spec,
                job_id=job_id,
                job_timeout=int(job_timeout),
                result_ttl=86400,
                failure_ttl=604800,
            )
            self.publish_job_event(
                job_id,
                {
                    "job_id": job_id,
                    "status": "QUEUED",
                    "current_stage": "QUEUED_IN_REDIS_RQ",
                    "queue": q_name,
                    "progress_pct": 0,
                    "timestamp": time.time(),
                },
            )
            return {
                "dispatched_via": "redis_rq",
                "queue": q_name,
                "job_id": getattr(rq_job, "id", job_id),
            }

        if local_runner is None:
            raise ValueError("local_runner callable is required when running in local_threadpool mode.")
        self._executor.submit(local_runner)
        return {
            "dispatched_via": "local_threadpool",
            "queue": q_name,
            "job_id": job_id,
        }

    def publish_job_event(self, job_id: str, payload: Dict[str, Any]) -> None:
        """Broadcasts job progress event to Redis Pub/Sub + state snapshot (or local cache)."""
        serialized = json.dumps(payload, default=str)
        if self.is_redis:
            r = self._get_redis()
            r.set(f"dx:job_state:{job_id}", serialized, ex=3600)
            r.publish(f"dx:job:{job_id}", serialized)
            return
        with self._local_lock:
            self._local_latest[job_id] = dict(payload)

    def get_latest_job_event(self, job_id: str) -> Optional[Dict[str, Any]]:
        if self.is_redis:
            raw = self._get_redis().get(f"dx:job_state:{job_id}")
            if not raw:
                return None
            return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else str(raw))
        with self._local_lock:
            ev = self._local_latest.get(job_id)
            return dict(ev) if ev is not None else None

    def iter_job_events(self, job_id: str, max_events: int = 100, poll_timeout: float = 0.5) -> Iterator[Dict[str, Any]]:
        """Yields Pub/Sub events for a job on Redis (terminates once COMPLETED/FAILED/PURGED)."""
        if not self.is_redis:
            latest = self.get_latest_job_event(job_id)
            if latest:
                yield latest
            return

        r = self._get_redis()
        pubsub = r.pubsub()
        channel = f"dx:job:{job_id}"
        pubsub.subscribe(channel)
        emitted = 0
        try:
            while emitted < max_events:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=poll_timeout)
                if not msg:
                    latest = self.get_latest_job_event(job_id)
                    if latest and latest.get("status") in ("COMPLETED", "FAILED", "PURGED"):
                        yield latest
                        break
                    continue
                raw = msg.get("data")
                if not raw:
                    continue
                ev = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else str(raw))
                yield ev
                emitted += 1
                if ev.get("status") in ("COMPLETED", "FAILED", "PURGED"):
                    break
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass


class DistributedRateLimiter:
    """
    Shared API / Gemini rate limiter:
    - Uses atomic Redis INCR + EXPIRE counters when REDIS_URL or redis_client is provided.
    - Falls back cleanly to a thread-safe in-process sliding window deque when offline.
    """

    def __init__(self, redis_url: Optional[str] = None, redis_client: Optional[Any] = None):
        env_url = os.environ.get("REDIS_URL", "").strip()
        resolved_url = (redis_url if redis_url is not None else env_url).strip()
        self.redis_url = resolved_url
        self.is_redis = is_redis_url(resolved_url) or (redis_client is not None)
        self._redis_client = redis_client
        self._lock = threading.Lock()
        self._local_windows: Dict[str, Deque[float]] = defaultdict(deque)

    def _get_redis(self) -> Any:
        if self._redis_client is not None:
            return self._redis_client
        import redis
        self._redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client

    def allow_request(
        self,
        client_key: str,
        max_requests: int,
        window_sec: int = 60,
        now_ts: Optional[float] = None,
    ) -> Tuple[bool, int]:
        """Returns (is_allowed, current_count) for the given client key within window_sec."""
        limit = max(1, int(max_requests))
        win = max(1, int(window_sec))
        now = float(now_ts if now_ts is not None else time.time())

        if self.is_redis:
            bucket = int(now // win)
            r_key = f"dx:rl:{client_key}:{bucket}"
            try:
                r = self._get_redis()
                cnt = int(r.incr(r_key))
                if cnt == 1:
                    r.expire(r_key, win + 5)
                return (cnt <= limit), cnt
            except Exception:
                # Fail-open to local window rather than crashing traffic on transient Redis blip
                pass

        with self._lock:
            dq = self._local_windows[client_key]
            cutoff = now - win
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= limit:
                return False, len(dq)
            dq.append(now)
            return True, len(dq)
