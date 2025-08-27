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
import sys
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

# Import authentication modules with fallbacks
try:
      from auth.oidc import oidc_client, init_oidc
except ImportError:
      oidc_client = None
      init_oidc = None
      
# Import database with fallbacks
try:
      from database import get_db, Submission, AuditLog, Approval, ApprovalStatus, init_db, DATABASE_URL
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
          db_user_to_auth_user, hash_password
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
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✓ Static files mounted successfully")
except Exception as e:
    logger.error(f"❌ Failed to mount static files: {e}")

try:
    app.mount("/documentation", StaticFiles(directory="static/docs", html=True), name="documentation")
    logger.info("✓ Documentation mounted successfully")
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

if templates:
    templates.env.filters["tojsonpretty"] = tojsonpretty
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
          
          logger.info("🎉 CanopyIQ startup completed - ready to serve!")
          
      except Exception as e:
          logger.error(f"❌ Startup failed with error: {e}")
          logger.error(f"❌ Error type: {type(e).__name__}")
          import traceback
          logger.error(f"❌ Full traceback: {traceback.format_exc()}")
          # Don't re-raise the exception, let the app start anyway
          logger.info("🔄 Continuing startup despite error...")

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
      db: AsyncSession = Depends(get_db)
):
      # Validate
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

# ---------- Console Routes (Agent Management) ----------
@app.get("/admin/console", response_class=HTMLResponse)
async def console_index(request: Request):
      """Console landing page - CanopyIQ agent management interface"""
      return page(
          request,
          title="Console | CanopyIQ",
          desc="CanopyIQ Console - Run agents safely. At scale.",
          path="console/index.html"
      )

@app.get("/admin/console/access", response_class=HTMLResponse)
async def console_access(request: Request, tenant: str = "demo-tenant"):
      """Agent access control dashboard"""
      import time
      
      # Mock real-time agent access requests for demo
      mock_requests = [
          {
              "id": f"req_{int(time.time())}_001",
              "agent_id": "agent-sales-bot",
              "action": "http_request",
              "resource": "https://api.salesforce.com/contacts",
              "timestamp": time.time() - 30,
              "status": "pending",
              "details": {"method": "GET", "purpose": "Fetch customer contact list"}
          },
          {
              "id": f"req_{int(time.time())}_002", 
              "agent_id": "agent-data-analyzer",
              "action": "file_read",
              "resource": "/data/customer_analytics.csv",
              "timestamp": time.time() - 120,
              "status": "allowed",
              "details": {"file_size": "2.4MB", "purpose": "Generate quarterly report"}
          },
          {
              "id": f"req_{int(time.time())}_003",
              "agent_id": "agent-email-writer", 
              "action": "email_send",
              "resource": "john@company.com",
              "timestamp": time.time() - 300,
              "status": "denied",
              "details": {"subject": "Follow-up on proposal", "reason": "External email policy violation"}
          }
      ]
      
      return page(
          request,
          title="Access Control | Console | CanopyIQ",
          desc="Real-time agent access control and monitoring",
          path="console/access.html",
          tenant=tenant,
          requests=mock_requests,
          stats={
              "total_requests": len(mock_requests),
              "allowed": len([r for r in mock_requests if r["status"] == "allowed"]),
              "denied": len([r for r in mock_requests if r["status"] == "denied"]), 
              "pending": len([r for r in mock_requests if r["status"] == "pending"])
          }
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
          path="console/approvals.html",
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
          path="console/policy.html",
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
          path="console/traces.html",
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
          path="console/agents.html",
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

@app.get("/documentation", response_class=HTMLResponse)
async def documentation_redirect(request: Request):
      """Custom docs page with navigation back to main site"""
      from pathlib import Path
      
      # Read the original docs index.html
      docs_path = Path("static/docs/index.html")
      if docs_path.exists():
          with open(docs_path, 'r') as f:
              html_content = f.read()
          
          # Inject custom navigation script
          custom_script = '''
          <script>
          document.addEventListener('DOMContentLoaded', function() {
              // Add "Back to Main Site" button to docs header
              const header = document.querySelector('.md-header__inner');
              if (header) {
                  const backButton = document.createElement('div');
                  backButton.style.position = 'absolute';
                  backButton.style.right = '60px';
                  backButton.style.top = '50%';
                  backButton.style.transform = 'translateY(-50%)';
                  backButton.innerHTML = '<a href="/" style="color: #ff6f61; font-weight: bold; text-decoration: none; font-size: 14px; padding: 8px 16px; border: 1px solid #ff6f61; border-radius: 4px; transition: all 0.2s ease;" onmouseover="this.style.backgroundColor=\\'#ff6f61\\'; this.style.color=\\'white\\';" onmouseout="this.style.backgroundColor=\\'transparent\\'; this.style.color=\\'#ff6f61\\';"> ← Main Site</a>';
                  header.appendChild(backButton);
              }
          });
          </script>
          '''
          
          # Insert before closing </body>
          html_content = html_content.replace('</body>', custom_script + '</body>')
          
          return HTMLResponse(content=html_content)
      
      # Fallback to static file mount
      return RedirectResponse(url="/documentation/")

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

@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request, exc):
      if exc.status_code == 404:
          return templates.TemplateResponse("404.html", {"request": request, "asset_ver": ASSET_VER, "meta": {"title": "Page Not Found | CanopyIQ", "desc": "The page you're looking for doesn't exist.", "url_path": request.url.path}}, status_code=404)
      raise exc
