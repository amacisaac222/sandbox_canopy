# CanopyIQ MCP Production Features

## 1. Redis-backed Approvals with Dual-Control

### Enable Redis and Slack approvals
```bash
export REDIS_URL="redis://redis:6379/0"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export SLACK_SIGNING_SECRET="xxxx"
export APPROVAL_SYNC_WAIT_MS="0"  # 0 for async, 20000 for 20s sync wait
```

### Configure Slack App
Set Slack Interactivity → Request URL → `https://<host>/approvals/slack/callback`

### Dual-control policy example
```yaml
- name: "FS-write outside jail requires dual approval"
  match: "fs.write"
  where:
    path_not_under: ["/sandbox/tmp", "/sandbox/out"]
  action: approval
  approver_group: "secops"
  required_approvals: 2
  reason: "Write outside jail requires two approvers"
```

### Test dual-control flow
```bash
curl -X POST http://localhost:8080/approvals/create \
  -H 'Content-Type: application/json' \
  -d '{
        "pending_id":"abc123",
        "tenant":"demo-tenant",
        "subject":"agent-42",
        "tool":"fs.write",
        "required_approvals": 2,
        "args":{"path":"/etc/hosts","content":"malicious"},
        "summary":"Write to /etc/hosts by agent-42"
      }'
```

Two different Slack users must click Approve for the request to be allowed. Any Deny immediately rejects.

## 2. Policy Bundle Signing

### Generate signing keys
```bash
python cli/policy_sign.py gen-key --out-dir keys/
```

### Sign policy bundle
```bash
python cli/policy_sign.py sign app/policies/samples.yaml --private-key keys/canopyiq_policy_private.key
```

### Verify signature (optional)
```bash
python cli/policy_sign.py verify app/policies/samples.yaml \
  --public-key keys/canopyiq_policy_public.key \
  --signature app/policies/samples.yaml.sig
```

### Run server with signature verification
```bash
export POLICY_PUBLIC_KEY_B64=$(cat keys/canopyiq_policy_public.key)
export POLICY_SIG_PATH=app/policies/samples.yaml.sig
export POLICY_REQUIRE_SIGNATURE=true
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## 3. Database Setup

### Seed database
```bash
export DATABASE_URL="postgresql://user:pass@pg:5432/audit"
psql "$DATABASE_URL" -f app/audit/migrate.sql
```

## 4. Kubernetes Deployment

### Install Helm chart with new features
```bash
helm upgrade --install canopyiq-mcp deployment/helm/canopyiq-mcp \
  --set image.repository=yourrepo/canopyiq-mcp \
  --set image.tag=v0.1.0 \
  --set env.APPROVAL_SYNC_WAIT_MS=20000 \
  --set env.POLICY_PUBLIC_KEY_B64="$(cat keys/canopyiq_policy_public.key)" \
  --set env.POLICY_REQUIRE_SIGNATURE=true
```

### Create secrets
```bash
kubectl create secret generic canopyiq-mcp-secrets \
  --from-literal=DATABASE_URL="postgresql://user:pass@pg:5432/audit" \
  --from-literal=SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
  --from-literal=SLACK_SIGNING_SECRET="xxxx"

kubectl create secret generic canopyiq-policy-sig \
  --from-file=policy.sig=app/policies/samples.yaml.sig
```

## 5. Testing Features

### A) Dual-control approval
- Policy rule has `required_approvals: 2`
- Trigger matching tool call → "approval required"
- Two different Slack users press Approve → status becomes `allow`
- Any user presses Deny → status becomes `deny` immediately

### B) Redis pub/sub notify
Call `wait_for_resolution(pid, 10)` from Python shell; press button in Slack — function returns immediately without polling.

### C) Policy signature tampering
Tamper with YAML → server refuses to load when `POLICY_REQUIRE_SIGNATURE=true`.

## 6. New Production Add-ons

### A) Cost Estimator

Test cost estimation before expensive operations:

```bash
curl -s -X POST http://localhost:8080/mcp -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cloud.estimate","arguments":{"provider":"aws","action":"ec2.run_instances","units":10}}}' | jq .
```

### B) Policy Simulator

Test policy evaluation with detailed trace:

```bash
curl -s -X POST http://localhost:8080/v1/policy/simulate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool":"cloud.ops","arguments":{"provider":"aws","resource":"ec2","action":"run_instances","estimated_cost_usd":75}}' | jq .
```

### C) RBAC with Dev Tokens

Mint development tokens and assign roles:

```bash
# Create admin token
export TOKEN=$(python cli/admin.py mint-token --tenant demo-tenant --subject alice --roles admin,approver --ttl 7200)

# Assign roles to users
curl -s -X PUT http://localhost:8080/admin/rbac/demo-tenant/users/bob \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"roles":["approver","viewer"]}' | jq .
```

### D) Policy Diff API

Compare policy changes with risk analysis:

```bash
curl -s -X POST "http://localhost:8080/v1/policy/diff" \
  -H "Authorization: Bearer $TOKEN" \
  -F "proposed=@app/policies/samples.yaml" | jq .headline
```

### E) Complete Demo

Run the full approval + budget demo:

```bash
make demo
```

This will:
1. Start the Docker stack
2. Configure tenant quotas and rate limits
3. Trigger a high-cost operation requiring approval
4. Simulate approval via signed callback
5. Demonstrate budget enforcement
6. Test all major features

## Production Notes

- ✅ Durable Redis-backed approvals with TTL and pub/sub
- ✅ Dual-control (N-of-M approvers) with deny precedence  
- ✅ Policy signing & verification for tamper-evident governance
- ✅ Immutable audit log with hash chain for tamper detection
- ✅ ServiceMonitor included for Prometheus Operator integration
- ✅ Synchronous approval mode for real-time agent responses
- ✅ Cost estimation with policy integration
- ✅ Policy simulator with evaluation traces
- ✅ RBAC with JWT authentication (dev + OIDC production)
- ✅ Policy diff API with risk analysis
- ✅ OpenAPI documentation with security scheme
- ✅ One-command demo with scripted approval flow