# CanopyIQ MCP Server

🛡️ **Secure your Claude Desktop tools with CanopyIQ's AI Agent Security Platform**

The CanopyIQ MCP (Model Control Protocol) server adds security, logging, and approval workflows to your Claude Desktop tools without changing any code.

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