import os, time, hmac, hashlib, base64
from fastapi import FastAPI, HTTPException, UploadFile, Header, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from .db import async_session, init_db
from .models import Tenant, Agent, Policy, Approval, ToolCall
from .signer import sign_payload

app = FastAPI(title="Agent Sandbox Control Plane")
app.mount("/static", StaticFiles(directory="control_plane/static"), name="static")
templates = Jinja2Templates(directory="control_plane/templates")
TENANT_SECRET = os.getenv("CP_TENANT_SECRET","devsecret")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("pages/homepage.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("pages/dashboard.html", {"request": request})

@app.get("/user-dashboard", response_class=HTMLResponse)
async def user_dashboard_page(request: Request):
    return templates.TemplateResponse("user_dashboard.html", {"request": request})

@app.get("/demo", response_class=HTMLResponse)  
async def demo_page(request: Request):
    return templates.TemplateResponse("pages/demo.html", {"request": request})

@app.get("/api/info")
async def api_info():
    return {"message": "Agent Sandbox Control Plane", "version": "0.1.0", "docs": "/docs", "approvals": "/approvals"}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/api/v1/health")
async def api_health():
    return {"ok": True, "status": "healthy", "service": "canopyiq-api"}

@app.get("/favicon.ico")
async def favicon():
    return {"status": "no favicon"}

class TenantIn(BaseModel):
    name: str

@app.post("/v1/tenants")
async def create_tenant(body: TenantIn):
    async with async_session() as s:
        t = Tenant(name=body.name)
        s.add(t); await s.commit(); await s.refresh(t)
        return {"id": t.id, "name": t.name}

class AgentIn(BaseModel):
    agent_id: str
    api_key: str

@app.post("/v1/tenants/{tenant_id}/agents")
async def create_agent(tenant_id: int, body: AgentIn):
    async with async_session() as s:
        a = Agent(tenant_id=tenant_id, agent_id=body.agent_id)
        a.set_api_key(body.api_key)
        s.add(a); await s.commit(); await s.refresh(a)
        return {"id": a.id, "agent_id": a.agent_id}

# Upload YAML policy (signed & stored)
@app.put("/v1/policies/{agent_id}", response_class=JSONResponse)
async def put_policy(agent_id: str, request: Request, x_agent_key: str = Header(None)):
    yaml_bytes = await request.body()
    if not yaml_bytes:
        raise HTTPException(400, "Empty body")
    async with async_session() as s:
        res = await s.execute(select(Agent).where(Agent.agent_id==agent_id))
        agent = res.scalar_one_or_none()
        if not agent: raise HTTPException(404,"Agent not found")
        # simple auth: require agent's api key for now
        if x_agent_key and not agent.verify_api_key(x_agent_key):
            raise HTTPException(401,"Invalid API key")

        bundle = {"agent_id": agent_id, "yaml": yaml_bytes.decode("utf-8"), "ts": int(time.time())}
        signature = sign_payload(bundle, TENANT_SECRET)
        p = Policy(agent_id=agent.id, yaml=bundle["yaml"], json_bundle=bundle, signature=signature)
        s.add(p); await s.commit(); await s.refresh(p)
        return {"policy_id": p.id, "signature": signature}

# Fetch latest signed policy bundle
@app.get("/v1/policies/{agent_id}", response_class=JSONResponse)
async def get_policy(agent_id: str, x_agent_key: str = Header(None)):
    async with async_session() as s:
        res = await s.execute(select(Agent).where(Agent.agent_id==agent_id))
        agent = res.scalar_one_or_none()
        if not agent: raise HTTPException(404,"Agent not found")
        if not x_agent_key or not agent.verify_api_key(x_agent_key):
            raise HTTPException(401,"Invalid API key")

        res = await s.execute(
            select(Policy).where(Policy.agent_id==agent.id).order_by(Policy.created_at.desc())
        )
        pol = res.scalars().first()
        if not pol: raise HTTPException(404,"No policy")
        return {"bundle": pol.json_bundle, "signature": pol.signature}

# Approvals API (SDK posts a pending approval)
class ApprovalIn(BaseModel):
    agent_id: str
    tool: str
    params_hash: str
    payload_redacted: dict | None = None

@app.post("/v1/approvals")
async def create_approval(a: ApprovalIn):
    async with async_session() as s:
        res = await s.execute(select(Agent).where(Agent.agent_id==a.agent_id))
        agent = res.scalar_one_or_none()
        if not agent: raise HTTPException(404,"Agent not found")
        appr = Approval(agent_id=agent.id, tool=a.tool, params_hash=a.params_hash,
                        status="pending", payload_redacted=a.payload_redacted)
        s.add(appr); await s.commit(); await s.refresh(appr)
        return {"id": appr.id, "status": appr.status}

@app.post("/v1/approvals/{approval_id}/decision")
async def decide_approval(approval_id: int, decision: str = Form(...)):
    if decision not in ("approve","deny"):
        raise HTTPException(400,"decision must be approve|deny")
    async with async_session() as s:
        res = await s.execute(select(Approval).where(Approval.id==approval_id))
        appr = res.scalar_one_or_none()
        if not appr: raise HTTPException(404,"Not found")
        appr.status = "approved" if decision=="approve" else "denied"
        await s.commit()
        return {"id": appr.id, "status": appr.status}

# Simple HTML UI for reviewers
@app.get("/approvals", response_class=HTMLResponse)
async def approvals_page(request: Request):
    async with async_session() as s:
        # Join with agent to get data in one query
        res = await s.execute(
            select(Approval.id, Approval.tool, Approval.status, Approval.params_hash, 
                   Approval.created_at, Agent.agent_id)
            .join(Agent)
            .order_by(Approval.created_at.desc())
        )
        rows = res.all()
        
        # Convert to simple dict for template
        approvals_data = [
            {
                "id": row.id,
                "agent_id": row.agent_id,
                "tool": row.tool,
                "status": row.status,
                "params_hash": row.params_hash,
                "created_at": row.created_at
            }
            for row in rows
        ]
        
        return templates.TemplateResponse("approvals.html", {"request": request, "rows": approvals_data})

# Audit export (time range in epoch seconds)  
@app.get("/v1/audit/export", response_class=JSONResponse)
async def audit_export(frm: int = 0, to: int = 9999999999):
    async with async_session() as s:
        # Join with agent to get data in one query
        res = await s.execute(
            select(Approval.id, Approval.tool, Approval.status, Approval.created_at, 
                   Approval.params_hash, Agent.agent_id)
            .join(Agent)
            .where(Approval.created_at >= frm, Approval.created_at <= to)
            .order_by(Approval.created_at.desc())
        )
        rows = res.all()
        
        out = [
            {
                "id": r.id, 
                "agent_id": r.agent_id, 
                "tool": r.tool,
                "status": r.status, 
                "created_at": r.created_at, 
                "params_hash": r.params_hash
            }
            for r in rows
        ]
        return out

# Tool Call Logging API for MCP Server
class ToolCallIn(BaseModel):
    timestamp: str
    tool: str
    arguments: dict
    result: str
    status: str  # approved|denied
    source: str  # mcp-server, sdk, etc

@app.post("/api/v1/logs/tool-calls")
async def log_tool_call(body: ToolCallIn, x_agent_key: str = Header(None)):
    async with async_session() as s:
        # Try to find agent by API key if provided
        agent_id = None
        if x_agent_key:
            res = await s.execute(select(Agent).where(Agent.api_key_hash.isnot(None)))
            agents = res.scalars().all()
            for agent in agents:
                if agent.verify_api_key(x_agent_key):
                    agent_id = agent.id
                    break
        
        # Create tool call log entry
        tool_call = ToolCall(
            agent_id=agent_id,
            timestamp=body.timestamp,
            tool=body.tool,
            arguments=body.arguments,
            result=body.result,
            status=body.status,
            source=body.source
        )
        s.add(tool_call)
        await s.commit()
        await s.refresh(tool_call)
        
        return {"id": tool_call.id, "status": "logged"}

# User Registration and Management
import secrets

class UserSignupIn(BaseModel):
    name: str
    email: str = None

@app.post("/api/v1/signup")
async def user_signup(body: UserSignupIn):
    """Create a new user with their own tenant and agent"""
    async with async_session() as s:
        # Create tenant for user
        tenant = Tenant(name=body.name)
        s.add(tenant)
        await s.commit()
        await s.refresh(tenant)
        
        # Generate API key
        api_key = f"ciq_user_{tenant.id}_{secrets.token_hex(12)}"
        
        # Create agent for user
        agent = Agent(tenant_id=tenant.id, agent_id=f"user_{tenant.id}_agent")
        agent.set_api_key(api_key)
        s.add(agent)
        await s.commit()
        await s.refresh(agent)
        
        return {
            "tenant_id": tenant.id,
            "agent_id": agent.agent_id,
            "api_key": api_key,
            "message": "Account created! Use this API key with canopyiq-mcp-server"
        }

# Helper function to get agent from API key
async def get_agent_from_key(api_key: str, session):
    if not api_key:
        return None
    res = await session.execute(select(Agent).where(Agent.api_key_hash.isnot(None)))
    agents = res.scalars().all()
    for agent in agents:
        if agent.verify_api_key(api_key):
            return agent
    return None

# User Dashboard - View their own data
@app.get("/api/v1/user/tool-calls")
async def get_user_tool_calls(x_agent_key: str = Header(None)):
    """Get tool calls for the authenticated user"""
    async with async_session() as s:
        agent = await get_agent_from_key(x_agent_key, s)
        if not agent:
            raise HTTPException(401, "Invalid API key")
        
        res = await s.execute(
            select(ToolCall).where(ToolCall.agent_id == agent.id).order_by(ToolCall.created_at.desc())
        )
        tool_calls = res.scalars().all()
        
        return [
            {
                "id": tc.id,
                "timestamp": tc.timestamp,
                "tool": tc.tool,
                "arguments": tc.arguments,
                "result": tc.result,
                "status": tc.status,
                "source": tc.source,
                "created_at": tc.created_at
            }
            for tc in tool_calls
        ]

@app.get("/api/v1/user/approvals")
async def get_user_approvals(x_agent_key: str = Header(None)):
    """Get approvals for the authenticated user"""
    async with async_session() as s:
        agent = await get_agent_from_key(x_agent_key, s)
        if not agent:
            raise HTTPException(401, "Invalid API key")
        
        res = await s.execute(
            select(Approval).where(Approval.agent_id == agent.id).order_by(Approval.created_at.desc())
        )
        approvals = res.scalars().all()
        
        return [
            {
                "id": a.id,
                "tool": a.tool,
                "params_hash": a.params_hash,
                "status": a.status,
                "payload_redacted": a.payload_redacted,
                "created_at": a.created_at
            }
            for a in approvals
        ]

# User Policy Management
@app.put("/api/v1/user/policy")
async def upload_user_policy(request: Request, x_agent_key: str = Header(None)):
    """Upload policy for authenticated user"""
    async with async_session() as s:
        agent = await get_agent_from_key(x_agent_key, s)
        if not agent:
            raise HTTPException(401, "Invalid API key")
        
        yaml_bytes = await request.body()
        if not yaml_bytes:
            raise HTTPException(400, "Empty body")
        
        bundle = {"agent_id": agent.agent_id, "yaml": yaml_bytes.decode("utf-8"), "ts": int(time.time())}
        signature = sign_payload(bundle, TENANT_SECRET)
        
        policy = Policy(agent_id=agent.id, yaml=bundle["yaml"], json_bundle=bundle, signature=signature)
        s.add(policy)
        await s.commit()
        await s.refresh(policy)
        
        return {"policy_id": policy.id, "signature": signature, "message": "Policy uploaded successfully"}

@app.get("/api/v1/user/policy")
async def get_user_policy(x_agent_key: str = Header(None)):
    """Get current policy for authenticated user"""
    async with async_session() as s:
        agent = await get_agent_from_key(x_agent_key, s)
        if not agent:
            raise HTTPException(401, "Invalid API key")
        
        res = await s.execute(
            select(Policy).where(Policy.agent_id == agent.id).order_by(Policy.created_at.desc())
        )
        policy = res.scalars().first()
        
        if not policy:
            return {"message": "No policy found"}
        
        return {"bundle": policy.json_bundle, "signature": policy.signature}

@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("pages/contact.html", {"request": request})
