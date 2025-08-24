#!/usr/bin/env python3
"""
Railway startup script - tries main app, falls back to simple app if it fails
"""
import os
import sys
import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def try_main_app():
    """Try to start the main CanopyIQ app"""
    try:
        logger.info("Attempting to start main CanopyIQ application...")
        
        # Import test - if this fails, fall back to simple app
        from app import app
        logger.info("Main app import successful")
        
        port = os.environ.get("PORT", "8000")
        logger.info(f"Starting main app on port {port}")
        
        # Start with uvicorn
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=int(port))
        
    except Exception as e:
        logger.error(f"Main app failed to start: {e}")
        logger.info("Falling back to simple app...")
        return False
    
    return True

def start_simple_app():
    """Start the simple fallback app"""
    try:
        logger.info("Starting simple fallback app...")
        from simple_app import simple_app
        
        port = os.environ.get("PORT", "8000")
        logger.info(f"Starting simple app on port {port}")
        
        import uvicorn
        uvicorn.run(simple_app, host="0.0.0.0", port=int(port))
        
    except Exception as e:
        logger.error(f"Simple app also failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("CanopyIQ Railway startup script")
    
    # Try main app first
    if not try_main_app():
        # Fall back to simple app
        start_simple_app()