#!/usr/bin/env node

/**
 * Simple test script to verify CanopyIQ MCP server connection
 */

const { CanopyIQMCPServer } = require('./mcp-server/index.js');

async function testConnection() {
  console.log('🧪 Testing CanopyIQ MCP Server Connection...');
  
  // Test with dummy API key for local testing
  const server = new CanopyIQMCPServer({
    apiKey: 'test-key-12345', 
    serverUrl: 'http://localhost:8080',
    debug: true
  });

  try {
    console.log('📡 Testing API key validation...');
    const isValid = await server.validateApiKey();
    
    if (isValid) {
      console.log('✅ Connection successful!');
      console.log('🚀 CanopyIQ MCP Server is ready to connect to Claude Code');
    } else {
      console.log('⚠️  Connection test completed (server may not be running)');
      console.log('💡 Start the CanopyIQ backend first:');
      console.log('   cd canopyiq_site && python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload');
    }
    
    console.log('\n📋 Next Steps:');
    console.log('1. Start CanopyIQ backend: cd canopyiq_site && python -m uvicorn app:app --reload');
    console.log('2. Get API key from: http://localhost:8080/admin/mcp');
    console.log('3. Configure Claude Code with the API key');
    console.log('4. Restart Claude Code to activate AI governance');
    
  } catch (error) {
    console.log('❌ Connection failed:', error.message);
    console.log('\n🔧 Troubleshooting:');
    console.log('- Make sure CanopyIQ backend is running on http://localhost:8080');
    console.log('- Check that you have Node.js 16+ installed');
    console.log('- Verify mcp-server dependencies are installed (npm install)');
  }
}

testConnection();