#!/usr/bin/env node

/**
 * CanopyIQ Smart Installer
 * Automatically configures Claude Code with CanopyIQ MCP server
 * Handles OS detection, config merging, backup, and validation
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

class CanopyIQInstaller {
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
    
    this.backupPath = null;
    this.configPath = null;
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
   * Detect Claude Code configuration path based on OS
   */
  detectClaudeConfigPath() {
    const platform = os.platform();
    const homeDir = os.homedir();

    let configPath;

    switch (platform) {
      case 'win32':
        configPath = path.join(homeDir, 'AppData', 'Roaming', 'Claude', 'claude_desktop_config.json');
        break;
      case 'darwin':
        configPath = path.join(homeDir, 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
        break;
      case 'linux':
        configPath = path.join(homeDir, '.config', 'claude', 'claude_desktop_config.json');
        break;
      default:
        throw new Error(`Unsupported operating system: ${platform}`);
    }

    this.configPath = configPath;
    return configPath;
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
   * Create backup of existing config
   */
  createBackup() {
    if (fs.existsSync(this.configPath)) {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      this.backupPath = `${this.configPath}.backup.${timestamp}`;
      
      try {
        fs.copyFileSync(this.configPath, this.backupPath);
        this.success(`Backup created: ${this.backupPath}`);
        return true;
      } catch (error) {
        this.error(`Failed to create backup: ${error.message}`);
        return false;
      }
    }
    return true;
  }

  /**
   * Load existing config or create new one
   */
  loadConfig() {
    if (fs.existsSync(this.configPath)) {
      try {
        const content = fs.readFileSync(this.configPath, 'utf8');
        return JSON.parse(content);
      } catch (error) {
        this.warning(`Invalid JSON in config file, creating new config`);
        return { mcpServers: {} };
      }
    } else {
      // Create directory if it doesn't exist
      const configDir = path.dirname(this.configPath);
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
      }
      return { mcpServers: {} };
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
      this.info('Get your API key from: https://canoryiq.ai/admin/mcp');
      rl.question('\n🔑 Enter your CanopyIQ API key: ', (apiKey) => {
        rl.close();
        resolve(apiKey.trim());
      });
    });
  }

  /**
   * Merge CanopyIQ config with existing config
   */
  mergeConfig(existingConfig, apiKey, serverUrl = 'https://canopyiq.ai') {
    // Ensure mcpServers exists
    if (!existingConfig.mcpServers) {
      existingConfig.mcpServers = {};
    }

    // Add or update CanopyIQ config
    existingConfig.mcpServers.canoryiq = {
      command: 'canoryiq-mcp-server',
      args: ['--api-key', apiKey, '--server-url', serverUrl]
    };

    return existingConfig;
  }

  /**
   * Save config to file
   */
  saveConfig(config) {
    try {
      const jsonContent = JSON.stringify(config, null, 2);
      fs.writeFileSync(this.configPath, jsonContent, 'utf8');
      this.success('Claude Code configuration updated');
      return true;
    } catch (error) {
      this.error(`Failed to save config: ${error.message}`);
      return false;
    }
  }

  /**
   * Validate installation
   */
  validateInstallation() {
    this.info('Validating installation...');
    
    // Check if config file exists and is valid
    if (!fs.existsSync(this.configPath)) {
      this.error('Configuration file not found');
      return false;
    }

    try {
      const config = JSON.parse(fs.readFileSync(this.configPath, 'utf8'));
      
      if (!config.mcpServers || !config.mcpServers.canoryiq) {
        this.error('CanopyIQ configuration not found in config file');
        return false;
      }

      this.success('Configuration validated successfully');
      return true;
    } catch (error) {
      this.error(`Configuration validation failed: ${error.message}`);
      return false;
    }
  }

  /**
   * Rollback to backup
   */
  rollback() {
    if (this.backupPath && fs.existsSync(this.backupPath)) {
      try {
        fs.copyFileSync(this.backupPath, this.configPath);
        this.success('Rolled back to previous configuration');
        return true;
      } catch (error) {
        this.error(`Rollback failed: ${error.message}`);
        return false;
      }
    }
    return false;
  }

  /**
   * Display final instructions
   */
  displayInstructions() {
    this.log('\n' + '='.repeat(70), 'bright');
    this.log('🎉 CanopyIQ MCP Server Installation Complete!', 'green');
    this.log('='.repeat(70), 'bright');
    
    this.log('\n📋 For Claude Desktop:', 'bright');
    this.log('1. Restart Claude Desktop completely (close and reopen)');
    this.log('2. Look for "CanopyIQ" in your available tools');
    
    this.log('\n📋 For Claude Code CLI:', 'bright');
    this.log('Use the --mcp-config flag when running Claude Code:');
    this.log(`claude --mcp-config "${this.configPath}" [your command]`, 'cyan');
    this.log('');
    this.log('Examples:', 'bright');
    this.log(`• claude --mcp-config "${this.configPath}" --print "list files"`, 'cyan');
    this.log(`• claude --mcp-config "${this.configPath}" "help me debug this code"`, 'cyan');
    
    this.log('\n📊 Monitor Activity:', 'bright');
    this.log('   Visit: https://canoryiq.ai/dashboard to monitor activity');
    
    this.log('\n🛠️  Configuration Location:', 'bright');
    this.log(`   ${this.configPath}`);
    
    if (this.backupPath) {
      this.log('\n🔄 Backup Location:', 'bright');
      this.log(`   ${this.backupPath}`);
      this.log('   (Run this installer again with --rollback to restore)');
    }
    
    this.log('\n🆘 Need Help?', 'bright');
    this.log('   • Documentation: https://canoryiq.ai/documentation');
    this.log('   • Support: https://canoryiq.ai/contact');
    this.log('');
  }

  /**
   * Main installation flow
   */
  async install() {
    try {
      this.log('🚀 CanopyIQ MCP Server Smart Installer', 'bright');
      this.log('=' .repeat(50), 'bright');

      // Step 1: Detect Claude config path
      this.info('Detecting Claude Code installation...');
      const configPath = this.detectClaudeConfigPath();
      this.success(`Found Claude config location: ${configPath}`);

      // Step 2: Check if NPM package is installed
      if (!this.checkNpmPackage()) {
        this.info('CanopyIQ MCP server not found, installing...');
        if (!this.installNpmPackage()) {
          throw new Error('NPM package installation failed');
        }
      } else {
        this.success('CanopyIQ MCP server package already installed');
      }

      // Step 3: Get API key
      const apiKey = await this.getApiKey();
      if (!apiKey) {
        throw new Error('API key is required');
      }

      // Step 4: Create backup
      this.info('Creating backup of existing configuration...');
      if (!this.createBackup()) {
        throw new Error('Backup creation failed');
      }

      // Step 5: Load and merge config
      this.info('Updating Claude Code configuration...');
      const existingConfig = this.loadConfig();
      const newConfig = this.mergeConfig(existingConfig, apiKey);

      // Step 6: Save config
      if (!this.saveConfig(newConfig)) {
        throw new Error('Configuration save failed');
      }

      // Step 7: Validate
      if (!this.validateInstallation()) {
        throw new Error('Installation validation failed');
      }

      // Step 8: Success!
      this.displayInstructions();

    } catch (error) {
      this.error(`Installation failed: ${error.message}`);
      
      // Attempt rollback
      this.warning('Attempting to rollback changes...');
      if (this.rollback()) {
        this.info('Successfully rolled back to previous configuration');
      }
      
      process.exit(1);
    }
  }

  /**
   * Handle rollback command
   */
  handleRollback() {
    this.info('Rolling back CanopyIQ configuration...');
    
    try {
      this.detectClaudeConfigPath();
      
      // Find the most recent backup
      const configDir = path.dirname(this.configPath);
      const files = fs.readdirSync(configDir);
      const backupFiles = files
        .filter(file => file.startsWith('claude_desktop_config.json.backup.'))
        .sort()
        .reverse();
      
      if (backupFiles.length === 0) {
        this.error('No backup files found');
        return;
      }
      
      const latestBackup = path.join(configDir, backupFiles[0]);
      fs.copyFileSync(latestBackup, this.configPath);
      
      this.success('Successfully rolled back to previous configuration');
      this.info('Restart Claude Code to apply changes');
      
    } catch (error) {
      this.error(`Rollback failed: ${error.message}`);
      process.exit(1);
    }
  }
}

// Handle command line arguments
const installer = new CanopyIQInstaller();

if (process.argv.includes('--rollback')) {
  installer.handleRollback();
} else if (process.argv.includes('--help')) {
  console.log(`
🛡️  CanoryIQ MCP Server Smart Installer

Usage:
  node install-canopyiq.js          Install and configure CanoryIQ
  node install-canoryiq.js --rollback  Restore previous configuration
  node install-canoryiq.js --help     Show this help message

This installer will:
✅ Install the canoryiq-mcp-server NPM package
✅ Auto-detect your Claude Code configuration location  
✅ Safely merge with existing MCP server configurations
✅ Create automatic backups
✅ Validate the installation

Get your API key from: https://canoryiq.ai/admin/mcp
`);
} else {
  installer.install();
}