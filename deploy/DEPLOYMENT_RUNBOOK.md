# DataX-Ray Production Deployment Runbook (Phase A Launch Kit)

## 1. 5-Minute Live Cloud Launch (Docker Compose + Automatic HTTPS)

1. Provision a Linux VM (2 vCPU, 4 GB RAM minimum — AWS EC2, DigitalOcean, Hetzner, or GCP Compute Engine) with Docker & Docker Compose installed.
2. Point your domain's DNS `A` record (`app.yourdomain.com`) to the VM's public IPv4 address.
3. Copy `.env.production.example` to `.env.production` and populate your real secrets:
   ```bash
   cp .env.production.example .env.production
   python3 -c "import secrets; print(secrets.token_hex(32))"  # Generate JWT & Admin API keys
   ```
4. Launch the stack (Caddy automatically provisions & renews Let's Encrypt HTTPS certificates):
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
   ```
5. Verify live health:
   ```bash
   curl -fsS https://app.yourdomain.com/api/v1/health
   curl -fsS https://app.yourdomain.com/api/v1/billing/plans
   ```

## 2. Configure Stripe & Razorpay Webhooks

- **Stripe Dashboard → Developers → Webhooks → Add endpoint**:
  - Endpoint URL: `https://app.yourdomain.com/api/v1/billing/webhooks/stripe`
  - Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`
  - Copy the signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET` in `.env.production`.
- **Razorpay Dashboard → Settings → Webhooks → Add New Webhook**:
  - Endpoint URL: `https://app.yourdomain.com/api/v1/billing/webhooks/razorpay`
  - Events: `subscription.activated`, `subscription.charged`, `subscription.cancelled`, `payment_link.paid`
  - Set `RAZORPAY_WEBHOOK_SECRET` in `.env.production` to the exact secret configured in Razorpay.

## 3. Activate Automated Daily / Weekly Scheduled Digests (Cron)

Add a host crontab entry (or GitHub Actions / Cloud Scheduler job) running every morning at 08:00 local time to execute due tenant connector syncs & dispatch Morning Munim-Ji alerts:

```cron
0 8 * * * curl -fsS -X POST https://app.yourdomain.com/api/v1/schedules/run-due -H "X-API-Key: ${DATAXRAY_API_KEY}" >> /var/log/dataxray-cron.log 2>&1
```

## 4. Platform-as-a-Service Alternative (Railway / Render / Fly.io)

- Deploy directly from the root `Dockerfile` (already non-root `uid 1001`, healthchecked, and trimmed via `.dockerignore`).
- Mount a persistent volume at `/app/runs` so SQLite WAL state (`auth_users.sqlite`, `billing_plans.sqlite`, `action_ledger.sqlite`) and tenant workspaces survive container restarts.
- Configure the same environment variables from `.env.production.example` in your platform dashboard.

## 5. Phase C Horizontal Cloud Scale (PostgreSQL 16 + S3/R2 + Redis/RQ Workers)

When scaling beyond a single VM (multiple stateless API pods + autoscaled DuckDB worker replicas):

1. Install optional cloud scale drivers (`pip install 'psycopg[binary,pool]' boto3 redis rq`) and set `DATABASE_URL`, `REDIS_URL`, and `DATAXRAY_S3_BUCKET` (plus `DATAXRAY_S3_ENDPOINT_URL` for Cloudflare R2) in `.env.production`.
2. Migrate existing single-node SQLite state into PostgreSQL 16 with automatic row-count verification:
   ```bash
   python scripts/migrate_sqlite_to_postgres.py --dry-run
   python scripts/migrate_sqlite_to_postgres.py --database-url "$DATABASE_URL"
   ```
3. Launch the multi-container horizontal stack (e.g. 2 stateless API pods + 4 background RQ DuckDB workers):
   ```bash
   docker compose -f docker-compose.cloud.yml --env-file .env.production up -d --build --scale dataxray-worker=4
   ```
4. Verify live cloud topology (all credentials masked):
   ```bash
   curl -fsS https://app.yourdomain.com/api/v1/system/cloud-status -H "X-API-Key: ${DATAXRAY_API_KEY}"
   ```
