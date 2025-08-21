from fastapi import FastAPI, Request, Form, status, Depends
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
        resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; font-src 'self' https://fonts.gstatic.com;"
        return resp

app = FastAPI(title="CanopyIQ")

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["GET","POST"], 
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")
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
    """Initialize services on startup"""
    await init_db()  # Create tables if they don't exist (dev only)
    await init_oidc()

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
        title="Run AI agents safely. At scale. | CanopyIQ",
        desc="CanopyIQ is the runtime sandbox & policy control plane for 10,000+ enterprise agents.",
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

@app.get("/documentation", response_class=HTMLResponse)
async def documentation(request: Request):
    return page(
        request,
        title="Documentation | CanopyIQ",
        desc="Reference architecture, quickstart, policies reference, API endpoints, deploy options.",
        path="docs.html",
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

@app.get("/auth/callback")
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
        
        # Create user from claims
        user = oidc_client.create_user_from_claims(claims)
        
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
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin dashboard"""
    user = get_current_user(request)
    
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

@app.get("/robots.txt", response_class=Response)
async def robots():
    return Response("User-agent: *\nAllow: /\nSitemap: https://canopyiq.ai/sitemap.txt", media_type="text/plain")

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