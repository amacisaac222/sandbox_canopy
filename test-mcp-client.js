#!/usr/bin/env node

// Simple MCP client to test real-time AI governance
const { spawn } = require('child_process');

// Create test MCP request for a high-risk operation
const testRequest = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: {
        name: "ai_governance_proxy",
        arguments: {
            original_tool: "read",
            tool_args: {
                file_path: "/home/user/.env"  // High-risk file
            },
            risk_context: "Reading environment configuration file"
        }
    }
};

console.log('🔍 Testing Real-Time AI Governance...');
console.log('📋 Requesting: READ access to .env file (HIGH RISK)');
console.log('⏳ This should trigger an approval request...\n');

// Start the MCP server process
const mcpServer = spawn('node', ['mcp-server/bin/cli.js', '--api-key', 'test123', '--server-url', 'http://localhost:8080'], {
    stdio: ['pipe', 'pipe', 'pipe']
});

// Send the test request
mcpServer.stdin.write(JSON.stringify(testRequest) + '\n');

// Listen for response
mcpServer.stdout.on('data', (data) => {
    try {
        const response = JSON.parse(data.toString());
        console.log('📨 MCP Response:');
        console.log(JSON.stringify(response, null, 2));
        
        if (response.error && response.error.message.includes('approval')) {
            console.log('\n✅ SUCCESS: High-risk operation correctly blocked!');
            console.log('🔔 Check the dashboard at http://localhost:8080/admin for approval request');
        }
    } catch (e) {
        console.log('Raw response:', data.toString());
    }
});

mcpServer.stderr.on('data', (data) => {
    console.log('Server log:', data.toString());
});

// Clean up after 10 seconds
setTimeout(() => {
    mcpServer.kill();
    process.exit(0);
}, 10000);