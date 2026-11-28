# =============================================================================
# DATAX-RAY AUTONOMOUS DECISION ENGINE - ENTERPRISE PRODUCTION DOCKERFILE
# =============================================================================
FROM python:3.12-slim AS runtime

# 1. System dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Create non-privileged operational service user
RUN groupadd -g 1001 dataxray && \
    useradd -u 1001 -g dataxray -s /bin/bash -m dataxray

WORKDIR /app

# 3. Install Python dependencies (core + PDF + Phase C horizontal cloud scale drivers)
COPY requirements.txt requirements-cloud.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -r requirements-cloud.txt

# 4. Copy source code, domain ontologies, and benchmark assets
COPY autonomous_engine/ /app/autonomous_engine/
COPY 02_domain_intelligence/ /app/02_domain_intelligence/
COPY kaggle_benchmarks/ /app/kaggle_benchmarks/
COPY enterprise_showcase_data/ /app/enterprise_showcase_data/

# 5. Initialize writable run state directories (SQLite WAL state, tenants, ledgers, backups, i18n)
RUN mkdir -p /app/runs/uploads /app/runs/tenants /app/runs/action_ledgers /app/runs/state /app/runs/decision_outcomes /app/runs/i18n_cache /app/runs/backups && \
    chown -R dataxray:dataxray /app

USER dataxray

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UVICORN_PORT=8000 \
    DATAXRAY_REQUIRE_AUTH=true \
    DATAXRAY_ALLOW_AI_CODEGEN=false \
    DATAXRAY_RATE_LIMIT_RPM=120

# 6. Container healthcheck probing physical DuckDB API status
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "autonomous_engine.api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
