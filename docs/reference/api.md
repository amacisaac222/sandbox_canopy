# API Reference

## Policy Simulator

### POST /v1/policy/simulate

Evaluate policies with detailed trace for debugging and change reviews.

**Request:**
```json
{
  "tool": "net.http",
  "arguments": {
    "method": "GET",
    "url": "https://intranet.api/status"
  }
}
```

**Optional Parameters:**
```json
{
  "tool": "net.http",
  "arguments": {...},
  "policy_file": "app/policies/custom.yaml"
}
```

**Response:**
```json
{
  "decision": "allow",
  "rule": "Allow intranet HTTP",
  "reason": null,
  "required_approvals": 1,
  "trace": [
    {
      "rule": "Allow intranet HTTP",
      "match": true,
      "explain": [
        {"ok": true, "msg": "host 'intranet.api' allowed"}
      ]
    }
  ]
}
```

**Authentication:** Requires `viewer`, `approver`, or `admin` role.

## RBAC Administration

### PUT /admin/rbac/{tenant}/users/{subject}

Assign roles to a user.

**Request:**
```json
{
  "roles": ["approver", "viewer"]
}
```

**Response:**
```json
{
  "ok": true,
  "tenant": "demo-tenant",
  "subject": "alice",
  "roles": ["approver", "viewer"]
}
```

### GET /admin/rbac/{tenant}/users/{subject}

Get roles for a user.

**Response:**
```json
{
  "tenant": "demo-tenant", 
  "subject": "alice",
  "roles": ["approver", "viewer"]
}
```

**Authentication:** Requires `admin` role.

## Available Roles

- **admin**: Full administrative access, can assign roles
- **approver**: Can approve pending requests in Slack
- **viewer**: Can use policy simulator and view system status