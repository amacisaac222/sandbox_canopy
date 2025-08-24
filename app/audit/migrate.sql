-- Immutable audit log w/ hash chain
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  tenant TEXT NOT NULL,
  subject TEXT NOT NULL,          -- agent id / client id
  tool TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('allow','deny','approval')),
  rule TEXT,
  args_json JSONB,
  result_meta JSONB,
  approver TEXT,
  hash BYTEA NOT NULL,
  prev_hash BYTEA,
  CONSTRAINT audit_prev_fk FOREIGN KEY (prev_hash) REFERENCES audit_log(hash) DEFERRABLE INITIALLY DEFERRED
);

CREATE UNIQUE INDEX IF NOT EXISTS audit_log_hash_idx ON audit_log (hash);
CREATE INDEX IF NOT EXISTS audit_log_ts_idx ON audit_log (ts);
CREATE INDEX IF NOT EXISTS audit_log_tenant_idx ON audit_log (tenant);
CREATE INDEX IF NOT EXISTS audit_log_tool_idx ON audit_log (tool);

-- Pending approvals
CREATE TABLE IF NOT EXISTS approvals (
  pending_id TEXT PRIMARY KEY,
  ts_created TIMESTAMPTZ NOT NULL DEFAULT now(),
  ts_decided TIMESTAMPTZ,
  tenant TEXT NOT NULL,
  requester TEXT NOT NULL,        -- subject
  approver TEXT,
  tool TEXT NOT NULL,
  args_json JSONB,
  status TEXT NOT NULL CHECK (status IN ('pending','allow','deny')) DEFAULT 'pending',
  reason TEXT
);

CREATE INDEX IF NOT EXISTS approvals_status_idx ON approvals (status);
CREATE INDEX IF NOT EXISTS approvals_tenant_idx ON approvals (tenant);

-- Policy version catalog
CREATE TABLE IF NOT EXISTS policy_version (
  version TEXT PRIMARY KEY,                  -- e.g., 2025-08-21_154512_4d9c
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sha256 BYTEA NOT NULL,
  path TEXT NOT NULL,                        -- server local path to yaml
  sig_path TEXT NOT NULL                     -- server local path to .sig
);

-- Current rollout (single row)
CREATE TABLE IF NOT EXISTS policy_rollout (
  id SMALLINT PRIMARY KEY DEFAULT 1,
  active_version TEXT NOT NULL REFERENCES policy_version(version),
  canary_version TEXT,
  canary_percent INTEGER NOT NULL DEFAULT 0 CHECK (canary_percent >= 0 AND canary_percent <= 100),
  seed INTEGER NOT NULL DEFAULT 1,           -- stable hash seed for percent rollout
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-tenant overrides (pin a tenant to a specific version)
CREATE TABLE IF NOT EXISTS tenant_policy_override (
  tenant TEXT PRIMARY KEY,
  version TEXT NOT NULL REFERENCES policy_version(version),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);