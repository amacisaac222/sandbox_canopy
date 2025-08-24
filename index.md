# CanopyIQ

Enterprise MCP tool-gateway with policy, approvals, budgets, and audit.

## Overview

CanopyIQ is a production-ready MCP (Model Context Protocol) server that provides:

- **Policy-driven Security**: Rule-based tool access with fail-closed defaults
- **Human Approvals**: Slack/Teams integration with dual-control support  
- **Cost Controls**: Pre-flight estimation and budget enforcement
- **Audit & Compliance**: Immutable logs with tamper-evident hash chains
- **Staged Rollouts**: Signed policy deployment with canary releases

## Key Features

- 🔒 **Zero-Trust Policy Engine** - Every tool call evaluated against signed policies
- 🤝 **Approval Workflows** - Human oversight for sensitive operations with N-of-M controls
- 💰 **Budget Management** - Per-tenant quotas with real-time cost tracking
- 📊 **Complete Observability** - Prometheus metrics, structured logging, audit trails
- 🚀 **Enterprise Ready** - Kubernetes deployment, OIDC auth, staged rollouts

## Quick Start

```bash
# Clone and start
git clone https://github.com/<your-org>/canopyiq-mcp
cd canopyiq-mcp
make demo

# Visit the admin UI
open http://localhost:8080/ui/audit
```

## Architecture

CanopyIQ sits between AI agents and external tools, providing:

1. **Policy Evaluation** - Rules determine allow/deny/approval for each tool call
2. **Approval Orchestration** - Route sensitive operations to human approvers
3. **Cost Tracking** - Estimate and enforce spending limits per tenant
4. **Audit Logging** - Tamper-evident records for compliance

See [Quick Start](quickstart.md) for detailed setup instructions.