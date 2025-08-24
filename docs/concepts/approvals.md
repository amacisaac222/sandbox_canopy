# Approval System

CanopyIQ supports human approval workflows for sensitive operations through Redis-backed persistent approvals with Slack integration.

## Basic Approvals

When a policy rule returns `approval`, the tool call is paused and routed to approvers via Slack:

```yaml
- name: "External API calls need approval"
  match: "net.http"
  where:
    host_not_in: ["internal.api", "intranet.corp"]
  action: approval
  reason: "External HTTP requests require approval"
```

## Dual-Control Approvals

Add `required_approvals: 2` (or N) to any `approval` rule. The request stays `pending` until N unique approvers approve. Any single **deny** resolves to `deny` immediately.

```yaml
- name: "Write outside jail"
  match: "fs.write"
  where:
    path_not_under: ["/sandbox/tmp", "/sandbox/out"]
  action: approval
  required_approvals: 2
  reason: "Two-person control for non-jail writes"
```

## Approval Flow

1. **Policy Match**: Tool call matches an `approval` rule
2. **Redis Store**: Pending approval created with TTL (default 15min)
3. **Slack Notification**: Interactive message posted with Approve/Deny buttons
4. **Decision Recording**: Each approver's choice is recorded
5. **Resolution**: Status changes to `allow` when required approvals reached, or `deny` on any rejection
6. **Audit Log**: All decisions are logged with approver identity

## Synchronous vs Asynchronous

- **Asynchronous (default)**: Agent gets "approval required" response immediately
- **Synchronous**: Set `APPROVAL_SYNC_WAIT_MS=20000` to wait up to 20s for approval before responding

## Redis Pub/Sub

The system uses Redis pub/sub to notify waiting processes when approvals are resolved, enabling real-time responses without polling.

## Configuration

```bash
export REDIS_URL="redis://redis:6379/0"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export SLACK_SIGNING_SECRET="your-signing-secret"
export APPROVAL_SYNC_WAIT_MS="0"  # 0 for async, >0 for sync wait
```