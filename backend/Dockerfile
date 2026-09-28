# syntax=docker/dockerfile:1

# ---- builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Cache-friendly layer order: dependency manifest before source.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security hardening: Non-root user (UID/GID 1000) with no login shell or home directory
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/false --no-create-home app

# Security & performance optimizations:
# - PYTHONDONTWRITEBYTECODE=1 prevents creating .pyc on read-only root filesystems
# - PYTHONUNBUFFERED=1 streams logs directly to stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini .
COPY --chown=app:app scripts ./scripts

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
