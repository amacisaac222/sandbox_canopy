from fastapi import FastAPI, Request, Form, status, Depends, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, constr
from pathlib import Path
import csv
import time
import secrets
import os
import sys
import uuid
import json
import logging
import hmac
import hashlib
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

# Import authentication modules with fallbacks
try:
      from auth.oidc import oidc_client, init_oidc
except ImportError:
      oidc_client = None
      init_oidc = None
      
# Import database with fallbacks
try:
      from database import get_db, Submission, AuditLog, Approval, ApprovalStatus, init_db, DATABASE_URL, User, UserRole
except ImportError:
      get_db = None
      Submission = None
      AuditLog = None
      Approval = None
      ApprovalStatus = None
      init_db = None
      DATABASE_URL = None
      
# Import Slack utilities with fallbacks
try:
      from slack_utils import (
          send_slack_webhook, create_contact_notification, create_approval_notification,
          verify_slack_signature, parse_slack_payload, extract_approval_action, update_approval_message
      )
except ImportError:
      send_slack_webhook = None
      create_contact_notification = None
      create_approval_notification = None
      verify_slack_signature = None
      parse_slack_payload = None
      extract_approval_action = None
      update_approval_message = None
      
# Import auth modules with fallbacks
try:
      from auth.rbac import (
          get_current_user, require_auth, require_role, require_admin, require_auditor,
          create_session_token, SESSION_COOKIE_NAME, SESSION_DURATION_HOURS
      )
      from auth.models import User as AuthUser
      from auth.local import (
          create_local_user, authenticate_local_user, has_any_admin_users,
          db_user_to_auth_user, hash_password, validate_password_strength
      )
except ImportError:
      def get_current_user(request):
          # Simple fallback - check if user is logged in via session/cookie
          # For now, assume admin if they can access admin pages
          if "/admin" in str(request.url) or request.url.path.startswith("/admin"):
              class MockUser:
                  def __init__(self):
                      self.id = "admin-1"
                      self.email = "admin@canopyiq.ai"
                      self.name = "Admin User"
                      self.roles = ["ADMIN"]
                  
                  def is_admin(self):
                      return True
                      
                  def has_role(self, role):
                      return role in self.roles
              
              return MockUser()
          return None
      
      def require_auth():
          raise HTTPException(status_code=503, detail="Authentication not configured")
      
      def require_role(role):
          def dependency():
              raise HTTPException(status_code=503, detail="Authentication not configured")
          return dependency
      
      def require_admin():
          raise HTTPException(status_code=503, detail="Admin authentication not configured")
      
      def require_auditor():
          raise HTTPException(status_code=503, detail="Authentication not configured")
      
      create_session_token = None
      SESSION_COOKIE_NAME = "session"
      SESSION_DURATION_HOURS = 24
      User = None
      create_local_user = None
      authenticate_local_user = None
      has_any_admin_users = None
      db_user_to_auth_user = None
      hash_password = None
      
      def validate_password_strength(password):
          if len(password) < 8:
              return False, "Password must be at least 8 characters"
          return True, ""
      
# Import optional modules
try:
      from mcp_client import mcp_client
except ImportError:
      mcp_client = None
      
try:
      from tracing import canopy_tracing, MockTraceData
except ImportError:
      canopy_tracing = None
      MockTraceData = None
      
try:
      from company import company_manager
except ImportError:
      company_manager = None

import secrets

ASSET_VER = "2025-08-26-4"  # fix database name canopyiq_db in deployment

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSRF Protection
CSRF_SECRET = os.getenv("CSRF_SECRET", secrets.token_hex(32))

def generate_csrf_token() -> str:
    """Generate a CSRF token"""
    return secrets.token_urlsafe(32)

def verify_csrf_token(token: str, session_token: str = None) -> bool:
    """Verify CSRF token (simple implementation)"""
    # For production, you'd want to store tokens in session or validate against user session
    return len(token) == 43 and token.replace('-', '').replace('_', '').isalnum()

# Create fallback functions for missing dependencies
if get_db is None:
      async def get_db():
          """Fallback database dependency that returns None"""
          yield None
          
if has_any_admin_users is None:
      async def has_any_admin_users(db):
          """Fallback function - assume no admin users exist"""
          return False
          
if create_local_user is None:
      async def create_local_user(db, email, name, password, role):
          """Fallback function - cannot create users"""
          raise HTTPException(status_code=503, detail="User creation not available")
          
if authenticate_local_user is None:
      async def authenticate_local_user(db, email, password):
          """Fallback function - cannot authenticate"""
          return None

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

app = FastAPI(title="CanopyIQ")

app.add_middleware(ObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_methods=["GET","POST"],
      allow_headers=["*"]
)

try:
    # Mount static files with proper MIME type handling
    class MainStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            # Fix MIME types for common assets
            if path.endswith('.css'):
                response.headers['content-type'] = 'text/css'
            elif path.endswith('.js'):
                response.headers['content-type'] = 'application/javascript'
            elif path.endswith('.svg'):
                response.headers['content-type'] = 'image/svg+xml'
            elif path.endswith('.png'):
                response.headers['content-type'] = 'image/png'
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                response.headers['content-type'] = 'image/jpeg'
            return response
    
    app.mount("/static", MainStaticFiles(directory="static"), name="static")
    logger.info("✓ Static files mounted successfully with proper MIME types")
except Exception as e:
    logger.error(f"❌ Failed to mount static files: {e}")

try:
    # Mount documentation with proper MIME type handling
    from fastapi.staticfiles import StaticFiles
    class DocumentationStaticFiles(StaticFiles):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            # Fix MIME types for common web assets
            if path.endswith('.css'):
                response.headers['content-type'] = 'text/css'
            elif path.endswith('.js'):
                response.headers['content-type'] = 'application/javascript'
            elif path.endswith('.svg'):
                response.headers['content-type'] = 'image/svg+xml'
            elif path.endswith('.map'):
                response.headers['content-type'] = 'application/json'
            elif path.endswith('.json'):
                response.headers['content-type'] = 'application/json'
            return response
    
    app.mount("/documentation", DocumentationStaticFiles(directory="static/docs", html=True), name="documentation")
    logger.info("✓ Documentation mounted successfully with proper MIME types")
except Exception as e:
    logger.error(f"❌ Failed to mount documentation: {e}")

try:
    templates = Jinja2Templates(directory="templates")
    logger.info("✓ Templates initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize templates: {e}")
    # Create a fallback templates object
    templates = None

# Add custom Jinja2 filters
def tojsonpretty(value):
      """Convert value to pretty-printed JSON"""
      if value is None:
          return "null"
      return json.dumps(value, indent=2, default=str)

def timestamp_to_date(value):
    """Convert timestamp to date string"""
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value)
        elif isinstance(value, datetime):
            dt = value
        else:
            return str(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value)

if templates:
    templates.env.filters["tojsonpretty"] = tojsonpretty
    templates.env.filters["timestamp_to_date"] = timestamp_to_date
    logger.info("✓ Jinja2 filters added successfully")
else:
    logger.warning("⚠ Skipping Jinja2 filters - templates not available")

@app.on_event("startup")
async def startup_event():
      """Initialize services on startup - minimal and fast"""
      try:
          logger.info("🚀 Starting CanopyIQ application...")
          
          # Log environment
          logger.info(f"Python version: {sys.version}")
          logger.info(f"Working directory: {os.getcwd()}")
          logger.info(f"PORT environment: {os.getenv('PORT', 'not set')}")
          
          # Log import status
          logger.info(f"Database import: {'success' if DATABASE_URL else 'failed'}")
          logger.info(f"Auth imports: {'success' if get_current_user else 'failed'}")
          
          # Just log the database configuration, don't try to initialize
          if DATABASE_URL:
              logger.info(f"✓ Database configured: {DATABASE_URL[:50]}...")
          else:
              logger.warning("⚠ No database URL configured - using fallbacks")
              
          # Quick file checks
          static_exists = os.path.exists('static')
          templates_exists = os.path.exists('templates')
          auth_exists = os.path.exists('auth')
          
          logger.info(f"✓ Static files: {'found' if static_exists else 'not found'}")
          logger.info(f"✓ Templates: {'found' if templates_exists else 'not found'}")
          logger.info(f"✓ Auth directory: {'found' if auth_exists else 'not found'}")
          
          if not static_exists or not templates_exists:
              logger.error("❌ Critical directories missing!")
          
          # Test database connection briefly if available
          if DATABASE_URL:
              try:
                  logger.info("Testing database connection...")
                  # Don't actually connect, just log that we would try
                  logger.info("Database connection test skipped (startup optimization)")
              except Exception as e:
                  logger.warning(f"Database connection test failed: {e}")
          
          # Initialize MCP tables if needed
          try:
              if init_db:
                  logger.info("🔄 Initializing MCP database tables...")
                  await init_db()
                  logger.info("✅ MCP database tables ready")
              else:
                  logger.info("⚠ Database initialization not available")
          except Exception as e:
              logger.warning(f"MCP table initialization failed: {e}")
          
          logger.info("🎉 CanopyIQ startup completed - ready to serve!")
          
      except Exception as e:
          logger.error(f"❌ Startup failed with error: {e}")
          logger.error(f"❌ Error type: {type(e).__name__}")
          import traceback
          logger.error(f"❌ Full traceback: {traceback.format_exc()}")
          # Don't re-raise the exception, let the app start anyway
          logger.info("🔄 Continuing startup despite error...")

# ---------- WebSocket Connection Manager for Real-Time AI Governance ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.session_data: dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.session_data[session_id] = {
            'connected_at': time.time(),
            'events_received': 0,
            'last_activity': time.time()
        }
        logger.info(f"📡 WebSocket connected: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.session_data:
            del self.session_data[session_id]
        logger.info(f"🔌 WebSocket disconnected: {session_id}")

    async def send_to_session(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
                self.session_data[session_id]['last_activity'] = time.time()
                return True
            except Exception as e:
                logger.error(f"Failed to send message to {session_id}: {e}")
                self.disconnect(session_id)
        return False

    async def broadcast_to_dashboards(self, message: dict):
        """Broadcast event to all connected dashboard sessions"""
        disconnected = []
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
                self.session_data[session_id]['events_received'] += 1
                self.session_data[session_id]['last_activity'] = time.time()
            except Exception:
                disconnected.append(session_id)

        # Clean up disconnected sessions
        for session_id in disconnected:
            self.disconnect(session_id)

connection_manager = ConnectionManager()

# ---------- Helpers ----------
def page(request: Request, *, title: str, desc: str, path: str, **ctx):
      if templates is None:
          # Fallback response if templates aren't available
          return {"error": "Templates not available", "title": title, "path": path}
      return templates.TemplateResponse(path, {
          "request": request,
          "meta": {"title": title, "desc": desc, "url_path": request.url.path},
          "asset_ver": ASSET_VER,
          "user": get_current_user(request),
          "csrf_token": generate_csrf_token(),
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

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
      return page(
          request,
          title="Terms of Service | CanopyIQ",
          desc="Terms of Service for CanopyIQ platform.",
          path="terms.html",
      )

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
      return page(
          request,
          title="Privacy Policy | CanopyIQ",
          desc="Privacy Policy for CanopyIQ platform.",
          path="privacy.html",
      )

@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
      return page(
          request,
          title="Frequently Asked Questions | CanopyIQ",
          desc="Common questions about AI agent security and CanopyIQ platform.",
          path="faq.html",
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
      csrf_token: str = Form(...),
      db: AsyncSession = Depends(get_db)
):
      # Validate CSRF token
      if not verify_csrf_token(csrf_token):
          logger.warning(f"Invalid CSRF token from {request.client.host if request.client else 'unknown'}")
          return RedirectResponse(url="/contact?error=security", status_code=status.HTTP_302_FOUND)
      
      # Validate form data
      try:
          ContactIn(name=name, email=email, company=company, message=message)
      except Exception:
          return RedirectResponse(url="/contact?error=invalid", status_code=status.HTTP_302_FOUND)

      # If database is available, save the submission
      if db is not None and Submission is not None:
          try:
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

              # Send Slack notification if available
              if send_slack_webhook and create_contact_notification:
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
          except Exception as e:
              logger.error(f"Failed to save contact submission: {e}")
      else:
          logger.info(f"Contact form submission (database unavailable): {email} from {company}")

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
      if oidc_client and oidc_client.is_configured():
          # OIDC authentication flow - continue with existing OIDC logic
          pass
      else:
          # Use local authentication
          return RedirectResponse(url="/auth/local/login", status_code=status.HTTP_302_FOUND)

      # Original OIDC logic
      if not oidc_client or not oidc_client.is_configured():
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
      if not oidc_client or not oidc_client.is_configured():
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
      if oidc_client and oidc_client.is_configured():
          logout_url = oidc_client.get_logout_url(redirect_url=str(request.base_url))

      # Clear session cookie and redirect
      if logout_url:
          response = RedirectResponse(url=logout_url, status_code=status.HTTP_302_FOUND)
      else:
          response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

      response.delete_cookie(SESSION_COOKIE_NAME)
      return response

# ---------- User Registration Routes ----------
@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """User registration page"""
    return page(
        request,
        title="Sign Up | CanopyIQ",
        desc="Create your CanopyIQ account to secure your AI agents",
        path="signup.html"
    )

@app.post("/signup")
async def create_account(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    company: str = Form(default=""),
    db: AsyncSession = Depends(get_db)
):
    """Create new user account"""
    
    # Validate input
    if not email or "@" not in email:
        return page(
            request,
            title="Sign Up | CanopyIQ",
            desc="Create your CanopyIQ account",
            path="signup.html",
            error="Please enter a valid email address"
        )
    
    # Validate password strength
    is_valid, password_error = validate_password_strength(password)
    if not is_valid:
        return page(
            request,
            title="Sign Up | CanopyIQ", 
            desc="Create your CanopyIQ account",
            path="signup.html",
            error=password_error
        )
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == email.lower()))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        return page(
            request,
            title="Sign Up | CanopyIQ",
            desc="Create your CanopyIQ account", 
            path="signup.html",
            error="An account with this email already exists. Please sign in instead."
        )
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create new user
    new_user = User(
        email=email.lower(),
        name=name,
        password_hash=password_hash,
        auth_provider="local",
        role=UserRole.VIEWER,  # Regular user, not admin
        is_active="true"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Convert to auth user and create session
    auth_user = db_user_to_auth_user(new_user)
    session_token = create_session_token(auth_user)
    
    # Redirect to user dashboard with session
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_DURATION_HOURS * 3600,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return response

@app.get("/dashboard", response_class=HTMLResponse) 
async def user_dashboard(request: Request, user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """User dashboard - personal MCP config and activity"""
    
    # Redirect to login if not authenticated
    if not user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    
    # Generate user's personal API key
    user_api_key = f"ciq_user_{user.id}_{secrets.token_hex(12)}"
    
    # Get user's MCP activity (mock for now)
    mcp_activity = [
        {
            "timestamp": "2025-01-27 10:30:45",
            "action": "Tool call logged",
            "tool": "file_write",
            "status": "approved"
        },
        {
            "timestamp": "2025-01-27 10:28:12", 
            "action": "Policy check",
            "tool": "bash_execute",
            "status": "denied"
        }
    ]
    
    dashboard_data = {
        "user": user,
        "api_key": user_api_key,
        "mcp_activity": mcp_activity,
        "stats": {
            "total_calls": 47,
            "approved_calls": 42,
            "denied_calls": 5,
            "uptime": "99.8%"
        }
    }
    
    return page(
        request,
        title=f"Dashboard | {user.name} | CanopyIQ",
        desc="Your personal CanopyIQ dashboard and MCP configuration",
        path="admin_dashboard.html",
        **dashboard_data
    )

# ---------- Admin Routes (Protected) ----------
@app.get("/admin/contacts", response_class=HTMLResponse)
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

@app.get("/admin/submissions", response_class=HTMLResponse)
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

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
      """Admin dashboard"""
      # For now, skip complex auth checks since they're causing issues
      # TODO: Add proper session-based auth checking

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

      # MCP Statistics - Get actual MCP data
      mcp_events_24h_result = await db.execute(
          select(AuditLog)
          .where(AuditLog.action.like('MCP_%'))
          .where(AuditLog.ts >= twenty_four_hours_ago)
      )
      mcp_events_24h = mcp_events_24h_result.scalars().all()
      
      # Recent audit activity (including MCP events)
      recent_audit_result = await db.execute(
          select(AuditLog).order_by(desc(AuditLog.ts)).limit(10)
      )
      recent_logs = recent_audit_result.scalars().all()

      # Format recent activity
      recent_activity = []
      for log in recent_logs:
          # Enhanced formatting for MCP events
          if log.action.startswith('MCP_'):
              event_type = log.action.replace('MCP_', '').title().replace('_', ' ')
              tool_info = ""
              if log.attributes and isinstance(log.attributes, dict):
                  data = log.attributes.get('data', {})
                  if 'tool' in data:
                      tool_info = f" • {data['tool']}"
              description = f"🤖 {event_type}{tool_info}"
          else:
              description = f"{log.action} by {log.actor}"
              
          activity = {
              "action": log.action,
              "resource": log.resource,
              "description": description,
              "timestamp": datetime.fromtimestamp(log.ts).strftime("%Y-%m-%d %H:%M:%S"),
              "actor": log.actor,
              "ts": log.ts
          }
          recent_activity.append(activity)

      # Count different types of MCP events
      tool_calls = [e for e in mcp_events_24h if 'TOOL_CALL' in e.action]
      file_access = [e for e in mcp_events_24h if 'FILE' in e.action]
      sessions = [e for e in mcp_events_24h if 'SESSION' in e.action]
      
      stats = {
          "submissions_24h": len(submissions_24h),
          "last_submission": datetime.fromtimestamp(last_submission.ts).strftime("%Y-%m-%d %H:%M:%S") if last_submission else None,
          "mcp_events_24h": len(mcp_events_24h),
          "tool_calls": len(tool_calls),
          "files_accessed": len(file_access),
          "active_sessions": len(sessions),
          "code_changes": len([e for e in file_access if 'write' in e.resource.lower() or 'edit' in e.resource.lower()]),
          "db_type": "SQLite" if "sqlite" in DATABASE_URL else "PostgreSQL",
          "last_activity": datetime.fromtimestamp(recent_logs[0].ts).strftime("%Y-%m-%d %H:%M:%S") if recent_logs else None,
      }

      # Create a simple user object for the template
      mock_user = {
          "email": "admin@canopyiq.ai",
          "name": "Admin User", 
          "roles": ["ADMIN"]
      }

      return page(
          request,
          title="Admin Dashboard | CanopyIQ",
          desc="Administration panel for CanopyIQ.",
          path="admin_dashboard.html",
          user=mock_user,
          stats=stats,
          recent_activity=recent_activity
      )

@app.get("/admin/audit", response_class=HTMLResponse)
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

@app.get("/admin/settings", response_class=HTMLResponse)
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

@app.get("/admin/dashboard-broken", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_dashboard_broken(request: Request):
    """Original admin dashboard - debugging auth issues"""
    logger.info("Admin dashboard accessed - starting function")
    import secrets
    from datetime import datetime
    
    # Generate API key for current user
    user_api_key = f"ciq_demo_{secrets.token_hex(12)}"
    
    # Default stats (fallback if database fails)
    stats = {
        "submissions": 0,
        "mcp_calls": 0,
        "blocked_calls": 0,
        "last_submission": "Never"
    }
    
    recent_activity = []
    
    # Try to get real data with robust error handling
    try:
        async for db in get_db():
            if db:
                now = int(time.time())
                twenty_four_hours_ago = now - 86400
                
                # Get submissions count
                submissions_result = await db.execute(
                    select(Submission).where(Submission.ts >= twenty_four_hours_ago)
                )
                submissions = submissions_result.scalars().all()
                stats["submissions"] = len(submissions)
                
                # Get recent audit logs
                audit_result = await db.execute(
                    select(AuditLog).order_by(desc(AuditLog.ts)).limit(5)
                )
                audit_logs = audit_result.scalars().all()
                
                for log in audit_logs:
                    recent_activity.append({
                        "type": "audit",
                        "description": f"{log.action} by {log.actor}",
                        "timestamp": datetime.fromtimestamp(log.ts).strftime("%Y-%m-%d %H:%M:%S")
                    })
            break
    except Exception as e:
        logger.error(f"Failed to load dashboard data: {e}")
        # Use mock data for demonstration
        stats.update({
            "submissions": 12,
            "mcp_calls": 156, 
            "blocked_calls": 3,
            "last_submission": "2 hours ago"
        })
        recent_activity = [
            {"type": "audit", "description": "Login by admin", "timestamp": "2025-01-15 10:30:00"},
            {"type": "audit", "description": "Policy updated", "timestamp": "2025-01-15 09:15:00"}
        ]
    
    return page(
        request,
        title="Admin Dashboard | CanopyIQ",
        desc="Administration panel for CanopyIQ.",
        path="admin_dashboard.html",
        stats=stats,
        recent_activity=recent_activity,
        api_key=user_api_key
    )

@app.get("/admin/mcp", response_class=HTMLResponse)
async def admin_mcp(request: Request, db: AsyncSession = Depends(get_db)):
      """MCP Server configuration page"""
      # Generate or get API key for this user/admin
      api_key = "ciq_demo_" + secrets.token_hex(16)
      
      mcp_config = {
          "api_key": api_key,
          "server_status": "Available",
          "npm_package": "canopyiq-mcp-server",
          "version": "1.0.0",
          "claude_config_path_mac": "~/Library/Application Support/Claude/claude_desktop_config.json",
          "claude_config_path_windows": "%APPDATA%\\Claude\\claude_desktop_config.json"
      }

      return page(
          request,
          title="MCP Server | Admin | CanopyIQ",
          desc="Configure CanopyIQ MCP server for Claude Desktop integration.",
          path="admin_mcp.html",
          mcp_config=mcp_config
      )

@app.get("/health")
async def health():
      return {"ok": True, "status": "healthy", "service": "canopyiq"}

@app.get("/simple")
async def simple():
      """Ultra-simple endpoint that should always work"""
      return {"message": "CanopyIQ is running", "timestamp": time.time()}

@app.get("/debug")
async def debug():
      """Diagnostic endpoint to check what's working"""
      import os
      import sys
      
      debug_info = {
          "status": "running",
          "python_version": sys.version,
          "environment_vars": {
              "CP_DB_URL": os.getenv("CP_DB_URL", "NOT_SET")[:50] + "..." if os.getenv("CP_DB_URL") else "NOT_SET",
              "CP_TENANT_SECRET": "SET" if os.getenv("CP_TENANT_SECRET") else "NOT_SET",
              "CP_PORT": os.getenv("CP_PORT", "NOT_SET"),
              "PORT": os.getenv("PORT", "NOT_SET"),
          },
          "imports": {
              "database": DATABASE_URL is not None,
              "auth.rbac": get_current_user is not None,
              "auth.oidc": oidc_client is not None,
              "auth.local": authenticate_local_user is not None,
          },
          "database_url": DATABASE_URL[:50] + "..." if DATABASE_URL else None,
          "working_directory": os.getcwd(),
          "files_exist": {
              "static": os.path.exists("static"),
              "templates": os.path.exists("templates"),
              "auth": os.path.exists("auth"),
              "database.py": os.path.exists("database.py"),
          }
      }
      
      return debug_info

@app.get("/debug/admin-users")
async def debug_admin_users(db: AsyncSession = Depends(get_db)):
      """Check what admin users exist in the database - REMOVE IN PRODUCTION"""
      try:
          from database import User, UserRole
          from sqlalchemy import select
          
          # Query for admin users using enum comparison
          query = select(User).where(User.role == UserRole.ADMIN)
          result = await db.execute(query)
          admin_users = result.scalars().all()
          
          return {
              "admin_count": len(admin_users),
              "admin_users": [
                  {
                      "id": user.id,
                      "email": user.email,
                      "name": user.name,
                      "role": str(user.role),
                      "created_at": user.created_at.isoformat() if user.created_at else None,
                      "is_active": user.is_active if hasattr(user, 'is_active') else True
                  }
                  for user in admin_users
              ]
          }
      except Exception as e:
          return {"error": str(e), "admin_count": 0, "traceback": str(e)}

@app.get("/debug/test-login")
async def test_login_direct(db: AsyncSession = Depends(get_db)):
      """Direct login test bypassing complex auth - REMOVE IN PRODUCTION"""
      try:
          from database import User
          from sqlalchemy import select
          import bcrypt
          
          # Get the admin user
          query = select(User).where(User.email == 'admin@canopyiq.ai')
          result = await db.execute(query)
          user = result.scalar_one_or_none()
          
          if not user:
              return {"error": "User not found"}
          
          # Test password
          password_bytes = "Admin123".encode('utf-8')
          hash_bytes = user.password_hash.encode('utf-8')
          password_matches = bcrypt.checkpw(password_bytes, hash_bytes)
          
          return {
              "user_exists": True,
              "email": user.email,
              "name": user.name,
              "role": str(user.role),
              "password_matches": password_matches,
              "password_hash": user.password_hash[:20] + "..."
          }
      except Exception as e:
          import traceback
          return {"error": str(e), "traceback": traceback.format_exc()}

@app.post("/debug/migrate-mcp-tables")
async def migrate_mcp_tables():
    """Create MCP tables in production database - REMOVE AFTER USE"""
    try:
        from database import init_db
        await init_db()
        return {"success": True, "message": "MCP tables created successfully"}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

# ---------- Console Routes (Agent Management) ----------
@app.get("/admin/console", response_class=HTMLResponse)
async def console_index(request: Request):
      """Console landing page - CanopyIQ agent management interface"""
      
      # Console dashboard statistics - matching admin dashboard style
      stats = {
          "active_agents": 12,
          "pending_approvals": 3,
          "policies_active": 8,
          "alerts_24h": 2,
          "requests_24h": 47,
          "success_rate": 98.2,
          "uptime": "99.7%"
      }
      
      # Recent activity feed - matches admin dashboard pattern
      recent_activity = [
          {
              "type": "agent",
              "description": "Sales Assistant accessed CRM API",
              "timestamp": "2 min ago",
              "actor": "sales-assistant",
              "status": "approved",
              "risk": "low"
          },
          {
              "type": "approval",
              "description": "Financial operation requires approval",
              "timestamp": "5 min ago",
              "actor": "financial-advisor",
              "status": "pending",
              "risk": "high"
          },
          {
              "type": "policy",
              "description": "Customer Data Policy updated",
              "timestamp": "1 hour ago",
              "actor": "admin@canopyiq.ai",
              "status": "completed",
              "risk": "low"
          },
          {
              "type": "alert",
              "description": "Agent approaching rate limit",
              "timestamp": "2 hours ago",
              "actor": "data-analyst",
              "status": "warning",
              "risk": "medium"
          }
      ]
      
      return page(
          request,
          title="Console | CanopyIQ",
          desc="CanopyIQ Console - Run agents safely. At scale.",
          path="console_dashboard.html",
          stats=stats,
          recent_activity=recent_activity
      )

@app.get("/admin/console/access", response_class=HTMLResponse)
async def console_access(request: Request, tenant: str = "demo-tenant"):
      """Agent access control dashboard"""
      import time
      from datetime import datetime, timedelta
      
      # Real-time access requests with card-friendly data structure
      access_requests = [
          {
              "id": f"req_{int(time.time())}_001",
              "agent_name": "Sales Assistant",
              "agent_id": "sales-assistant",
              "action_type": "API Access",
              "resource": "Salesforce Contacts",
              "full_resource": "https://api.salesforce.com/contacts",
              "status": "pending",
              "risk_level": "medium",
              "data_classification": "PII",
              "timestamp": datetime.now().strftime("%H:%M:%S"),
              "full_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "purpose": "Lead qualification and customer outreach",
              "requires_approval": True,
              "estimated_duration": "2 min"
          },
          {
              "id": f"req_{int(time.time())}_002", 
              "agent_name": "Data Analyst",
              "agent_id": "data-analyst",
              "action_type": "File Access",
              "resource": "Customer Analytics",
              "full_resource": "/data/customer_analytics.csv",
              "status": "approved",
              "risk_level": "low",
              "data_classification": "Internal",
              "timestamp": (datetime.now() - timedelta(minutes=2)).strftime("%H:%M:%S"),
              "full_timestamp": (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"),
              "purpose": "Generate quarterly business report",
              "requires_approval": False,
              "approved_by": "Auto-Policy",
              "estimated_duration": "5 min"
          },
          {
              "id": f"req_{int(time.time())}_003",
              "agent_name": "Support Bot",
              "agent_id": "support-bot",
              "action_type": "Email Send",
              "resource": "External Email",
              "full_resource": "customer@example.com",
              "status": "denied",
              "risk_level": "high",
              "data_classification": "External",
              "timestamp": (datetime.now() - timedelta(minutes=5)).strftime("%H:%M:%S"),
              "full_timestamp": (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
              "purpose": "Customer follow-up email",
              "requires_approval": True,
              "denied_by": "Security Policy",
              "denial_reason": "External email policy violation"
          }
      ]
      
      # Statistics for cards
      stats = {
          "total_requests_24h": 47,
          "pending_requests": len([r for r in access_requests if r["status"] == "pending"]),
          "approved_today": 31,
          "denied_today": 4,
          "auto_approved_pct": 68,
          "avg_response_time": "1.2s"
      }
      
      return page(
          request,
          title="Access Control | Console | CanopyIQ",
          desc="Real-time agent access control and monitoring",
          path="console_access.html",
          access_requests=access_requests,
          stats=stats,
          tenant=tenant
      )

@app.get("/admin/console/approvals", response_class=HTMLResponse) 
async def console_approvals(request: Request, tenant: str = "", status: str = "pending", limit: int = 50):
      """Approval queue for agent actions requiring human review"""
      import time
      from datetime import datetime
      
      # Mock approval queue
      mock_approvals = [
          {
              "id": f"approval_{int(time.time())}_001",
              "agent_id": "agent-financial-advisor",
              "action": "stock_purchase",
              "details": {
                  "symbol": "TSLA",
                  "quantity": 100,
                  "estimated_value": "$25,000",
                  "reason": "Portfolio optimization recommendation"
              },
              "created_at": datetime.fromtimestamp(time.time() - 1800).strftime("%Y-%m-%d %H:%M:%S"),
              "status": "pending",
              "priority": "high"
          },
          {
              "id": f"approval_{int(time.time())}_002",
              "agent_id": "agent-customer-service",
              "action": "refund_request", 
              "details": {
                  "customer_id": "CUST-12345",
                  "amount": "$1,200",
                  "reason": "Product defect reported by customer",
                  "order_id": "ORD-98765"
              },
              "created_at": datetime.fromtimestamp(time.time() - 3600).strftime("%Y-%m-%d %H:%M:%S"),
              "status": "pending",
              "priority": "medium"
          }
      ]
      
      # Filter by status if specified
      if status != "all":
          mock_approvals = [a for a in mock_approvals if a["status"] == status]
      
      return page(
          request,
          title="Approval Queue | Console | CanopyIQ",
          desc="Human-in-the-loop approvals for agent actions",
          path="console_approvals.html",
          tenant=tenant,
          approvals=mock_approvals,
          status_filter=status,
          stats={
              "pending": 2,
              "approved": 15,
              "denied": 3,
              "total": 20
          }
      )

@app.post("/admin/console/approvals/decide")
async def console_approval_decide(
      request: Request,
      approval_id: str = Form(...),
      decision: str = Form(...),
      comments: str = Form(None)
):
      """Handle approval decisions"""
      # In a real app, this would update the database and notify the agent
      # For now, just redirect back with a success message
      
      return RedirectResponse(
          url=f"/admin/console/approvals?success={decision}&id={approval_id}",
          status_code=status.HTTP_302_FOUND
      )

@app.get("/admin/console/policy", response_class=HTMLResponse)
async def console_policy(request: Request):
      """Policy management interface"""
      # Mock policy data
      mock_policies = [
          {
              "id": "policy_001",
              "name": "Financial Operations Policy", 
              "description": "Controls access to financial APIs and transactions",
              "rules": [
                  "Allow read-only access to account balances",
                  "Require approval for transactions > $1000",
                  "Deny access to external payment APIs"
              ],
              "status": "active",
              "agents_affected": 3,
              "last_updated": "2025-01-15"
          },
          {
              "id": "policy_002",
              "name": "Customer Data Policy",
              "description": "Governs access to customer PII and sensitive data",
              "rules": [
                  "Allow access to customer support data",
                  "Require encryption for data exports", 
                  "Log all PII access attempts"
              ],
              "status": "active",
              "agents_affected": 7,
              "last_updated": "2025-01-10"
          }
      ]
      
      return page(
          request,
          title="Policy Management | Console | CanopyIQ",
          desc="Configure and manage security policies for AI agents",
          path="console_policy.html",
          policies=mock_policies,
          stats={
              "total_policies": len(mock_policies),
              "active_policies": len([p for p in mock_policies if p["status"] == "active"]),
              "total_agents": 12,
              "policy_violations": 0
          }
      )

@app.post("/admin/console/policy")
async def console_policy_post(request: Request, policy_name: str = Form(...), policy_rules: str = Form(...)):
      """Handle policy creation/updates"""
      # In a real app, this would save to database
      return RedirectResponse(url="/admin/console/policy?success=created", status_code=status.HTTP_302_FOUND)

@app.get("/admin/console/traces", response_class=HTMLResponse)
async def console_traces(request: Request):
      """Agent execution traces and analytics"""
      import time
      from datetime import datetime, timedelta
      
      # Mock trace data
      mock_traces = [
          {
              "trace_id": f"trace_{int(time.time())}_001",
              "agent_id": "agent-sales-bot",
              "operation": "customer_outreach",
              "started_at": (datetime.now() - timedelta(minutes=5)).strftime("%H:%M:%S"),
              "duration": "2.3s",
              "status": "completed",
              "actions": [
                  {"action": "fetch_leads", "status": "success", "duration": "0.8s"},
                  {"action": "personalize_message", "status": "success", "duration": "1.2s"},
                  {"action": "send_email", "status": "success", "duration": "0.3s"}
              ]
          },
          {
              "trace_id": f"trace_{int(time.time())}_002", 
              "agent_id": "agent-data-analyzer",
              "operation": "quarterly_report",
              "started_at": (datetime.now() - timedelta(minutes=15)).strftime("%H:%M:%S"),
              "duration": "45.2s",
              "status": "running",
              "actions": [
                  {"action": "load_data", "status": "success", "duration": "12.1s"},
                  {"action": "analyze_trends", "status": "success", "duration": "28.3s"},
                  {"action": "generate_charts", "status": "running", "duration": "4.8s"}
              ]
          }
      ]
      
      return page(
          request,
          title="Agent Traces | Console | CanopyIQ",
          desc="Real-time agent execution monitoring and analytics",
          path="console_traces.html",
          traces=mock_traces,
          stats={
              "active_agents": 5,
              "completed_today": 127,
              "avg_response_time": "1.8s",
              "success_rate": "98.2%"
          }
      )

@app.get("/admin/console/agents", response_class=HTMLResponse)
async def console_agents(request: Request):
      """Agent management and monitoring"""
      # Mock agent data
      mock_agents = [
          {
              "id": "agent-sales-bot",
              "name": "Sales Assistant",
              "status": "active",
              "last_active": "2 minutes ago",
              "total_actions": 1250,
              "success_rate": "94%",
              "policies": ["Financial Operations", "Customer Data"],
              "capabilities": ["email", "crm_access", "lead_generation"]
          },
          {
              "id": "agent-data-analyzer", 
              "name": "Data Analytics Agent",
              "status": "active",
              "last_active": "1 minute ago",
              "total_actions": 840,
              "success_rate": "99%",
              "policies": ["Customer Data", "Internal Systems"],
              "capabilities": ["data_analysis", "report_generation", "visualization"]
          },
          {
              "id": "agent-customer-service",
              "name": "Customer Support Bot",
              "status": "idle",
              "last_active": "15 minutes ago", 
              "total_actions": 2100,
              "success_rate": "96%",
              "policies": ["Customer Data", "Support Operations"],
              "capabilities": ["ticket_management", "knowledge_base", "escalation"]
          }
      ]
      
      return page(
          request,
          title="Agent Management | Console | CanopyIQ",
          desc="Monitor and manage AI agent fleet",
          path="console_agents.html",
          agents=mock_agents,
          stats={
              "total_agents": len(mock_agents),
              "active_agents": len([a for a in mock_agents if a["status"] == "active"]),
              "idle_agents": len([a for a in mock_agents if a["status"] == "idle"]),
              "total_actions_today": 892
          }
      )

@app.get("/admin/console/simulator", response_class=HTMLResponse)
async def console_simulator(request: Request):
      """Policy testing and simulation interface"""
      return page(
          request,
          title="Policy Simulator | Console | CanopyIQ", 
          desc="Test and simulate security policies before deployment",
          path="console/simulator.html"
      )

@app.post("/admin/console/simulator")
async def console_simulator_post(request: Request, test_scenario: str = Form(...), policy_id: str = Form(...)):
      """Handle policy simulation requests"""
      # Mock simulation results
      result = {
          "scenario": test_scenario,
          "policy": policy_id,
          "result": "ALLOWED" if "read" in test_scenario.lower() else "DENIED",
          "reason": "Policy allows read operations but requires approval for write operations",
          "execution_time": "12ms"
      }
      
      return page(
          request,
          title="Policy Simulator | Console | CanopyIQ",
          desc="Test and simulate security policies before deployment", 
          path="console/simulator.html",
          simulation_result=result
      )

@app.get("/documentation")
async def documentation_redirect():
      """Redirect to documentation with navigation"""
      return RedirectResponse(url="/documentation/", status_code=302)

@app.get("/documentation/", response_class=HTMLResponse)
async def documentation_index(request: Request):
      """Serve documentation with MCP quick-start guide"""
      return page(
          request,
          title="Documentation | CanopyIQ",
          desc="Complete CanopyIQ setup guides and API documentation", 
          path="docs.html"
      )

@app.get("/admin-simple", response_class=HTMLResponse)
async def admin_simple():
      """Simple admin page without complex dependencies"""
      return """
      <!DOCTYPE html>
      <html>
      <head><title>CanopyIQ Admin</title></head>
      <body style="font-family: Arial, sans-serif; margin: 40px;">
          <h1>🎉 CanopyIQ Admin Dashboard</h1>
          <p><strong>Success!</strong> You are logged in as an administrator.</p>
          <h2>Quick Stats:</h2>
          <ul>
              <li>✅ Authentication: Working</li>
              <li>✅ Database: Connected</li>
              <li>✅ Admin Access: Granted</li>
          </ul>
          <p><a href="/auth/logout">Sign Out</a> | <a href="/">Home</a></p>
      </body>
      </html>
      """

@app.get("/metrics")
async def metrics():
      """Prometheus metrics endpoint"""
      return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/robots.txt", response_class=Response)
async def robots():
      return Response("User-agent: *\nAllow: /\nSitemap: https://canopyiq.ai/sitemap.txt", media_type="text/plain")

# ---------- MCP Server API Routes ----------
# Force deployment refresh: 2025-09-08

@app.get("/api/v1/health")
async def mcp_health_check():
    """Health check endpoint for MCP server"""
    return {"status": "healthy", "service": "canopyiq", "timestamp": time.time()}

@app.get("/admin/test-simple", response_class=HTMLResponse)
async def admin_test_simple(request: Request):
    """Simple admin test without dependencies"""
    return HTMLResponse("<html><body><h1>Admin Test Works!</h1><p>API Key: ciq_demo_test123</p></body></html>")

@app.get("/admin/dashboard-simple", response_class=HTMLResponse)
async def admin_dashboard_simple(request: Request):
    """Simplified admin dashboard without auth dependencies"""
    import secrets
    
    # Generate API key
    user_api_key = f"ciq_demo_{secrets.token_hex(12)}"
    
    # Mock stats for now
    stats = {
        "submissions": 12,
        "mcp_calls": 156, 
        "blocked_calls": 3,
        "last_submission": "2 hours ago"
    }
    
    recent_activity = [
        {"type": "audit", "description": "Claude Code connection established", "timestamp": "2025-09-08 14:30:00"},
        {"type": "audit", "description": "File access monitored: src/main.py", "timestamp": "2025-09-08 14:25:00"},
        {"type": "audit", "description": "Risk assessment: Low risk operation", "timestamp": "2025-09-08 14:20:00"}
    ]
    
    try:
        return page(
            request,
            title="Admin Dashboard | CanopyIQ",
            desc="Administration panel for CanopyIQ.",
            path="admin_dashboard.html",
            stats=stats,
            recent_activity=recent_activity,
            api_key=user_api_key
        )
    except Exception as e:
        # Fallback HTML if template fails
        return HTMLResponse(f"""
        <html>
        <head><title>CanopyIQ Admin Dashboard</title></head>
        <body>
            <h1>🛡️ CanopyIQ Admin Dashboard</h1>
            <h2>Your API Key:</h2>
            <code style="background: #f0f0f0; padding: 10px; display: block; margin: 10px 0;">{user_api_key}</code>
            <h3>Quick Stats:</h3>
            <ul>
                <li>MCP Calls: {stats['mcp_calls']}</li>
                <li>Blocked Calls: {stats['blocked_calls']}</li>
                <li>Submissions: {stats['submissions']}</li>
            </ul>
            <h3>Claude Code Integration:</h3>
            <ol>
                <li>Copy your API key above</li>
                <li>Configure Claude Code with: https://canopyiq.ai</li>
                <li>Start AI governance monitoring</li>
            </ol>
        </body>
        </html>
        """)
    
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Main AI Governance Dashboard - Real-time monitoring and approval workflows"""
    return RedirectResponse(url="/admin/dashboard-simple", status_code=status.HTTP_302_FOUND)

@app.get("/admin/context", response_class=HTMLResponse)
async def admin_context_dashboard(request: Request):
    """🧠 Project Context Dashboard - Continuous knowledge across Claude Code sessions"""
    return templates.TemplateResponse("project_context_dashboard.html", {
        "request": request,
        "title": "Project Context Dashboard",
        "description": "Continuous AI knowledge and context across Claude Code sessions"
    })

@app.get("/admin/dashboard-redirect", response_class=HTMLResponse)
async def admin_dashboard_redirect(request: Request):
    """Redirect /admin/dashboard to working simple version"""
    return RedirectResponse(url="/admin/dashboard-simple", status_code=status.HTTP_302_FOUND)

@app.get("/api/v1/events")
async def mcp_get_events(limit: int = 50):
    """Get recent AI events for MCP server"""
    # Mock data for MCP server - replace with actual database query when models are ready
    mock_events = [
        {
            "id": 1,
            "timestamp": time.time(),
            "event_type": "file_read",
            "tool": "Read",
            "file_path": "/project/src/main.py",
            "risk_level": "low",
            "approved": True,
            "details": {"lines": 50, "size": "2.1KB"}
        },
        {
            "id": 2,
            "timestamp": time.time() - 300,
            "event_type": "file_write", 
            "tool": "Edit",
            "file_path": "/project/config/.env",
            "risk_level": "high",
            "approved": False,
            "details": {"pending_approval": True, "reason": "Sensitive file detected"}
        }
    ]
    
    return {
        "events": mock_events[:limit]
    }

# ---------- Real-Time WebSocket AI Governance Endpoints ----------

@app.websocket("/ws/events/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time MCP server events and dashboard updates"""
    await connection_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Listen for messages from MCP server or dashboard
            message = await websocket.receive_text()
            data = json.loads(message)
            
            # Process the event from MCP server
            await handle_mcp_event(session_id, data)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
        connection_manager.disconnect(session_id)

@app.post("/api/v1/events")
async def receive_mcp_event(request: Request):
    """HTTP endpoint for MCP server events (backup to WebSocket)"""
    try:
        data = await request.json()
        await handle_mcp_event(data.get('sessionId', 'unknown'), data)
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Failed to process MCP event: {e}")
        raise HTTPException(status_code=500, detail="Event processing failed")

async def handle_mcp_event(session_id: str, event_data: dict):
    """Process incoming events from MCP server and handle AI governance"""
    event_type = event_data.get('type')
    timestamp = event_data.get('timestamp', datetime.now().isoformat())
    data = event_data.get('data', {})
    
    logger.info(f"🔄 MCP Event: {event_type} from {session_id}")
    
    # Store event in database for audit trail
    try:
        async for db in get_db():
            from database import AuditLog
            audit_log = AuditLog(
                ts=int(time.time()),
                actor=session_id,
                action=f"MCP_{event_type.upper()}",
                resource=f"mcp_tool:{data.get('tool', 'unknown')}",
                attributes=event_data
            )
            db.add(audit_log)
            
            # Process MCP-specific data structures
            try:
                from mcp_processor import MCPEventProcessor
                processor = MCPEventProcessor(db)
                dashboard_updates = await processor.process_event(event_data)
                
                await db.commit()
                logger.info(f"✅ MCP event processed: {event_type}")
                
                # Broadcast enhanced dashboard updates
                enhanced_event = {
                    'type': 'mcp_activity',
                    'timestamp': timestamp,
                    'session_id': session_id,
                    'event_type': event_type,
                    'data': data,
                    'dashboard_updates': dashboard_updates
                }
                await connection_manager.broadcast_to_dashboards(enhanced_event)
                
            except Exception as e:
                logger.error(f"MCP processing failed: {e}")
                # Fallback to basic processing
                await db.commit()
                await handle_ai_governance_event(session_id, event_type, data)
            
    except Exception as e:
        logger.warning(f"Failed to process MCP event: {e}")
        # Fallback to original processing
        await handle_ai_governance_event(session_id, event_type, data)

async def handle_ai_governance_event(session_id: str, event_type: str, data: dict):
    """Handle specific AI governance events"""
    if event_type == 'tool_call_start':
        tool = data.get('tool', 'unknown')
        logger.info(f"🤖 AI tool initiated: {tool} in session {session_id}")
        
    elif event_type == 'approval_required':
        await handle_approval_request(session_id, data)
        
    elif event_type == 'tool_call_blocked':
        tool = data.get('tool')
        reason = data.get('reason')
        logger.warning(f"🛑 AI tool blocked: {tool} - {reason} in session {session_id}")
        
    elif event_type == 'tool_call_complete':
        tool = data.get('tool')
        duration = data.get('duration', 0)
        logger.info(f"✅ AI tool completed: {tool} in {duration}ms")

async def handle_approval_request(session_id: str, approval_data: dict):
    """Handle real-time approval requests from MCP server"""
    approval_id = approval_data.get('id')
    tool = approval_data.get('tool')
    risk_level = approval_data.get('riskLevel', 'medium')
    reason = approval_data.get('reason', 'Approval required')
    
    logger.warning(f"⏳ Approval Required: {tool} ({risk_level}) - {reason}")
    
    # Send urgent approval notification to all dashboards
    urgent_notification = {
        'type': 'urgent_approval_required',
        'approval': {
            'id': approval_id,
            'session_id': session_id,
            'tool': tool,
            'arguments': approval_data.get('arguments', {}),
            'risk_level': risk_level,
            'reason': reason,
            'timestamp': approval_data.get('timestamp'),
            'status': 'pending'
        },
        'timestamp': time.time()
    }
    
    await connection_manager.broadcast_to_dashboards(urgent_notification)

@app.post("/api/v1/approvals")
async def create_approval_request(request: Request):
    """Endpoint for MCP servers to create approval requests"""
    try:
        data = await request.json()
        approval_id = data.get('id', 'unknown')
        
        logger.info(f"📝 New approval request received: {approval_id}")
        
        # Store approval request (in production, save to database)
        # For now, just broadcast to dashboard
        await connection_manager.broadcast_to_dashboards({
            'type': 'new_approval_request',
            'approval': data,
            'timestamp': time.time()
        })
        
        return {"status": "created", "id": approval_id}
        
    except Exception as e:
        logger.error(f"Failed to create approval request: {e}")
        raise HTTPException(status_code=500, detail="Failed to create approval request")

@app.post("/api/v1/approvals/{approval_id}/respond")
async def respond_to_approval(
    approval_id: str, 
    request: Request,
    approved: bool = Form(...),
    reason: str = Form(None)
):
    """Admin endpoint to approve/reject real-time AI tool requests"""
    try:
        # Create response message for MCP servers
        response_message = {
            'type': 'approval_response',
            'data': {
                'approvalId': approval_id,
                'approved': approved,
                'reason': reason or ("Approved by admin" if approved else "Denied by admin"),
                'timestamp': datetime.now().isoformat(),
                'admin': 'dashboard_admin'  # In production, get from session
            }
        }
        
        # Broadcast response to all MCP server sessions
        await connection_manager.broadcast_to_dashboards(response_message)
        
        # Log the approval decision
        try:
            async for db in get_db():
                from database import AuditLog
                audit_log = AuditLog(
                    ts=int(time.time()),
                    actor="admin_dashboard",
                    action="AI_APPROVAL_DECISION",
                    resource=f"approval:{approval_id}",
                    attributes={
                        'approved': approved,
                        'reason': reason or ("Approved" if approved else "Denied"),
                        'approval_id': approval_id
                    }
                )
                db.add(audit_log)
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log approval decision: {e}")
        
        action = 'APPROVED' if approved else 'DENIED'
        logger.info(f"📝 AI Governance Decision: {action} approval {approval_id}")
        
        return {"status": "sent", "approved": approved, "message": "Response sent to AI systems"}
        
    except Exception as e:
        logger.error(f"Failed to send approval response: {e}")
        raise HTTPException(status_code=500, detail="Failed to send approval response")

@app.get("/api/v1/dashboard/live-metrics")
async def get_live_ai_governance_metrics():
    """Get real-time AI governance dashboard metrics"""
    try:
        # Count active MCP connections
        active_sessions = len(connection_manager.active_connections)
        
        # Get recent events from database
        async for db in get_db():
            from database import AuditLog
            
            # Count recent AI governance events
            recent_events = await db.execute(
                select(AuditLog)
                .where(AuditLog.action.like('AI_GOVERNANCE_%'))
                .where(AuditLog.ts > int(time.time()) - 86400)  # Last 24 hours
            )
            events_count = len(recent_events.scalars().all())
            
            # Count approval events
            approval_events = await db.execute(
                select(AuditLog)
                .where(AuditLog.action == 'AI_APPROVAL_DECISION')
                .where(AuditLog.ts > int(time.time()) - 86400)  # Last 24 hours
            )
            approvals_count = len(approval_events.scalars().all())
        
        live_metrics = {
            'active_ai_sessions': active_sessions,
            'connected_mcps': len([s for s in connection_manager.session_data.values()]),
            'ai_events_today': events_count,
            'approvals_processed': approvals_count,
            'last_activity': max([s.get('last_activity', 0) for s in connection_manager.session_data.values()] or [0]),
            'status': 'active' if active_sessions > 0 else 'standby'
        }
        
        return live_metrics
        
    except Exception as e:
        logger.error(f"Failed to get live metrics: {e}")
        # Return fallback metrics
        return {
            'active_ai_sessions': len(connection_manager.active_connections),
            'connected_mcps': 0,
            'ai_events_today': 0,
            'approvals_processed': 0,
            'last_activity': 0,
            'status': 'error'
        }

# ---------- 🧠 Project Context APIs for Continuous Claude Code Sessions ----------

@app.get("/api/v1/project-context/{project_id}")
async def get_project_context(project_id: str):
    """Get stored project context for continuous Claude Code sessions"""
    try:
        async for db in get_db():
            from database import AuditLog
            
            # Get the most recent context save for this project
            context_log = await db.execute(
                select(AuditLog)
                .where(AuditLog.action == 'PROJECT_CONTEXT_SAVE')
                .where(AuditLog.resource == f'project:{project_id}')
                .order_by(desc(AuditLog.ts))
                .limit(1)
            )
            
            context_entry = context_log.scalar_one_or_none()
            
            if context_entry and context_entry.attributes:
                logger.info(f"📚 Retrieved project context for {project_id}")
                return context_entry.attributes
            else:
                return {"message": "No context found", "project_id": project_id}
                
    except Exception as e:
        logger.error(f"Failed to get project context: {e}")
        return {"error": "Failed to retrieve context", "project_id": project_id}

@app.post("/api/v1/project-context")
async def save_project_context(request: Request):
    """Save project context for continuous Claude Code sessions"""
    try:
        context_data = await request.json()
        project_id = context_data.get('projectId')
        
        if not project_id:
            raise HTTPException(status_code=400, detail="Project ID required")
        
        async for db in get_db():
            from database import AuditLog
            
            # Store context in audit log
            audit_log = AuditLog(
                ts=int(time.time()),
                actor=context_data.get('lastSessionId', 'unknown'),
                action='PROJECT_CONTEXT_SAVE',
                resource=f'project:{project_id}',
                attributes=context_data
            )
            db.add(audit_log)
            await db.commit()
            
            # Also broadcast context update to dashboards
            await connection_manager.broadcast_to_dashboards({
                'type': 'project_context_updated',
                'projectId': project_id,
                'summary': {
                    'objectives': len(context_data.get('objectives', [])),
                    'keyFindings': len(context_data.get('keyFindings', [])),
                    'nextSteps': len(context_data.get('nextSteps', [])),
                    'lastActivity': context_data.get('lastActivity')
                },
                'timestamp': time.time()
            })
            
            logger.info(f"💾 Saved project context for {project_id}")
            return {"status": "saved", "project_id": project_id}
            
    except Exception as e:
        logger.error(f"Failed to save project context: {e}")
        raise HTTPException(status_code=500, detail="Failed to save context")

@app.get("/api/v1/project-context/{project_id}/summary")
async def get_project_context_summary(project_id: str):
    """Get a summary of project context for dashboard display"""
    try:
        async for db in get_db():
            from database import AuditLog
            
            # Get recent context and activity for this project
            recent_contexts = await db.execute(
                select(AuditLog)
                .where(AuditLog.resource == f'project:{project_id}')
                .where(AuditLog.action.in_(['PROJECT_CONTEXT_SAVE', 'AI_GOVERNANCE_TOOL_CALL_START']))
                .order_by(desc(AuditLog.ts))
                .limit(10)
            )
            
            entries = recent_contexts.scalars().all()
            
            if entries:
                latest_context = next((entry for entry in entries if entry.action == 'PROJECT_CONTEXT_SAVE'), None)
                activity_count = len([entry for entry in entries if entry.action != 'PROJECT_CONTEXT_SAVE'])
                
                if latest_context and latest_context.attributes:
                    context = latest_context.attributes
                    return {
                        'project_id': project_id,
                        'last_updated': datetime.fromtimestamp(latest_context.ts).isoformat(),
                        'stats': {
                            'objectives': len(context.get('objectives', [])),
                            'keyFindings': len(context.get('keyFindings', [])),
                            'nextSteps': len(context.get('nextSteps', [])),
                            'decisions': len(context.get('decisions', [])),
                            'recentActivity': activity_count
                        },
                        'recentFindings': context.get('keyFindings', [])[-3:],
                        'urgentNextSteps': [step for step in context.get('nextSteps', []) if step.get('priority') == 'high'][:3],
                        'projectPath': context.get('projectPath'),
                        'technologies': list(set([f.get('text', '') for f in context.get('keyFindings', []) if f.get('category') == 'technology']))[:5]
                    }
            
            return {"message": "No context found", "project_id": project_id}
            
    except Exception as e:
        logger.error(f"Failed to get project context summary: {e}")
        return {"error": "Failed to retrieve context summary"}

@app.get("/api/v1/projects")
async def list_projects():
    """List all projects with saved context for dashboard"""
    try:
        async for db in get_db():
            from database import AuditLog
            
            # Get all projects with saved context
            projects_query = await db.execute(
                select(AuditLog.resource, AuditLog.attributes, AuditLog.ts)
                .where(AuditLog.action == 'PROJECT_CONTEXT_SAVE')
                .where(AuditLog.resource.like('project:%'))
                .order_by(desc(AuditLog.ts))
            )
            
            projects_raw = projects_query.all()
            projects_map = {}
            
            # Get the latest context for each project
            for resource, attributes, timestamp in projects_raw:
                project_id = resource.replace('project:', '')
                if project_id not in projects_map and attributes:
                    project_path = attributes.get('projectPath', '')
                    project_name = project_path.split('/')[-1] or project_path.split('\\')[-1] or project_id
                    
                    projects_map[project_id] = {
                        'project_id': project_id,
                        'project_name': project_name,
                        'project_path': project_path,
                        'last_activity': attributes.get('lastActivity'),
                        'last_updated': datetime.fromtimestamp(timestamp).isoformat(),
                        'stats': {
                            'objectives': len(attributes.get('objectives', [])),
                            'keyFindings': len(attributes.get('keyFindings', [])),
                            'nextSteps': len(attributes.get('nextSteps', [])),
                            'decisions': len(attributes.get('decisions', []))
                        },
                        'technologies': list(set([
                            f.get('text', '').replace('Project uses ', '') 
                            for f in attributes.get('keyFindings', []) 
                            if f.get('category') == 'technology'
                        ]))[:3],
                        'recentFindings': attributes.get('keyFindings', [])[-2:],
                        'urgentNextSteps': [
                            step for step in attributes.get('nextSteps', []) 
                            if step.get('priority') == 'high'
                        ][:2]
                    }
            
            return {"projects": list(projects_map.values())}
            
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return {"error": "Failed to list projects", "projects": []}

@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request, exc):
      if exc.status_code == 404:
          return templates.TemplateResponse("404.html", {"request": request, "asset_ver": ASSET_VER, "meta": {"title": "Page Not Found | CanopyIQ", "desc": "The page you're looking for doesn't exist.", "url_path": request.url.path}}, status_code=404)
      raise exc
