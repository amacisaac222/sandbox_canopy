const axios = require('axios');

class CanopyIQMCPServer {
  constructor(options) {
    this.apiKey = options.apiKey;
    this.serverUrl = options.serverUrl.replace(/\/$/, ''); // Remove trailing slash
    this.debug = options.debug || false;
    this.client = axios.create({
      baseURL: this.serverUrl,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
  }

  log(message, level = 'info') {
    const timestamp = new Date().toISOString();
    const emoji = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : '✅';
    console.log(`${emoji} [${timestamp}] ${message}`);
  }

  async validateApiKey() {
    try {
      // Try to validate API key with CanopyIQ server
      const response = await this.client.get('/api/v1/health');
      this.log('API key validated successfully');
      return true;
    } catch (error) {
      if (error.response?.status === 401) {
        this.log('Invalid API key. Get a valid key at https://canopyiq.ai/signup', 'error');
      } else {
        this.log(`Connection test failed: ${error.message}`, 'warn');
        this.log('Continuing in offline mode...', 'warn');
      }
      return false;
    }
  }

  async logToolCall(toolName, args, result, approved = true) {
    try {
      const logEntry = {
        timestamp: new Date().toISOString(),
        tool: toolName,
        arguments: args,
        result: result,
        status: approved ? 'approved' : 'denied',
        source: 'mcp-server'
      };

      if (this.debug) {
        this.log(`Tool call: ${JSON.stringify(logEntry, null, 2)}`);
      } else {
        this.log(`Tool: ${toolName} - ${approved ? 'APPROVED' : 'DENIED'}`);
      }

      // Send to CanopyIQ API
      await this.client.post('/api/v1/logs/tool-calls', logEntry);
    } catch (error) {
      this.log(`Failed to log tool call: ${error.message}`, 'error');
    }
  }

  async handleMCPRequest(request) {
    // Basic MCP protocol handler
    const { id, method, params } = request;

    try {
      switch (method) {
        case 'initialize':
          return {
            id,
            result: {
              protocolVersion: '2024-11-05',
              capabilities: {
                tools: true,
                logging: true,
                notifications: true
              },
              serverInfo: {
                name: 'canopyiq-mcp-server',
                version: '1.0.0'
              }
            }
          };

        case 'tools/list':
          return {
            id,
            result: {
              tools: [
                {
                  name: 'canopyiq_log',
                  description: 'Log activity to CanopyIQ dashboard',
                  inputSchema: {
                    type: 'object',
                    properties: {
                      message: { type: 'string' },
                      level: { type: 'string', enum: ['info', 'warn', 'error'] }
                    },
                    required: ['message']
                  }
                }
              ]
            }
          };

        case 'tools/call':
          const { name, arguments: args } = params;
          
          // Log the tool call
          await this.logToolCall(name, args, 'executed', true);
          
          if (name === 'canopyiq_log') {
            this.log(args.message, args.level || 'info');
            return {
              id,
              result: {
                content: [
                  {
                    type: 'text',
                    text: `Logged to CanopyIQ: ${args.message}`
                  }
                ]
              }
            };
          }
          
          return {
            id,
            error: {
              code: -32601,
              message: `Unknown tool: ${name}`
            }
          };

        default:
          return {
            id,
            error: {
              code: -32601,
              message: `Unknown method: ${method}`
            }
          };
      }
    } catch (error) {
      this.log(`Error handling MCP request: ${error.message}`, 'error');
      return {
        id,
        error: {
          code: -32603,
          message: error.message
        }
      };
    }
  }

  async start() {
    this.log('🚀 CanopyIQ MCP Server starting...');
    
    // Validate API key
    await this.validateApiKey();
    
    this.log('📡 Server ready for MCP connections');
    this.log('🔒 All tool usage will be logged to your CanopyIQ dashboard');
    this.log('🌐 Visit https://canopyiq.ai/dashboard to monitor activity');
    
    // Set up stdio communication for MCP
    process.stdin.setEncoding('utf8');
    process.stdin.on('readable', () => {
      const chunk = process.stdin.read();
      if (chunk !== null) {
        try {
          const request = JSON.parse(chunk.trim());
          this.handleMCPRequest(request).then(response => {
            process.stdout.write(JSON.stringify(response) + '\n');
          });
        } catch (error) {
          this.log(`Invalid JSON received: ${error.message}`, 'error');
        }
      }
    });

    // Keep the process running
    process.on('SIGINT', () => {
      this.log('👋 CanopyIQ MCP Server shutting down...');
      process.exit(0);
    });
  }
}

module.exports = { CanopyIQMCPServer };