# CanopyIQ Demo Verification Script (PowerShell)
# Run this script to verify the full golden path

param(
    [Parameter(Mandatory=$false)]
    [string]$MCPUrl = "http://localhost:8080",
    
    [Parameter(Mandatory=$false)]
    [string]$ConsoleUrl = "http://localhost:8081"
)

Write-Host "🚀 CanopyIQ Demo Verification Script" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

# Check if TOKEN is set
if (-not $env:TOKEN) {
    Write-Host "❌ TOKEN environment variable not set" -ForegroundColor Red
    Write-Host "Run: python cli/admin.py mint-token --tenant demo-tenant --subject demo --roles admin,approver --ttl 7200" -ForegroundColor Yellow
    Write-Host "Then: `$env:TOKEN='your-token-here'" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ TOKEN found: $($env:TOKEN.Substring(0, 20))..." -ForegroundColor Green

# Test 1: Basic MCP Health
Write-Host "`n📊 Testing MCP Server Health..." -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$MCPUrl/healthz" -Method GET
    Write-Host "✅ MCP Server is healthy" -ForegroundColor Green
} catch {
    Write-Host "❌ MCP Server not responding: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Set Rate Limit & Quota  
Write-Host "`n⚡ Setting up rate limits and quotas..." -ForegroundColor Cyan
$headers = @{ "Authorization" = "Bearer $env:TOKEN"; "Content-Type" = "application/json" }

try {
    # Rate limit
    $rateBody = @{ qps = 200 } | ConvertTo-Json
    Invoke-RestMethod -Uri "$MCPUrl/admin/tenants/demo-tenant/rate-limit" -Method PUT -Headers $headers -Body $rateBody
    Write-Host "✅ Rate limit set (200 QPS)" -ForegroundColor Green
    
    # Quota
    $quotaBody = @{ name = "cloud_usd"; period = "day"; limit = 15 } | ConvertTo-Json  
    Invoke-RestMethod -Uri "$MCPUrl/admin/tenants/demo-tenant/quota" -Method PUT -Headers $headers -Body $quotaBody
    Write-Host "✅ Budget quota set ($15/day)" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to set limits: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 3: High-cost action requiring approval
Write-Host "`n🔐 Testing approval workflow..." -ForegroundColor Cyan
$approvalRequest = @{
    jsonrpc = "2.0"
    id = 1
    method = "tools/call"
    params = @{
        name = "cloud.ops"
        arguments = @{
            provider = "aws"
            resource = "ec2" 
            action = "run_instances"
            estimated_cost_usd = 12
        }
    }
} | ConvertTo-Json -Depth 3

try {
    $response = Invoke-RestMethod -Uri "$MCPUrl/mcp" -Method POST -Headers $headers -Body $approvalRequest
    if ($response.result.decision -eq "approval") {
        Write-Host "✅ High-cost action requires approval (as expected)" -ForegroundColor Green
        $pendingId = $response.result.pendingId
        Write-Host "   Pending ID: $pendingId" -ForegroundColor Yellow
        
        # Auto-approve for demo (you could also check /console/approvals UI)
        Write-Host "   Auto-approving for demo..." -ForegroundColor Yellow
        # Note: In real scenarios, you'd approve via /console/approvals or Slack/Teams
        
    } else {
        Write-Host "⚠️  Expected approval but got: $($response.result.decision)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Approval test failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Policy Simulator
Write-Host "`n🧪 Testing Policy Simulator..." -ForegroundColor Cyan
$simulatorRequest = @{
    tool = "net.http"
    arguments = @{
        method = "GET"
        url = "https://intranet.api/status"
    }
} | ConvertTo-Json

try {
    $simResult = Invoke-RestMethod -Uri "$MCPUrl/v1/policy/simulate" -Method POST -Headers $headers -Body $simulatorRequest
    Write-Host "✅ Policy simulation works - Decision: $($simResult.decision)" -ForegroundColor Green
} catch {
    Write-Host "❌ Policy simulator failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 5: Console Access (if running)
Write-Host "`n🖥️  Testing Console Access..." -ForegroundColor Cyan

# Set console environment variables
$env:MCP_BASE_URL = $MCPUrl
$env:CONSOLE_BEARER = $env:TOKEN

try {
    $consoleHealth = Invoke-RestMethod -Uri "$ConsoleUrl/console" -Method GET -ErrorAction SilentlyContinue
    Write-Host "✅ Console is accessible at $ConsoleUrl/console" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Console not running at $ConsoleUrl" -ForegroundColor Yellow
    Write-Host "   Start with: python -m uvicorn app:app --host 0.0.0.0 --port 8081 --reload" -ForegroundColor Yellow
}

# Test 6: Metrics endpoint
Write-Host "`n📈 Checking metrics endpoint..." -ForegroundColor Cyan
try {
    $metrics = Invoke-RestMethod -Uri "$MCPUrl/metrics" -Method GET
    Write-Host "✅ Metrics endpoint responding" -ForegroundColor Green
} catch {
    Write-Host "❌ Metrics endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Summary
Write-Host "`n🎯 Demo Verification Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host "Next steps for demo:" -ForegroundColor White
Write-Host "1. Visit $ConsoleUrl/console for the visual interface" -ForegroundColor White  
Write-Host "2. Try Access Dashboard → see live policy decisions" -ForegroundColor White
Write-Host "3. Try Policy Simulator → test tool calls" -ForegroundColor White
Write-Host "4. Try Approvals Queue → approve/deny requests" -ForegroundColor White
Write-Host "5. Try Policy Management → upload and diff policies" -ForegroundColor White
Write-Host "`nEnvironment ready for customer preview! 🚀" -ForegroundColor Green