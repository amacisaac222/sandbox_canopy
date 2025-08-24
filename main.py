# Railway/Nixpacks entry point
# Redirects to the actual FastAPI app in canopyiq_site/
import subprocess
import sys
import os

if __name__ == "__main__":
    # Change to the canopyiq_site directory and run the app
    os.chdir("canopyiq_site")
    subprocess.run([sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "8000")])