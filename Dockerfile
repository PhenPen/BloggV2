# FastAPI Blog — production image (deployable to any Docker host/VPS).
#
# Build:   docker build -t fastapi-blog .
# Run:     docker run --env-file .env -p 8000:8000 fastapi-blog
#          (full stack with Postgres: see docker-compose.yml)

FROM python:3.13-slim

# Python: no bytecode cache files on disk, unbuffered stdout/stderr so container
# logs stream immediately; pip: no cache, no version check (smaller, quieter).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system package needed by Pillow's wheel at import time (libjpeg is
# unbundled on slim images). apt caches cleared in the same layer to keep the
# image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first (cached across builds while source changes).
COPY pyproject.toml ./
COPY app/ app/
COPY alembic.ini alembic.ini
COPY alembic/ alembic/
RUN pip install --no-cache-dir .

# Run as an unprivileged user — the process must never need root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Migrate, then hand over PID 1 to uvicorn (exec). Single worker by design:
# the in-memory rate limiter is per-process, and uvicorn's own worker model is
# the documented one-worker deployment for this app.
ENTRYPOINT ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]