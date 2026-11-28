"""
=============================================================================
DATAX-RAY GLOBAL SUBSCRIPTION BILLING, WEBHOOK & QUOTA ENGINE (STRIPE + RAZORPAY)
=============================================================================
Production-grade, zero-dependency subscription & metering engine:
1. Global Pricing Tiers: Free Trial, Starter ($49 / ₹3,999), Pro ($199 / ₹14,999),
   Enterprise ($799 / ₹64,999).
2. Persistent Thread-Safe SQLite WAL Store (`runs/state/billing_plans.sqlite`)
   with per-tenant monthly run & Q&A metering and idempotent webhook event ledger.
3. Cryptographic HMAC-SHA256 Webhook Verification:
   - Stripe (`Stripe-Signature`: timestamp replay protection <= 300s + constant-time digest)
   - Razorpay (`X-Razorpay-Signature`: constant-time digest over raw payload)
4. Live Checkout Session Creation (Stripe Checkout API & Razorpay Payment Links API)
   with honest configuration-required fallback when live keys are not yet provisioned.
5. Non-breaking quota enforcement gated by `DATAXRAY_ENFORCE_BILLING_QUOTAS=true`.
=============================================================================
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .tenant_auth import sanitize_tenant_id
    from .db_adapter import DatabaseAdapter
except ImportError:
    from tenant_auth import sanitize_tenant_id
    from db_adapter import DatabaseAdapter


WORKSPACE_ROOT = Path.cwd().resolve()

BILLING_PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "plan_id": "free",
        "name": "Free Trial",
        "price_usd_monthly": 0,
        "price_inr_monthly": 0,
        "max_runs_per_month": 3,
        "max_rows_per_run": 10_000,
        "max_qa_per_month": 50,
        "scheduled_digests": False,
        "live_connectors": False,
        "features": [
            "3 audited runs / month (up to 10,000 rows each)",
            "50 DuckDB grounded English/Hinglish Q&A queries / month",
            "Air-gapped bespoke interactive HTML dashboard & Priority Worklist",
        ],
    },
    "starter": {
        "plan_id": "starter",
        "name": "Starter",
        "price_usd_monthly": 49,
        "price_inr_monthly": 3999,
        "max_runs_per_month": 25,
        "max_rows_per_run": 100_000,
        "max_qa_per_month": 500,
        "scheduled_digests": True,
        "live_connectors": True,
        "features": [
            "25 audited runs / month (up to 100,000 rows each)",
            "500 DuckDB grounded Q&A queries / month",
            "Automated Morning Digest alerts (Email / WhatsApp / Slack)",
            "Multi-table ZIP & multi-tab CFO Excel support",
        ],
    },
    "pro": {
        "plan_id": "pro",
        "name": "Pro Growth",
        "price_usd_monthly": 199,
        "price_inr_monthly": 14999,
        "max_runs_per_month": 150,
        "max_rows_per_run": 500_000,
        "max_qa_per_month": 5_000,
        "scheduled_digests": True,
        "live_connectors": True,
        "features": [
            "150 audited runs / month (up to 500,000 rows each)",
            "5,000 Q&A queries / month + Live API connectors (Shopify, Stripe, Razorpay, Zoho, WooCommerce)",
            "Forensic fraud, duplicate billing, AR cash-gap & Simpson's Paradox audits",
            "Power BI / Fabric TMDL semantic model export",
        ],
    },
    "enterprise": {
        "plan_id": "enterprise",
        "name": "Enterprise",
        "price_usd_monthly": 799,
        "price_inr_monthly": 64999,
        "max_runs_per_month": 100_000,
        "max_rows_per_run": 5_000_000,
        "max_qa_per_month": 1_000_000,
        "scheduled_digests": True,
        "live_connectors": True,
        "features": [
            "Unlimited audited runs (up to 5M rows/run)",
            "Unlimited grounded Q&A & scheduled drift monitoring",
            "Dedicated on-prem / VPC Docker deployment & GDPR Art. 17 API",
            "Priority SLA & custom connector onboarding",
        ],
    },
}


def is_billing_quota_enforced() -> bool:
    return os.environ.get("DATAXRAY_ENFORCE_BILLING_QUOTAS", "false").strip().lower() in ("1", "true", "yes")


def _current_month_key() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")


def verify_stripe_webhook_signature(
    raw_body: bytes,
    sig_header: str,
    webhook_secret: str,
    tolerance_sec: int = 300,
    now_ts: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Verifies Stripe `Stripe-Signature` header (`t=<unix_ts>,v1=<hex_hmac>`).
    Uses constant-time digest comparison and enforces replay window <= tolerance_sec.
    """
    if not webhook_secret:
        return False, "Stripe webhook secret (STRIPE_WEBHOOK_SECRET) is not configured."
    if not sig_header:
        return False, "Missing Stripe-Signature header."

    timestamp: Optional[int] = None
    v1_sigs: List[str] = []
    for part in str(sig_header).split(","):
        if "=" not in part:
            continue
        k, v = part.strip().split("=", 1)
        if k == "t":
            try:
                timestamp = int(v)
            except ValueError:
                return False, "Malformed Stripe-Signature timestamp."
        elif k == "v1":
            v1_sigs.append(v.strip())

    if timestamp is None or not v1_sigs:
        return False, "Stripe-Signature missing required 't' or 'v1' fields."

    curr = int(now_ts if now_ts is not None else time.time())
    if abs(curr - timestamp) > tolerance_sec:
        return False, f"Stripe webhook timestamp outside replay tolerance ({tolerance_sec}s)."

    signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
    expected_hex = hmac.new(webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if any(hmac.compare_digest(expected_hex, cand) for cand in v1_sigs):
        return True, "ok"
    return False, "Invalid Stripe webhook signature."


def verify_razorpay_webhook_signature(
    raw_body: bytes,
    sig_header: str,
    webhook_secret: str,
) -> Tuple[bool, str]:
    """
    Verifies Razorpay `X-Razorpay-Signature` HMAC-SHA256 hex digest over exact raw body.
    """
    if not webhook_secret:
        return False, "Razorpay webhook secret (RAZORPAY_WEBHOOK_SECRET) is not configured."
    if not sig_header:
        return False, "Missing X-Razorpay-Signature header."

    expected_hex = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected_hex, str(sig_header).strip()):
        return True, "ok"
    return False, "Invalid Razorpay webhook signature."


class TenantBillingManager:
    """Thread-safe SQLite WAL subscription, quota metering & payment webhook manager."""

    def __init__(self, state_dir: Optional[Path] = None, database_url: Optional[str] = None):
        self.state_dir = (state_dir or (WORKSPACE_ROOT / "runs" / "state")).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "billing_plans.sqlite"
        self.db = DatabaseAdapter(self.db_path, database_url=database_url)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return self.db.connect()

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_subscriptions (
                    tenant_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL DEFAULT 'free',
                    status TEXT NOT NULL DEFAULT 'active',
                    provider TEXT NOT NULL DEFAULT 'none',
                    external_customer_id TEXT,
                    external_subscription_id TEXT,
                    current_period_end REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            # Idempotent schema upgrade for existing DBs created before current_period_end
            try:
                conn.execute("ALTER TABLE tenant_subscriptions ADD COLUMN current_period_end REAL")
            except Exception:
                pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_monthly_usage (
                    tenant_id TEXT NOT NULL,
                    month_key TEXT NOT NULL,
                    runs_used INTEGER NOT NULL DEFAULT 0,
                    qa_used INTEGER NOT NULL DEFAULT 0,
                    rows_audited INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (tenant_id, month_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_webhook_events (
                    event_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    tenant_id TEXT,
                    processed_at REAL NOT NULL
                )
                """
            )

    def get_plan_catalog(self) -> List[Dict[str, Any]]:
        return [BILLING_PLANS[k] for k in ("free", "starter", "pro", "enterprise")]

    def set_tenant_plan(
        self,
        tenant_id: str,
        plan_id: str,
        provider: str = "manual",
        external_customer_id: Optional[str] = None,
        external_subscription_id: Optional[str] = None,
        status: str = "active",
        current_period_end: Optional[float] = None,
    ) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        norm_plan = str(plan_id or "free").strip().lower()
        if norm_plan not in BILLING_PLANS:
            norm_plan = "free"
        now = time.time()
        eff_period_end = None if norm_plan == "free" else (float(current_period_end) if current_period_end is not None else None)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tenant_subscriptions (
                    tenant_id, plan_id, status, provider, external_customer_id, external_subscription_id, current_period_end, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    plan_id=excluded.plan_id,
                    status=excluded.status,
                    provider=excluded.provider,
                    external_customer_id=COALESCE(excluded.external_customer_id, tenant_subscriptions.external_customer_id),
                    external_subscription_id=COALESCE(excluded.external_subscription_id, tenant_subscriptions.external_subscription_id),
                    current_period_end=excluded.current_period_end,
                    updated_at=excluded.updated_at
                """,
                (norm_tid, norm_plan, status, provider, external_customer_id, external_subscription_id, eff_period_end, now),
            )
        return self.get_tenant_billing_status(norm_tid)

    def get_tenant_billing_status(self, tenant_id: str) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        mkey = _current_month_key()
        now = time.time()
        with self._lock, self._connect() as conn:
            sub = conn.execute(
                "SELECT * FROM tenant_subscriptions WHERE tenant_id = ?",
                (norm_tid,),
            ).fetchone()
            usage = conn.execute(
                "SELECT * FROM tenant_monthly_usage WHERE tenant_id = ? AND month_key = ?",
                (norm_tid, mkey),
            ).fetchone()

            plan_id = str(sub["plan_id"]) if sub else "free"
            sub_status = str(sub["status"]) if sub else "active"
            provider = str(sub["provider"]) if sub else "none"
            period_end_raw = None
            if sub is not None:
                try:
                    period_end_raw = sub["current_period_end"]
                except Exception:
                    period_end_raw = None
            current_period_end = float(period_end_raw) if period_end_raw is not None else None

            # Auto-expire lapsed time-bounded subscriptions (e.g., Razorpay one-time 30-day payment links)
            if (
                plan_id != "free"
                and sub_status in ("active", "trialing")
                and current_period_end is not None
                and current_period_end < now
            ):
                plan_id = "free"
                sub_status = "expired"
                conn.execute(
                    "UPDATE tenant_subscriptions SET plan_id = 'free', status = 'expired', updated_at = ? WHERE tenant_id = ?",
                    (now, norm_tid),
                )

        if sub_status not in ("active", "trialing"):
            plan_id = "free"
        plan_cfg = BILLING_PLANS.get(plan_id, BILLING_PLANS["free"])

        runs_used = int(usage["runs_used"]) if usage else 0
        qa_used = int(usage["qa_used"]) if usage else 0
        rows_audited = int(usage["rows_audited"]) if usage else 0

        return {
            "tenant_id": norm_tid,
            "plan_id": plan_cfg["plan_id"],
            "plan_name": plan_cfg["name"],
            "subscription_status": sub_status,
            "provider": provider,
            "current_period_end": current_period_end,
            "billing_period": mkey,
            "quota_enforcement_active": is_billing_quota_enforced(),
            "usage": {
                "runs_used": runs_used,
                "runs_limit": plan_cfg["max_runs_per_month"],
                "runs_remaining": max(0, plan_cfg["max_runs_per_month"] - runs_used),
                "qa_used": qa_used,
                "qa_limit": plan_cfg["max_qa_per_month"],
                "qa_remaining": max(0, plan_cfg["max_qa_per_month"] - qa_used),
                "rows_audited_this_month": rows_audited,
                "max_rows_per_run": plan_cfg["max_rows_per_run"],
            },
            "entitlements": {
                "scheduled_digests": plan_cfg["scheduled_digests"],
                "live_connectors": plan_cfg["live_connectors"],
            },
        }

    def check_run_quota(self, tenant_id: str, is_admin: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        st = self.get_tenant_billing_status(tenant_id)
        if is_admin or not is_billing_quota_enforced():
            return True, "ok", st
        if st["usage"]["runs_used"] >= st["usage"]["runs_limit"]:
            return (
                False,
                f"Monthly run limit reached ({st['usage']['runs_used']}/{st['usage']['runs_limit']} on {st['plan_name']}). Upgrade via /api/v1/billing/checkout to unlock higher limits.",
                st,
            )
        return True, "ok", st

    def check_row_limit(self, tenant_id: str, row_count: int, is_admin: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        """Enforces per-run dataset row ceiling (`max_rows_per_run`) when billing quotas are active."""
        st = self.get_tenant_billing_status(tenant_id)
        if is_admin or not is_billing_quota_enforced():
            return True, "ok", st
        max_rows = int(st["usage"].get("max_rows_per_run") or 0)
        if max_rows > 0 and int(row_count or 0) > max_rows:
            return (
                False,
                f"Dataset row count ({int(row_count):,}) exceeds your {st['plan_name']} limit of {max_rows:,} rows/run. Upgrade via /api/v1/billing/checkout to analyze larger datasets.",
                st,
            )
        return True, "ok", st

    def check_feature_access(self, tenant_id: str, feature_key: str, is_admin: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        """Enforces plan feature entitlements (`live_connectors`, `scheduled_digests`) when billing quotas are active."""
        st = self.get_tenant_billing_status(tenant_id)
        if is_admin or not is_billing_quota_enforced():
            return True, "ok", st
        ent = st.get("entitlements") or {}
        if not bool(ent.get(feature_key, False)):
            nice = str(feature_key).replace("_", " ").title()
            return (
                False,
                f"Feature '{nice}' is not included in your {st['plan_name']}. Upgrade via /api/v1/billing/checkout to enable {nice}.",
                st,
            )
        return True, "ok", st

    def check_qa_quota(self, tenant_id: str, is_admin: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        st = self.get_tenant_billing_status(tenant_id)
        if is_admin or not is_billing_quota_enforced():
            return True, "ok", st
        if st["usage"]["qa_used"] >= st["usage"]["qa_limit"]:
            return (
                False,
                f"Monthly Q&A query limit reached ({st['usage']['qa_used']}/{st['usage']['qa_limit']} on {st['plan_name']}). Upgrade your plan to continue.",
                st,
            )
        return True, "ok", st

    def record_run_usage(self, tenant_id: str, rows_audited: int = 0) -> None:
        norm_tid = sanitize_tenant_id(tenant_id)
        mkey = _current_month_key()
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tenant_monthly_usage (tenant_id, month_key, runs_used, qa_used, rows_audited, updated_at)
                VALUES (?, ?, 1, 0, ?, ?)
                ON CONFLICT(tenant_id, month_key) DO UPDATE SET
                    runs_used = tenant_monthly_usage.runs_used + 1,
                    rows_audited = tenant_monthly_usage.rows_audited + excluded.rows_audited,
                    updated_at = excluded.updated_at
                """,
                (norm_tid, mkey, max(0, int(rows_audited or 0)), now),
            )

    def record_qa_usage(self, tenant_id: str) -> None:
        norm_tid = sanitize_tenant_id(tenant_id)
        mkey = _current_month_key()
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tenant_monthly_usage (tenant_id, month_key, runs_used, qa_used, rows_audited, updated_at)
                VALUES (?, ?, 0, 1, 0, ?)
                ON CONFLICT(tenant_id, month_key) DO UPDATE SET
                    qa_used = tenant_monthly_usage.qa_used + 1,
                    updated_at = excluded.updated_at
                """,
                (norm_tid, mkey, now),
            )

    def _is_event_processed(self, event_id: str) -> bool:
        if not event_id:
            return False
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT 1 FROM processed_webhook_events WHERE event_id = ?", (event_id,)).fetchone()
            return row is not None

    def _mark_event_processed(self, event_id: str, provider: str, event_type: str, tenant_id: Optional[str]) -> None:
        if not event_id:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_webhook_events (event_id, provider, event_type, tenant_id, processed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, provider, event_type, tenant_id, time.time()),
            )

    def handle_stripe_webhook(self, raw_body: bytes, sig_header: str) -> Dict[str, Any]:
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
        ok, msg = verify_stripe_webhook_signature(raw_body, sig_header, secret)
        if not ok:
            raise PermissionError(msg)

        payload = json.loads(raw_body.decode("utf-8"))
        event_id = str(payload.get("id") or "")
        event_type = str(payload.get("type") or "")
        if event_id and self._is_event_processed(event_id):
            return {"status": "duplicate_ignored", "event_id": event_id, "event_type": event_type}

        obj = (payload.get("data") or {}).get("object") or {}
        meta = obj.get("metadata") or {}
        tenant_id = meta.get("tenant_id") or obj.get("client_reference_id")
        plan_id = str(meta.get("plan_id") or "pro").lower()
        cust_id = obj.get("customer")
        sub_id = obj.get("subscription") or (obj.get("id") if event_type.startswith("customer.subscription") else None)

        updated_status = None
        if tenant_id:
            if event_type in ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"):
                sub_state = str(obj.get("status") or "active").lower()
                if sub_state in ("active", "trialing", "complete", "paid"):
                    updated_status = self.set_tenant_plan(
                        tenant_id=str(tenant_id),
                        plan_id=plan_id,
                        provider="stripe",
                        external_customer_id=str(cust_id) if cust_id else None,
                        external_subscription_id=str(sub_id) if sub_id else None,
                        status="active",
                    )
                elif sub_state in ("canceled", "unpaid", "past_due", "incomplete_expired"):
                    updated_status = self.set_tenant_plan(
                        tenant_id=str(tenant_id),
                        plan_id="free",
                        provider="stripe",
                        status=sub_state,
                    )
            elif event_type == "customer.subscription.deleted":
                updated_status = self.set_tenant_plan(
                    tenant_id=str(tenant_id),
                    plan_id="free",
                    provider="stripe",
                    status="canceled",
                )

        self._mark_event_processed(event_id, "stripe", event_type, str(tenant_id) if tenant_id else None)
        return {
            "status": "processed",
            "provider": "stripe",
            "event_id": event_id,
            "event_type": event_type,
            "tenant_billing": updated_status,
        }

    def handle_razorpay_webhook(self, raw_body: bytes, sig_header: str) -> Dict[str, Any]:
        secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()
        ok, msg = verify_razorpay_webhook_signature(raw_body, sig_header, secret)
        if not ok:
            raise PermissionError(msg)

        payload = json.loads(raw_body.decode("utf-8"))
        event_type = str(payload.get("event") or "")
        event_id = str(payload.get("id") or hashlib.sha256(raw_body).hexdigest()[:32])
        if self._is_event_processed(event_id):
            return {"status": "duplicate_ignored", "event_id": event_id, "event_type": event_type}

        p_body = payload.get("payload") or {}
        sub_ent = ((p_body.get("subscription") or {}).get("entity")) or {}
        plink_ent = ((p_body.get("payment_link") or {}).get("entity")) or {}
        pay_ent = ((p_body.get("payment") or {}).get("entity")) or {}
        notes = sub_ent.get("notes") or plink_ent.get("notes") or pay_ent.get("notes") or {}

        tenant_id = notes.get("tenant_id")
        plan_id = str(notes.get("plan_id") or "starter").lower()
        sub_id = sub_ent.get("id") or plink_ent.get("id")
        cust_id = sub_ent.get("customer_id") or pay_ent.get("email")

        updated_status = None
        if tenant_id:
            if event_type in ("subscription.activated", "subscription.charged", "payment_link.paid", "payment.captured"):
                now = time.time()
                # Prevent one-time payment links from granting permanent lifetime paid access:
                # always attach an explicit expiration timestamp (current_end from Razorpay subscription or 30-day cycle).
                period_end: float
                if sub_ent.get("current_end"):
                    try:
                        # Add 24h webhook-delivery grace window after Razorpay's current_end
                        period_end = float(sub_ent["current_end"]) + 86400.0
                    except Exception:
                        period_end = now + 31.0 * 86400.0
                else:
                    try:
                        days = int(notes.get("billing_period_days") or 30)
                    except Exception:
                        days = 30
                    days = max(1, min(days, 366))
                    period_end = now + float(days) * 86400.0

                updated_status = self.set_tenant_plan(
                    tenant_id=str(tenant_id),
                    plan_id=plan_id,
                    provider="razorpay",
                    external_customer_id=str(cust_id) if cust_id else None,
                    external_subscription_id=str(sub_id) if sub_id else None,
                    status="active",
                    current_period_end=period_end,
                )
            elif event_type in ("subscription.cancelled", "subscription.halted", "subscription.expired"):
                updated_status = self.set_tenant_plan(
                    tenant_id=str(tenant_id),
                    plan_id="free",
                    provider="razorpay",
                    status="canceled",
                    current_period_end=None,
                )

        self._mark_event_processed(event_id, "razorpay", event_type, str(tenant_id) if tenant_id else None)
        return {
            "status": "processed",
            "provider": "razorpay",
            "event_id": event_id,
            "event_type": event_type,
            "tenant_billing": updated_status,
        }

    def create_checkout_session(
        self,
        tenant_id: str,
        plan_id: str,
        provider: str = "stripe",
        success_url: str = "https://app.dataxray.io/app?billing=success",
        cancel_url: str = "https://app.dataxray.io/app?billing=cancelled",
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        norm_tid = sanitize_tenant_id(tenant_id)
        norm_plan = str(plan_id or "").strip().lower()
        if norm_plan not in ("starter", "pro", "enterprise"):
            raise ValueError("Invalid paid plan_id. Choose one of: starter, pro, enterprise.")
        for label, u in (("success_url", success_url), ("cancel_url", cancel_url)):
            if not str(u or "").startswith(("https://", "http://")):
                raise ValueError(f"Invalid {label}: must start with https:// or http://")
        plan_cfg = BILLING_PLANS[norm_plan]
        prov = str(provider or "stripe").strip().lower()

        if prov == "stripe":
            api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
            price_env_key = f"STRIPE_PRICE_{norm_plan.upper()}"
            price_id = os.environ.get(price_env_key, "").strip()
            if not api_key:
                return {
                    "status": "configuration_required",
                    "provider": "stripe",
                    "plan": plan_cfg,
                    "message": "Set STRIPE_SECRET_KEY (and optional STRIPE_PRICE_STARTER/PRO/ENTERPRISE + STRIPE_WEBHOOK_SECRET) to enable live Stripe checkout.",
                    "required_env_vars": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", price_env_key],
                }
            form_fields: Dict[str, str] = {
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": norm_tid,
                "metadata[tenant_id]": norm_tid,
                "metadata[plan_id]": norm_plan,
                "subscription_data[metadata][tenant_id]": norm_tid,
                "subscription_data[metadata][plan_id]": norm_plan,
                "line_items[0][quantity]": "1",
            }
            if customer_email:
                form_fields["customer_email"] = customer_email
            if price_id:
                form_fields["line_items[0][price]"] = price_id
            else:
                form_fields["line_items[0][price_data][currency]"] = "usd"
                form_fields["line_items[0][price_data][unit_amount]"] = str(int(plan_cfg["price_usd_monthly"]) * 100)
                form_fields["line_items[0][price_data][recurring][interval]"] = "month"
                form_fields["line_items[0][price_data][product_data][name]"] = f"DataX-Ray {plan_cfg['name']}"

            req = urllib.request.Request(
                "https://api.stripe.com/v1/checkout/sessions",
                data=urllib.parse.urlencode(form_fields).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "checkout_created",
                "provider": "stripe",
                "checkout_url": data.get("url"),
                "session_id": data.get("id"),
                "plan": plan_cfg,
            }

        elif prov == "razorpay":
            key_id = os.environ.get("RAZORPAY_KEY_ID", "").strip()
            key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
            if not key_id or not key_secret:
                return {
                    "status": "configuration_required",
                    "provider": "razorpay",
                    "plan": plan_cfg,
                    "message": "Set RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and RAZORPAY_WEBHOOK_SECRET to enable live Razorpay INR/UPI checkout.",
                    "required_env_vars": ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"],
                }
            auth_b64 = base64.b64encode(f"{key_id}:{key_secret}".encode("utf-8")).decode("ascii")
            rzp_plan_env = f"RAZORPAY_PLAN_{norm_plan.upper()}"
            rzp_plan_id = os.environ.get(rzp_plan_env, "").strip()
            if rzp_plan_id:
                # True recurring monthly subscription when RAZORPAY_PLAN_<TIER> is configured
                sub_body: Dict[str, Any] = {
                    "plan_id": rzp_plan_id,
                    "total_count": 12,
                    "quantity": 1,
                    "customer_notify": 1,
                    "notes": {"tenant_id": norm_tid, "plan_id": norm_plan, "billing_period_days": "30"},
                }
                req = urllib.request.Request(
                    "https://api.razorpay.com/v1/subscriptions",
                    data=json.dumps(sub_body).encode("utf-8"),
                    headers={
                        "Authorization": f"Basic {auth_b64}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "checkout_created",
                    "provider": "razorpay",
                    "billing_mode": "recurring_subscription",
                    "checkout_url": data.get("short_url"),
                    "subscription_id": data.get("id"),
                    "plan": plan_cfg,
                }

            # Fallback: 30-day time-bounded payment link (auto-expires via current_period_end after 30 days)
            body_obj: Dict[str, Any] = {
                "amount": int(plan_cfg["price_inr_monthly"]) * 100,
                "currency": "INR",
                "description": f"DataX-Ray {plan_cfg['name']} (30-Day Monthly Pass)",
                "callback_url": success_url,
                "callback_method": "get",
                "notes": {"tenant_id": norm_tid, "plan_id": norm_plan, "billing_period_days": "30"},
            }
            if customer_email:
                body_obj["customer"] = {"email": customer_email}
            req = urllib.request.Request(
                "https://api.razorpay.com/v1/payment_links",
                data=json.dumps(body_obj).encode("utf-8"),
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "checkout_created",
                "provider": "razorpay",
                "billing_mode": "time_bounded_30d_pass",
                "checkout_url": data.get("short_url"),
                "payment_link_id": data.get("id"),
                "plan": plan_cfg,
            }
        else:
            raise ValueError("Unsupported billing provider. Use 'stripe' or 'razorpay'.")
