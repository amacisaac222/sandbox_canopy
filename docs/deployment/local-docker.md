# Local (Docker)

```bash
docker build -t canopyiq:dev .
docker run --rm -p 8080:8080 \
  -e CP_DB_URL=postgresql://... \
  -e SLACK_WEBHOOK_URL=... \
  canopyiq:dev
```

**Health:**
- `/healthz` liveness
- `/readyz` readiness
- `/metrics` Prometheus