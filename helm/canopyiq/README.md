# CanopyIQ Helm Chart

This Helm chart deploys CanopyIQ, a runtime sandbox & policy control plane for AI agents, on a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- A PostgreSQL database (external or in-cluster)
- (Optional) Prometheus Operator for monitoring

## Installation

### 1. Add Helm Repository (if published)

```bash
helm repo add canopyiq https://helm.canopyiq.ai
helm repo update
```

### 2. Install from Local Chart

```bash
# Clone the repository
git clone https://github.com/canopyiq/canopy.git
cd canopy/helm/canopyiq

# Install with default values
helm install canopyiq . --namespace canopyiq --create-namespace

# Install with custom values
helm install canopyiq . --namespace canopyiq --create-namespace -f my-values.yaml
```

### 3. Configure Secrets

**⚠️ Important: You must create a Kubernetes secret with your configuration before the application will work properly.**

```bash
kubectl create secret generic canopyiq-secret \
  --from-literal=CP_DB_URL="postgresql://username:password@hostname:5432/database" \
  --from-literal=OIDC_ISSUER="https://your-identity-provider.com" \
  --from-literal=OIDC_CLIENT_ID="your-client-id" \
  --from-literal=OIDC_CLIENT_SECRET="your-client-secret" \
  --from-literal=SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --from-literal=SLACK_SIGNING_SECRET="your-slack-signing-secret" \
  --from-literal=SESSION_SECRET="$(openssl rand -base64 32)" \
  --namespace=canopyiq
```

### 4. Restart Deployment

```bash
kubectl rollout restart deployment/canopyiq --namespace=canopyiq
```

## Configuration

### Basic Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | CanopyIQ image repository | `canopyiq/canopyiq` |
| `image.tag` | CanopyIQ image tag | `latest` |
| `replicaCount` | Number of replicas | `1` |
| `resources.requests.cpu` | CPU requests | `250m` |
| `resources.requests.memory` | Memory requests | `256Mi` |
| `resources.limits.cpu` | CPU limits | `500m` |
| `resources.limits.memory` | Memory limits | `512Mi` |

### Ingress Configuration

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: canopyiq.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: canopyiq-tls
      hosts:
        - canopyiq.example.com
```

### Environment Variables

The chart supports both non-sensitive and sensitive environment variables:

**Non-sensitive (via values.yaml):**
```yaml
env:
  ENVIRONMENT: production
  PORT: "8080"
  BASE_URL: https://canopyiq.example.com
```

**Sensitive (via Kubernetes Secret):**
```yaml
secrets:
  keys:
    dbUrl: CP_DB_URL
    oidcIssuer: OIDC_ISSUER
    oidcClientId: OIDC_CLIENT_ID
    oidcClientSecret: OIDC_CLIENT_SECRET
    slackWebhookUrl: SLACK_WEBHOOK_URL
    slackSigningSecret: SLACK_SIGNING_SECRET
    sessionSecret: SESSION_SECRET
```

### Health Checks

Health checks are enabled by default and point to CanopyIQ's built-in endpoints:

```yaml
healthChecks:
  liveness:
    enabled: true
    path: /healthz
  readiness:
    enabled: true
    path: /readyz
```

### Monitoring

Enable Prometheus monitoring with ServiceMonitor:

```yaml
monitoring:
  serviceMonitor:
    enabled: true
    interval: 30s
    path: /metrics
    labels:
      prometheus: kube-prometheus
```

## Examples

### Development Environment

```yaml
# values-dev.yaml
replicaCount: 1
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi

ingress:
  enabled: true
  hosts:
    - host: canopyiq-dev.local
      paths:
        - path: /
          pathType: Prefix

autoscaling:
  enabled: false
```

### Production Environment

```yaml
# values-prod.yaml
replicaCount: 3
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
  hosts:
    - host: canopyiq.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: canopyiq-tls
      hosts:
        - canopyiq.example.com

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

monitoring:
  serviceMonitor:
    enabled: true
    labels:
      prometheus: kube-prometheus

podDisruptionBudget:
  enabled: true
  minAvailable: 2

networkPolicy:
  enabled: true
```

## Upgrading

```bash
# Upgrade to a new version
helm upgrade canopyiq . --namespace canopyiq

# Upgrade with new values
helm upgrade canopyiq . --namespace canopyiq -f my-values.yaml

# Check upgrade status
helm status canopyiq --namespace canopyiq
```

## Testing

Run the built-in tests:

```bash
helm test canopyiq --namespace canopyiq
```

## Troubleshooting

### Common Issues

1. **Pods not starting**: Check if secrets are properly configured
2. **Database connection errors**: Verify database URL and credentials
3. **Ingress not working**: Check ingress controller and DNS configuration

### Useful Commands

```bash
# Check pod logs
kubectl logs -f deployment/canopyiq --namespace canopyiq

# Check pod status
kubectl get pods -l app.kubernetes.io/name=canopyiq --namespace canopyiq

# Describe pod for detailed information
kubectl describe pod <pod-name> --namespace canopyiq

# Check service endpoints
kubectl get endpoints canopyiq --namespace canopyiq

# Check ingress status
kubectl get ingress canopyiq --namespace canopyiq
```

## Security

### Best Practices

1. **Use external secret management** (e.g., External Secrets Operator, Vault)
2. **Enable network policies** in production
3. **Use non-root containers** (enabled by default)
4. **Enable TLS** for all external communication
5. **Regularly update** container images

### Security Context

The chart uses secure defaults:

```yaml
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `helm lint` and `helm template`
5. Submit a pull request

## License

This chart is part of the CanopyIQ project. See the main project license for details.