# Kubernetes (Helm)

```bash
helm repo add canopyiq https://your-helm-repo
helm install canopyiq canopyiq/canopyiq \
  --set env.CP_DB_URL="postgres://..." \
  --set env.SLACK_WEBHOOK_URL="..."
```

Probes wired to `/healthz` and `/readyz`.
Optional ServiceMonitor for Prometheus Operator.