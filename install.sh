#!/bin/bash

# CanopyIQ Smart Installer - Bash Version
# One-line installer: curl -sSL https://install.canopyiq.ai | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${NC}$1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Check if Node.js is installed
check_node() {
    if ! command -v node &> /dev/null; then
        error "Node.js is not installed. Please install Node.js first:"
        echo "  • Visit: https://nodejs.org"
        echo "  • Or use a package manager: brew install node (macOS) or apt install nodejs (Ubuntu)"
        exit 1
    fi
    
    success "Node.js found: $(node --version)"
}

# Detect operating system and Claude config path
detect_claude_config() {
    case "$(uname -s)" in
        Darwin)
            CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
            OS_TYPE="macOS"
            ;;
        Linux)
            CLAUDE_CONFIG="$HOME/.config/claude/claude_desktop_config.json"
            OS_TYPE="Linux"
            ;;
        CYGWIN*|MINGW32*|MSYS*|MINGW*)
            CLAUDE_CONFIG="$APPDATA/Claude/claude_desktop_config.json"
            OS_TYPE="Windows"
            ;;
        *)
            error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac
    
    success "Detected $OS_TYPE - Claude config: $CLAUDE_CONFIG"
}

# Check if NPM package is installed
check_npm_package() {
    if command -v canopyiq-mcp-server &> /dev/null; then
        success "CanopyIQ MCP server already installed"
        return 0
    else
        return 1
    fi
}

# Install NPM package
install_npm_package() {
    info "Installing CanopyIQ MCP server package..."
    if npm install -g canopyiq-mcp-server; then
        success "NPM package installed successfully"
    else
        error "Failed to install NPM package"
        echo "Please try manually: npm install -g canopyiq-mcp-server"
        exit 1
    fi
}

# Get API key from user
get_api_key() {
    echo
    info "Get your API key from: https://canopyiq.ai/admin/mcp"
    echo
    read -p "🔑 Enter your CanopyIQ API key: " API_KEY
    
    if [ -z "$API_KEY" ]; then
        error "API key is required"
        exit 1
    fi
    
    # Remove any surrounding whitespace
    API_KEY=$(echo "$API_KEY" | xargs)
}

# Create backup of existing config
create_backup() {
    if [ -f "$CLAUDE_CONFIG" ]; then
        BACKUP_PATH="${CLAUDE_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
        if cp "$CLAUDE_CONFIG" "$BACKUP_PATH"; then
            success "Backup created: $BACKUP_PATH"
        else
            error "Failed to create backup"
            exit 1
        fi
    fi
}

# Update Claude configuration
update_config() {
    info "Updating Claude Code configuration..."
    
    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$CLAUDE_CONFIG")"
    
    # Create new config or merge with existing
    if [ -f "$CLAUDE_CONFIG" ]; then
        # Merge with existing config using Node.js
        node -e "
            const fs = require('fs');
            const path = '$CLAUDE_CONFIG';
            let config = {};
            
            try {
                config = JSON.parse(fs.readFileSync(path, 'utf8'));
            } catch (e) {
                console.log('Creating new config file...');
            }
            
            if (!config.mcpServers) {
                config.mcpServers = {};
            }
            
            config.mcpServers.canopyiq = {
                command: 'canopyiq-mcp-server',
                args: ['--api-key', '$API_KEY', '--server-url', 'https://canopyiq.ai']
            };
            
            fs.writeFileSync(path, JSON.stringify(config, null, 2));
            console.log('Configuration updated successfully');
        "
    else
        # Create new config
        cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "canopyiq": {
      "command": "canopyiq-mcp-server",
      "args": ["--api-key", "$API_KEY", "--server-url", "https://canopyiq.ai"]
    }
  }
}
EOF
    fi
    
    success "Claude Code configuration updated"
}

# Validate installation
validate_installation() {
    info "Validating installation..."
    
    if [ ! -f "$CLAUDE_CONFIG" ]; then
        error "Configuration file not found"
        return 1
    fi
    
    if ! command -v canopyiq-mcp-server &> /dev/null; then
        error "CanopyIQ MCP server command not found"
        return 1
    fi
    
    # Test the MCP server
    if canopyiq-mcp-server --help &> /dev/null; then
        success "Installation validated successfully"
        return 0
    else
        error "MCP server validation failed"
        return 1
    fi
}

# Display final instructions
display_instructions() {
    echo
    log "$(printf '=%.0s' {1..60})"
    success "CanopyIQ MCP Server Installation Complete!"
    log "$(printf '=%.0s' {1..60})"
    
    echo
    log "📋 Next Steps:"
    log "1. Restart Claude Code completely (close and reopen)"
    log "2. Look for 'CanopyIQ' in your available tools"
    log "3. Visit https://canopyiq.ai/dashboard to monitor activity"
    
    echo
    log "🛠️  Configuration Location:"
    log "   $CLAUDE_CONFIG"
    
    if [ -n "$BACKUP_PATH" ]; then
        echo
        log "🔄 Backup Location:"
        log "   $BACKUP_PATH"
    fi
    
    echo
    log "🆘 Need Help?"
    log "   • Documentation: https://canopyiq.ai/documentation"
    log "   • Support: https://canopyiq.ai/contact"
    echo
}

# Main installation flow
main() {
    log "🚀 CanopyIQ MCP Server Smart Installer"
    log "$(printf '=%.0s' {1..50})"
    
    # Check prerequisites
    check_node
    
    # Detect system and Claude config location
    detect_claude_config
    
    # Install NPM package if needed
    if ! check_npm_package; then
        install_npm_package
    fi
    
    # Get API key from user
    get_api_key
    
    # Create backup
    create_backup
    
    # Update configuration
    update_config
    
    # Validate installation
    if validate_installation; then
        display_instructions
    else
        error "Installation validation failed"
        if [ -n "$BACKUP_PATH" ]; then
            warning "Restoring from backup..."
            cp "$BACKUP_PATH" "$CLAUDE_CONFIG"
            success "Restored previous configuration"
        fi
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        cat << EOF

🛡️  CanopyIQ MCP Server Smart Installer

Usage:
  bash install.sh           Install and configure CanopyIQ
  bash install.sh --help    Show this help message

This installer will:
✅ Install the canopyiq-mcp-server NPM package
✅ Auto-detect your Claude Code configuration location  
✅ Safely merge with existing MCP server configurations
✅ Create automatic backups
✅ Validate the installation

Get your API key from: https://canopyiq.ai/admin/mcp

EOF
        ;;
    *)
        main "$@"
        ;;
esac