"""
Production-safe CanopyIQ application that starts without dependencies
"""
from fastapi import FastAPI, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create app with minimal dependencies
app = FastAPI(
    title="CanopyIQ", 
    description="AI Agent Runtime Security",
    version="1.0.0"
)

# Mount static files - this should work without database
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/documentation", StaticFiles(directory="static/docs", html=True), name="documentation")
    templates = Jinja2Templates(directory="templates")
    logger.info("Static files and templates mounted successfully")
except Exception as e:
    logger.error(f"Failed to mount static files: {e}")
    # Create minimal fallback
    templates = None

# Health endpoint
@app.get("/health")
async def health():
    return {"ok": True, "service": "canopyiq", "version": "production", "status": "healthy"}

@app.get("/healthz") 
async def healthz():
    return {"status": "ok"}

# Helper function for page rendering
def page(request: Request, *, title: str, desc: str, path: str, **ctx):
    """Render page with metadata"""
    if templates is None:
        return HTMLResponse("<h1>CanopyIQ</h1><p>Static files not available</p>")
    
    return templates.TemplateResponse(path, {
        "request": request,
        "meta": {
            "title": title,
            "desc": desc,
            "url_path": request.url.path
        },
        "asset_ver": "2025-08-24-prod",
        "user": None,  # No authentication yet
        **ctx
    })

# Main routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        return page(
            request,
            title="CanopyIQ - AI Agent Runtime Security",
            desc="Enterprise-grade security and policy enforcement for AI agents.",
            path="home.html"
        )
    except Exception as e:
        logger.error(f"Home page error: {e}")
        return HTMLResponse("<h1>CanopyIQ</h1><p>AI Agent Runtime Security</p>")

@app.get("/product", response_class=HTMLResponse)
async def product(request: Request):
    try:
        return page(
            request,
            title="Product | CanopyIQ",
            desc="Complete AI agent security platform with sandboxing and policy enforcement.",
            path="product.html"
        )
    except Exception as e:
        logger.error(f"Product page error: {e}")
        return HTMLResponse("<h1>Product</h1><p>CanopyIQ Product Information</p>")

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    try:
        return page(
            request,
            title="Contact | CanopyIQ",
            desc="Get in touch with our team.",
            path="contact.html"
        )
    except Exception as e:
        return HTMLResponse("<h1>Contact</h1><p>Contact CanopyIQ</p>")

@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    try:
        return page(
            request,
            title="FAQ | CanopyIQ",
            desc="Frequently asked questions about CanopyIQ.",
            path="faq.html"
        )
    except Exception as e:
        return HTMLResponse("<h1>FAQ</h1><p>CanopyIQ FAQ</p>")

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    try:
        return page(
            request,
            title="Pricing | CanopyIQ",
            desc="Simple, transparent pricing for CanopyIQ.",
            path="pricing.html"
        )
    except Exception as e:
        return HTMLResponse("<h1>Pricing</h1><p>CanopyIQ Pricing</p>")

@app.get("/auth/login", response_class=HTMLResponse)
async def login(request: Request):
    return HTMLResponse("""
    <html><body>
    <h1>CanopyIQ Login</h1>
    <p>Authentication features will be available once the database is configured.</p>
    <a href="/">← Back to Home</a>
    </body></html>
    """)

# Fallback 404 handler
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return HTMLResponse("""
    <html><body>
    <h1>Page Not Found</h1>
    <p>The page you're looking for doesn't exist.</p>
    <a href="/">← Go Home</a>
    </body></html>
    """, status_code=404)

@app.on_event("startup")
async def startup_event():
    """Production-safe startup"""
    logger.info("Starting CanopyIQ production application")
    logger.info("✓ Basic FastAPI app initialized")
    logger.info("✓ Health endpoints available")
    
    # Test static files
    if os.path.exists("static"):
        logger.info("✓ Static files directory found")
    else:
        logger.warning("⚠ Static files directory not found")
        
    if os.path.exists("static/docs"):
        logger.info("✓ Documentation directory found")
    else:
        logger.warning("⚠ Documentation directory not found")
        
    logger.info("CanopyIQ production startup completed successfully")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)