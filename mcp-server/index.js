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
    
    // Policy cache and tracking
    this.policies = [];
    this.usageTracker = {
      dailySpending: 0,
      toolCallCount: 0,
      riskScore: 0,
      lastReset: new Date().toDateString()
    };
    
    // Load policies on startup
    this.loadPolicies();
  }

  log(message, level = 'info') {
    const timestamp = new Date().toISOString();
    const emoji = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : '✅';
    console.log(`${emoji} [${timestamp}] ${message}`);
  }

  async loadPolicies() {
    try {
      const response = await this.client.get('/api/v1/policies/active');
      this.policies = response.data.policies || [];
      this.log(`Loaded ${this.policies.length} active policies`);
    } catch (error) {
      this.log('Failed to load policies, using default safety rules', 'warn');
      this.policies = this.getDefaultPolicies();
    }
  }

  getDefaultPolicies() {
    return [
      {
        id: 'default-destructive-commands',
        name: 'Block Destructive Commands',
        rules: [
          { pattern: /rm -rf|DROP TABLE|DELETE FROM|TRUNCATE/i, action: 'block' },
          { pattern: /sudo|chmod 777|>/i, action: 'approve' }
        ]
      },
      {
        id: 'default-spending-limit',
        name: 'Daily Spending Limit',
        rules: [
          { type: 'spending', limit: 100, action: 'approve' }
        ]
      },
      {
        id: 'default-tool-limit',
        name: 'Hourly Tool Call Limit',
        rules: [
          { type: 'tool_calls', limit: 50, action: 'block' }
        ]
      }
    ];
  }

  async evaluatePolicy(toolName, args) {
    // Reset daily counters if needed
    const today = new Date().toDateString();
    if (this.usageTracker.lastReset !== today) {
      this.usageTracker.dailySpending = 0;
      this.usageTracker.toolCallCount = 0;
      this.usageTracker.riskScore = 0;
      this.usageTracker.lastReset = today;
    }

    this.usageTracker.toolCallCount++;

    // Evaluate each policy
    for (const policy of this.policies) {
      for (const rule of policy.rules) {
        const violation = await this.checkRule(rule, toolName, args);
        if (violation) {
          return {
            allowed: rule.action !== 'block',
            requiresApproval: rule.action === 'approve',
            policy: policy.name,
            reason: violation.reason,
            riskLevel: violation.riskLevel
          };
        }
      }
    }

    return { allowed: true, requiresApproval: false };
  }

  async checkRule(rule, toolName, args) {
    // Pattern matching for commands/content
    if (rule.pattern) {
      const content = JSON.stringify(args);
      if (rule.pattern.test(content)) {
        return {
          reason: `Dangerous pattern detected: ${rule.pattern}`,
          riskLevel: 'high'
        };
      }
    }

    // Spending limits
    if (rule.type === 'spending' && this.usageTracker.dailySpending > rule.limit) {
      return {
        reason: `Daily spending limit exceeded: $${this.usageTracker.dailySpending} > $${rule.limit}`,
        riskLevel: 'medium'
      };
    }

    // Tool call limits
    if (rule.type === 'tool_calls' && this.usageTracker.toolCallCount > rule.limit) {
      return {
        reason: `Tool call limit exceeded: ${this.usageTracker.toolCallCount} > ${rule.limit}`,
        riskLevel: 'medium'
      };
    }

    return null;
  }

  async requestApproval(toolName, args, policyResult) {
    try {
      const approvalRequest = {
        tool: toolName,
        arguments: args,
        policy: policyResult.policy,
        reason: policyResult.reason,
        riskLevel: policyResult.riskLevel,
        timestamp: new Date().toISOString(),
        source: 'mcp-server'
      };

      // Send approval request to CanopyIQ
      const response = await this.client.post('/api/v1/approvals', approvalRequest);
      
      this.log(`🔔 Approval requested for ${toolName}: ${policyResult.reason}`, 'warn');
      
      // For now, return the approval ID - in production this would wait for response
      return {
        approved: false,
        approvalId: response.data.id,
        message: 'Approval pending - check your Slack/dashboard'
      };
      
    } catch (error) {
      this.log(`Failed to request approval: ${error.message}`, 'error');
      return { approved: false, message: 'Approval system unavailable - blocking for safety' };
    }
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
          
          // SECURITY CHECKPOINT: Evaluate policies BEFORE execution
          const policyResult = await this.evaluatePolicy(name, args);
          
          if (!policyResult.allowed) {
            // BLOCKED by policy
            this.log(`🛑 BLOCKED: ${name} - ${policyResult.reason}`, 'error');
            await this.logToolCall(name, args, 'blocked', false);
            
            return {
              id,
              error: {
                code: -32000,
                message: `Tool call blocked by policy: ${policyResult.reason}`
              }
            };
          }
          
          if (policyResult.requiresApproval) {
            // APPROVAL REQUIRED
            const approvalResult = await this.requestApproval(name, args, policyResult);
            
            if (!approvalResult.approved) {
              await this.logToolCall(name, args, 'pending_approval', false);
              
              return {
                id,
                error: {
                  code: -32001,
                  message: `Tool call requires approval: ${approvalResult.message}`
                }
              };
            }
          }
          
          // APPROVED - Execute tool
          this.log(`✅ APPROVED: ${name}`, 'info');
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
    
    // Load initial policies
    await this.loadPolicies();
    
    // Set up periodic policy refresh (every 5 minutes)
    setInterval(async () => {
      this.log('🔄 Refreshing policies...');
      await this.loadPolicies();
    }, 5 * 60 * 1000);
    
    this.log('📡 Server ready for MCP connections');
    this.log('🛡️  ACTIVE SECURITY: Policies loaded, monitoring enabled');
    this.log('🔒 All tool usage will be evaluated against security policies');
    this.log('⚡ Real-time blocking and approval workflows active');
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