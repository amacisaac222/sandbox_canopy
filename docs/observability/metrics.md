# Metrics

Expose Prometheus at `/metrics`:
- `http_requests_total{path,method,status}`
- `http_request_duration_seconds_bucket{...}`
- `policy_decisions_total{outcome}`
- `approvals_pending`
- `audit_writes_total`

Ship a Grafana dashboard JSON in `observability/grafana/`.