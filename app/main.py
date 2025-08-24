from fastapi import FastAPI, Header, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates
import json
import time
import os
import uuid
import yaml
import psycopg2, psycopg2.extras
from urllib.parse import parse_qs

# Import existing components (assuming they exist)
from .approvals.verify import verify_slack_request
from .approvals.slack import request_approval
from .approvals.state import create_pending, new_pending_id, wait_for_resolution, record_decision, get as get_pending
from .audit.writer import write_log
from .policies.engine import PolicyEngine
from .policies.verify import verify_bundle
from .auth import verify_token
from .rbac.store import set_roles, get_roles
from .approvals.teams import verify_teams_signature
from .policies.diff import compare as compare_policies
from .policies.manager import PolicyManager
from .policies.storage import register_policy

app = FastAPI(title="CanopyIQ MCP Server", version="0.1.0")

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="CanopyIQ MCP Server",
        version="0.1.0",
        description="MCP tool-gateway with policy, approvals, budgets, and audit.",
        routes=app.routes,
    )
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
      "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
      }
    }
    # Mark all paths as requiring bearer by default (docs display)
    for path in openapi_schema.get("paths", {}):
        for method in openapi_schema["paths"][path]:
            op = openapi_schema["paths"][path][method]
            if method.lower() in ("get","post","put","delete","patch"):
                op.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Configuration
APPROVAL_SYNC_WAIT_MS = int(os.getenv("APPROVAL_SYNC_WAIT_MS", "0"))  # e.g., 20000 to wait up to 20s
POLICY_PUBLIC_KEY_B64 = os.getenv("POLICY_PUBLIC_KEY_B64", "")
POLICY_SIG_PATH = os.getenv("POLICY_SIG_PATH", "")
POLICY_REQUIRE_SIGNATURE = os.getenv("POLICY_REQUIRE_SIGNATURE", "false").lower() in ("1", "true", "yes")

def s(n: int) -> str: 
    return "" if n == 1 else "s"

def _load_policy():
    path = os.getenv("CANOPYIQ_POLICY_FILE", "./app/policies/samples.yaml")
    if POLICY_PUBLIC_KEY_B64 and POLICY_SIG_PATH:
        ok, msg = verify_bundle(path, POLICY_SIG_PATH, POLICY_PUBLIC_KEY_B64)
        if not ok:
            if POLICY_REQUIRE_SIGNATURE:
                raise RuntimeError(f"Policy signature invalid: {msg}")
            else:
                print(f"[WARN] Policy signature invalid: {msg}")
        else:
            print("[INFO] Policy signature verified.")
    import yaml
    with open(path, "r") as f:
        return PolicyEngine(yaml.safe_load(f))

POLICY = _load_policy()

# Initialize policy manager and templates
PM = PolicyManager(os.getenv("DATABASE_URL", "postgresql://canopy:canopy@localhost:5432/audit"))
templates_ui = Jinja2Templates(directory="app")

@app.get("/healthz", tags=["Observability"], summary="Liveness probe")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/readyz", tags=["Observability"], summary="Readiness probe")
async def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready", "timestamp": time.time()}

@app.get("/metrics", tags=["Observability"], summary="Prometheus metrics")
async def metrics():
    """Basic metrics endpoint (replace with prometheus_client in production)"""
    # Count pending approvals in Redis (simplified)
    import redis
    from .approvals.state import r
    try:
        keys = r.keys("appr:*")
        pending_count = len([k for k in keys if not k.startswith("appr:notify:")])
        return {"pending_approvals": pending_count}
    except:
        return {"pending_approvals": 0}

@app.post("/approvals/create")
async def create_approval(payload: dict):
    """
    Example entrypoint when a policy returns `approval`.
    Creates a pending approval and posts message to Slack.
    """
    # payload: { "pending_id", "tenant", "subject", "tool", "summary", "required_approvals" }
    pending_id = payload["pending_id"]
    create_pending(
        pending_id=pending_id,
        tenant=payload["tenant"],
        requester=payload["subject"],
        tool=payload["tool"],
        args=payload.get("args", {}),
        required_approvals=payload.get("required_approvals", 1),
        ttl_sec=900,
        reason=payload.get("summary", "")
    )
    
    summary = payload.get("summary", f"{payload['tool']} pending approval")
    if payload.get("required_approvals", 1) > 1:
        summary += f" (needs {payload['required_approvals']} approval{s(payload['required_approvals'])})"
    
    request_approval(pending_id, summary)
    return {"ok": True, "pending_id": pending_id}

@app.post("/approvals/slack/callback")
async def slack_callback(
    request: Request,
    x_slack_request_timestamp: str = Header(None),
    x_slack_signature: str = Header(None)
):
    """
    Slack interactive message/button callback URL.
    Configure this in your Slack App:
      Interactivity -> Request URL -> https://<host>/approvals/slack/callback
    """
    body = await request.body()
    verify_slack_request(x_slack_request_timestamp, x_slack_signature, body)

    # Slack sends payload=form-encoded (payload=JSON)
    form = parse_qs(body.decode("utf-8"))
    if "payload" not in form:
        return JSONResponse({"ok": False, "error": "no payload"}, status_code=400)

    payload = json.loads(form["payload"][0])

    action = payload.get("actions", [{}])[0].get("action_id")
    pending_id = payload.get("actions", [{}])[0].get("value")  # we set 'value' to pending_id in slack.py
    approver = payload.get("user", {}).get("username") or payload.get("user", {}).get("id") or "unknown"

    try:
        final = record_decision(pending_id, approver, "allow" if action == "approve" else "deny")
        
        # Write audit entry
        if final:
            write_log({
                "tenant": final["tenant"],
                "subject": final["requester"],
                "tool": final["tool"],
                "decision": final["status"],
                "rule": "human_approval",
                "args": final["args"],
                "result_meta": {"source": "slack", "approvals": final["approvals"], "rejections": final["rejections"]},
                "approver": approver
            }, prev_hash=None)
        
        # Show current approval status
        status_text = f"Decision recorded: {action.upper()}"
        if final and final["status"] == "pending":
            approvals_count = len(final["approvals"])
            required = final["required_approvals"]
            status_text += f" ({approvals_count}/{required} approvals needed)"
        elif final and final["status"] == "allow":
            status_text = "APPROVED - All required approvals received"
        elif final and final["status"] == "deny":
            status_text = "DENIED"
            
    except KeyError:
        status_text = "Error: Approval not found or expired"

    # Replace Slack message content
    resp = {
      "response_action": "update",
      "text": status_text
    }
    return JSONResponse(resp)

@app.get("/approvals/teams/decision")
async def teams_decision_callback(
    pending_id: str,
    decision: str,
    ts: str,
    sig: str
):
    """Teams-style signed approval callback for CI testing"""
    secret = os.getenv("TEAMS_SIGNING_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="Teams signing secret not configured")
    
    verify_teams_signature(pending_id, decision, ts, sig, secret)
    
    try:
        final = record_decision(pending_id, "ci-approver", "allow" if decision == "approve" else "deny")
        
        # Write audit entry
        if final:
            write_log({
                "tenant": final["tenant"],
                "subject": final["requester"],
                "tool": final["tool"],
                "decision": final["status"],
                "rule": "teams_approval",
                "args": final["args"],
                "result_meta": {"source": "teams", "approvals": final["approvals"], "rejections": final["rejections"]},
                "approver": "ci-approver"
            }, prev_hash=None)
        
        return {"status": "ok", "decision": decision, "pending_id": pending_id}
        
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval not found or expired")

def require_admin(claims):
    """Require admin role for administrative operations"""
    roles = claims.get("roles") or claims.get("role") or []
    if isinstance(roles,str): roles=[roles]
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="admin role required")

@app.put("/admin/tenants/{tenant}/quota", tags=["Admin"], summary="Set tenant quota (budget)")
async def admin_set_quota(tenant: str, payload: dict, request: Request):
    """Set daily/weekly quota for a tenant"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        require_admin(claims)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    # Mock implementation - in production would store in database
    quota_name = payload.get("name", "cloud_usd")
    period = payload.get("period", "day")
    limit = payload.get("limit", 0)
    
    print(f"[QUOTA] Set {tenant} {quota_name} {period} limit to {limit}")
    return {"ok": True, "tenant": tenant, "quota": quota_name, "period": period, "limit": limit}

@app.put("/admin/tenants/{tenant}/rate-limit", tags=["Admin"], summary="Set tenant QPS")
async def admin_set_rate_limit(tenant: str, payload: dict, request: Request):
    """Set QPS rate limit for a tenant"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        require_admin(claims)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    # Mock implementation - in production would store in database
    qps = payload.get("qps", 100)
    
    print(f"[RATE_LIMIT] Set {tenant} QPS to {qps}")
    return {"ok": True, "tenant": tenant, "qps": qps}

@app.put("/admin/rbac/{tenant}/users/{subject}", tags=["Admin"], summary="Assign roles to user")
async def admin_assign_roles(tenant:str, subject:str, payload:dict, request:Request):
    """Assign roles to a user"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        require_admin(claims)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    roles = payload.get("roles", [])
    set_roles(tenant, subject, roles)
    return {"ok": True, "tenant": tenant, "subject": subject, "roles": get_roles(tenant, subject)}

@app.get("/admin/rbac/{tenant}/users/{subject}", tags=["Admin"], summary="Get user roles")
async def admin_get_roles(tenant:str, subject:str, request:Request):
    """Get roles for a user"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        require_admin(claims)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    return {"tenant": tenant, "subject": subject, "roles": get_roles(tenant, subject)}

@app.post("/v1/policy/diff", tags=["Policy"], summary="Diff two policy bundles")
async def policy_diff(
    request: Request,
    current: UploadFile = File(None, description="Current policy YAML (optional)"),
    proposed: UploadFile = File(..., description="Proposed policy YAML")
):
    """Compare two policy bundles and return risk analysis"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        # Allow viewer/admin to use diff
        roles = claims.get("roles") or claims.get("role") or []
        if isinstance(roles,str): roles=[roles]
        if not any(role in ["admin", "approver", "viewer"] for role in roles):
            raise HTTPException(status_code=403, detail="requires viewer, approver, or admin role")
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    # Load current policy (default to server's current policy if not provided)
    if current is None:
        current_path = os.getenv("CANOPYIQ_POLICY_FILE", "./app/policies/samples.yaml")
        with open(current_path, "r") as f:
            cur_doc = yaml.safe_load(f.read())
    else:
        current_data = await current.read()
        cur_doc = yaml.safe_load(current_data.decode())
    
    # Load proposed policy
    proposed_data = await proposed.read()
    prop_doc = yaml.safe_load(proposed_data.decode())
    
    result = compare_policies(cur_doc, prop_doc)
    return JSONResponse(result)

@app.post("/v1/policy/simulate", tags=["Policy"], summary="Simulate a policy decision with trace")
async def policy_simulate(payload: dict, request: Request):
    """
    Policy simulator endpoint with evaluation trace.
    Request: { "tool": "net.http", "arguments": { ... } }
    Optional: { "policy_file": "app/policies/samples.yaml" } to override.
    """
    try:
        claims = verify_token(request.headers.get("authorization",""))
        # Allow viewer, approver, or admin roles
        roles = claims.get("roles") or claims.get("role") or []
        if isinstance(roles,str): roles=[roles]
        if not any(role in ["admin", "approver", "viewer"] for role in roles):
            raise HTTPException(status_code=403, detail="requires viewer, approver, or admin role")
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    tool = payload["tool"]
    args = payload.get("arguments", {})

    # Optionally load custom bundle for simulation
    import yaml, os
    if payload.get("policy_file"):
        with open(payload["policy_file"], "r") as f:
            pe = PolicyEngine(yaml.safe_load(f))
    else:
        pe = POLICY

    result = pe.evaluate_with_trace(tool, args)
    return JSONResponse(result)

# MCP endpoint 
@app.post("/mcp", tags=["MCP"], summary="MCP JSON-RPC endpoint", description="Implements tools/list and tools/call.")
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC endpoint"""
    try:
        claims = verify_token(request.headers.get("authorization", ""))
    except PermissionError as e:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32003, "message": str(e)}, "id": None}, status_code=401)
    
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id")
    
    if method == "tools/list":
        from .tools.registry import list_tools
        return JSONResponse({"jsonrpc": "2.0", "result": {"tools": list_tools()}, "id": req_id})
    
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        # Policy evaluation using manager for tenant-specific policy
        tenant = claims.get("tenant", "default")
        try:
            engine = PM.engine_for(tenant)
            decision = engine.evaluate(tool_name, args)
        except Exception as e:
            # Fallback to static policy if manager fails
            print(f"[WARN] Policy manager failed, using static policy: {e}")
            decision = POLICY.evaluate(tool_name, args)
        
        if decision.outcome == "deny":
            return JSONResponse({"jsonrpc": "2.0", "result": {
                "content": [{"type": "text", "text": decision.reason or "Blocked by policy"}],
                "isError": True
            }, "id": req_id})
        
        elif decision.outcome == "approval":
            # Create pending approval
            pending_id = new_pending_id()
            create_pending(
                pending_id=pending_id,
                tenant=claims.get("tenant", "default"),
                requester=claims.get("sub", "unknown"),
                tool=tool_name,
                args=args,
                required_approvals=decision.required_approvals,
                ttl_sec=900,
                reason=decision.reason or ""
            )
            
            # Send approval request
            summary = f"[{claims.get('tenant', 'default')}] {tool_name} requested by {claims.get('sub', 'unknown')}"
            if decision.required_approvals > 1:
                summary += f" (needs {decision.required_approvals} approval{s(decision.required_approvals)})"
            request_approval(pending_id, summary)
            
            # Optionally wait for synchronous approval
            if APPROVAL_SYNC_WAIT_MS > 0:
                resolved = wait_for_resolution(pending_id, timeout_sec=APPROVAL_SYNC_WAIT_MS//1000)
                if resolved and resolved["status"] == "allow":
                    # Execute tool after approval
                    from .tools.registry import get_handler
                    handler = get_handler(tool_name)
                    result = handler(args, {"tenant": claims.get("tenant"), "subject": claims.get("sub")})
                    return JSONResponse({"jsonrpc": "2.0", "result": {
                        "content": [{"type": "text", "text": json.dumps(result)}],
                        "structuredContent": result,
                        "isError": False
                    }, "id": req_id})
                elif resolved and resolved["status"] == "deny":
                    return JSONResponse({"jsonrpc": "2.0", "result": {
                        "content": [{"type": "text", "text": "Denied by approver"}],
                        "isError": True
                    }, "id": req_id})
            
            # Async mode - return pending
            return JSONResponse({"jsonrpc": "2.0", "result": {
                "content": [{"type": "text", "text": f"Approval required (pending_id={pending_id})"}],
                "pendingId": pending_id,
                "isError": True
            }, "id": req_id})
        
        else:  # allow
            from .tools.registry import get_handler
            try:
                handler = get_handler(tool_name)
                result = handler(args, {"tenant": claims.get("tenant"), "subject": claims.get("sub")})
                return JSONResponse({"jsonrpc": "2.0", "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "structuredContent": result,
                    "isError": False
                }, "id": req_id})
            except KeyError:
                return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"}, "id": req_id})
            except Exception as e:
                return JSONResponse({"jsonrpc": "2.0", "result": {
                    "content": [{"type": "text", "text": f"Tool error: {e}"}],
                    "isError": True
                }, "id": req_id})
    
    return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32601, "message": "method not found"}, "id": req_id})

# Policy management endpoints
@app.get("/v1/policy/status", tags=["Policy"], summary="Current policy rollout status")
async def policy_status(request: Request):
    """Get current policy rollout status"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        # Allow viewer/admin to check status
        roles = claims.get("roles") or claims.get("role") or []
        if isinstance(roles,str): roles=[roles]
        if not any(role in ["admin", "approver", "viewer"] for role in roles):
            raise HTTPException(status_code=403, detail="requires viewer, approver, or admin role")
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    # Minimal status view
    try:
        with psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://canopy:canopy@localhost:5432/audit")) as cx, cx.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM policy_rollout WHERE id=1")
            ro = cur.fetchone()
            if not ro:
                return {"active_version":"__builtin__", "canary_version":None, "canary_percent":0, "seed":1}
            cur.execute("SELECT COUNT(*) FROM tenant_policy_override")
            cnt = cur.fetchone()[0]
            return {**dict(ro), "tenant_overrides": cnt}
    except Exception as e:
        return {"active_version":"__builtin__", "canary_version":None, "canary_percent":0, "seed":1, "error": str(e)}

@app.post("/v1/policy/apply", tags=["Policy"], summary="Apply signed policy with staged rollout")
async def policy_apply(
    request: Request,
    proposed: UploadFile = File(..., description="Policy YAML"),
    signature: UploadFile = File(..., description="Signature .sig JSON"),
    public_key_b64: str = Form(..., description="Ed25519 public key (base64)"),
    strategy: str = Form("immediate_all"),   # immediate_all | canary_percent | explicit
    canary_percent: int = Form(0),
    seed: int = Form(1),
    tenants_csv: str = Form("", description="Comma-separated tenants for explicit overrides (optional)")
):
    """Apply signed policy with staged rollout"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        require_admin(claims)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Save uploads to temp files
    import tempfile
    pf = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
    pf.write(await proposed.read())
    pf.close()
    
    sf = tempfile.NamedTemporaryFile(delete=False, suffix=".sig")
    sf.write(await signature.read())
    sf.close()

    try:
        # Register (verifies signature)
        db_url = os.getenv("DATABASE_URL", "postgresql://canopy:canopy@localhost:5432/audit")
        version, path, sig_path, sha = register_policy(db_url, pf.name, sf.name, public_key_b64)

        with psycopg2.connect(db_url) as cx, cx.cursor() as cur:
            # Update rollout according to strategy
            if strategy == "immediate_all":
                cur.execute("""
                  INSERT INTO policy_rollout(id, active_version, canary_version, canary_percent, seed)
                  VALUES (1, %s, NULL, 0, %s)
                  ON CONFLICT (id) DO UPDATE SET active_version=EXCLUDED.active_version, canary_version=NULL, canary_percent=0, seed=EXCLUDED.seed, updated_at=now()
                """, (version, seed))
            elif strategy == "canary_percent":
                cur.execute("""
                  INSERT INTO policy_rollout(id, active_version, canary_version, canary_percent, seed)
                  VALUES (1,
                    COALESCE((SELECT active_version FROM policy_rollout WHERE id=1), %s),
                    %s, %s, %s)
                  ON CONFLICT (id) DO UPDATE SET canary_version=EXCLUDED.canary_version, canary_percent=EXCLUDED.canary_percent, seed=EXCLUDED.seed, updated_at=now()
                """, (version, version, int(canary_percent), seed))
            elif strategy == "explicit":
                # do not change rollout row; just write tenant overrides
                tenants = [t.strip() for t in tenants_csv.split(",") if t.strip()]
                for t in tenants:
                    cur.execute("""
                      INSERT INTO tenant_policy_override(tenant, version) VALUES (%s,%s)
                      ON CONFLICT (tenant) DO UPDATE SET version=EXCLUDED.version, updated_at=now()
                    """, (t, version))
            else:
                raise ValueError("Unknown strategy")
            cx.commit()

        return {
            "ok": True,
            "version": version,
            "sha256": sha.hex(),
            "strategy": strategy,
            "canary_percent": int(canary_percent),
            "seed": int(seed)
        }
    finally:
        # Clean up temp files
        os.unlink(pf.name)
        os.unlink(sf.name)

@app.post("/v1/policy/rollback", tags=["Policy"], summary="Rollback active policy")
async def policy_rollback(request: Request, to_version: str):
    """Rollback to a previous policy version"""
    try:
        claims = verify_token(request.headers.get("authorization",""))
        require_admin(claims)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    db_url = os.getenv("DATABASE_URL", "postgresql://canopy:canopy@localhost:5432/audit")
    with psycopg2.connect(db_url) as cx, cx.cursor() as cur:
        cur.execute("""
          UPDATE policy_rollout SET active_version=%s, canary_version=NULL, canary_percent=0, updated_at=now()
          WHERE id=1
        """, (to_version,))
        cx.commit()
    return {"ok": True, "active_version": to_version}

# Read-only UI endpoints
@app.get("/ui/audit", response_class=HTMLResponse, tags=["UI"], summary="Audit view (read-only)")
async def ui_audit(request: Request, tenant: str = "", tool: str = "", decision: str = "", limit: int = 50):
    """Read-only audit log viewer"""
    q = """
      SELECT to_char(ts,'YYYY-MM-DD HH24:MI:SS') as ts, tenant, subject, tool, decision, rule, approver
      FROM audit_log WHERE 1=1
    """
    args = []
    if tenant:
        q += " AND tenant=%s"; args.append(tenant)
    if tool:
        q += " AND tool=%s"; args.append(tool)
    if decision:
        q += " AND decision=%s"; args.append(decision)
    q += " ORDER BY ts DESC LIMIT %s"; args.append(min(limit, 1000))
    
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://canopy:canopy@localhost:5432/audit")
        with psycopg2.connect(db_url) as cx, cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, args)
            rows = cur.fetchall()
    except Exception as e:
        rows = []
        print(f"[ERROR] Failed to fetch audit logs: {e}")
    
    return templates_ui.TemplateResponse("ui/audit.html", {
        "request": request, 
        "rows": rows, 
        "tenant": tenant, 
        "tool": tool, 
        "decision": decision, 
        "limit": limit
    })

@app.get("/ui/approvals", response_class=HTMLResponse, tags=["UI"], summary="Approvals view (read-only)")
async def ui_approvals(request: Request, tenant: str = "", status: str = "pending", limit: int = 50):
    """Read-only approvals viewer"""
    q = """
      SELECT 
        to_char(ts_created,'YYYY-MM-DD HH24:MI:SS') as ts_created, 
        tenant, 
        requester, 
        tool, 
        status,
        COALESCE(required_approvals, 1) as required_approvals,
        COALESCE(array_length(string_to_array(NULLIF(trim(both '[]"' from args_json::text), ''), ','), 1), 0) as approvals_count,
        0 as rejections_count
      FROM approvals WHERE 1=1
    """
    args = []
    if tenant:
        q += " AND tenant=%s"; args.append(tenant)
    if status:
        q += " AND status=%s"; args.append(status)
    q += " ORDER BY ts_created DESC LIMIT %s"; args.append(min(limit, 1000))
    
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://canopy:canopy@localhost:5432/audit")
        with psycopg2.connect(db_url) as cx, cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, args)
            rows = cur.fetchall()
    except Exception as e:
        rows = []
        print(f"[ERROR] Failed to fetch approvals: {e}")
    
    return templates_ui.TemplateResponse("ui/approvals.html", {
        "request": request, 
        "rows": rows, 
        "tenant": tenant, 
        "status": status, 
        "limit": limit
    })