from fastapi import FastAPI, Request, Form, status, Depends, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, constr
from pathlib import Path
import csv
import time
import secrets
import os
import uuid
import json
import logging
from datetime import datetime
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from starlette.responses import Response, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

# Import authentication modules  
from auth.oidc import oidc_client, init_oidc
# Import database
from database import get_db, Submission, AuditLog, Approval, ApprovalStatus, init_db, DATABASE_URL
# Import Slack utilities
from slack_utils import (
    send_slack_webhook, create_contact_notification, create_approval_notification,
    verify_slack_signature, parse_slack_payload, extract_approval_action, update_approval_message
)
from auth.rbac import (
    get_current_user, require_auth, require_role, require_admin, require_auditor,
    create_session_token, SESSION_COOKIE_NAME, SESSION_DURATION_HOURS
)
from auth.models import User
from auth.local import (
    create_local_user, authenticate_local_user, has_any_admin_users,
    db_user_to_auth_user, hash_password
)
from mcp_client import mcp_client
from tracing import canopy_tracing, MockTraceData
from company import company_manager
import secrets

ASSET_VER = "2025-08-20-1"  # bump on deploy

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'path']
)

contact_submissions_total = Counter(
    'contact_submissions_total',
    'Total contact form submissions'
)

auth_logins_total = Counter(
    'auth_logins_total',
    'Total authentication logins'
)

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timer
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency
        latency_seconds = time.time() - start_time
        latency_ms = round(latency_seconds * 1000, 2)
        
        # Get path template for metrics (avoid high cardinality)
        path = request.url.path
        if path.startswith('/static/'):
            path = '/static/*'
        elif path.startswith('/admin/') and path != '/admin':
            path = '/admin/*'
        
        # Update metrics
        http_requests_total.labels(
            method=request.method,
            path=path,
            status=response.status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            path=path
        ).observe(latency_seconds)
        
        # Get user info
        user = get_current_user(request)
        user_id = user.id if user else None
        
        # Structured logging
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
            "user_id": user_id,
            "user_agent": request.headers.get("user-agent", ""),
            "remote_addr": request.client.host if request.client else None
        }
        
        logger.info(json.dumps(log_data))
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp: Response = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Light CSP; adjust if you embed 3rd-party scripts
        resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com;"
        return resp

app = FastAPI(title="CanopyIQ - MCP Server for Claude Desktop")

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["GET","POST"], 
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/documentation", StaticFiles(directory="static/docs", html=True), name="documentation")
templates = Jinja2Templates(directory="templates")

# Add custom Jinja2 filters
def tojsonpretty(value):
    """Convert value to pretty-printed JSON"""
    if value is None:
        return "null"
    return json.dumps(value, indent=2, default=str)

templates.env.filters["tojsonpretty"] = tojsonpretty

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup - production safe"""
    logger.info("Starting CanopyIQ application...")
    
    # Skip all complex initialization for Railway deployment
    # Just log what we would do
    logger.info("Skipping database initialization for production deployment")
    logger.info("Skipping OIDC initialization for production deployment") 
    logger.info("Skipping tracing initialization for production deployment")
    logger.info("CanopyIQ application startup completed successfully")

# ---------- Helpers ----------
def page(request: Request, *, title: str, desc: str, path: str, **ctx):
    return templates.TemplateResponse(path, {
        "request": request,
        "meta": {"title": title, "desc": desc, "url_path": request.url.path},
        "asset_ver": ASSET_VER,
        "user": get_current_user(request),
        **ctx
    })

# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return page(
        request,
        title="Secure Claude Desktop with MCP Server | CanopyIQ",
        desc="Add security, approval workflows, and monitoring to Claude Desktop in 30 seconds. Official MCP server for Claude Code users.",
        path="home.html",
    )

@app.get("/product", response_class=HTMLResponse)
async def product(request: Request):
    return page(
        request,
        title="Product | CanopyIQ",
        desc="Runtime guardrails, approvals, cross-vendor policies, observability, and scale.",
        path="product.html",
    )

@app.get("/security", response_class=HTMLResponse)
async def security(request: Request):
    return page(
        request,
        title="Security & Compliance | CanopyIQ",
        desc="Security posture, data handling, redaction, signed policies, compliance packs.",
        path="security.html",
    )

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return page(
        request,
        title="Pricing | CanopyIQ",
        desc="Starter, Growth, and Enterprise tiers for agent fleets.",
        path="pricing.html",
    )

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return page(
        request,
        title="Contact / Book a Demo | CanopyIQ",
        desc="Talk to us about running AI agents safely at scale.",
        path="contact.html",
    )

class ContactIn(BaseModel):
    name: constr(strip_whitespace=True, min_length=2)
    email: EmailStr
    company: constr(strip_whitespace=True, min_length=2)
    message: constr(strip_whitespace=True, min_length=5)

class ApprovalRequest(BaseModel):
    action: constr(strip_whitespace=True, min_length=1)
    payload: dict = {}

DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "contact_submissions.csv"

@app.post("/contact")
async def submit_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(...),
    message: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Validate
    try:
        ContactIn(name=name, email=email, company=company, message=message)
    except Exception:
        return RedirectResponse(url="/contact?error=invalid", status_code=status.HTTP_302_FOUND)

    # Create submission record
    submission = Submission(
        ts=int(time.time()),
        name=name.strip(),
        email=email.strip(),
        company=company.strip(),
        message=message.strip(),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")
    )
    
    db.add(submission)
    await db.commit()
    await db.refresh(submission)  # Get the ID after commit

    # Send Slack notification
    slack_message = create_contact_notification(
        name=submission.name,
        email=submission.email,
        company=submission.company,
        message=submission.message,
        submission_id=submission.id
    )
    await send_slack_webhook(slack_message)

    # Track contact submission metric
    contact_submissions_total.inc()

    return RedirectResponse(url="/contact?success=1", status_code=status.HTTP_302_FOUND)

# ---------- Setup Routes ----------
@app.get("/setup")
async def setup_wizard(request: Request, db: AsyncSession = Depends(get_db)):
    """First-run setup wizard"""
    # Check if admin users already exist
    if await has_any_admin_users(db):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("setup_wizard.html", {
        "request": request,
        "step": 1,
        "form_data": {},
        "error": None
    })

@app.post("/setup")
async def setup_wizard_post(
    request: Request,
    step: int = Form(...),
    db: AsyncSession = Depends(get_db),
    # Step 1 fields
    name: str = Form(None),
    email: str = Form(None),
    password: str = Form(None),
    confirm_password: str = Form(None),
    # Step 2 fields  
    site_title: str = Form(None),
    base_url: str = Form(None),
    slack_webhook_url: str = Form(None),
    # Skip flag
    skip: bool = Form(False)
):
    """Handle setup wizard form submissions"""
    
    # Check if admin users already exist (except during setup)
    if await has_any_admin_users(db) and step == 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    if step == 1:
        # Validate step 1 - Create admin account
        form_data = {"name": name, "email": email}
        error = None
        
        if not name or not email or not password or not confirm_password:
            error = "All fields are required"
        elif len(password) < 8:
            error = "Password must be at least 8 characters long"
        elif password != confirm_password:
            error = "Passwords do not match"
        else:
            # Check if email already exists
            from database import User as DBUser
            result = await db.execute(select(DBUser).where(DBUser.email == email))
            if result.scalar_one_or_none():
                error = "An account with this email already exists"
        
        if error:
            return templates.TemplateResponse("setup_wizard.html", {
                "request": request,
                "step": 1,
                "form_data": form_data,
                "error": error
            })
        
        # Create admin user
        try:
            from database import UserRole
            await create_local_user(db, email, name, password, UserRole.ADMIN)
            
            # Log the account creation
            audit_log = AuditLog(
                ts=int(time.time()),
                actor=email,
                action="CREATE_ADMIN_ACCOUNT",
                resource="user:admin",
                attributes={
                    "setup_wizard": True,
                    "auth_provider": "local"
                }
            )
            db.add(audit_log)
            await db.commit()
            
            # Move to step 2
            return templates.TemplateResponse("setup_wizard.html", {
                "request": request,
                "step": 2,
                "form_data": {"site_title": "CanopyIQ", "base_url": "http://localhost:8080"},
                "error": None
            })
            
        except Exception as e:
            return templates.TemplateResponse("setup_wizard.html", {
                "request": request,
                "step": 1,
                "form_data": form_data,
                "error": f"Failed to create admin account: {str(e)}"
            })
    
    elif step == 2 or skip:
        # Step 2 - Basic settings (or skip)
        if not skip:
            # Save basic settings - for now just log them
            audit_log = AuditLog(
                ts=int(time.time()),
                actor="setup_wizard",
                action="UPDATE_INITIAL_SETTINGS",
                resource="settings:initial",
                attributes={
                    "site_title": site_title or "CanopyIQ",
                    "base_url": base_url or "http://localhost:8080",
                    "slack_webhook_url": slack_webhook_url or "",
                    "skipped": False
                }
            )
            db.add(audit_log)
            await db.commit()
        
        # Get admin email for display
        from database import User as DBUser, UserRole
        result = await db.execute(
            select(DBUser).where(DBUser.role == UserRole.ADMIN).limit(1)
        )
        admin_user = result.scalar_one_or_none()
        admin_email = admin_user.email if admin_user else "admin@example.com"
        
        # Complete setup
        return templates.TemplateResponse("setup_wizard.html", {
            "request": request,
            "step": 3,
            "admin_email": admin_email,
            "error": None
        })
    
    else:
        return RedirectResponse(url="/setup", status_code=status.HTTP_302_FOUND)

# ---------- Local Authentication Routes ----------
@app.get("/auth/local/login")
async def local_login_page(request: Request, error: str = None):
    """Local login page"""
    return templates.TemplateResponse("local_login.html", {
        "request": request,
        "error": error
    })

@app.post("/auth/local/login")
async def local_login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle local login form submission"""
    # Authenticate user
    db_user = await authenticate_local_user(db, email, password)
    
    if not db_user:
        return RedirectResponse(
            url="/auth/local/login?error=invalid", 
            status_code=status.HTTP_302_FOUND
        )
    
    # Convert to auth user and create session
    auth_user = db_user_to_auth_user(db_user)
    session_token = create_session_token(auth_user)
    
    # Create response and set session cookie
    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_DURATION_HOURS * 3600,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    # Track login metric
    auth_logins_total.inc()
    
    return response

# ---------- Authentication Routes ----------
@app.get("/auth/login")
async def auth_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Redirect to appropriate authentication method"""
    # Check if any admin users exist - if not, redirect to setup
    if not await has_any_admin_users(db):
        return RedirectResponse(url="/setup", status_code=status.HTTP_302_FOUND)
    
    # If OIDC is configured, use that
    if oidc_client.is_configured():
        # OIDC authentication flow
        pass  # Continue with existing OIDC logic below
    else:
        # Use local authentication
        return RedirectResponse(url="/auth/local/login", status_code=status.HTTP_302_FOUND)
    
    # Original OIDC logic
    if not oidc_client.is_configured():
        raise HTTPException(status_code=503, detail="Authentication not configured")
    
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)
    auth_url = oidc_client.get_authorization_url(state)
    
    # Store state in session for verification
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="auth_state",
        value=state,
        max_age=600,  # 10 minutes
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return response

@app.get("/auth/oidc/callback")
async def auth_callback(request: Request, code: str, state: str):
    """Handle OIDC callback and create user session"""
    if not oidc_client.is_configured():
        raise HTTPException(status_code=503, detail="Authentication not configured")
    
    # Verify CSRF state
    stored_state = request.cookies.get("auth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    try:
        # Exchange authorization code for tokens
        tokens = await oidc_client.exchange_code(code, state)
        
        # Verify ID token and extract claims
        claims = oidc_client.verify_id_token(tokens.id_token)
        
        # Create user from claims with company context
        user = company_manager.create_company_user(claims)
        
        # Create session token
        session_token = create_session_token(user)
        
        # Redirect to home with session cookie
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            max_age=SESSION_DURATION_HOURS * 3600,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        
        # Clear auth state cookie
        response.delete_cookie("auth_state")
        
        # Track successful login metric
        auth_logins_total.inc()
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@app.get("/auth/logout")
async def auth_logout(request: Request):
    """Log out user and clear session"""
    # Get logout URL from provider if available
    logout_url = None
    if oidc_client.is_configured():
        logout_url = oidc_client.get_logout_url(redirect_url=str(request.base_url))
    
    # Clear session cookie and redirect
    if logout_url:
        response = RedirectResponse(url=logout_url, status_code=status.HTTP_302_FOUND)
    else:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response

# ---------- Admin Routes (Protected) ----------
@app.get("/admin/contacts", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_contacts(request: Request, db: AsyncSession = Depends(get_db)):
    """View contact submissions (admin only)"""
    # Get last 50 submissions, newest first
    result = await db.execute(
        select(Submission)
        .order_by(desc(Submission.ts))
        .limit(50)
    )
    submissions = result.scalars().all()
    
    # Format for template
    contacts = []
    for submission in submissions:
        contacts.append({
            "id": submission.id,
            "timestamp": datetime.fromtimestamp(submission.ts).strftime("%Y-%m-%d %H:%M:%S"),
            "name": submission.name,
            "email": submission.email,
            "company": submission.company,
            "message": submission.message,
            "source_ip": submission.source_ip,
            "user_agent": submission.user_agent
        })
    
    return page(
        request,
        title="Contact Submissions | Admin | CanopyIQ",
        desc="Manage contact form submissions.",
        path="admin_contacts.html",
        contacts=contacts
    )

@app.get("/admin/submissions", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_submissions(request: Request, db: AsyncSession = Depends(get_db)):
    """View recent submissions (admin only)"""
    
    # Get last 50 submissions, newest first
    result = await db.execute(
        select(Submission)
        .order_by(desc(Submission.ts))
        .limit(50)
    )
    submissions = result.scalars().all()
    
    # Format for simple display
    submissions_list = []
    for submission in submissions:
        submissions_list.append({
            "id": submission.id,
            "timestamp": datetime.fromtimestamp(submission.ts).strftime("%Y-%m-%d %H:%M:%S"),
            "name": submission.name,
            "email": submission.email,
            "company": submission.company,
            "message": submission.message[:100] + "..." if len(submission.message) > 100 else submission.message,
            "source_ip": submission.source_ip,
        })
    
    return page(
        request,
        title="Recent Submissions | CanopyIQ",
        desc="Recent contact form submissions.",
        path="admin_submissions.html",
        submissions=submissions_list
    )

@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Admin dashboard"""
    # user is already injected from dependency
    
    # Get dashboard statistics
    now = int(time.time())
    twenty_four_hours_ago = now - 86400
    
    # Submissions in last 24h
    submissions_24h_result = await db.execute(
        select(Submission).where(Submission.ts >= twenty_four_hours_ago)
    )
    submissions_24h = submissions_24h_result.scalars().all()
    
    # Get last submission
    last_submission_result = await db.execute(
        select(Submission).order_by(desc(Submission.ts)).limit(1)
    )
    last_submission = last_submission_result.scalar_one_or_none()
    
    # Recent audit activity
    recent_audit_result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.ts)).limit(10)
    )
    recent_logs = recent_audit_result.scalars().all()
    
    # Format recent activity
    recent_activity = []
    for log in recent_logs:
        activity = {
            "type": "audit",
            "description": f"{log.action} by {log.actor}",
            "timestamp": datetime.fromtimestamp(log.ts).strftime("%Y-%m-%d %H:%M:%S"),
            "actor": log.actor
        }
        recent_activity.append(activity)
    
    stats = {
        "submissions_24h": len(submissions_24h),
        "last_submission": datetime.fromtimestamp(last_submission.ts).strftime("%Y-%m-%d %H:%M:%S") if last_submission else None,
        "logins_24h": 0,  # TODO: Implement login tracking
        "db_type": "SQLite" if "sqlite" in DATABASE_URL else "PostgreSQL",
        "total_submissions": len(submissions_24h),  # TODO: Get actual total
        "oidc_enabled": False,  # TODO: Check OIDC status
        "active_sessions": 0,  # TODO: Count active sessions
    }
    
    return page(
        request,
        title="Admin Dashboard | CanopyIQ",
        desc="Administration panel for CanopyIQ.",
        path="admin_dashboard.html",
        user=user,
        stats=stats,
        recent_activity=recent_activity
    )

@app.get("/admin/audit", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_audit(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin audit log viewer"""
    # Get last 100 audit logs
    result = await db.execute(
        select(AuditLog)
        .order_by(desc(AuditLog.ts))
        .limit(100)
    )
    audit_logs = result.scalars().all()
    
    # Format for template
    formatted_logs = []
    for log in audit_logs:
        formatted_log = {
            "id": log.id,
            "ts": log.ts,
            "formatted_timestamp": datetime.fromtimestamp(log.ts).strftime("%Y-%m-%d %H:%M:%S"),
            "actor": log.actor,
            "action": log.action,
            "resource": log.resource,
            "attributes": log.attributes,
            "get_risk_level": lambda: "low"  # Simple risk assessment
        }
        formatted_logs.append(formatted_log)
    
    # Audit statistics
    audit_stats = {
        "total_events": len(formatted_logs),
        "failed_logins": 0,  # TODO: Count failed login attempts
        "admin_actions": len([log for log in formatted_logs if "admin" in log["actor"].lower()]),
        "high_risk_events": 0,  # TODO: Implement risk assessment
    }
    
    return page(
        request,
        title="Audit Log | Admin | CanopyIQ",
        desc="Security and activity audit trail.",
        path="admin_audit.html",
        audit_logs=formatted_logs,
        audit_stats=audit_stats,
        security_alerts=[],  # TODO: Implement security alerts
        total_logs=len(formatted_logs)
    )

@app.get("/admin/settings", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_settings(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin settings page"""
    # Get current settings from database or environment
    settings = {
        "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
        "slack_signing_secret": os.getenv("SLACK_SIGNING_SECRET", ""),
        "site_title": "CanopyIQ",
        "site_description": "Run AI agents safely. At scale.",
        "base_url": os.getenv("BASE_URL", "http://localhost:8080"),
        "oidc_issuer": os.getenv("OIDC_ISSUER", ""),
        "db_type": "SQLite" if "sqlite" in DATABASE_URL else "PostgreSQL"
    }
    
    return page(
        request,
        title="Settings | Admin | CanopyIQ", 
        desc="Configure your CanopyIQ system.",
        path="admin_settings.html",
        settings=settings
    )

@app.post("/admin/settings/slack", dependencies=[Depends(require_admin)])
async def update_slack_settings(
    request: Request,
    slack_webhook_url: str = Form(None),
    slack_signing_secret: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Update Slack configuration settings"""
    user = get_current_user(request)
    actor = user.email if user else "admin"
    
    # Log the configuration change
    audit_log = AuditLog(
        ts=int(time.time()),
        actor=actor,
        action="UPDATE_SLACK_SETTINGS",
        resource="settings:slack",
        attributes={
            "webhook_url_set": bool(slack_webhook_url),
            "signing_secret_set": bool(slack_signing_secret)
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return RedirectResponse(url="/admin/settings?success=slack", status_code=status.HTTP_302_FOUND)

@app.post("/admin/settings/branding", dependencies=[Depends(require_admin)])
async def update_branding_settings(
    request: Request,
    site_title: str = Form(...),
    site_description: str = Form(...),
    base_url: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Update branding settings"""
    user = get_current_user(request)
    actor = user.email if user else "admin"
    
    # Log the configuration change
    audit_log = AuditLog(
        ts=int(time.time()),
        actor=actor,
        action="UPDATE_BRANDING_SETTINGS",
        resource="settings:branding",
        attributes={
            "site_title": site_title,
            "site_description": site_description,
            "base_url": base_url
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return RedirectResponse(url="/admin/settings?success=branding", status_code=status.HTTP_302_FOUND)

@app.post("/admin/test-slack", dependencies=[Depends(require_admin)])
async def test_slack_connection(
    request: Request,
    webhook_url: str = Form(...),
    message: str = Form(...)
):
    """Test Slack webhook connection"""
    try:
        # Simple test message
        test_payload = {
            "text": f"🧪 Test from CanopyIQ Admin: {message}",
            "username": "CanopyIQ Admin",
            "icon_emoji": ":robot_face:"
        }
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=test_payload) as response:
                if response.status == 200:
                    return {"status": "success", "message": "Test message sent successfully"}
                else:
                    return {"status": "error", "message": f"HTTP {response.status}"}
                    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Slack test failed: {str(e)}")

@app.get("/admin/submissions/export", dependencies=[Depends(require_admin)])
async def export_submissions(request: Request, db: AsyncSession = Depends(get_db)):
    """Export submissions as CSV"""
    result = await db.execute(
        select(Submission).order_by(desc(Submission.ts))
    )
    submissions = result.scalars().all()
    
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # CSV headers
    writer.writerow(['ID', 'Timestamp', 'Name', 'Email', 'Company', 'Message', 'Source IP', 'User Agent'])
    
    # CSV rows
    for submission in submissions:
        writer.writerow([
            submission.id,
            datetime.fromtimestamp(submission.ts).isoformat(),
            submission.name,
            submission.email,
            submission.company,
            submission.message,
            submission.source_ip or '',
            submission.user_agent or ''
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions.csv"}
    )

@app.post("/admin/audit/export", dependencies=[Depends(require_admin)])
async def export_audit_log(request: Request, db: AsyncSession = Depends(get_db)):
    """Export audit log as CSV"""
    result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.ts))
    )
    audit_logs = result.scalars().all()
    
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # CSV headers
    writer.writerow(['ID', 'Timestamp', 'Actor', 'Action', 'Resource', 'Attributes'])
    
    # CSV rows  
    for log in audit_logs:
        writer.writerow([
            log.id,
            datetime.fromtimestamp(log.ts).isoformat(),
            log.actor,
            log.action,
            log.resource,
            json.dumps(log.attributes) if log.attributes else ''
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"}
    )

# ---------- API Routes ----------
@app.post("/api/approvals", dependencies=[Depends(require_admin)])
async def create_approval(
    request: Request,
    approval_request: ApprovalRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new approval request (admin only)"""
    # Get current user (from auth system or placeholder)
    user = get_current_user(request)
    actor = user.email if user else "system"
    
    # Create approval record
    approval = Approval(
        actor=actor,
        action=approval_request.action,
        status=ApprovalStatus.PENDING,
        payload=approval_request.payload
    )
    
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    
    # Send Slack notification with interactive buttons
    slack_message = create_approval_notification(
        approval_id=approval.id,
        actor=actor,
        action=approval.action,
        payload=approval_request.payload
    )
    await send_slack_webhook(slack_message)
    
    # Log to audit trail
    audit_log = AuditLog(
        ts=int(time.time()),
        actor=actor,
        action="CREATE_APPROVAL",
        resource=f"approval:{approval.id}",
        attributes={
            "approval_action": approval.action,
            "payload": approval_request.payload
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return {
        "id": approval.id,
        "status": approval.status.value,
        "created_at": approval.created_at.isoformat(),
        "message": "Approval request created and Slack notification sent"
    }

@app.post("/slack/interactive")
async def slack_interactive_handler(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Slack interactive button clicks"""
    # Get raw body for signature verification
    body = await request.body()
    body_str = body.decode('utf-8')
    
    # Verify Slack signature for security
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not verify_slack_signature(body_str, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")
    
    # Parse form data
    form_data = {}
    for line in body_str.split('&'):
        if '=' in line:
            key, value = line.split('=', 1)
            # URL decode the values
            import urllib.parse
            form_data[urllib.parse.unquote_plus(key)] = urllib.parse.unquote_plus(value)
    
    # Parse Slack payload
    payload = parse_slack_payload(form_data)
    
    # Extract approval action
    action_type, approval_id = extract_approval_action(payload)
    
    # Get the approval from database
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval.status != ApprovalStatus.PENDING:
        return {"text": f"Approval #{approval_id} has already been {approval.status.value}"}
    
    # Get user info from Slack payload
    user = payload.get("user", {})
    slack_user_id = user.get("id", "unknown")
    slack_user_name = user.get("name", user.get("username", "unknown"))
    approver = f"{slack_user_name} ({slack_user_id})"
    
    # Update approval status
    new_status = ApprovalStatus.APPROVED if action_type == "approve" else ApprovalStatus.DENIED
    approval.status = new_status
    approval.approved_by = approver
    approval.approved_at = datetime.utcnow()
    
    await db.commit()
    
    # Log to audit trail
    audit_log = AuditLog(
        ts=int(time.time()),
        actor=approver,
        action=f"{action_type.upper()}_APPROVAL",
        resource=f"approval:{approval.id}",
        attributes={
            "original_actor": approval.actor,
            "approval_action": approval.action,
            "slack_user": slack_user_name,
            "slack_user_id": slack_user_id
        }
    )
    db.add(audit_log)
    await db.commit()
    
    # Update the original Slack message
    response_url = payload.get("response_url")
    if response_url:
        await update_approval_message(response_url, approval_id, new_status.value, approver)
    
    return {
        "text": f"Approval #{approval_id} has been {new_status.value} by {approver}",
        "response_type": "ephemeral"
    }

@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    return page(request, title="FAQ | CanopyIQ", desc="Frequently asked questions about CanopyIQ's AI agent security platform.", path="faq.html")

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return page(request, title="Privacy Policy | CanopyIQ", desc="Our commitment to protecting your privacy and data.", path="privacy.html")

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return page(request, title="Terms of Service | CanopyIQ", desc="Terms and conditions for using CanopyIQ's services.", path="terms.html")

@app.get("/legal/privacy", response_class=HTMLResponse)
async def privacy_legacy(request: Request):
    return page(request, title="Privacy Policy | CanopyIQ", desc="Our commitment to protecting your privacy and data.", path="privacy.html")

@app.get("/legal/terms", response_class=HTMLResponse)
async def terms_legacy(request: Request):
    return page(request, title="Terms of Service | CanopyIQ", desc="Terms and conditions for using CanopyIQ's services.", path="terms.html")

@app.get("/health")
async def health():
    return {"ok": True}

# ---------- Observability Endpoints ----------
@app.get("/healthz")
async def liveness():
    """Liveness probe - returns OK if the service is running"""
    return {"status": "ok"}

@app.get("/readyz")
async def readiness():
    """Readiness probe - checks if service is ready to handle requests"""
    try:
        # Check if OIDC is configured (if environment variables are set)
        if oidc_client.config:
            # Service is configured for OIDC
            if not oidc_client.is_configured():
                raise HTTPException(status_code=503, detail="OIDC not ready")
        
        # Check if templates directory exists
        if not Path("templates").exists():
            raise HTTPException(status_code=503, detail="Templates not found")
        
        # Check if static files are available
        if not Path("static").exists():
            raise HTTPException(status_code=503, detail="Static files not found")
        
        return {"status": "ready", "checks": {"oidc": "ok", "templates": "ok", "static": "ok"}}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ---------- Console Routes ----------
@app.get("/admin/console", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def console_index(request: Request):
    """Console landing page"""
    return page(
        request,
        title="Console | CanopyIQ",
        desc="CanopyIQ Console - Run agents safely. At scale.",
        path="console/index.html"
    )

@app.get("/admin/console/access", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def console_access(request: Request, tenant: str = "demo-tenant"):
    """Access Dashboard - tool permissions overview"""
    
    # Define tool probes to simulate
    tools = [
        {
            "name": "net.http",
            "label": "HTTP Requests", 
            "icon": "🌐",
            "probe": {
                "tool": "net.http",
                "arguments": {
                    "method": "GET",
                    "url": "https://intranet.api/health"
                }
            }
        },
        {
            "name": "fs.write",
            "label": "File Write",
            "icon": "📁", 
            "probe": {
                "tool": "fs.write",
                "arguments": {
                    "path": "/etc/passwd",
                    "bytes": "Zm9v"
                }
            }
        },
        {
            "name": "cloud.ops",
            "label": "Cloud Operations",
            "icon": "☁️",
            "probe": {
                "tool": "cloud.ops", 
                "arguments": {
                    "provider": "aws",
                    "resource": "ec2",
                    "action": "run_instances",
                    "estimated_cost_usd": 12.0
                }
            }
        },
        {
            "name": "mail.send",
            "label": "Email Send",
            "icon": "📧",
            "probe": {
                "tool": "mail.send",
                "arguments": {
                    "to": "user@external.com",
                    "subject": "Test message"
                }
            }
        }
    ]
    
    # Simulate policy decisions for each tool
    enriched_tools = []
    for tool in tools:
        try:
            # Start tracing span for policy simulation
            with canopy_tracing.tracer.start_as_current_span("console.policy.simulate") as span:
                span.set_attributes({
                    "canopy.tool": tool["name"],
                    "canopy.tenant": tenant
                })
                
                # Call MCP policy simulator
                result = mcp_client.simulate_policy(tool["probe"])
                decision = result.get("decision", "deny")
                trace = result.get("trace", {})
                
                # Record decision in span
                span.set_attribute("canopy.decision", decision)
                
                # Map decision to status and styling
                if decision == "allow":
                    status = "Allowed"
                    status_class = "bg-green-500/20 text-green-400"
                elif decision == "approval":
                    status = "Approval"
                    status_class = "bg-amber-500/20 text-amber-400"
                else:
                    status = "Blocked"
                    status_class = "bg-red-500/20 text-red-400"
                
                # Extract explanation from trace
                explain = "Policy evaluated"
                if trace.get("matched_rule"):
                    explain = trace["matched_rule"].get("reason", explain)
                    span.set_attribute("canopy.matched_rule", trace["matched_rule"].get("name", "unknown"))
                
                tool_data = {
                    **tool,
                    "status": status,
                    "status_class": status_class,
                    "explain": explain,
                    "decision": decision
                }
            
        except Exception as e:
            # Fallback on simulator error
            tool_data = {
                **tool,
                "status": "Unknown",
                "status_class": "bg-slate-500/20 text-slate-400",
                "explain": f"Simulator error: {str(e)}",
                "decision": "error"
            }
        
        enriched_tools.append(tool_data)
    
    return page(
        request,
        title="Access Dashboard | Console | CanopyIQ", 
        desc="View tool access permissions and policy decisions.",
        path="console/access.html",
        tenant=tenant,
        tools=enriched_tools
    )

@app.get("/admin/console/approvals", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def console_approvals(request: Request, tenant: str = "", status: str = "pending", limit: int = 50):
    """Approvals Queue - pending approval requests"""
    
    # Get approval items from MCP
    try:
        result = mcp_client.list_approvals(tenant=tenant, status=status, limit=limit)
        approvals = result.get("items", [])
        
        # Format approvals for template
        formatted_approvals = []
        for approval in approvals:
            # Format timestamps
            created_at = approval.get("created_at", "")
            if created_at:
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_display = dt.strftime('%Y-%m-%d %H:%M:%S')
                    time_ago = "Just now"  # Simple placeholder
                except:
                    created_display = created_at
                    time_ago = "Unknown"
            else:
                created_display = "Unknown"
                time_ago = "Unknown"
            
            formatted_approval = {
                "id": approval.get("id", "unknown"),
                "tool": approval.get("tool", "unknown"),
                "tenant": approval.get("tenant", tenant or "default"),
                "requester": approval.get("requester", "system"),
                "action": approval.get("action", "unknown action"),
                "status": approval.get("status", "pending"),
                "created_at": created_display,
                "time_ago": time_ago,
                "payload": approval.get("payload", {}),
                "arguments": approval.get("arguments", {})
            }
            formatted_approvals.append(formatted_approval)
    
    except Exception as e:
        formatted_approvals = []
        error_message = f"Unable to load approvals: {str(e)}"
    else:
        error_message = None
    
    return page(
        request,
        title="Approvals Queue | Console | CanopyIQ",
        desc="View and manage pending approval requests.", 
        path="console/approvals.html",
        tenant=tenant,
        status=status,
        limit=limit,
        approvals=formatted_approvals,
        error_message=error_message
    )

@app.post("/admin/console/approvals/decide", dependencies=[Depends(require_admin)])
async def console_approval_decide(
    request: Request,
    pending_id: str = Form(...),
    decision: str = Form(...)
):
    """Handle approval decisions from console"""
    
    # Validate decision
    if decision not in ["approve", "deny"]:
        raise HTTPException(status_code=400, detail="Invalid decision")
    
    try:
        # For MVP, we'll simulate the decision since we don't have direct MCP callback access
        # In a real implementation, this would call the MCP approval callback endpoint
        
        # Get the current user for audit purposes
        user = get_current_user(request)
        approver = user.email if user else "console-user"
        
        # Flash a message about the decision
        message = f"Approval {pending_id} has been {decision}d by {approver}"
        
        # Redirect back to approvals with success message
        return RedirectResponse(
            url=f"/console/approvals?success={decision}&id={pending_id}", 
            status_code=status.HTTP_302_FOUND
        )
        
    except Exception as e:
        # Redirect with error
        return RedirectResponse(
            url=f"/admin/console/approvals?error=decision_failed&detail={str(e)}", 
            status_code=status.HTTP_302_FOUND
        )

@app.get("/admin/console/simulator", response_class=HTMLResponse, dependencies=[Depends(require_admin)]) 
async def console_simulator(request: Request):
    """Policy Simulator - test tool calls against policies"""
    return page(
        request,
        title="Policy Simulator | Console | CanopyIQ",
        desc="Test tool calls against current policies.",
        path="console/simulator.html"
    )

@app.post("/console/simulator", response_class=HTMLResponse)
async def console_simulator_post(
    request: Request,
    tool: str = Form(...),
    arguments: str = Form(...)
):
    """Handle policy simulator form submission"""
    
    try:
        # Parse JSON arguments
        import json
        try:
            parsed_args = json.loads(arguments)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in arguments: {str(e)}")
        
        # Build simulation request
        simulation_request = {
            "tool": tool,
            "arguments": parsed_args
        }
        
        # Call MCP policy simulator
        result = mcp_client.simulate_policy(simulation_request)
        
        # Extract results
        decision = result.get("decision", "unknown")
        matched_rule = result.get("matched_rule", {})
        trace = result.get("trace", {})
        
        # Format for display
        simulation_result = {
            "success": True,
            "decision": decision,
            "rule_name": matched_rule.get("name", "Unknown rule"),
            "rule_reason": matched_rule.get("reason", "No reason provided"),
            "trace_data": trace,
            "request": simulation_request
        }
        
    except HTTPException:
        raise
    except Exception as e:
        simulation_result = {
            "success": False,
            "error": str(e),
            "request": {"tool": tool, "arguments": arguments}
        }
    
    return page(
        request,
        title="Policy Simulator | Console | CanopyIQ",
        desc="Test tool calls against current policies.",
        path="console/simulator.html",
        result=simulation_result,
        tool=tool,
        arguments=arguments
    )

@app.get("/admin/console/traces", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def console_traces(request: Request):
    """Trace viewer and workflow analytics"""
    # Generate mock trace data for demo
    traces = MockTraceData.generate_traces(50)
    
    # Calculate summary stats
    total_traces = len(traces)
    successful_traces = len([t for t in traces if t["status"] == "success"])
    avg_duration = sum(t["duration_ms"] for t in traces) / total_traces if total_traces > 0 else 0
    total_cost = sum(t["total_cost_usd"] for t in traces)
    
    # Group by workflow type
    workflow_stats = {}
    for trace in traces:
        wf_type = trace["workflow_type"]
        if wf_type not in workflow_stats:
            workflow_stats[wf_type] = {"count": 0, "avg_duration": 0, "total_cost": 0}
        workflow_stats[wf_type]["count"] += 1
        workflow_stats[wf_type]["total_cost"] += trace["total_cost_usd"]
    
    # Calculate averages
    for wf_type in workflow_stats:
        wf_traces = [t for t in traces if t["workflow_type"] == wf_type]
        workflow_stats[wf_type]["avg_duration"] = sum(t["duration_ms"] for t in wf_traces) / len(wf_traces)
        workflow_stats[wf_type]["success_rate"] = len([t for t in wf_traces if t["status"] == "success"]) / len(wf_traces) * 100
    
    return page(
        request,
        title="Trace Analytics | Console | CanopyIQ",
        desc="Distributed tracing and workflow performance analytics.",
        path="console/traces.html",
        traces=traces[:20],  # Show latest 20
        stats={
            "total_traces": total_traces,
            "success_rate": round(successful_traces / total_traces * 100, 1) if total_traces > 0 else 0,
            "avg_duration_ms": round(avg_duration, 0),
            "total_cost_usd": round(total_cost, 2)
        },
        workflow_stats=workflow_stats
    )

@app.get("/admin/console/agents", response_class=HTMLResponse, dependencies=[Depends(require_admin)]) 
async def console_agents(request: Request):
    """Agent dependency map and performance analytics"""
    # Generate mock agent dependency data
    dependency_data = MockTraceData.generate_agent_dependency_map()
    
    return page(
        request,
        title="Agent Dependencies | Console | CanopyIQ",
        desc="Visualize agent-to-agent communication patterns and performance.",
        path="console/agents.html",
        agents=dependency_data["agents"],
        connections=dependency_data["connections"],
        generated_at=dependency_data["generated_at"]
    )

@app.get("/admin/console/policy", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def console_policy(request: Request):
    """Policy Diff & Rollout - upload and compare policies"""
    
    # Get policy status from MCP
    try:
        policy_status = mcp_client.policy_status()
        if policy_status.get("status") == "error":
            status_info = None
            status_error = policy_status.get("message")
        else:
            status_info = policy_status
            status_error = None
    except Exception as e:
        status_info = None
        status_error = f"Unable to fetch policy status: {str(e)}"
    
    return page(
        request,
        title="Policy Management | Console | CanopyIQ", 
        desc="Upload, diff, and rollout policy changes.",
        path="console/policy.html",
        policy_status=status_info,
        status_error=status_error
    )

@app.post("/admin/console/policy", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def console_policy_post(
    request: Request,
    current: UploadFile = File(None),
    proposed: UploadFile = File(...)
):
    """Handle policy diff form submission"""
    
    try:
        # Read proposed file
        proposed_content = await proposed.read()
        if not proposed_content:
            raise HTTPException(status_code=400, detail="Proposed policy file is empty")
        
        # Read current file (optional)
        current_content = None
        if current and current.filename:
            current_content = await current.read()
        
        # Call MCP diff API
        diff_result = mcp_client.diff_policy(current_content, proposed_content)
        
        # Format diff results for template
        formatted_diff = {
            "success": True,
            "headline": diff_result.get("headline", []),
            "added_rules": diff_result.get("added_rules", []),
            "removed_rules": diff_result.get("removed_rules", []),
            "modified_rules": diff_result.get("modified_rules", []),
            "risk_level": diff_result.get("risk_level", "medium"),
            "summary": diff_result.get("summary", "Policy changes detected")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        formatted_diff = {
            "success": False,
            "error": str(e)
        }
    
    # Get policy status again for display
    try:
        policy_status = mcp_client.policy_status()
        if policy_status.get("status") == "error":
            status_info = None
            status_error = policy_status.get("message")
        else:
            status_info = policy_status
            status_error = None
    except:
        status_info = None
        status_error = "Unable to fetch policy status"
    
    return page(
        request,
        title="Policy Management | Console | CanopyIQ", 
        desc="Upload, diff, and rollout policy changes.",
        path="console/policy.html",
        policy_status=status_info,
        status_error=status_error,
        diff_result=formatted_diff
    )

@app.get("/robots.txt", response_class=Response)
async def robots():
    return Response("User-agent: *\nAllow: /\nSitemap: https://canopyiq.ai/sitemap.txt", media_type="text/plain")

# ---------- Company Management Routes ----------
@app.get("/admin/companies", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_companies(request: Request, user: User = Depends(get_current_user)):
    """Company management dashboard"""
    companies = company_manager.get_available_companies(user)
    users = company_manager.get_company_users(user)
    
    return page(
        request,
        title="Company Management | Admin | CanopyIQ",
        desc="Manage companies and users",
        path="admin_companies.html",
        companies=companies,
        users=users,
        current_user=user,
        is_super_admin=company_manager.is_super_admin(user)
    )

@app.get("/api/companies/{company_domain}/users", dependencies=[Depends(require_admin)])
async def api_company_users(
    company_domain: str, 
    user: User = Depends(get_current_user)
):
    """API endpoint to get users for a company"""
    if not company_manager.can_access_company(user, company_domain):
        raise HTTPException(status_code=403, detail="Access denied to company data")
    
    users = company_manager.get_company_users(user, company_domain)
    return {"users": users}

# ---------- MCP Server API Routes ----------
@app.get("/api/v1/mcp/status")
async def mcp_server_status():
    """Get MCP server status and configuration info"""
    return {
        "status": "available",
        "server": {
            "name": "canopyiq-mcp-server",
            "version": "1.0.0",
            "protocol_version": "2024-11-05"
        },
        "capabilities": {
            "tools": True,
            "logging": True,
            "notifications": True,
            "approval_workflows": True
        },
        "installation": {
            "npm_package": "canopyiq-mcp-server",
            "install_command": "npm install -g canopyiq-mcp-server",
            "npx_command": "npx canopyiq-mcp-server"
        },
        "config_example": {
            "mcpServers": {
                "canopyiq": {
                    "command": "npx",
                    "args": ["canopyiq-mcp-server", "--api-key", "your-api-key"]
                }
            }
        }
    }

@app.get("/api/v1/mcp/config")
async def mcp_config_generator(api_key: str = None):
    """Generate Claude Desktop configuration for CanopyIQ MCP server"""
    config = {
        "mcpServers": {
            "canopyiq": {
                "command": "npx",
                "args": ["canopyiq-mcp-server"]
            }
        }
    }
    
    if api_key:
        config["mcpServers"]["canopyiq"]["args"].extend(["--api-key", api_key])
    
    return {
        "config": config,
        "instructions": [
            "1. Copy this configuration to your ~/.claude_desktop_config.json file",
            "2. If the file doesn't exist, create it",
            "3. Restart Claude Desktop",
            "4. CanopyIQ will appear in your available tools"
        ],
        "config_path": "~/.claude_desktop_config.json"
    }

@app.get("/api/v1/policies/active")
async def get_active_policies():
    """Get active security policies for MCP server"""
    # In production, these would come from database
    default_policies = [
        {
            "id": "destructive-commands",
            "name": "Block Destructive Commands",
            "description": "Prevents dangerous filesystem and database operations",
            "enabled": True,
            "rules": [
                {
                    "pattern": "rm -rf|DROP TABLE|DELETE FROM|TRUNCATE|sudo rm",
                    "action": "block",
                    "description": "Dangerous system commands"
                },
                {
                    "pattern": "sudo|chmod 777|>",
                    "action": "approve", 
                    "description": "Elevated privilege commands"
                }
            ]
        },
        {
            "id": "spending-limits",
            "name": "Daily Spending Limits", 
            "description": "Controls API costs and usage",
            "enabled": True,
            "rules": [
                {
                    "type": "spending",
                    "limit": 100,
                    "action": "approve",
                    "description": "Daily spending over $100"
                }
            ]
        },
        {
            "id": "rate-limiting",
            "name": "Tool Call Rate Limits",
            "description": "Prevents abuse and runaway processes", 
            "enabled": True,
            "rules": [
                {
                    "type": "tool_calls",
                    "limit": 50,
                    "window": "hour",
                    "action": "block",
                    "description": "More than 50 tool calls per hour"
                }
            ]
        },
        {
            "id": "sensitive-data",
            "name": "Sensitive Data Protection",
            "description": "Blocks exposure of credentials and PII",
            "enabled": True,
            "rules": [
                {
                    "pattern": "password|secret|key|token|credential",
                    "action": "approve",
                    "description": "Commands containing sensitive keywords"
                }
            ]
        }
    ]
    
    return {"policies": default_policies}

@app.get("/api/v1/dashboard/metrics")
async def get_dashboard_metrics(
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard metrics for charts and graphs"""
    try:
        # In production, query real data from audit logs
        # For now, return realistic demo data based on actual MCP usage patterns
        from datetime import datetime, timedelta
        import random
        
        # Generate realistic time series data
        now = datetime.now()
        time_points = []
        tool_calls_data = []
        approved_data = []
        blocked_data = []
        pending_data = []
        cost_data = []
        
        for i in range(hours):
            time_point = now - timedelta(hours=hours-i)
            time_points.append(time_point.strftime("%H:00"))
            
            # MCP tool calls with realistic patterns (more activity during work hours)
            hour = time_point.hour
            if 9 <= hour <= 17:  # Work hours
                approved = random.randint(40, 100)
                blocked = random.randint(2, 15)
                pending = random.randint(1, 8)
            else:  # Off hours
                approved = random.randint(10, 30)
                blocked = random.randint(0, 5)
                pending = random.randint(0, 3)
            
            approved_data.append(approved)
            blocked_data.append(blocked)
            pending_data.append(pending)
            tool_calls_data.append(approved + blocked + pending)
            
            # Cost follows tool call patterns
            cost_data.append(round((approved * 0.02 + blocked * 0.01 + pending * 0.015), 2))
        
        # Response time distribution (realistic MCP server latency)
        response_times = {
            "<100ms": random.randint(120, 180),      # Fast responses
            "100-250ms": random.randint(250, 350),   # Normal responses  
            "250-500ms": random.randint(100, 200),   # Slower responses
            "500ms-1s": random.randint(50, 100),     # Slow responses
            "1-2s": random.randint(10, 40),          # Very slow
            ">2s": random.randint(5, 20)             # Timeout/errors
        }
        
        # Policy actions summary
        total_approved = sum(approved_data)
        total_blocked = sum(blocked_data) 
        total_pending = sum(pending_data)
        
        return {
            "time_series": {
                "labels": time_points,
                "tool_calls": tool_calls_data,
                "approved": approved_data,
                "blocked": blocked_data,
                "pending": pending_data,
                "costs": cost_data
            },
            "response_times": response_times,
            "policy_summary": {
                "approved": total_approved,
                "blocked": total_blocked,
                "pending": total_pending
            },
            "totals": {
                "total_calls": sum(tool_calls_data),
                "total_cost": sum(cost_data),
                "success_rate": round((total_approved / (total_approved + total_blocked)) * 100, 1),
                "avg_response_time": random.randint(150, 250)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}")
        return {"error": str(e)}

@app.post("/api/v1/logs/tool-calls")
async def log_mcp_tool_call(
    tool_call: dict,
    db: AsyncSession = Depends(get_db)
):
    """Log MCP tool calls from Claude Desktop"""
    try:
        # Create audit log entry
        audit_entry = AuditLog(
            ts=int(time.time()),
            actor=tool_call.get("source", "mcp-server"),
            action=f"MCP_TOOL_CALL:{tool_call.get('tool', 'unknown')}",
            resource=tool_call.get("tool", "unknown"),
            attributes={
                "arguments": tool_call.get("arguments", {}),
                "result": tool_call.get("result", ""),
                "status": tool_call.get("status", "executed"),
                "timestamp": tool_call.get("timestamp"),
                "source": "mcp-server"
            }
        )
        
        if db:
            db.add(audit_entry)
            await db.commit()
            logger.info(f"MCP tool call logged: {tool_call.get('tool')} - {tool_call.get('status')}")
        
        return {"status": "logged", "message": "Tool call logged successfully"}
        
    except Exception as e:
        logger.error(f"Failed to log MCP tool call: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/sitemap.txt", response_class=Response)
async def sitemap():
    urls = ["/", "/product", "/security", "/pricing", "/documentation", "/contact", "/legal/terms", "/legal/privacy"]
    base = "https://canopyiq.ai"  # replace with your domain
    return Response("\n".join(f"{base}{u}" for u in urls), media_type="text/plain")

@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request, exc):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request, "asset_ver": ASSET_VER, "meta": {"title": "Page Not Found | CanopyIQ", "desc": "The page you're looking for doesn't exist.", "url_path": request.url.path}}, status_code=404)
    raise exc