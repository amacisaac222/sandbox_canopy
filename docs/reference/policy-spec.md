# Policy Specification

CanopyIQ policies are YAML documents that define rules for tool access control.

## Basic Structure

```yaml
version: 1
defaults:
  decision: deny  # fail-closed by default

rules:
  - name: "Rule name"
    match: "tool.name"
    where:
      # conditions
    action: allow | deny | approval
    reason: "Human-readable explanation"
```

## Rule Matching

### Tool Patterns
- `net.http` - Exact match
- `fs.*` - Wildcard (not implemented yet)

### Where Conditions

#### HTTP Rules
```yaml
where:
  method: "GET"                           # HTTP method
  host_in: ["api.internal.com"]           # Allowed hosts
  host_not_in: ["external.badsite.com"]   # Blocked hosts  
  body_bytes_over: 1048576                # Size limit
```

#### File System Rules  
```yaml
where:
  path_not_under: ["/etc", "/usr"]        # Forbidden paths
  path_under: ["/tmp", "/sandbox"]        # Allowed paths
```

#### Cost Rules
```yaml
where:
  estimated_cost_usd_over: 10.0          # Dollar threshold
```

## Actions

### Allow
```yaml
action: allow
```
Tool call proceeds without intervention.

### Deny
```yaml  
action: deny
reason: "External API access forbidden"
```
Tool call is blocked with optional reason.

### Approval
```yaml
action: approval
required_approvals: 2                    # Dual-control
approver_group: "security-team"         # Route to specific team  
reason: "High-cost operation requires approval"
```

## Advanced Features

### Dual Control
Require N approvers before allowing:
```yaml
action: approval
required_approvals: 2
```

### Staged Rollout
Policies support versioning and canary deployment:
```bash
# Deploy to 10% of tenants
curl -X POST /v1/policy/apply \
  -F strategy=canary_percent \
  -F canary_percent=10
```

### Tenant Overrides
Pin specific tenants to policy versions:
```bash
curl -X POST /v1/policy/apply \
  -F strategy=explicit \
  -F tenants_csv="acme-prod,globex-critical"
```

## Best Practices

1. **Start Restrictive**: Use `deny` by default, explicitly allow what's needed
2. **Layer Defense**: Combine multiple conditions (host + method + size)
3. **Meaningful Names**: Use descriptive rule names for audit trails
4. **Test Changes**: Use policy simulator before deployment
5. **Version Control**: Sign policies and use staged rollouts