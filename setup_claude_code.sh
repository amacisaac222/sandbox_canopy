#!/bin/bash

echo "🛡️ CanopyIQ Claude Code Quick Setup"
echo

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 16+ first."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js found: $(node --version)"
echo

# Navigate to MCP server directory
if [ ! -f "mcp-server/package.json" ]; then
    echo "❌ MCP server files not found. Please run from the CanopyIQ project root."
    exit 1
fi

cd mcp-server
echo "📦 Installing MCP server dependencies..."
if ! npm install; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo

# Start CanopyIQ backend in background
cd ../canopyiq_site
echo "🚀 Starting CanopyIQ backend..."
python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload &
BACKEND_PID=$!

# Wait for server to start
echo "Waiting for backend to start..."
sleep 5

# Test the connection
cd ..
echo "🧪 Testing MCP server connection..."
node test_mcp_connection.js

echo
echo "🎉 Setup complete!"
echo
echo "📋 Next Steps:"
echo "1. Get your API key from:"
echo "   https://canopyiq.ai/admin/mcp"
echo "   (For local development: http://localhost:8080/admin/mcp)"
echo "2. Copy the example configuration below:"
echo
echo "Production Configuration (Recommended):"
echo "{"
echo '  "mcpServers": {'
echo '    "canopyiq": {'
echo '      "command": "node",'
echo '      "args": ['
echo "        \"$(pwd)/mcp-server/index.js\","
echo '        "--api-key", "YOUR_API_KEY_HERE",'
echo '        "--server-url", "https://canopyiq.ai"'
echo '      ]'
echo '    }'
echo '  }'
echo "}"
echo
echo "Local Development Configuration:"
echo "{"
echo '  "mcpServers": {'
echo '    "canopyiq": {'
echo '      "command": "node",'
echo '      "args": ['
echo "        \"$(pwd)/mcp-server/index.js\","
echo '        "--api-key", "YOUR_API_KEY_HERE",'
echo '        "--server-url", "http://localhost:8080"'
echo '      ]'
echo '    }'
echo '  }'
echo "}"
echo
echo "3. Add this to your Claude Code config file at:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   ~/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "   ~/.config/claude/claude_desktop_config.json"
fi
echo "4. Restart Claude Code"
echo
echo "Backend is running with PID: $BACKEND_PID"
echo "Press Ctrl+C to stop the backend server"
echo