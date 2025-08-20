# CanopyIQ Helm Chart - Quick Installation Guide

## Prerequisites

- Kubernetes cluster (1.19+)
- Helm 3.0+
- kubectl configured
- PostgreSQL database

## Quick Start

### 1. Install the Chart

```bash
# Navigate to the chart directory
cd helm/canopyiq

# Install with default values
helm install canopyiq . --namespace canopyiq --create-namespace
```

### 2. Create the Required Secret

**⚠️ This step is mandatory - the application will not work without proper secrets:**

```bash
kubectl create secret generic canopyiq-secret \
  --from-literal=CP_DB_URL="postgresql://user:pass@host:5432/db" \
  --from-literal=OIDC_ISSUER="https://your-oidc-provider.com" \
  --from-literal=OIDC_CLIENT_ID="your-client-id" \
  --from-literal=OIDC_CLIENT_SECRET="your-client-secret" \
  --from-literal=SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
  --from-literal=SLACK_SIGNING_SECRET="your-slack-secret" \
  --from-literal=SESSION_SECRET="$(openssl rand -base64 32)" \
  --namespace=canopyiq
```

### 3. Restart the Deployment

```bash
kubectl rollout restart deployment/canopyiq --namespace=canopyiq
```

### 4. Access the Application

```bash
# Port forward to access locally
kubectl port-forward svc/canopyiq 8080:80 --namespace=canopyiq

# Then visit:
# - http://localhost:8080/setup (first-time setup)
# - http://localhost:8080/admin (admin panel)
# - http://localhost:8080 (main application)
```

## Production Installation

### 1. Prepare Production Values

```bash
# Copy and edit the production values
cp values-production.yaml my-prod-values.yaml
# Edit my-prod-values.yaml with your specific configuration
```

### 2. Install with Production Settings

```bash
helm install canopyiq . \
  --namespace canopyiq \
  --create-namespace \
  --values my-prod-values.yaml
```

### 3. Configure Ingress

Ensure your ingress controller is installed and update the values:

```yaml
ingress:
  enabled: true
  className: "nginx"  # or your ingress class
  hosts:
    - host: canopyiq.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: canopyiq-tls
      hosts:
        - canopyiq.yourdomain.com
```

## Monitoring Setup

Enable Prometheus monitoring:

```bash
helm upgrade canopyiq . \
  --namespace canopyiq \
  --set monitoring.serviceMonitor.enabled=true \
  --set monitoring.serviceMonitor.labels.prometheus=kube-prometheus
```

## Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n canopyiq
kubectl logs -f deployment/canopyiq -n canopyiq
```

### Verify Secret
```bash
kubectl get secret canopyiq-secret -n canopyiq -o yaml
```

### Test Connectivity
```bash
helm test canopyiq --namespace canopyiq
```

## Uninstall

```bash
helm uninstall canopyiq --namespace canopyiq
kubectl delete namespace canopyiq  # Optional: removes the entire namespace
```

## Next Steps

1. Visit `/setup` to create your first admin user
2. Configure OIDC authentication if needed
3. Set up Slack integration for notifications
4. Review security settings for production use

For detailed configuration options, see [README.md](README.md).