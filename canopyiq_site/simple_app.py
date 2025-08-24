# Minimal FastAPI app for Railway deployment debugging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import uvicorn

# Create minimal app
simple_app = FastAPI(title="CanopyIQ Simple")

@simple_app.get("/")
async def root():
    return {"message": "CanopyIQ is running!", "port": os.getenv("PORT", "unknown")}

@simple_app.get("/health")
async def health():
    return {"status": "ok", "service": "canopyiq"}

@simple_app.get("/healthz")  
async def healthz():
    return {"status": "ok", "service": "canopyiq"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(simple_app, host="0.0.0.0", port=port)