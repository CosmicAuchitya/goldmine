# =============================================================================
# DATAX-RAY ENTERPRISE AUTONOMOUS ENGINE & API DOCKERFILE
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# Install minimal OS dependencies for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install required Python packages for full engine, FastAPI server & Streamlit portal
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    scipy \
    duckdb \
    pyarrow \
    openpyxl \
    tabulate \
    fastapi \
    uvicorn \
    python-multipart \
    streamlit \
    google-genai \
    requests \
    python-dotenv \
    pytest

# Copy core engine components and ontologies
COPY autonomous_engine/ /app/autonomous_engine/
COPY 02_domain_intelligence/ /app/02_domain_intelligence/
COPY pikabo/ /app/pikabo/

# Run as non-root user for enterprise container security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/runs && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "autonomous_engine.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
