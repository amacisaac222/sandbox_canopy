"""
Simple production CanopyIQ application
This version starts reliably with minimal dependencies and gradually adds features
"""
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CanopyIQ", 
    description="AI Agent Runtime Security",
    version="1.0.0"
)

# Mount static files safely
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✓ Static files mounted")
except Exception as e:
    logger.warning(f"Static files not available: {e}")

try:
    app.mount("/documentation", StaticFiles(directory="static/docs", html=True), name="documentation")  
    logger.info("✓ Documentation mounted")
except Exception as e:
    logger.warning(f"Documentation not available: {e}")

try:
    templates = Jinja2Templates(directory="templates")
    logger.info("✓ Templates loaded")
except Exception as e:
    logger.warning(f"Templates not available: {e}")
    templates = None

# Helper for page rendering
def page(request: Request, *, title: str, desc: str, path: str, **ctx):
    if templates is None:
        return HTMLResponse(f"<h1>{title}</h1><p>{desc}</p>")
    
    try:
        return templates.TemplateResponse(path, {
            "request": request,
            "meta": {
                "title": title,
                "desc": desc,
                "url_path": request.url.path
            },
            "asset_ver": "2025-08-26-simple",
            "user": None,
            **ctx
        })
    except Exception as e:
        logger.error(f"Template error for {path}: {e}")
        return HTMLResponse(f"<h1>{title}</h1><p>{desc}</p>")

# Health checks
@app.get("/health")
async def health():
    return {"ok": True, "service": "canopyiq", "version": "simple-production", "status": "healthy"}

@app.get("/healthz") 
async def healthz():
    return {"status": "ok"}

# Main routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return page(
        request,
        title="CanopyIQ - AI Agent Runtime Security",
        desc="Enterprise-grade security and policy enforcement for AI agents.",
        path="home.html"
    )

@app.get("/product", response_class=HTMLResponse)
async def product(request: Request):
    return page(
        request,
        title="Product | CanopyIQ",
        desc="Complete AI agent security platform with sandboxing and policy enforcement.",
        path="product.html"
    )

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return page(
        request,
        title="Pricing | CanopyIQ",
        desc="Simple, transparent pricing for CanopyIQ.",
        path="pricing.html"
    )

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return page(
        request,
        title="Contact | CanopyIQ",
        desc="Get in touch with our team.",
        path="contact.html"
    )

@app.post("/contact")
async def submit_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(...),
    message: str = Form(...)
):
    # Log the contact submission for now
    logger.info(f"Contact submission: {email} from {company}")
    logger.info(f"Message: {message[:100]}...")
    
    return RedirectResponse(url="/contact?success=1", status_code=302)

# Authentication pages (temporary)
@app.get("/auth/login", response_class=HTMLResponse)
async def login(request: Request):
    return page(
        request,
        title="Login | CanopyIQ",
        desc="CanopyIQ Login",
        path="local_login.html" if templates else None
    ) if templates else HTMLResponse("""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
    <h1>CanopyIQ Authentication</h1>
    <div style="background: #f0f8ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h3>🚀 System Status: Online</h3>
        <p>The CanopyIQ application is running successfully!</p>
        <p>Authentication system is being configured with PostgreSQL database integration.</p>
    </div>
    <div style="background: #f9f9f9; padding: 15px; border-radius: 8px;">
        <h4>Next Steps:</h4>
        <ul>
            <li>Database tables will be created automatically</li>
            <li>Admin user creation will be available once database is connected</li>
            <li>Full authentication features will be enabled</li>
        </ul>
    </div>
    <p><a href="/" style="color: #007bff;">← Back to Home</a></p>
    </body></html>
    """)

# 404 handler
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return HTMLResponse("""
    <html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
    <h1>404 - Page Not Found</h1>
    <p>The page you're looking for doesn't exist.</p>
    <a href="/" style="color: #007bff;">← Go Home</a>
    </body></html>
    """, status_code=404)

@app.on_event("startup")
async def startup_event():
    """Simple startup with minimal dependencies"""
    logger.info("🚀 Starting CanopyIQ Simple Production App")
    logger.info(f"✓ FastAPI app initialized")
    logger.info(f"✓ Health endpoints available") 
    logger.info(f"✓ Basic routes configured")
    
    # Check environment
    db_url = os.getenv("CP_DB_URL", "Not configured")
    logger.info(f"Database URL: {db_url[:50]}..." if len(db_url) > 50 else f"Database URL: {db_url}")
    
    if os.path.exists("static"):
        logger.info("✓ Static files directory found")
    else:
        logger.warning("⚠ Static files directory not found")
        
    if os.path.exists("templates"):
        logger.info("✓ Templates directory found")
    else:
        logger.warning("⚠ Templates directory not found")
        
    logger.info("🎉 CanopyIQ startup completed successfully")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)