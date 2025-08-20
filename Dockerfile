FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy deps first for better caching
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# copy app
COPY control_plane /app/control_plane

# default env (override in runtime)
ENV CP_DB_URL=sqlite+aiosqlite:///./sandbox.db \
    CP_TENANT_SECRET=change_me \
    CP_BIND=0.0.0.0 \
    CP_PORT=8080

EXPOSE 8080

# simple healthcheck
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "control_plane.app:app", "--host", "0.0.0.0", "--port", "8080"]