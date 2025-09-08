# 🛡️ CanopyIQ Claude Code Integration Guide

This guide shows you how to connect CanopyIQ's AI Code Governance platform to Claude Code for real-time monitoring and control.

## Prerequisites

1. **Claude Code** installed and working
2. **Node.js** 16+ installed
3. **CanopyIQ account** (get API key from http://localhost:8080/admin/mcp)

## Step 1: Install the CanopyIQ MCP Server

```bash
# Navigate to the mcp-server directory
cd mcp-server

# Install dependencies
npm install

# Test the server (optional)
npm start
```

## Step 2: Get Your CanopyIQ API Key

### Option A: Use Production CanopyIQ (Recommended)

1. **Visit CanopyIQ.ai:**
   - Go to: https://canopyiq.ai/admin/mcp
   - Sign up or login with your account
   - Navigate to the "Setup" tab
   - Copy your generated API key

### Option B: Local Development

1. **Start CanopyIQ Backend:**
   ```bash
   cd canopyiq_site
   python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload
   ```

2. **Get Your API Key:**
   - Visit: http://localhost:8080/admin/mcp
   - Login with admin credentials
   - Navigate to the "Setup" tab
   - Copy your generated API key

## Step 3: Configure Claude Code

### Find Your Claude Code Config File

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/claude/claude_desktop_config.json
```

### Add CanopyIQ MCP Server Configuration

Open `claude_desktop_config.json` and add this configuration:

### For Production CanopyIQ.ai (Recommended)
```json
{
  "mcpServers": {
    "canopyiq": {
      "command": "node",
      "args": [
        "C:/Users/amaci/Desktop/canopy/mcp-server/index.js",
        "--api-key", "YOUR_API_KEY_HERE",
        "--server-url", "https://canopyiq.ai"
      ]
    }
  }
}
```

### For Local Development
```json
{
  "mcpServers": {
    "canopyiq": {
      "command": "node",
      "args": [
        "C:/Users/amaci/Desktop/canopy/mcp-server/index.js",
        "--api-key", "YOUR_API_KEY_HERE",
        "--server-url", "http://localhost:8080"
      ]
    }
  }
}
```

**Replace:**
- `C:/Users/amaci/Desktop/canopy/mcp-server/index.js` with your actual path
- `YOUR_API_KEY_HERE` with the API key from Step 2
- Use `https://canopyiq.ai` for production or `http://localhost:8080` for local

### Alternative: Use the CLI Tool

```bash
# For production CanopyIQ.ai
node mcp-server/bin/cli.js --api-key YOUR_API_KEY_HERE --server-url https://canopyiq.ai

# For local development  
node mcp-server/bin/cli.js --api-key YOUR_API_KEY_HERE --server-url http://localhost:8080
```

## Step 4: Restart Claude Code

1. **Close Claude Code completely**
2. **Restart Claude Code**
3. **Verify connection** - you should see CanopyIQ logs in the console

## Step 5: Verify the Integration

### Test 1: Basic Connection
Open Claude Code and ask:
```
Can you help me create a simple Python file?
```

**Expected Result:**
- CanopyIQ dashboard at https://canopyiq.ai/admin/mcp shows "🟢 Live" connection status
- Real-time activity appears in the dashboard
- File access is tracked in "Recent File Access by AI"

### Test 2: Risk-Based Governance
Ask Claude Code to:
```
Can you read my .env file and help me understand the configuration?
```

**Expected Result:**
- CanopyIQ identifies this as "High Risk"  
- Approval modal appears in dashboard
- Admin can approve/reject the operation
- Claude Code waits for approval before proceeding

### Test 3: Context Continuity
1. **Work with Claude Code** on a project for a few minutes
2. **Close Claude Code completely**
3. **Restart Claude Code**
4. **Check the dashboard** - you should see:
   - Project context preserved
   - Objectives and next steps maintained
   - "🧠 AI Context Restored" notification

## Features You'll See

### 🛡️ AI Governance Dashboard
- **Live Metrics:** Files accessed, code changes, pending approvals
- **Real-time Monitoring:** Every Claude Code action tracked
- **Risk Assessment:** High/medium/low risk scoring
- **Instant Approvals:** 30-second modal popups for risky operations

### 🧠 Project Context Continuity  
- **Persistent Memory:** Context survives Claude Code restarts
- **Smart Objectives:** Extracted from code comments and patterns
- **Decision History:** Track all AI-assisted code decisions
- **Session Handoffs:** "Where you left off" summaries

### 🔄 Real-time Events
- **WebSocket Connection:** Live updates as you code
- **Activity Feed:** Real-time stream of AI actions
- **Approval Workflows:** Instant approve/reject for sensitive files
- **Pattern Recognition:** Learn your project's coding patterns

## Troubleshooting

### Connection Issues

**Problem:** "🔴 Offline" status in dashboard
**Solution:**
1. Check that CanopyIQ backend is running on port 8080
2. Verify API key is correct
3. Check console logs for errors

**Problem:** "Connection test failed" in MCP server logs
**Solution:**
1. Ensure `http://localhost:8080` is accessible
2. Check firewall settings
3. Try `curl http://localhost:8080/health`

### MCP Server Not Starting

**Problem:** Claude Code doesn't show MCP connection
**Solution:**
1. Check claude_desktop_config.json syntax is valid
2. Verify file paths are absolute and correct
3. Check Node.js version (requires 16+)
4. Look at Claude Code logs for error messages

### Permission Issues

**Problem:** "EACCES" or permission denied errors
**Solution:**
1. Run with proper permissions
2. Check that mcp-server directory is readable
3. Try running CLI tool directly first

## Advanced Configuration

### Custom Risk Patterns

Edit `mcp-server/index.js` to customize risk patterns:

```javascript
this.riskPatterns = {
  highRisk: [
    /\.env/i, 
    /secrets?/i, 
    /api[_-]?keys?/i,
    // Add your custom patterns here
  ]
};
```

### Approval Timeouts

Change the approval timeout (default 30 seconds):

```javascript
// In requestRealTimeApproval method
const timeout = setTimeout(() => {
  // Change 30000 to your desired timeout in milliseconds
}, 30000);
```

### Custom Policies

Add custom governance policies:

```javascript
// In getDefaultPolicies method
{
  id: 'custom-policy',
  name: 'Custom Security Rule',
  rules: [
    { pattern: /your-custom-pattern/i, action: 'block' }
  ]
}
```

## Next Steps

1. **Explore the Dashboard:** Visit http://localhost:8080/admin/mcp
2. **Monitor AI Activity:** Watch real-time events as you code with Claude
3. **Test Approvals:** Try accessing sensitive files to see approval workflows
4. **Check Project Memory:** Close/restart Claude Code to see context continuity
5. **Customize Policies:** Modify risk patterns for your specific needs

## Support

- **Dashboard:** http://localhost:8080/admin/mcp
- **Setup Guide:** http://localhost:8080/admin/mcp  
- **Activity Logs:** http://localhost:8080/admin/audit
- **Issues:** https://github.com/amacisaac222/sandbox_canopy/issues

---

**🎉 Congratulations!** You now have enterprise-grade AI Code Governance with Claude Code integration!