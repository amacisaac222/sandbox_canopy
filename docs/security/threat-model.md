# Threat Model

**Risks prevented**
- Data exfiltration via external APIs
- Runaway spend (budget caps)
- Unauthorized system changes
- Schema-unsafe outputs

**Controls**
- Policy enforcement (allow/deny/approval)
- Network/domain whitelists
- Human approvals with identity binding
- Immutable audit + SIEM export