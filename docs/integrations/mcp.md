# Connect to CanopyIQ via MCP

CanopyIQ provides enterprise AI governance for Claude through the **Model Context Protocol (MCP)**:
- **Real-time monitoring** of all Claude tool usage  
- **Policy enforcement** with automatic allow/deny/approval decisions
- **Audit logging** and compliance tracking
- **Project context continuity** across sessions

**Supported Clients:**
- 🖥️ **Claude Desktop** - Full GUI integration with real-time monitoring
- ⌨️ **Claude Code CLI** - Command-line integration with `--mcp-config` flag

---

## Quick Setup

### Option 1: One-Line Installer (Recommended)

```bash
npx canopyiq-setup
```

This automatically:
- ✅ Installs the `canopyiq-mcp-server` package
- ✅ Configures both Claude Desktop and Claude Code
- ✅ Provides usage instructions for both platforms
- ✅ Creates backups of existing configurations

### Option 2: Claude Code CLI Only

For Claude Code CLI users who want direct setup:

1. **Install the MCP server:**
   ```bash
   npm install -g canopyiq-mcp-server
   ```

2. **Get your API key:** Visit https://canopyiq.ai/admin/mcp

3. **Create configuration file:**
   ```bash
   echo '{"mcpServers":{"canopyiq":{"command":"canopyiq-mcp-server","args":["--api-key","YOUR_API_KEY","--server-url","https://canopyiq.ai"]}}}' > ~/.canopyiq-claude-code.json
   ```

4. **Use with Claude Code:**
   ```bash
   claude --mcp-config ~/.canopyiq-claude-code.json "your prompt here"
   ```

---

## Transport Options

- **HTTP JSON-RPC** (recommended for shared/remote)
- **stdio** (launch as a child process; great for local dev)

---

## Option A — HTTP JSON-RPC

### 1. **Run the server**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
# /mcp endpoint, /metrics, /healthz, /readyz
```

### 2. **Set auth & policy**

Issue a bearer token from your IdP (OIDC).

Point the server at your policy bundle:
```bash
export CANOPYIQ_POLICY_FILE=./app/policies/samples.yaml
```

### 3. **Configure your MCP client**

- **MCP Endpoint**: `https://mcp.canopyiq.internal/mcp` (or `http://localhost:8080/mcp`)
- **Auth**: `Authorization: Bearer <token>`
- **Protocol**: JSON-RPC 2.0

Expect capabilities:
```json
{
  "capabilities": { "tools": { "listChanged": true } },
  "protocolVersion": "2025-06-18"
}
```

### 4. **Test**

List tools:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

Call a tool (policy-guarded HTTP):
```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"net.http","arguments":{"method":"GET","url":"https://intranet.api/status"}}}
```

## Option B — stdio (local)

### 1. **Run stdio server**
```bash
cd canopyiq-mcp/app
python stdio_runner.py
```

The process reads JSON-RPC lines from stdin and writes responses to stdout.

### 2. **Configure your MCP client**

- **Transport**: stdio  
- **Command**: `python`
- **Args**: `app/stdio_runner.py`
- **Working dir**: repo root (so policies & tools import cleanly)

### 3. **Handshake (optional)**
Some clients send `initialize/server/initialize`; CanopyIQ responds with:
```json
{"jsonrpc":"2.0","id":1,"result":{"capabilities":{"tools":{"listChanged":true}},"protocolVersion":"2025-06-18"}}
```

---

## Policies (fast overview)

- **Fail-closed** by default (`defaults.decision: deny`)
- **First-match wins** (configurable)
- **Common matches**: `net.http`, `fs.read`, `fs.write`, `mail.send`, `cloud.ops`
- **Actions**: `allow` | `deny` | `approval`

Example:
```yaml
version: 1
defaults: { decision: deny }
rules:
  - name: "Allow intranet HTTP"
    match: "net.http"
    where: { host_in: ["intranet.api"] }
    action: allow

  - name: "Large uploads need approval"
    match: "net.http"
    where: { method: "POST", body_bytes_over: 1048576 }
    action: approval
```

## Approvals

When a rule returns `approval`, the tool call is paused and routed to your approver channel (e.g., Slack). Once approved/denied, the agent continues and the decision is logged.

## Observability

- **`/metrics`** → Prometheus (QPS, latency, decisions)
- **Audit** → Postgres (+ optional Splunk/Elastic sinks)
- **Dashboards** → Import the provided Grafana JSON

## Troubleshooting

- **401 Unauthorized** → Check bearer token, `aud`, `iss`, and JWKS.
- **Policy denies** → Inspect the rule hit and the `where` condition.
- **High latency** → See p95 histogram; scale replicas (HPA) or tune policy predicates.
- **Approval stuck** → Verify Slack webhook/permissions and callback URL.

## Next:

- [Policy Spec](../reference/policy-spec.md)
- [API Reference](../reference/api.md)
- [Security & Compliance](../security/compliance.md)