# CanopyIQ Demo Guide

This guide walks through the complete CanopyIQ demonstration flow, showcasing all enterprise features.

## Quick Demo Setup

### 1. Start the MCP Server

**Option A - Docker Compose (Recommended):**
```bash
docker compose up -d --build
```

**Option B - Direct Run:**
```bash
# Postgres migration
psql "$DATABASE_URL" -f app/audit/migrate.sql
# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Generate Admin Token

```bash
python cli/admin.py mint-token --tenant demo-tenant --subject demo --roles admin,approver --ttl 7200
```

Set the token in your environment:
```bash
# Linux/macOS
export TOKEN="your-token-here"

# Windows PowerShell  
$env:TOKEN="your-token-here"
```

### 3. Start the Console UI

```bash
# Set console environment
export MCP_BASE_URL="http://localhost:8080"
export CONSOLE_BEARER="$TOKEN"
export OTEL_CONSOLE_EXPORTER="true"  # Optional: Enable console tracing output

# Windows PowerShell
$env:MCP_BASE_URL="http://localhost:8080" 
$env:CONSOLE_BEARER=$env:TOKEN
$env:OTEL_CONSOLE_EXPORTER="true"

# Start console server
cd canopyiq_site
python -m uvicorn app:app --host 0.0.0.0 --port 8081 --reload
```

### 4. Run Verification Script

```bash
# Linux/macOS
./scripts/demo_verification.sh

# Windows PowerShell
./scripts/demo_verification.ps1
```

## 🎯 Golden Path Demo (5 minutes)

### Step 1: Policy & Budget Setup
```bash
# Set rate limit (200 QPS)
curl -s -X PUT 'http://localhost:8080/admin/tenants/demo-tenant/rate-limit' \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"qps":200}'

# Set daily budget ($15)
curl -s -X PUT 'http://localhost:8080/admin/tenants/demo-tenant/quota' \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"cloud_usd","period":"day","limit":15}'
```

### Step 2: Trigger High-Cost Approval
```bash
# Try expensive cloud operation ($12)
REQ='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cloud.ops","arguments":{"provider":"aws","resource":"ec2","action":"run_instances","estimated_cost_usd":12}}}'
RESP=$(curl -s -X POST http://localhost:8080/mcp -H "Authorization: Bearer $TOKEN" -d "$REQ")
echo "$RESP" | jq .
```
**Expected:** `"decision": "approval"` with a `pendingId`

### Step 3: Approve via Console
1. Visit: **http://localhost:8081/console/approvals**
2. See the pending approval request
3. Click **"Approve"** button
4. Verify success message

### Step 4: Retry After Approval
```bash
# Same request should now succeed
curl -s -X POST http://localhost:8080/mcp -H "Authorization: Bearer $TOKEN" -d "$REQ" | jq .
```
**Expected:** `"decision": "allow"` and budget debited

### Step 5: Budget Enforcement
```bash
# Try to exceed daily budget (12 + 9 = 21 > 15)
REQ2='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"cloud.ops","arguments":{"provider":"aws","resource":"ec2","action":"run_instances","estimated_cost_usd":9}}}'
curl -s -X POST http://localhost:8080/mcp -H "Authorization: Bearer $TOKEN" -d "$REQ2" | jq .
```
**Expected:** `"decision": "deny"` due to budget limit

## 🖥️ Console Demo Flow

### 1. Access Dashboard
- **URL:** http://localhost:8081/console/access
- **Demo:** Show live policy tiles (Allow/Approval/Blocked)
- **Features:**
  - Real-time policy simulation with OpenTelemetry tracing
  - Visual status indicators  
  - Expandable rule details
  - Trace spans for each policy evaluation

### 2. Approvals Queue
- **URL:** http://localhost:8081/console/approvals
- **Demo:** Interactive approve/deny workflow
- **Features:**
  - Live approval feed
  - One-click approve/deny
  - Success/error feedback
  - Trace correlation for approval workflows

### 3. **NEW: Trace Analytics**
- **URL:** http://localhost:8081/console/traces
- **Demo:** Distributed tracing and workflow performance
- **Features:**
  - End-to-end trace visualization
  - Workflow performance metrics
  - Span details with cost attribution
  - Success/error rate analysis
  - Multi-agent workflow tracking

### 4. **NEW: Agent Dependencies**
- **URL:** http://localhost:8081/console/agents
- **Demo:** Agent-to-agent communication service mesh
- **Features:**
  - Agent dependency map
  - Communication patterns visualization
  - Performance metrics per agent pair
  - Network topology diagram
  - Service mesh health monitoring

### 5. Policy Simulator
- **URL:** http://localhost:8081/console/simulator
- **Demo:** Test policy decisions
- **Example:**
  - Tool: `net.http`
  - Arguments: `{"method":"GET","url":"https://intranet.api/status"}`
- **Features:**
  - Live policy testing with tracing
  - Decision trace visualization
  - Rule explanation
  - Request/response correlation

### 6. Policy Management  
- **URL:** http://localhost:8081/console/policy
- **Demo:** Upload and diff YAML policies
- **Features:**
  - Current policy status
  - Visual diff highlighting
  - Risk assessment
  - Rollout controls (stubbed)

## 🧪 Policy Testing

### Simulator API
```bash
curl -s -X POST http://localhost:8080/v1/policy/simulate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool":"net.http","arguments":{"method":"GET","url":"https://intranet.api/status"}}' | jq .
```

### Policy Diff
```bash
curl -s -X POST http://localhost:8080/v1/policy/diff \
  -H "Authorization: Bearer $TOKEN" \
  -F proposed=@app/policies/samples.yaml | jq .
```

### Signed Policy Apply (Advanced)
```bash
curl -s -X POST http://localhost:8080/v1/policy/apply \
  -H "Authorization: Bearer $TOKEN" \
  -F public_key_b64="$(cat keys/canopyiq_policy_public.key)" \
  -F strategy=canary_percent -F canary_percent=10 -F seed=42 \
  -F proposed=@app/policies/samples.yaml \
  -F signature=@app/policies/samples.yaml.sig | jq .
```

## 📊 Observability

### Metrics
```bash
curl -s http://localhost:8080/metrics | head -20
```

### Audit Logs
```bash
# Via API
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/v1/audit | jq .

# Direct database (if using Postgres)
psql "$DATABASE_URL" -c "SELECT * FROM audit_log ORDER BY ts DESC LIMIT 20;"
```

## 🔒 Security Features Demo

### Rate Limiting
```bash
# Burst test (should hit rate limit)
for i in {1..10}; do
  curl -s -X POST http://localhost:8080/mcp -H "Authorization: Bearer $TOKEN" -d "$REQ" &
done
wait
```

### Network Allowlist
```bash
# Try blocked external domain
curl -s -X POST http://localhost:8080/v1/policy/simulate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool":"net.http","arguments":{"method":"GET","url":"https://malicious-site.com/api"}}' | jq .
```

### File System Jail
```bash
# Try writing to restricted path
curl -s -X POST http://localhost:8080/v1/policy/simulate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tool":"fs.write","arguments":{"path":"/etc/passwd","bytes":"ZGVtbw=="}}' | jq .
```

## 🎬 Sales Demo Script (2-3 minutes)

### Opening (30 seconds)
"CanopyIQ provides enterprise-grade runtime security for AI agents. Let me show you how it works."

**Show:** http://localhost:8081/console

### Access Control (45 seconds)
"Here's our Access Dashboard - it shows exactly what each agent can do in real-time."

**Demo:** 
1. Visit /console/access
2. Show Allow/Approval/Blocked tiles
3. Expand details to show rule explanations

### Approval Workflow (60 seconds)
"When agents try risky actions, they're automatically routed for human approval."

**Demo:**
1. Trigger expensive cloud operation via API
2. Show approval appearing in /console/approvals  
3. Click Approve button
4. Show retry succeeding

### Budget Protection (30 seconds)
"Budget controls prevent runaway costs automatically."

**Demo:**
1. Try to exceed $15 daily budget
2. Show immediate denial
3. Explain real-time cost tracking

### Policy Management (15 seconds)
"Policies are managed visually with diff highlighting and staged rollouts."

**Show:** /console/policy upload screen

### Closing (10 seconds)
"All activities are logged for compliance, with Prometheus metrics for ops teams."

**Show:** Metrics endpoint output

## 🚨 Troubleshooting

### Common Issues

**Console shows 401/403:**
```bash
# Verify token is set
echo $TOKEN
# Verify console env vars
echo $MCP_BASE_URL $CONSOLE_BEARER
```

**MCP server not responding:**
```bash
# Check health
curl http://localhost:8080/healthz
# Check logs
docker compose logs canopyiq-mcp
```

**Approvals not working:**
- In dev/CI: Use `python tests/e2e/util_approve.py` 
- In production: Configure Slack/Teams webhooks

**Policy apply fails:**
- Verify signature matches YAML
- Check public key format
- Ensure Ed25519 keys are valid

## ✅ Pre-Demo Checklist

- [ ] MCP server healthy (`/healthz` returns 200)
- [ ] Admin token generated and set
- [ ] Console accessible at port 8081  
- [ ] Access Dashboard shows live policy tiles
- [ ] Approval workflow end-to-end working
- [ ] Budget enforcement blocking over-spend
- [ ] Policy simulator returning decisions
- [ ] Metrics endpoint responding
- [ ] Demo script practiced (under 3 minutes)

**Ready for customer preview! 🚀**