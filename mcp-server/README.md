# CanopyIQ MCP Server

**Enterprise AI governance for Claude Code** - Add security, monitoring, and approval workflows to your AI development workflow.

[![NPM Version](https://img.shields.io/npm/v/@canopyiq/mcp-server.svg)](https://www.npmjs.com/package/@canopyiq/mcp-server)
[![Node.js](https://img.shields.io/node/v/@canopyiq/mcp-server.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🛡️ What This Does

Transform Claude Code into a secure, enterprise-ready AI assistant with:

- **🔍 Real-time Monitoring** - Every tool call logged and analyzed
- **⚡ Smart Approvals** - Human-in-the-loop for risky operations  
- **📊 Live Dashboard** - See AI usage patterns across your team
- **🧠 Context Continuity** - Projects remembered across sessions
- **🚨 Policy Enforcement** - Custom security rules and guardrails

## 🚀 Quick Start

### 1. Install via npm

```bash
npm install -g @canopyiq/mcp-server
```

### 2. Get your API key

Visit [canopyiq.ai/admin/mcp](https://canopyiq.ai/admin/mcp) to get your API key.

### 3. Add to Claude Code configuration

**macOS/Linux:**
```bash
~/.config/claude/claude_desktop_config.json
```

**Windows:**
```bash
%APPDATA%\Claude\claude_desktop_config.json
```

Add this configuration:

```json
{
  "mcpServers": {
    "canopyiq": {
      "command": "canopyiq-mcp-server",
      "args": ["--api-key", "your-api-key-here", "--server-url", "https://canopyiq.ai"]
    }
  }
}
```

### 4. Restart Claude Code

You'll now see AI governance in action! 🎉

## 🚀 Quick Start

### 1. Install
```bash
npm install -g canopyiq-mcp-server
```

### 2. Get API Key
Sign up at [canopyiq.ai/signup](https://canopyiq.ai/signup) to get your personal API key.

### 3. Configure Claude Desktop
Add to your `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "canopyiq": {
      "command": "canopyiq-mcp-server",
      "args": ["--api-key", "your_canopyiq_api_key_here"]
    }
  }
}
```

### 4. Restart Claude Desktop
Your tools are now secured! Visit [canopyiq.ai/dashboard](https://canopyiq.ai/dashboard) to monitor activity.

## ✨ What You Get

- **🔍 Complete Audit Trail:** Every tool call logged with context
- **👨‍💼 Human Approval Workflows:** Require approval for risky actions  
- **🚨 Real-time Alerts:** Slack/email notifications on policy violations
- **📊 Usage Analytics:** Monitor agent behavior and performance
- **🛑 Emergency Controls:** Kill switches and rate limiting

## 🔧 Advanced Configuration

```bash
# Custom server URL
canopyiq-mcp-server --api-key your_key --server-url https://your-canopyiq-instance.com

# Debug mode
canopyiq-mcp-server --api-key your_key --debug

# Help
canopyiq-mcp-server --help
```

## 📚 Documentation

- **Setup Guide:** [canopyiq.ai/documentation](https://canopyiq.ai/documentation)
- **API Reference:** [canopyiq.ai/docs/api](https://canopyiq.ai/docs/api)
- **Support:** [canopyiq.ai/contact](https://canopyiq.ai/contact)

## 🎯 Perfect For

- Developers using Claude Code
- Teams with custom MCP tools  
- Companies needing compliance logs
- Anyone wanting agent oversight

## 📋 Requirements

- Node.js 16+ 
- Claude Desktop
- CanopyIQ account

## 🤝 Support

- **Issues:** [GitHub Issues](https://github.com/amacisaac222/sandbox_canopy/issues)
- **Email:** [support@canopyiq.ai](mailto:support@canopyiq.ai)
- **Community:** [CanopyIQ Discord](https://discord.gg/canopyiq)

---

**Made with ❤️ by the CanopyIQ team**

🌐 **Website:** [canopyiq.ai](https://canopyiq.ai)  
🐙 **GitHub:** [github.com/amacisaac222/sandbox_canopy](https://github.com/amacisaac222/sandbox_canopy)