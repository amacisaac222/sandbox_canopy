# Policy Engine

**Goal:** enforce enterprise rules in **<10ms** per decision.

**Policy actions**
- `allow` — execute immediately
- `deny` — block and log
- `approval` — pause and route to a human approver

**Match targets**
- Tool / API call
- File operation
- Network request
- Command execution
- Structured output schema

See: [Policy Spec](../reference/policy-spec.md)