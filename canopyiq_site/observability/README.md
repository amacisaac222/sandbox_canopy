# CanopyIQ Observability

This directory contains observability configurations for monitoring CanopyIQ in production.

## Overview

CanopyIQ includes comprehensive observability features:

### Health Checks
- **`/healthz`** - Liveness probe (returns 200 if service is running)
- **`/readyz`** - Readiness probe (returns 200 if service is ready, 503 if not)

### Prometheus Metrics
Available at `/metrics` endpoint:

#### Counters
- `http_requests_total{method,path,status}` - Total HTTP requests by method, path template, and status
- `contact_submissions_total` - Total contact form submissions
- `auth_logins_total` - Total successful authentication logins

#### Histograms
- `http_request_duration_seconds{method,path}` - HTTP request duration in seconds

### Structured Logging
All requests are logged as structured JSON with:
```json
{
  "timestamp": "2025-08-20T14:42:03.258Z",
  "request_id": "uuid4-string",
  "method": "GET", 
  "path": "/contact",
  "status": 200,
  "latency_ms": 45.2,
  "user_id": "user-oidc-subject-id-or-null",
  "user_agent": "Mozilla/5.0...",
  "remote_addr": "127.0.0.1"
}
```

Each response includes an `X-Request-ID` header for tracing.

## Grafana Dashboard

### Import Dashboard
1. Open Grafana
2. Go to Dashboards → Import
3. Upload `grafana/canopyiq-dashboard.json`
4. Configure data sources:
   - **Prometheus**: Point to your Prometheus instance scraping `/metrics`
   - **Loki** (optional): Point to your Loki instance ingesting structured logs

### Dashboard Panels
- **Request Rate**: Requests per second by endpoint
- **Response Time**: P95 and P50 latency by endpoint
- **Error Rate**: Percentage of 4xx/5xx responses
- **Business Metrics**: Contact submissions and auth logins per second
- **Request Summary**: Table showing request counts by endpoint (last hour)
- **Application Logs**: Real-time structured logs (requires Loki)

## Monitoring Setup

### Prometheus Configuration
Add this to your `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'canopyiq'
    static_configs:
      - targets: ['canopyiq:8080']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Kubernetes Health Checks
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /readyz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Loki Configuration (Optional)
To collect structured logs in Loki, configure your log shipper (Promtail, Fluent Bit, etc.) to:
1. Collect logs from CanopyIQ containers
2. Parse JSON log format
3. Add job label: `job="canopyiq"`

### Alerting Rules
Example Prometheus alerting rules:
```yaml
groups:
  - name: canopyiq
    rules:
      - alert: CanopyIQHighErrorRate
        expr: rate(http_requests_total{job="canopyiq",status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "CanopyIQ high error rate"
          description: "Error rate is {{ $value }} req/sec"
      
      - alert: CanopyIQHighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="canopyiq"}[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CanopyIQ high latency"
          description: "P95 latency is {{ $value }}s"
      
      - alert: CanopyIQDown
        expr: up{job="canopyiq"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "CanopyIQ is down"
          description: "CanopyIQ instance is not reachable"
```

## Production Considerations

### Path Normalization
Metrics use path templates to avoid high cardinality:
- `/static/*` for all static files
- `/admin/*` for admin sub-pages
- Actual paths for main application routes

### Log Volume
Structured logs are emitted for every request. In high-traffic environments:
1. Configure log rotation
2. Consider sampling for non-error requests
3. Use log aggregation (ELK, Loki, etc.)

### Security
- `/metrics` endpoint is public (consider restricting in production)
- Logs may contain sensitive data - review log retention policies
- Request IDs enable request tracing but don't log sensitive payloads

## Testing Observability

1. **Start the application**:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8080
   ```

2. **Check health endpoints**:
   ```bash
   curl http://localhost:8080/healthz
   curl http://localhost:8080/readyz
   ```

3. **View metrics**:
   ```bash
   curl http://localhost:8080/metrics
   ```

4. **Generate traffic and observe**:
   - Visit pages to generate HTTP metrics
   - Submit contact form to see `contact_submissions_total`
   - Sign in to see `auth_logins_total`
   - Check logs for structured JSON output