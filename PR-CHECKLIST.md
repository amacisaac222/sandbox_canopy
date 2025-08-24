# CanopyIQ MCP – Enterprise Add-ons

**Scope**
- Redis-backed approvals (pending store, pub/sub)
- Dual-control approvals (N approvers, deny precedence)
- Policy bundle signing (Ed25519) + verification on startup
- Per-tenant rate-limits + daily cost budgets
- Cost estimator tool (`cloud.estimate`)
- Policy simulator API with trace (`/v1/policy/simulate`)
- RBAC scaffolding + dev token CLI
- Slack & Microsoft Teams approvals (signed links)
- One-command Docker Compose e2e + GitHub Actions CI

---

## Reviewer Checklist

### Security
- [ ] OIDC or dev JWT required for all POST/PUT admin routes
- [ ] Policy default is fail-closed (`deny`)
- [ ] Egress allowlist enforced in `net.http`
- [ ] FS jail enforced; writes outside jail -> `approval`
- [ ] Signature verification path blocking start when `POLICY_REQUIRE_SIGNATURE=true`
- [ ] Teams links signed & time-limited; Slack requests signature-checked

### Reliability / Ops
- [ ] `/metrics`, `/healthz`, `/readyz` respond
- [ ] Redis/Postgres connections pooled; retry/backoff on startup
- [ ] Helm values expose env for budgets, approvals, signing
- [ ] Rate-limit/QPS configurable per tenant

### DX / Docs
- [ ] `docs/integrations/mcp.md` explains HTTP + stdio
- [ ] `docs/reference/api.md` documents simulator
- [ ] `cli/admin.py` mints dev tokens; README includes example
- [ ] `cli/policy_sign.py` keys, sign, verify documented

### E2E
- [ ] `docker-compose.yml` boots Redis, Postgres, Server
- [ ] `tests/e2e/ci_e2e.sh` runs full approval flow & budget enforcement
- [ ] GitHub Actions passes on clean repo