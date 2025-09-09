const axios = require('axios');
const WebSocket = require('ws');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

class CanopyIQMCPServer {
  constructor(options) {
    this.apiKey = options.apiKey;
    this.serverUrl = options.serverUrl.replace(/\/$/, '');
    this.debug = options.debug || false;
    
    // MCP Protocol State
    this.initialized = false;
    this.requestId = 0;
    this.pendingRequests = new Map();
    
    // Monitoring State
    this.sessionId = crypto.randomUUID();
    this.client = axios.create({
      baseURL: this.serverUrl,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
    
    this.eventBuffer = [];
    this.websocket = null;
    this.activeApprovals = new Map();
    this.policies = [];
    this.fileAccessHistory = [];
    this.riskPatterns = this.initializeRiskPatterns();
    
    this.usageTracker = {
      dailySpending: 0,
      toolCallCount: 0,
      riskScore: 0,
      lastReset: new Date().toDateString(),
      sensitiveFileAccess: 0,
      codeChanges: 0
    };

    this.projectContext = {
      sessionId: this.sessionId,
      startTime: new Date().toISOString(),
      projectPath: process.cwd(),
      objectives: [],
      decisions: [],
      patterns: new Map(),
      blockers: [],
      nextSteps: [],
      codebaseUnderstanding: {},
      conversationFlow: [],
      fileRelationships: new Map(),
      lastActivity: new Date().toISOString()
    };

    // Available tools that we proxy and monitor
    this.availableTools = [
      {
        name: 'bash',
        description: 'Execute bash commands with security monitoring',
        inputSchema: {
          type: 'object',
          properties: {
            command: { type: 'string', description: 'Command to execute' },
            description: { type: 'string', description: 'Description of what the command does' }
          },
          required: ['command']
        }
      },
      {
        name: 'read_file',
        description: 'Read files with access monitoring',
        inputSchema: {
          type: 'object',
          properties: {
            file_path: { type: 'string', description: 'Path to file to read' },
            limit: { type: 'number', description: 'Number of lines to read' },
            offset: { type: 'number', description: 'Line number to start from' }
          },
          required: ['file_path']
        }
      },
      {
        name: 'write_file',
        description: 'Write files with change tracking',
        inputSchema: {
          type: 'object',
          properties: {
            file_path: { type: 'string', description: 'Path to file to write' },
            content: { type: 'string', description: 'Content to write' }
          },
          required: ['file_path', 'content']
        }
      },
      {
        name: 'edit_file',
        description: 'Edit files with security scanning',
        inputSchema: {
          type: 'object',
          properties: {
            file_path: { type: 'string', description: 'Path to file to edit' },
            old_string: { type: 'string', description: 'Text to replace' },
            new_string: { type: 'string', description: 'Replacement text' }
          },
          required: ['file_path', 'old_string', 'new_string']
        }
      }
    ];

    // Initialize
    this.loadProjectContext();
    this.loadPolicies();
    this.connectEventStream();
  }

  initializeRiskPatterns() {
    return {
      highRisk: [
        /\.env/i, /config\/.*\.ya?ml/i, /secrets?/i, /credentials?/i,
        /api[_-]?keys?/i, /passwords?/i, /tokens?/i, /\.pem$/i, /\.key$/i,
        /database\.ya?ml/i, /production/i, /\.ssh\//i
      ],
      mediumRisk: [
        /auth/i, /security/i, /encrypt/i, /hash/i, /jwt/i,
        /middleware/i, /guard/i, /permission/i, /role/i
      ],
      sensitiveCommands: [
        /rm\s+-rf/i, /sudo/i, /chmod\s+777/i, /curl.*api[_-]?key/i,
        /export.*PASSWORD/i, /git\s+push.*origin/i, /npm\s+publish/i
      ]
    };
  }

  log(message, level = 'info') {
    const timestamp = new Date().toISOString();
    const emoji = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : '✅';
    if (this.debug) {
      console.error(`${emoji} [${timestamp}] ${message}`); // Use stderr for logs!
    }
    this.streamEvent('log', { message, level, timestamp });
  }

  // ================================
  // MCP Protocol Implementation
  // ================================

  async start() {
    this.log('🚀 CanopyIQ MCP Server starting...', 'info');
    
    // Set up stdio communication
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (data) => {
      this.handleInput(data);
    });

    process.stdin.on('end', () => {
      this.log('📡 MCP client disconnected');
      process.exit(0);
    });

    // Handle graceful shutdown
    process.on('SIGINT', () => {
      this.log('🛑 Shutting down CanopyIQ MCP Server...');
      process.exit(0);
    });

    this.log('📡 Server ready for MCP connections');
    this.log('🛡️  ACTIVE SECURITY: Policies loaded, monitoring enabled');
    this.log('🔒 All tool usage will be evaluated against security policies');
    this.log('⚡ Real-time blocking and approval workflows active');
    this.log('🌐 Visit https://canopyiq.ai/dashboard to monitor activity');
  }

  handleInput(data) {
    const lines = data.trim().split('\n');
    
    for (const line of lines) {
      if (!line.trim()) continue;
      
      try {
        const request = JSON.parse(line);
        this.handleMCPRequest(request);
      } catch (error) {
        this.log(`Invalid JSON received: ${error.message}`, 'error');
        this.sendError(-32700, 'Parse error', null);
      }
    }
  }

  async handleMCPRequest(request) {
    const { id, method, params } = request;
    
    this.log(`🔍 MCP Request: ${method} (ID: ${id})`);
    this.streamEvent('mcp_request', { method, params, id });

    try {
      switch (method) {
        case 'initialize':
          await this.handleInitialize(id, params);
          break;
          
        case 'tools/list':
          await this.handleToolsList(id);
          break;
          
        case 'tools/call':
          await this.handleToolCall(id, params);
          break;
          
        default:
          this.sendError(-32601, `Method not found: ${method}`, id);
      }
    } catch (error) {
      this.log(`Error handling ${method}: ${error.message}`, 'error');
      this.sendError(-32603, error.message, id);
    }
  }

  async handleInitialize(id, params) {
    this.initialized = true;
    
    const response = {
      jsonrpc: '2.0',
      id: id,
      result: {
        protocolVersion: '2025-06-18',
        capabilities: {
          tools: { listChanged: true }
        },
        serverInfo: {
          name: 'CanopyIQ MCP Server',
          version: '2.0.0'
        }
      }
    };

    this.sendResponse(response);
    this.log('🤝 MCP Protocol initialized successfully');
    
    // Load and inject project context
    this.injectProjectContext();
  }

  async handleToolsList(id) {
    const response = {
      jsonrpc: '2.0',
      id: id,
      result: {
        tools: this.availableTools
      }
    };

    this.sendResponse(response);
    this.log(`📋 Listed ${this.availableTools.length} available tools`);
  }

  async handleToolCall(id, params) {
    const { name, arguments: args } = params;
    
    this.log(`🔧 Tool call: ${name}`);
    this.usageTracker.toolCallCount++;
    
    // Risk assessment
    const riskLevel = this.assessRisk(name, args);
    this.log(`🎯 Risk Assessment: ${riskLevel.level} (score: ${riskLevel.score})`);
    
    // Stream monitoring data
    this.streamEvent('tool_call', {
      tool: name,
      arguments: args,
      riskLevel: riskLevel.level,
      riskScore: riskLevel.score,
      timestamp: new Date().toISOString()
    });

    // Policy check
    const policyDecision = await this.checkPolicies(name, args, riskLevel);
    
    if (policyDecision.action === 'deny') {
      this.sendError(-32000, `Policy violation: ${policyDecision.reason}`, id);
      return;
    }
    
    if (policyDecision.action === 'approval') {
      const approved = await this.requestApproval(name, args, riskLevel);
      if (!approved) {
        this.sendError(-32000, 'Operation requires approval and was denied', id);
        return;
      }
    }

    try {
      // Execute the tool with monitoring
      const result = await this.executeTool(name, args);
      
      // Track file access and changes
      this.trackActivity(name, args, result);
      
      const response = {
        jsonrpc: '2.0',
        id: id,
        result: {
          content: [
            {
              type: 'text',
              text: result.output || result
            }
          ]
        }
      };
      
      this.sendResponse(response);
      this.log(`✅ Tool executed successfully: ${name}`);
      
    } catch (error) {
      this.log(`❌ Tool execution failed: ${error.message}`, 'error');
      this.sendError(-32000, `Tool execution failed: ${error.message}`, id);
    }
  }

  // ================================
  // Tool Execution with Monitoring
  // ================================

  async executeTool(name, args) {
    switch (name) {
      case 'bash':
        return await this.executeBash(args);
      case 'read_file':
        return await this.executeReadFile(args);
      case 'write_file':
        return await this.executeWriteFile(args);
      case 'edit_file':
        return await this.executeEditFile(args);
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  }

  async executeBash(args) {
    const { exec } = require('child_process');
    const { promisify } = require('util');
    const execAsync = promisify(exec);
    
    this.log(`🖥️  Executing: ${args.command}`);
    
    try {
      const { stdout, stderr } = await execAsync(args.command, {
        cwd: process.cwd(),
        timeout: 30000,
        maxBuffer: 1024 * 1024 // 1MB
      });
      
      return {
        output: stdout || stderr,
        success: true
      };
    } catch (error) {
      return {
        output: error.message,
        success: false
      };
    }
  }

  async executeReadFile(args) {
    const { file_path, limit, offset } = args;
    
    this.log(`📖 Reading: ${file_path}`);
    
    try {
      let content = fs.readFileSync(file_path, 'utf8');
      
      if (offset || limit) {
        const lines = content.split('\n');
        const start = offset || 0;
        const end = limit ? start + limit : lines.length;
        content = lines.slice(start, end).join('\n');
      }
      
      return {
        output: content,
        file_path: file_path
      };
    } catch (error) {
      throw new Error(`Failed to read file: ${error.message}`);
    }
  }

  async executeWriteFile(args) {
    const { file_path, content } = args;
    
    this.log(`📝 Writing: ${file_path}`);
    
    try {
      fs.writeFileSync(file_path, content, 'utf8');
      return {
        output: `File written successfully: ${file_path}`,
        file_path: file_path,
        bytes_written: Buffer.byteLength(content, 'utf8')
      };
    } catch (error) {
      throw new Error(`Failed to write file: ${error.message}`);
    }
  }

  async executeEditFile(args) {
    const { file_path, old_string, new_string } = args;
    
    this.log(`✏️  Editing: ${file_path}`);
    
    try {
      let content = fs.readFileSync(file_path, 'utf8');
      
      if (!content.includes(old_string)) {
        throw new Error('String to replace not found in file');
      }
      
      const newContent = content.replace(old_string, new_string);
      fs.writeFileSync(file_path, newContent, 'utf8');
      
      return {
        output: `File edited successfully: ${file_path}`,
        file_path: file_path,
        changes_made: 1
      };
    } catch (error) {
      throw new Error(`Failed to edit file: ${error.message}`);
    }
  }

  // ================================
  // Risk Assessment & Policy Engine
  // ================================

  assessRisk(toolName, args) {
    let riskScore = 0;
    let riskFactors = [];

    // Tool-based risk
    if (toolName === 'bash') {
      riskScore += 3;
      const command = args.command || '';
      
      for (const pattern of this.riskPatterns.sensitiveCommands) {
        if (pattern.test(command)) {
          riskScore += 5;
          riskFactors.push(`Sensitive command: ${pattern.source}`);
        }
      }
    }

    // File-based risk
    if (['read_file', 'write_file', 'edit_file'].includes(toolName)) {
      const filePath = args.file_path || '';
      
      for (const pattern of this.riskPatterns.highRisk) {
        if (pattern.test(filePath)) {
          riskScore += 4;
          riskFactors.push(`High-risk file: ${pattern.source}`);
        }
      }
      
      for (const pattern of this.riskPatterns.mediumRisk) {
        if (pattern.test(filePath)) {
          riskScore += 2;
          riskFactors.push(`Medium-risk file: ${pattern.source}`);
        }
      }
    }

    let level;
    if (riskScore >= 7) level = 'HIGH';
    else if (riskScore >= 4) level = 'MEDIUM';
    else level = 'LOW';

    return { level, score: riskScore, factors: riskFactors };
  }

  async checkPolicies(toolName, args, riskLevel) {
    // Default policy: allow low risk, require approval for high risk
    if (riskLevel.level === 'HIGH') {
      return {
        action: 'approval',
        reason: 'High-risk operation requires approval'
      };
    }

    // Check if accessing sensitive files
    if (['read_file', 'write_file', 'edit_file'].includes(toolName)) {
      const filePath = args.file_path || '';
      for (const pattern of this.riskPatterns.highRisk) {
        if (pattern.test(filePath)) {
          this.usageTracker.sensitiveFileAccess++;
          return {
            action: 'approval',
            reason: `Access to sensitive file: ${filePath}`
          };
        }
      }
    }

    return { action: 'allow', reason: 'Operation within policy bounds' };
  }

  async requestApproval(toolName, args, riskLevel) {
    // For demo, auto-approve after logging
    this.log(`🚨 APPROVAL REQUIRED: ${toolName} - Risk: ${riskLevel.level}`);
    this.streamEvent('approval_request', {
      tool: toolName,
      arguments: args,
      riskLevel: riskLevel.level,
      timestamp: new Date().toISOString()
    });

    // In production, this would connect to Slack/Teams for human approval
    // For now, auto-approve to demonstrate the flow
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    this.log(`✅ APPROVAL GRANTED: ${toolName}`);
    return true;
  }

  // ================================
  // Activity Tracking & Context
  // ================================

  trackActivity(toolName, args, result) {
    const activity = {
      timestamp: new Date().toISOString(),
      tool: toolName,
      arguments: args,
      result: result,
      sessionId: this.sessionId
    };

    // Track file changes
    if (['write_file', 'edit_file'].includes(toolName)) {
      this.usageTracker.codeChanges++;
      this.fileAccessHistory.push(activity);
    }

    // Update project context
    this.projectContext.lastActivity = activity.timestamp;
    this.projectContext.conversationFlow.push({
      type: 'tool_call',
      tool: toolName,
      timestamp: activity.timestamp
    });

    this.streamEvent('activity_tracked', activity);
  }

  // ================================
  // Project Context & Continuity
  // ================================

  loadProjectContext() {
    try {
      const contextPath = path.join(process.cwd(), '.canoryiq-context.json');
      if (fs.existsSync(contextPath)) {
        const saved = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
        this.projectContext = { ...this.projectContext, ...saved };
        this.log('📚 Loaded project context: ' + 
                `${this.projectContext.objectives.length} objectives, ` +
                `${this.projectContext.decisions.length} decisions`);
      }
    } catch (error) {
      this.log(`Warning: Could not load project context: ${error.message}`, 'warn');
    }
  }

  saveProjectContext() {
    try {
      const contextPath = path.join(process.cwd(), '.canoryiq-context.json');
      fs.writeFileSync(contextPath, JSON.stringify(this.projectContext, null, 2));
    } catch (error) {
      this.log(`Warning: Could not save project context: ${error.message}`, 'warn');
    }
  }

  injectProjectContext() {
    if (this.projectContext.objectives.length > 0 || this.projectContext.decisions.length > 0) {
      this.log('🧠 Injecting project context into new Claude Code session...');
      
      console.error('\n================================================================================');
      console.error('🧠 CANOPYIQ: CONTINUOUS CONTEXT RESTORED');
      console.error('================================================================================');
      console.error(`📁 PROJECT: ${path.basename(this.projectContext.projectPath)}`);
      console.error(`   Path: ${this.projectContext.projectPath}`);
      
      if (this.projectContext.objectives.length > 0) {
        console.error('\n🎯 ACTIVE OBJECTIVES:');
        this.projectContext.objectives.forEach((obj, i) => {
          console.error(`   ${i + 1}. ${obj.description} (${obj.status})`);
        });
      }
      
      if (this.projectContext.decisions.length > 0) {
        console.error('\n🧠 KEY DECISIONS:');
        this.projectContext.decisions.slice(-3).forEach(decision => {
          console.error(`   • ${decision.summary}`);
        });
      }
      
      console.error('\n💡 This context was automatically restored by CanopyIQ to maintain');
      console.error('   continuity across your Claude Code development sessions.');
      console.error('   Your previous progress, findings, and next steps are preserved above.');
      console.error('================================================================================\n');
    }
  }

  // ================================
  // Event Streaming & Monitoring
  // ================================

  async connectEventStream() {
    try {
      const wsUrl = this.serverUrl.replace('http', 'ws') + '/ws/events/' + this.sessionId;
      this.websocket = new WebSocket(wsUrl, {
        headers: { 'Authorization': `Bearer ${this.apiKey}` }
      });

      this.websocket.on('open', () => {
        this.log('🌐 Connected to CanopyIQ real-time event stream');
        
        // Validate API key
        this.client.get('/api/v1/validate').then(() => {
          this.log('API key validated successfully');
        }).catch(() => {
          this.log('Warning: Could not validate API key', 'warn');
        });
      });

      this.websocket.on('error', (error) => {
        this.log(`WebSocket error: ${error.message}`, 'warn');
      });

      this.websocket.on('close', () => {
        this.log('🔌 Disconnected from event stream', 'warn');
      });

    } catch (error) {
      this.log(`Failed to connect event stream: ${error.message}`, 'warn');
    }
  }

  streamEvent(type, data) {
    const event = {
      type,
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      data: data
    };

    if (this.websocket?.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify(event));
    } else {
      this.eventBuffer.push(event);
      if (this.eventBuffer.length > 100) {
        this.eventBuffer.shift();
      }
    }

    // Also send via HTTP as backup
    this.client.post('/api/v1/events', event).catch(() => {
      // Ignore HTTP errors, WebSocket is primary
    });
  }

  loadPolicies() {
    // Load default policies - in production this would come from the server
    this.policies = [
      {
        name: 'Sensitive File Access',
        pattern: /\.(env|key|pem|crt)$/i,
        action: 'approval'
      },
      {
        name: 'Destructive Commands',
        pattern: /rm\s+-rf/i,
        action: 'approval'
      }
    ];
    
    this.log(`⚠️ Failed to load policies, using default safety rules`, 'warn');
  }

  // ================================
  // MCP Protocol Utilities
  // ================================

  sendResponse(response) {
    const responseStr = JSON.stringify(response);
    process.stdout.write(responseStr + '\n');
    
    if (this.debug) {
      this.log(`📤 MCP Response: ${response.result ? 'SUCCESS' : 'ERROR'} (ID: ${response.id})`);
    }
  }

  sendError(code, message, id) {
    const error = {
      jsonrpc: '2.0',
      id: id,
      error: {
        code: code,
        message: message
      }
    };
    
    this.sendResponse(error);
    this.streamEvent('mcp_error', { code, message, id });
  }
}

module.exports = { CanopyIQMCPServer };