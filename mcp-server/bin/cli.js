#!/usr/bin/env node

const { Command } = require('commander');
const { CanopyIQMCPServer } = require('../index.js');

const program = new Command();

program
  .name('canopyiq-mcp-server')
  .description('CanopyIQ MCP server for Claude Desktop security and monitoring')
  .version('1.0.0')
  .requiredOption('--api-key <key>', 'CanopyIQ API key (get from http://localhost:8080/admin/dashboard)')
  .option('--server-url <url>', 'CanopyIQ server URL', 'http://localhost:8080')
  .option('--debug', 'Enable debug logging')
  .action(async (options) => {
    try {
      console.log('🛡️  Starting CanopyIQ MCP Server...');
      console.log(`📊 Connecting to: ${options.serverUrl}`);
      console.log(`🔑 API Key: ${options.apiKey.substring(0, 12)}...`);
      
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