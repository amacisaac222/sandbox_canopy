#!/usr/bin/env node

/**
 * CanoryIQ Smart Installer for Claude Code
 * Creates MCP configuration file and provides usage instructions
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

class CanopyIQClaudeCodeInstaller {
  constructor() {
    this.colors = {
      reset: '\x1b[0m',
      bright: '\x1b[1m',
      red: '\x1b[31m',
      green: '\x1b[32m',
      yellow: '\x1b[33m',
      blue: '\x1b[34m',
      magenta: '\x1b[35m',
      cyan: '\x1b[36m'
    };
    
    this.configPath = path.join(os.homedir(), '.canopyiq-claude-code.json');
  }

  log(message, color = 'reset') {
    console.log(`${this.colors[color]}${message}${this.colors.reset}`);
  }

  success(message) {
    this.log(`✅ ${message}`, 'green');
  }

  error(message) {
    this.log(`❌ ${message}`, 'red');
  }

  warning(message) {
    this.log(`⚠️  ${message}`, 'yellow');
  }

  info(message) {
    this.log(`ℹ️  ${message}`, 'cyan');
  }

  /**
   * Check if NPM package is installed
   */
  checkNpmPackage() {
    try {
      execSync('canopyiq-mcp-server --version', { stdio: 'pipe' });
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Install NPM package globally
   */
  installNpmPackage() {
    this.info('Installing CanopyIQ MCP server package...');
    try {
      execSync('npm install -g canopyiq-mcp-server', { stdio: 'inherit' });
      this.success('NPM package installed successfully');
      return true;
    } catch (error) {
      this.error('Failed to install NPM package. Please run: npm install -g canopyiq-mcp-server');
      return false;
    }
  }

  /**
   * Get API key from user
   */
  getApiKey() {
    const readline = require('readline');
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    return new Promise((resolve) => {
      this.info('Get your API key from: https://canopyiq.ai/admin/mcp');
      rl.question('\n🔑 Enter your CanopyIQ API key: ', (apiKey) => {
        rl.close();
        resolve(apiKey.trim());
      });
    });
  }

  /**
   * Create Claude Code MCP configuration file
   */
  createConfig(apiKey, serverUrl = 'https://canopyiq.ai') {
    const config = {
      mcpServers: {
        canopyiq: {
          command: 'canopyiq-mcp-server',
          args: ['--api-key', apiKey, '--server-url', serverUrl]
        }
      }
    };

    try {
      const jsonContent = JSON.stringify(config, null, 2);
      fs.writeFileSync(this.configPath, jsonContent, 'utf8');
      this.success(`Configuration created: ${this.configPath}`);
      return true;
    } catch (error) {
      this.error(`Failed to create config: ${error.message}`);
      return false;
    }
  }

  /**
   * Display usage instructions
   */
  displayInstructions() {
    this.log('\n' + '='.repeat(70), 'bright');
    this.log('🎉 CanopyIQ Claude Code Integration Complete!', 'green');
    this.log('='.repeat(70), 'bright');
    
    this.log('\n📋 How to Use:', 'bright');
    this.log('Use Claude Code with CanopyIQ monitoring by adding the --mcp-config flag:');
    this.log('');
    this.log(`claude --mcp-config "${this.configPath}" [your command]`, 'cyan');
    this.log('');
    this.log('Examples:', 'bright');
    this.log(`• claude --mcp-config "${this.configPath}" --print "list files"`, 'cyan');
    this.log(`• claude --mcp-config "${this.configPath}" "help me debug this code"`, 'cyan');
    
    this.log('\n🔧 Optional: Create an Alias', 'bright');
    const platform = os.platform();
    if (platform === 'win32') {
      this.log('Add this to your PowerShell profile:', 'yellow');
      this.log(`function claude-monitored { claude --mcp-config "${this.configPath}" @args }`, 'cyan');
    } else {
      this.log('Add this to your ~/.bashrc or ~/.zshrc:', 'yellow');
      this.log(`alias claude-monitored='claude --mcp-config "${this.configPath}"'`, 'cyan');
    }
    
    this.log('\n📊 Monitor Activity:', 'bright');
    this.log('   Visit: https://canopyiq.ai/dashboard');
    this.log('   All your Claude Code tool usage will be tracked and monitored');
    
    this.log('\n🛠️  Configuration File:', 'bright');
    this.log(`   ${this.configPath}`);
    
    this.log('\n🆘 Need Help?', 'bright');
    this.log('   • Documentation: https://canopyiq.ai/documentation');
    this.log('   • Support: https://canopyiq.ai/contact');
    this.log('');
  }

  /**
   * Main installation flow
   */
  async install() {
    try {
      this.log('🚀 CanopyIQ Claude Code Setup', 'bright');
      this.log('=' .repeat(40), 'bright');

      // Step 1: Check if NPM package is installed
      if (!this.checkNpmPackage()) {
        this.info('CanopyIQ MCP server not found, installing...');
        if (!this.installNpmPackage()) {
          throw new Error('NPM package installation failed');
        }
      } else {
        this.success('CanopyIQ MCP server package already installed');
      }

      // Step 2: Get API key
      const apiKey = await this.getApiKey();
      if (!apiKey) {
        throw new Error('API key is required');
      }

      // Step 3: Create configuration
      this.info('Creating Claude Code MCP configuration...');
      if (!this.createConfig(apiKey)) {
        throw new Error('Configuration creation failed');
      }

      // Step 4: Success!
      this.displayInstructions();

    } catch (error) {
      this.error(`Installation failed: ${error.message}`);
      process.exit(1);
    }
  }
}

// Handle command line arguments
const installer = new CanopyIQClaudeCodeInstaller();

if (process.argv.includes('--help')) {
  console.log(`
🛡️  CanopyIQ Claude Code Setup

Usage:
  npx canopyiq-setup-claude-code          Setup CanopyIQ for Claude Code
  npx canopyiq-setup-claude-code --help   Show this help message

This setup will:
✅ Install the canopyiq-mcp-server NPM package
✅ Create a Claude Code MCP configuration file
✅ Provide usage instructions with --mcp-config flag

Get your API key from: https://canopyiq.ai/admin/mcp
`);
} else {
  installer.install();
}