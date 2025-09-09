# CanopyIQ Setup

**Smart installer for CanopyIQ MCP server** - automatically configures Claude Code with AI governance.

## 🚀 One-Line Install

```bash
npx canopyiq-setup
```

## What This Does

✅ **Installs** the `canoryiq-mcp-server` NPM package globally  
✅ **Auto-detects** your Claude Code configuration location  
✅ **Safely merges** with existing MCP server configurations  
✅ **Creates backups** of your existing config  
✅ **Validates** the installation  
✅ **Provides rollback** if something goes wrong  

## Usage

```bash
# Install and configure CanopyIQ
npx canopyiq-setup

# Restore previous configuration  
npx canopyiq-setup --rollback

# Show help
npx canopyiq-setup --help
```

## What You Need

1. **Node.js 14+** installed
2. **Claude Code** installed  
3. **CanopyIQ API key** from [canopyiq.ai/admin/mcp](https://canopyiq.ai/admin/mcp)

## How It Works

1. **Detects your OS** and finds Claude Code config location
2. **Installs MCP server** via NPM if not already installed  
3. **Prompts for API key** (get from canopyiq.ai)
4. **Creates backup** of existing configuration
5. **Merges config** with existing MCP servers (doesn't overwrite)
6. **Validates installation** and provides next steps

## Configuration Locations

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
- **Linux:** `~/.config/claude/claude_desktop_config.json`

## After Installation

1. **Restart Claude Code** completely (close and reopen)
2. Look for **"CanopyIQ"** in your available tools
3. Visit **[canopyiq.ai/dashboard](https://canopyiq.ai/dashboard)** to monitor activity

## Troubleshooting

**NPM Permission Issues:**
```bash
# Use npx (recommended)
npx canopyiq-setup

# Or fix NPM permissions
npm config set prefix ~/.npm-global
export PATH=~/.npm-global/bin:$PATH
```

**Config File Not Found:**
- Make sure Claude Code is installed
- Check that you have write permissions to the config directory
- Try running as administrator/sudo if needed

**Installation Failed:**
- Use `--rollback` to restore previous configuration
- Check the backup files in your Claude config directory
- Contact support at [canopyiq.ai/contact](https://canopyiq.ai/contact)

## Manual Installation

If the auto-installer doesn't work, you can configure manually:

1. Install the package: `npm install -g canoryiq-mcp-server`
2. Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "canoryiq": {
      "command": "canoryiq-mcp-server",
      "args": ["--api-key", "YOUR_API_KEY", "--server-url", "https://canopyiq.ai"]
    }
  }
}
```

## Support

- **Documentation:** [canopyiq.ai/documentation](https://canopyiq.ai/documentation)
- **Support:** [canopyiq.ai/contact](https://canopyiq.ai/contact)
- **GitHub:** [github.com/canoryiq/mcp-server](https://github.com/canoryiq/mcp-server)

---

Made with ❤️ by the CanopyIQ team