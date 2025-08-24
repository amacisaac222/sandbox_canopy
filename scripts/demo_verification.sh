#!/bin/bash
# CanopyIQ Demo Verification Script (Bash)
# Run this script to verify the full golden path

MCP_URL=${1:-"http://localhost:8080"}
CONSOLE_URL=${2:-"http://localhost:8081"}

echo "🚀 CanopyIQ Demo Verification Script"
echo "====================================="

# Check if TOKEN is set
if [[ -z "$TOKEN" ]]; then
    echo "❌ TOKEN environment variable not set"
    echo "Run: python cli/admin.py mint-token --tenant demo-tenant --subject demo --roles admin,approver --ttl 7200"
    echo "Then: export TOKEN='your-token-here'"
    exit 1
fi

echo "✅ TOKEN found: ${TOKEN:0:20}..."

# Test 1: Basic MCP Health
echo -e "\n📊 Testing MCP Server Health..."
if curl -s "$MCP_URL/healthz" > /dev/null; then
    echo "✅ MCP Server is healthy"
else
    echo "❌ MCP Server not responding"
    exit 1
fi

# Test 2: Set Rate Limit & Quota
echo -e "\n⚡ Setting up rate limits and quotas..."
curl -s -X PUT "$MCP_URL/admin/tenants/demo-tenant/rate-limit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"qps":200}' > /dev/null && echo "✅ Rate limit set (200 QPS)"

curl -s -X PUT "$MCP_URL/admin/tenants/demo-tenant/quota" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"cloud_usd","period":"day","limit":15}' > /dev/null && echo "✅ Budget quota set (\$15/day)"

# Test 3: High-cost action requiring approval
echo -e "\n🔐 Testing approval workflow..."
REQ='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cloud.ops","arguments":{"provider":"aws","resource":"ec2","action":"run_instances","estimated_cost_usd":12}}}'
RESP=$(curl -s -X POST "$MCP_URL/mcp" -H "Authorization: Bearer $TOKEN" -d "$REQ")

if echo "$RESP" | jq -e '.result.decision == "approval"' > /dev/null 2>&1; then
    echo "✅ High-cost action requires approval (as expected)"
    PID=$(echo "$RESP" | jq -r '.result.pendingId // empty')
    if [[ -n "$PID" ]]; then
        echo "   Pending ID: $PID"
        echo "   Check /console/approvals or approve with: python tests/e2e/util_approve.py \"$PID\" approve"
    fi
else
    echo "⚠️  Expected approval but got: $(echo "$RESP" | jq -r '.result.decision // "error"')"
fi

# Test 4: Policy Simulator
echo -e "\n🧪 Testing Policy Simulator..."
SIM_REQ='{"tool":"net.http","arguments":{"method":"GET","url":"https://intranet.api/status"}}'
SIM_RESP=$(curl -s -X POST "$MCP_URL/v1/policy/simulate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$SIM_REQ")

if echo "$SIM_RESP" | jq -e '.decision' > /dev/null 2>&1; then
    DECISION=$(echo "$SIM_RESP" | jq -r '.decision')
    echo "✅ Policy simulation works - Decision: $DECISION"
else
    echo "❌ Policy simulator failed"
fi

# Test 5: Console Access (if running)
echo -e "\n🖥️  Testing Console Access..."
export MCP_BASE_URL="$MCP_URL"
export CONSOLE_BEARER="$TOKEN"

if curl -s "$CONSOLE_URL/console" > /dev/null 2>&1; then
    echo "✅ Console is accessible at $CONSOLE_URL/console"
else
    echo "⚠️  Console not running at $CONSOLE_URL"
    echo "   Start with: python -m uvicorn app:app --host 0.0.0.0 --port 8081 --reload"
fi

# Test 6: Metrics endpoint
echo -e "\n📈 Checking metrics endpoint..."
if curl -s "$MCP_URL/metrics" > /dev/null; then
    echo "✅ Metrics endpoint responding"
else
    echo "❌ Metrics endpoint failed"
fi

# Summary
echo -e "\n🎯 Demo Verification Complete!"
echo "================================"
echo "Next steps for demo:"
echo "1. Visit $CONSOLE_URL/console for the visual interface"
echo "2. Try Access Dashboard → see live policy decisions"
echo "3. Try Policy Simulator → test tool calls"
echo "4. Try Approvals Queue → approve/deny requests"  
echo "5. Try Policy Management → upload and diff policies"
echo -e "\nEnvironment ready for customer preview! 🚀"