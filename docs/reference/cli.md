# CLI Reference

## Admin CLI

The admin CLI provides tools for managing authentication and RBAC in development environments.

### Mint Dev Token

Generate development JWT tokens for local testing:

```bash
python cli/admin.py mint-token --tenant demo --subject alice --roles admin,approver --ttl 3600
```

**Parameters:**
- `--tenant`: Tenant identifier
- `--subject`: User/subject identifier  
- `--roles`: Comma-separated list of roles
- `--ttl`: Token time-to-live in seconds (default: 3600)

**Example:**
```bash
# Create admin token
export ADMIN_TOKEN=$(python cli/admin.py mint-token --tenant demo-tenant --subject alice --roles admin --ttl 7200)

# Use token for API calls
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8080/metrics
```

**Available Roles:**
- `admin`: Full administrative access
- `approver`: Can approve pending requests
- `viewer`: Read-only access to simulator

## Policy Signing CLI

### Generate Keys

```bash
python cli/policy_sign.py gen-key --out-dir keys/
```

### Sign Policy Bundle

```bash
python cli/policy_sign.py sign app/policies/samples.yaml --private-key keys/canopyiq_policy_private.key
```

### Verify Signature

```bash
python cli/policy_sign.py verify app/policies/samples.yaml \
  --public-key keys/canopyiq_policy_public.key \
  --signature app/policies/samples.yaml.sig
```

## Environment Variables

### Development JWT
- `DEV_JWT_SECRET`: Secret for signing dev tokens (default: "change-me-dev-secret")
- `DEV_ISSUER`: Token issuer (default: "canopyiq-dev")
- `OIDC_AUDIENCE`: Token audience (default: "canopyiq-mcp")

### Production OIDC
- `OIDC_ISSUER`: OIDC provider issuer URL
- `OIDC_JWKS_URL`: JWKS endpoint URL
- `OIDC_AUDIENCE`: Expected audience claim