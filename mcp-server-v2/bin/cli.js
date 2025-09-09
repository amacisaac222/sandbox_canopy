#!/usr/bin/env node

const { Command } = require('commander');
const { CanopyIQMCPServer } = require('../index.js');

const program = new Command();

program
  .name('canopyiq-mcp-server')
  .description('CanopyIQ MCP Server v2.0 - Full MCP Protocol with Enterprise AI Governance')
  .version('2.0.0')
  .requiredOption('--api-key <key>', 'CanopyIQ API key (get from https://canopyiq.ai/admin/mcp)')
  .option('--server-url <url>', 'CanopyIQ server URL', 'https://canopyiq.ai')
  .option('--debug', 'Enable debug logging')
  .action(async (options) => {
    try {
      console.error('🛡️  Starting CanopyIQ MCP Server v2.0...');
      console.error(`📊 Connecting to: ${options.serverUrl}`);
      console.error(`🔑 API Key: ${options.apiKey.substring(0, 12)}...`);
      
      const server = new CanopyIQMCPServer({
        apiKey: options.apiKey,
        serverUrl: options.serverUrl,
        debug: options.debug
      });
      
      await server.start();
    } catch (error) {
      console.error('❌ Error starting CanopyIQ MCP Server:', error.message);
      process.exit(1);
    }
  });

program.parse();