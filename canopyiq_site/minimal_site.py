"""
Minimal CanopyIQ site with static templates - no complex dependencies
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

# Create minimal app
app = FastAPI(title="CanopyIQ", description="AI Agent Runtime Security")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helper function for page rendering
def page(request: Request, *, title: str, desc: str, path: str, **ctx):
    """Render page with metadata"""
    return templates.TemplateResponse(path, {
        "request": request,
        "meta": {
            "title": title,
            "desc": desc,
            "url_path": request.url.path
        },
        "asset_ver": "2025-08-20-1",
        "user": None,  # No authentication for now
        **ctx
    })

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return page(
        request,
        title="CanopyIQ - AI Agent Runtime Security",
        desc="Enterprise-grade security and policy enforcement for AI agents. Sandbox every action, enforce policies at scale, and maintain compliance across your AI fleet.",
        path="home.html"
    )

@app.get("/product", response_class=HTMLResponse)
async def product(request: Request):
    return page(
        request,
        title="Product | CanopyIQ",
        desc="Complete AI agent security platform with sandboxing, policy enforcement, audit trails, and enterprise compliance features.",
        path="product.html"
    )

@app.get("/contact", response_class=HTMLResponse) 
async def contact(request: Request):
    return page(
        request,
        title="Contact | CanopyIQ",
        desc="Get in touch with our team to learn how CanopyIQ can secure your AI agents and ensure compliance at enterprise scale.",
        path="contact.html"
    )

@app.get("/faq", response_class=HTMLResponse)
async def faq(request: Request):
    return page(
        request,
        title="FAQ | CanopyIQ", 
        desc="Frequently asked questions about CanopyIQ's AI agent security platform, deployment, and enterprise features.",
        path="faq.html"
    )

@app.get("/documentation", response_class=HTMLResponse)
async def documentation(request: Request):
    return page(
        request,
        title="Documentation | CanopyIQ",
        desc="Complete documentation for CanopyIQ's AI agent security platform.",
        path="docs.html"
    )

@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return page(
        request,
        title="Pricing | CanopyIQ",
        desc="Simple, transparent pricing for CanopyIQ's enterprise AI security platform.",
        path="pricing.html"
    )

@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return page(
        request,
        title="Terms of Service | CanopyIQ",
        desc="Terms of service for CanopyIQ's AI agent security platform.",
        path="terms.html"
    )

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return page(
        request,
        title="Privacy Policy | CanopyIQ",
        desc="Privacy policy for CanopyIQ's AI agent security platform.",
        path="privacy.html"
    )

# Health endpoints
@app.get("/health")
async def health():
    return {"status": "ok", "service": "canopyiq", "version": "minimal"}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "canopyiq", "version": "minimal"}

# Fallback for missing templates
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse("404.html", {
        "request": request,
        "meta": {
            "title": "Page Not Found | CanopyIQ",
            "desc": "The page you're looking for could not be found.",
            "url_path": request.url.path
        }
    }, status_code=404)