@echo off
echo 🛡️ CanopyIQ Claude Code Quick Setup
echo.

:: Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Please install Node.js 16+ first.
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)

echo ✅ Node.js found
echo.

:: Navigate to MCP server directory
cd mcp-server
if not exist package.json (
    echo ❌ MCP server files not found. Please run from the CanopyIQ project root.
    pause
    exit /b 1
)

echo 📦 Installing MCP server dependencies...
call npm install
if %errorlevel% neq 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed
echo.

:: Start CanopyIQ backend in background
cd ../canopyiq_site
echo 🚀 Starting CanopyIQ backend...
start "CanopyIQ Backend" cmd /k "python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload"

:: Wait a moment for server to start
echo Waiting for backend to start...
timeout /t 5 > nul

:: Test the connection
cd ..
echo 🧪 Testing MCP server connection...
node test_mcp_connection.js

echo.
echo 🎉 Setup complete!
echo.
echo 📋 Next Steps:
echo 1. Get your API key from: http://localhost:8080/admin/dashboard
echo 2. Copy the example configuration below:
echo.
echo {
echo   "mcpServers": {
echo     "canopyiq": {
echo       "command": "node",
echo       "args": [
echo         "%cd%\\mcp-server\\index.js",
echo         "--api-key", "YOUR_API_KEY_HERE",
echo         "--server-url", "http://localhost:8080"
echo       ]
echo     }
echo   }
echo }
echo.
echo 3. Add this to your Claude Code config file at:
echo    %APPDATA%\Claude\claude_desktop_config.json
echo 4. Restart Claude Code
echo.
pause