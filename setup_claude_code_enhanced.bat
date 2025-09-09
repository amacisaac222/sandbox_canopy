@echo off
setlocal enabledelayedexpansion

REM CanopyIQ Smart Installer for Windows
REM Enhanced version with automatic config management

echo.
echo =======================================================
echo   CanopyIQ MCP Server Smart Installer (Windows)
echo =======================================================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed
    echo Please install Node.js from: https://nodejs.org
    echo.
    pause
    exit /b 1
)

echo [INFO] Node.js found: 
node --version

REM Detect Claude config path
set "CLAUDE_CONFIG=%APPDATA%\Claude\claude_desktop_config.json"
echo [INFO] Claude config location: %CLAUDE_CONFIG%

REM Check if NPM package is installed
canopyiq-mcp-server --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing CanopyIQ MCP server package...
    npm install -g canopyiq-mcp-server
    if errorlevel 1 (
        echo [ERROR] Failed to install NPM package
        echo Please try manually: npm install -g canopyiq-mcp-server
        pause
        exit /b 1
    )
    echo [SUCCESS] NPM package installed successfully
) else (
    echo [SUCCESS] CanopyIQ MCP server already installed
)

REM Get API key from user
echo.
echo Get your API key from: https://canopyiq.ai/admin/mcp
echo.
set /p "API_KEY=Enter your CanopyIQ API key: "

if "%API_KEY%"=="" (
    echo [ERROR] API key is required
    pause
    exit /b 1
)

REM Create backup if config exists
if exist "%CLAUDE_CONFIG%" (
    set "BACKUP_PATH=%CLAUDE_CONFIG%.backup.%DATE:~-4%-%DATE:~4,2%-%DATE:~7,2%_%TIME:~0,2%-%TIME:~3,2%-%TIME:~6,2%"
    copy "%CLAUDE_CONFIG%" "!BACKUP_PATH!" >nul
    echo [SUCCESS] Backup created: !BACKUP_PATH!
)

REM Create config directory if it doesn't exist
if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"

REM Use Node.js to merge configuration
echo [INFO] Updating Claude Code configuration...

node -e "
const fs = require('fs');
const path = '%CLAUDE_CONFIG%'.replace(/\\\\/g, '/');

let config = {};
try {
    if (fs.existsSync(path)) {
        config = JSON.parse(fs.readFileSync(path, 'utf8'));
    }
} catch (e) {
    console.log('Creating new config file...');
}

if (!config.mcpServers) {
    config.mcpServers = {};
}

config.mcpServers.canopyiq = {
    command: 'canopyiq-mcp-server',
    args: ['--api-key', '%API_KEY%', '--server-url', 'https://canopyiq.ai']
};

fs.writeFileSync(path, JSON.stringify(config, null, 2));
console.log('[SUCCESS] Configuration updated successfully');
"

if errorlevel 1 (
    echo [ERROR] Failed to update configuration
    pause
    exit /b 1
)

REM Validate installation
echo [INFO] Validating installation...
canopyiq-mcp-server --help >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Validation failed - MCP server not working
    pause
    exit /b 1
)

if not exist "%CLAUDE_CONFIG%" (
    echo [ERROR] Configuration file was not created
    pause
    exit /b 1
)

echo [SUCCESS] Installation validated successfully

REM Display final instructions
echo.
echo ============================================================
echo   CanopyIQ MCP Server Installation Complete!
echo ============================================================
echo.
echo Next Steps:
echo 1. Restart Claude Code completely (close and reopen)
echo 2. Look for "CanopyIQ" in your available tools  
echo 3. Visit https://canopyiq.ai/dashboard to monitor activity
echo.
echo Configuration Location:
echo    %CLAUDE_CONFIG%
echo.
echo Need Help?
echo    • Documentation: https://canopyiq.ai/documentation
echo    • Support: https://canopyiq.ai/contact
echo.

pause