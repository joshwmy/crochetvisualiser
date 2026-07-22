# Contributor portal image. The deterministic pattern engine has no runtime
# dependency on any of this — this image exists solely to serve the FastAPI
# portal (crochet_reconstruction.portal.app:create_app).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install ".[portal]"

RUN useradd --create-home --uid 1000 portal \
    && mkdir -p /data \
    && chown -R portal:portal /data /app

ENV PORTAL_DATA_DIR=/data
VOLUME ["/data"]

USER portal

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

# Applies pending migrations, then starts the server. See
# docs/portal-deployment.md for the equivalent commands run manually.
CMD ["sh", "-c", "alembic upgrade head && uvicorn crochet_reconstruction.portal.app:create_app --factory --host 0.0.0.0 --port 8000"]
