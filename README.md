# Agent Sandbox — MVP

Agent Sandbox is a runtime policy layer for AI agents. It enforces:

- Tool/API allow/deny lists
- JSON-Schema parameter validation  
- Network/domain allowlists
- Budgets (requests/$/chain depth)
- Human approvals for sensitive actions
- Audit logs & basic metrics

This repo contains:

- `sdk/`: the client wrapper you embed in agents
- `control_plane/`: FastAPI service for policies + approvals  
- `demos/`: a tiny agent and fake tools to demo end-to-end

## Quickstart

### 1) Create & activate a venv
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Set env & launch control plane

Create `.env`:
```bash
cp .env.example .env
# Edit .env if needed
```

Run control plane:
```bash
./scripts/run_control_plane.sh
```

### 3) Seed demo data

In another terminal:
```bash
python scripts/seed_demo_data.py
```

### 4) Run the demo agent

```bash
python demos/demo_agent.py
```

### 5) Approve pending actions

Open the approvals UI:
```
http://localhost:8080/approvals
```

Approve the email.send request → rerun or have your SDK poll for approval.

### 6) Export audit log
```bash
curl -s "http://localhost:8080/v1/audit/export?from=0&to=9999999999" | jq .
```

## SDK Usage (embed in your agent)

```python
from sdk.client import SandboxClient
from sdk.tool_registry import DEFAULT_SCHEMAS

client = SandboxClient(
    control_plane_base="https://cp.yourdomain.com",
    agent_id="AGENT_ID",
    agent_api_key="AGENT_KEY", 
    initial_policy=None,            # will fetch from control plane
    tool_schemas=DEFAULT_SCHEMAS,
)

# Tool call (policy-checked)
decision = client.tool_call("email.send", {
    "recipient":"x@company.com",
    "subject":"Hi",
    "body":"..."
})

if decision["decision"] == "allow":
    # execute the real tool call here
    pass
elif decision["decision"] == "needs_approval":
    # wait/poll until approved or abort
    pass
else:
    # denied -> handle gracefully
    pass

# HTTP egress (policy-checked)
client.http_request("GET", "https://api.company.com/v1/users")
```

## Console (Dev)

The CanopyIQ Console provides a visual "Okta-for-Agents" interface for managing policies, approvals, and tool access.

### Setup

Set environment variables (Windows PowerShell):
```powershell
$env:MCP_BASE_URL="http://localhost:8080"
$env:CONSOLE_BEARER="your-dev-token"
```

Or Linux/macOS:
```bash
export MCP_BASE_URL="http://localhost:8080"
export CONSOLE_BEARER="your-dev-token"
```

### Run the Console

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

### Access

Visit: http://localhost:8080/console

### Features

- **Access Dashboard**: Live tool permission tiles with policy simulation
- **Approvals Queue**: Interactive approve/deny for pending requests
- **Policy Simulator**: Test tool calls against live policies with trace output
- **Policy Management**: Upload, diff, and rollout policy changes

### Health Check

Verify MCP server connection:
- http://localhost:8080/healthz

## Testing

```bash
pytest -v
```

## Docker

Build and run locally:
```bash
docker compose up --build
```

- Control plane: http://localhost:8080
- Through proxy: http://localhost:8081

## Kubernetes

```bash
# Build and push images
docker build -t yourrepo/agent-sandbox-cp:0.1.0 .
docker build -t yourrepo/agent-sandbox-proxy:0.1.0 ./nginx

# Install with Helm
helm upgrade --install sandbox ./helm/agent-sandbox \\
  --set image.repository=yourrepo/agent-sandbox-cp \\
  --set image.tag=0.1.0 \\
  --set proxyImage.repository=yourrepo/agent-sandbox-proxy \\
  --set proxyImage.tag=0.1.0
```

## What's in the box

- Policy hot-reload every 30s (signed bundle)
- Approvals with a simple HTML UI
- Budgets (requests, $), chain-depth guard  
- Allow/Deny by tool patterns
- Network allowlist (deny-by-default)
- Structured logs + basic metrics counters

## Roadmap (after MVP)

- Sidecar HTTP proxy (Envoy or tiny Go proxy)
- SIEM integrations (Splunk/Sentinel)
- Compliance packs (SOC2/HIPAA templates)
- Tool Schema Marketplace
- Anomaly detection on telemetry (later)

## Project Structure

```
agent-sandbox/
├─ control_plane/          # FastAPI control plane
│  ├─ app.py              # Main FastAPI app
│  ├─ db.py               # Database setup
│  ├─ models.py           # SQLAlchemy models
│  ├─ signer.py           # Policy signing
│  └─ templates/          # Jinja2 templates
├─ sdk/                   # Client SDK
│  ├─ client.py           # Main SandboxClient
│  ├─ enforcement.py      # Policy enforcement logic
│  ├─ policy_cache.py     # Hot-reloading policies
│  └─ tool_registry.py    # Tool schemas
├─ policies/examples/     # Example policies
├─ demos/                 # Demo agents and tools
├─ tests/                 # Test suite
├─ scripts/               # Helper scripts
├─ helm/agent-sandbox/    # Kubernetes Helm chart
└─ nginx/                 # Reverse proxy
```

## License

MIT