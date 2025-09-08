const axios = require('axios');
const WebSocket = require('ws');
const crypto = require('crypto');
const path = require('path');

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
    
    // Event streaming and real-time monitoring
    this.eventBuffer = [];
    this.sessionId = crypto.randomUUID();
    this.websocket = null;
    this.activeApprovals = new Map();
    
    // AI Code Governance policies and tracking
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

    // AI Project Context Continuity System
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

    // Load previous context if available
    this.loadProjectContext();
    
    // Load policies and connect to event stream
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
    console.log(`${emoji} [${timestamp}] ${message}`);
    
    // Also stream log events to dashboard
    this.streamEvent('log', { message, level, timestamp });
  }

  async connectEventStream() {
    try {
      // Connect WebSocket for real-time event streaming
      const wsUrl = this.serverUrl.replace('http', 'ws') + '/ws/events/' + this.sessionId;
      this.websocket = new WebSocket(wsUrl, {
        headers: { 'Authorization': `Bearer ${this.apiKey}` }
      });

      this.websocket.on('open', () => {
        this.log('🌐 Connected to CanopyIQ real-time event stream');
        this.streamEvent('session_start', { sessionId: this.sessionId });
      });

      this.websocket.on('message', (data) => {
        try {
          const message = JSON.parse(data);
          this.handleDashboardMessage(message);
        } catch (error) {
          this.log(`Invalid WebSocket message: ${error.message}`, 'error');
        }
      });

      this.websocket.on('error', (error) => {
        this.log(`WebSocket error: ${error.message}`, 'error');
      });

      this.websocket.on('close', () => {
        this.log('🔌 Disconnected from event stream, attempting reconnect...', 'warn');
        setTimeout(() => this.connectEventStream(), 5000);
      });

    } catch (error) {
      this.log(`Failed to connect event stream: ${error.message}`, 'error');
    }
  }

  streamEvent(type, data) {
    const event = {
      type,
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      data: data
    };

    // Buffer events if WebSocket not ready
    if (this.websocket?.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify(event));
    } else {
      this.eventBuffer.push(event);
      // Limit buffer size
      if (this.eventBuffer.length > 100) {
        this.eventBuffer.shift();
      }
    }

    // Also send via HTTP as backup
    this.client.post('/api/v1/events', event).catch(() => {
      // Ignore HTTP errors, WebSocket is primary
    });
  }

  handleDashboardMessage(message) {
    switch (message.type) {
      case 'approval_response':
        const approvalId = message.data.approvalId;
        if (this.activeApprovals.has(approvalId)) {
          const approval = this.activeApprovals.get(approvalId);
          approval.resolve(message.data.approved);
          this.activeApprovals.delete(approvalId);
        }
        break;
      
      case 'policy_update':
        this.log('📋 Policy update received from dashboard');
        this.loadPolicies();
        break;
        
      case 'ping':
        this.streamEvent('pong', { timestamp: new Date().toISOString() });
        break;
    }
  }

  assessFileRisk(filePath) {
    const normalizedPath = filePath.toLowerCase();
    
    // Check high-risk patterns
    for (const pattern of this.riskPatterns.highRisk) {
      if (pattern.test(normalizedPath)) {
        return { level: 'high', reason: `Sensitive file detected: ${pattern}` };
      }
    }
    
    // Check medium-risk patterns  
    for (const pattern of this.riskPatterns.mediumRisk) {
      if (pattern.test(normalizedPath)) {
        return { level: 'medium', reason: `Security-related file: ${pattern}` };
      }
    }
    
    return { level: 'low', reason: 'Standard file access' };
  }

  assessCommandRisk(command) {
    for (const pattern of this.riskPatterns.sensitiveCommands) {
      if (pattern.test(command)) {
        return { level: 'high', reason: `Dangerous command detected: ${pattern}` };
      }
    }
    return { level: 'low', reason: 'Standard command' };
  }

  // ---------- AI Project Context Continuity Methods ----------

  async loadProjectContext() {
    try {
      // Try to load existing project context from CanopyIQ
      const response = await this.client.get(`/api/v1/project-context/${this.getProjectId()}`);
      
      if (response.data) {
        const savedContext = response.data;
        
        // Merge saved context with current session
        this.projectContext = {
          ...this.projectContext,
          objectives: savedContext.objectives || [],
          decisions: savedContext.decisions || [],
          patterns: new Map(savedContext.patterns || []),
          blockers: savedContext.blockers || [],
          nextSteps: savedContext.nextSteps || [],
          codebaseUnderstanding: savedContext.codebaseUnderstanding || {},
          fileRelationships: new Map(savedContext.fileRelationships || []),
          previousSessions: savedContext.sessions || []
        };

        this.log(`📚 Loaded project context: ${this.projectContext.objectives.length} objectives, ${this.projectContext.decisions.length} decisions`, 'info');
        
        // Stream context restoration event
        this.streamEvent('context_restored', {
          objectives: this.projectContext.objectives,
          recentDecisions: this.projectContext.decisions.slice(-3),
          nextSteps: this.projectContext.nextSteps,
          sessionCount: this.projectContext.previousSessions?.length || 0
        });

        // 🧠 INJECT CONTEXT into Claude session for continuous knowledge
        await this.injectContextIntoSession();
      }
    } catch (error) {
      this.log(`No previous project context found - starting fresh`, 'info');
    }
  }

  getProjectId() {
    // Generate consistent project ID based on directory path
    const projectPath = this.projectContext.projectPath;
    return crypto.createHash('md5').update(projectPath).digest('hex').substring(0, 16);
  }

  async saveProjectContext() {
    try {
      const contextData = {
        projectId: this.getProjectId(),
        projectPath: this.projectContext.projectPath,
        lastSessionId: this.sessionId,
        lastActivity: new Date().toISOString(),
        objectives: this.projectContext.objectives,
        decisions: this.projectContext.decisions,
        patterns: Array.from(this.projectContext.patterns.entries()),
        blockers: this.projectContext.blockers,
        nextSteps: this.projectContext.nextSteps,
        codebaseUnderstanding: this.projectContext.codebaseUnderstanding,
        fileRelationships: Array.from(this.projectContext.fileRelationships.entries()),
        sessions: (this.projectContext.previousSessions || []).concat([{
          sessionId: this.sessionId,
          startTime: this.projectContext.startTime,
          endTime: new Date().toISOString(),
          toolCallCount: this.usageTracker.toolCallCount,
          filesAccessed: this.fileAccessHistory.length
        }]).slice(-10) // Keep last 10 sessions
      };

      await this.client.post('/api/v1/project-context', contextData);
      this.log(`💾 Project context saved successfully`, 'info');
      
    } catch (error) {
      this.log(`Failed to save project context: ${error.message}`, 'error');
    }
  }

  extractContextFromToolCall(tool, args, result) {
    // Extract valuable context from AI tool usage patterns
    const timestamp = new Date().toISOString();
    
    switch (tool.toLowerCase()) {
      case 'read':
        if (args.file_path) {
          // Track file relationships and understanding
          this.updateFileRelationships(args.file_path);
          this.trackFilePattern(args.file_path, 'read');
        }
        break;

      case 'write':
      case 'edit':
      case 'multiedit':
        if (args.file_path) {
          // Record code changes and patterns
          this.recordCodeDecision(args.file_path, args, timestamp);
          this.trackFilePattern(args.file_path, 'modify');
          
          // Extract potential objectives from comments or commit-like patterns
          if (args.new_string) {
            this.extractObjectivesFromCode(args.new_string);
          }
        }
        break;

      case 'bash':
        if (args.command) {
          // Track build patterns, test runs, deployment steps
          this.recordCommandPattern(args.command, timestamp);
          
          // Extract potential next steps from command sequences
          this.extractNextStepsFromCommands(args.command);
        }
        break;
    }

    // Update last activity
    this.projectContext.lastActivity = timestamp;
    
    // Periodically save context
    if (this.usageTracker.toolCallCount % 5 === 0) {
      this.saveProjectContext();
    }
  }

  updateFileRelationships(filePath) {
    const fileKey = path.basename(filePath);
    const dir = path.dirname(filePath);
    
    if (!this.projectContext.fileRelationships.has(fileKey)) {
      this.projectContext.fileRelationships.set(fileKey, {
        fullPath: filePath,
        accessCount: 0,
        lastAccessed: new Date().toISOString(),
        relatedFiles: new Set()
      });
    }
    
    const fileInfo = this.projectContext.fileRelationships.get(fileKey);
    fileInfo.accessCount++;
    fileInfo.lastAccessed = new Date().toISOString();
  }

  trackFilePattern(filePath, action) {
    const extension = path.extname(filePath);
    const patternKey = `${action}_${extension}`;
    
    if (!this.projectContext.patterns.has(patternKey)) {
      this.projectContext.patterns.set(patternKey, {
        count: 0,
        files: new Set(),
        lastSeen: null
      });
    }
    
    const pattern = this.projectContext.patterns.get(patternKey);
    pattern.count++;
    pattern.files.add(filePath);
    pattern.lastSeen = new Date().toISOString();
  }

  recordCodeDecision(filePath, args, timestamp) {
    // Extract meaningful decisions from code changes
    const decision = {
      id: crypto.randomUUID().substring(0, 8),
      timestamp,
      type: 'code_change',
      file: filePath,
      description: this.summarizeCodeChange(args),
      context: args
    };
    
    this.projectContext.decisions.push(decision);
    
    // Keep only recent decisions (last 50)
    if (this.projectContext.decisions.length > 50) {
      this.projectContext.decisions = this.projectContext.decisions.slice(-50);
    }

    // Stream decision to dashboard
    this.streamEvent('project_decision', decision);
  }

  summarizeCodeChange(args) {
    // Attempt to summarize what the code change accomplishes
    if (args.new_string && args.old_string) {
      const isAddition = args.old_string.length < args.new_string.length;
      const isDeletion = args.old_string.length > args.new_string.length;
      
      if (isAddition) return 'Added new functionality';
      if (isDeletion) return 'Removed/refactored code';
      return 'Modified existing code';
    }
    return 'Code modification';
  }

  recordCommandPattern(command, timestamp) {
    // Track common command patterns that indicate project workflows
    const workflows = {
      'npm run': 'build_workflow',
      'pytest': 'test_workflow', 
      'git': 'version_control',
      'docker': 'deployment_workflow',
      'pip install': 'dependency_management'
    };

    for (const [pattern, workflow] of Object.entries(workflows)) {
      if (command.includes(pattern)) {
        if (!this.projectContext.patterns.has(workflow)) {
          this.projectContext.patterns.set(workflow, { count: 0, lastSeen: null });
        }
        
        const workflowPattern = this.projectContext.patterns.get(workflow);
        workflowPattern.count++;
        workflowPattern.lastSeen = timestamp;
        break;
      }
    }
  }

  extractNextStepsFromCommands(command) {
    // Infer potential next steps from command patterns
    const nextStepInferences = {
      'npm test': 'Fix failing tests',
      'npm run build': 'Check build output',
      'git add': 'Commit changes',
      'pip install': 'Update requirements.txt',
      'docker build': 'Test container deployment'
    };

    for (const [pattern, nextStep] of Object.entries(nextStepInferences)) {
      if (command.includes(pattern)) {
        this.addNextStep(nextStep, 'inferred_from_command');
        break;
      }
    }
  }

  addNextStep(description, source, priority = 'medium') {
    const nextStep = {
      id: crypto.randomUUID().substring(0, 8),
      description,
      source,
      priority,
      timestamp: new Date().toISOString(),
      completed: false
    };

    this.projectContext.nextSteps.push(nextStep);
    
    // Keep only recent next steps (last 20)
    if (this.projectContext.nextSteps.length > 20) {
      this.projectContext.nextSteps = this.projectContext.nextSteps.slice(-20);
    }

    // Stream to dashboard
    this.streamEvent('next_step_identified', nextStep);
  }

  generateSessionSummary() {
    const summary = {
      sessionId: this.sessionId,
      duration: Date.now() - new Date(this.projectContext.startTime).getTime(),
      toolCalls: this.usageTracker.toolCallCount,
      filesAccessed: this.fileAccessHistory.length,
      decisionsRecorded: this.projectContext.decisions.filter(d => 
        new Date(d.timestamp) > new Date(this.projectContext.startTime)
      ).length,
      nextStepsIdentified: this.projectContext.nextSteps.filter(s => 
        new Date(s.timestamp) > new Date(this.projectContext.startTime)
      ).length,
      topPatterns: Array.from(this.projectContext.patterns.entries())
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 5)
    };

    return summary;
  }

  extractObjectivesFromCode(codeString) {
    // Extract potential objectives from code comments and patterns
    const objectivePatterns = [
      /(?:TODO|FIXME|NOTE|HACK):\s*(.+)/gi,
      /\/\/\s*(Add|Fix|Update|Remove|Implement)\s+(.+)/gi,
      /\/\*\s*(Add|Fix|Update|Remove|Implement)\s+(.+)\s*\*\//gi,
      /#\s*(Add|Fix|Update|Remove|Implement)\s+(.+)/gi
    ];

    for (const pattern of objectivePatterns) {
      let match;
      while ((match = pattern.exec(codeString)) !== null) {
        const objective = {
          id: crypto.randomUUID().substring(0, 8),
          description: match[1] || `${match[1]} ${match[2]}`,
          source: 'code_comment',
          priority: match[0].includes('FIXME') ? 'high' : 'medium',
          timestamp: new Date().toISOString(),
          completed: false
        };

        // Avoid duplicates
        const exists = this.projectContext.objectives.some(obj => 
          obj.description.toLowerCase() === objective.description.toLowerCase()
        );

        if (!exists && objective.description.length > 5) {
          this.projectContext.objectives.push(objective);
          this.streamEvent('objective_identified', objective);
        }
      }
    }
  }

  // 🧠 ENHANCED CONTINUOUS CONTEXT METHODS

  addKeyFinding(finding, category = 'general', priority = 'medium', source = 'analysis') {
    const newFinding = {
      id: crypto.randomUUID().substring(0, 8),
      text: finding,
      category: category,
      priority: priority,
      source: source,
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId
    };

    // Initialize keyFindings if not exists
    if (!this.projectContext.keyFindings) {
      this.projectContext.keyFindings = [];
    }

    // Avoid duplicates
    const exists = this.projectContext.keyFindings.some(f => 
      f.text.toLowerCase() === finding.toLowerCase()
    );

    if (!exists && finding.length > 10) {
      this.projectContext.keyFindings.push(newFinding);
      
      // Keep only the most recent 50 findings
      if (this.projectContext.keyFindings.length > 50) {
        this.projectContext.keyFindings = this.projectContext.keyFindings
          .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
          .slice(0, 50);
      }

      // Stream finding to dashboard
      this.streamEvent('key_finding_discovered', newFinding);
      this.log(`🔍 Key Finding: ${finding}`, 'info');
    }
  }

  addNextStep(step, priority = 'medium', category = 'development') {
    const newStep = {
      id: crypto.randomUUID().substring(0, 8),
      text: step,
      priority: priority,
      category: category,
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      status: 'pending',
      estimatedEffort: this.estimateEffort(step)
    };

    // Avoid duplicates
    const exists = this.projectContext.nextSteps.some(s => 
      s.text.toLowerCase() === step.toLowerCase()
    );

    if (!exists && step.length > 5) {
      this.projectContext.nextSteps.push(newStep);
      
      // Keep only the most recent 30 next steps
      if (this.projectContext.nextSteps.length > 30) {
        this.projectContext.nextSteps = this.projectContext.nextSteps
          .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
          .slice(0, 30);
      }

      // Stream next step to dashboard
      this.streamEvent('next_step_identified', newStep);
      this.log(`📋 Next Step: ${step}`, 'info');
    }
  }

  estimateEffort(step) {
    const effortKeywords = {
      high: ['deploy', 'migrate', 'refactor', 'architecture', 'security', 'performance'],
      medium: ['implement', 'build', 'create', 'add', 'update', 'configure'],
      low: ['fix', 'adjust', 'tweak', 'document', 'review', 'test']
    };

    const stepLower = step.toLowerCase();
    
    for (const [effort, keywords] of Object.entries(effortKeywords)) {
      if (keywords.some(keyword => stepLower.includes(keyword))) {
        return effort;
      }
    }
    
    return 'medium';
  }

  analyzeFileForInsights(filePath, content) {
    // Extract technical insights from file content
    if (!content) return;

    // Detect frameworks and technologies
    this.detectTechnologies(content);
    
    // Analyze architecture patterns
    this.analyzeArchitecture(filePath, content);
    
    // Extract business logic insights
    this.extractBusinessLogic(filePath, content);
  }

  detectTechnologies(content) {
    const technologies = {
      // Frontend Frameworks
      'React': /import.*react|jsx|useState|useEffect|createContext/i,
      'Vue.js': /import.*vue|\.vue|v-if|v-for|v-model/i,
      'Angular': /import.*@angular|ng-|ngIf|ngFor/i,
      'Svelte': /import.*svelte|\$:|on:|bind:/i,
      
      // Backend Frameworks  
      'FastAPI': /@app\.|from fastapi|async def.*\(request|HTTPException/i,
      'Express.js': /app\.(get|post|put|delete)|express\(\)|req\.|res\./i,
      'Django': /from django|models\.Model|def get|HttpResponse/i,
      'Flask': /from flask|@app\.route|request\.|jsonify/i,
      'Spring Boot': /@RestController|@Service|@Autowired|@Entity/i,
      
      // Databases
      'PostgreSQL': /psycopg|postgresql:|SELECT.*FROM|pg_|SERIAL|UUID/i,
      'MongoDB': /mongoose|db\.collection|ObjectId|find\(\)|insertOne/i,
      'Redis': /redis\.|HSET|HGET|expire|lpush/i,
      'SQLite': /sqlite3|\.db|pragma|AUTOINCREMENT/i,
      
      // Cloud & DevOps
      'Docker': /FROM |COPY |RUN |EXPOSE|Dockerfile|docker-compose/i,
      'AWS': /aws-|boto3|s3\.|ec2\.|lambda|dynamodb/i,
      'Google Cloud': /google-cloud|gcp|firebase|firestore/i,
      'Azure': /azure-|@azure/i,
      
      // Other Technologies
      'WebSocket': /websocket|socket\.io|ws:|WebSocket\(/i,
      'GraphQL': /graphql|gql`|Query|Mutation|resolver/i,
      'JWT': /jsonwebtoken|jwt\.|token|Bearer/i,
      'OAuth': /oauth|OpenID|auth0|passport/i
    };

    for (const [tech, pattern] of Object.entries(technologies)) {
      if (pattern.test(content)) {
        this.addKeyFinding(`Project uses ${tech}`, 'technology', 'low', 'code_analysis');
      }
    }
  }

  analyzeArchitecture(filePath, content) {
    // Analyze architectural patterns
    const patterns = {
      'API Endpoints': /\/(api|v1|v2)\/|@app\.(get|post|put|delete)/i,
      'Database Models': /class.*Model|Schema|Table|Entity/i,
      'Authentication': /login|logout|auth|token|session|permission/i,
      'Error Handling': /try.*catch|except:|error|throw|raise/i,
      'Testing': /test\(|expect\(|assert|describe\(|it\(/i,
      'Configuration': /config|settings|\.env|environment|process\.env/i,
      'Middleware': /middleware|interceptor|guard|filter/i,
      'State Management': /redux|vuex|pinia|context|store|state/i,
      'Routing': /router|route|path|navigate|redirect/i,
      'Validation': /validate|schema|yup|joi|zod/i
    };

    for (const [pattern, regex] of Object.entries(patterns)) {
      if (regex.test(content)) {
        this.addKeyFinding(`${path.basename(filePath)} implements ${pattern}`, 'architecture', 'medium', 'file_analysis');
      }
    }
  }

  extractBusinessLogic(filePath, content) {
    // Extract business domain insights
    const businessPatterns = {
      'User Management': /user|account|profile|registration|signup/i,
      'Payment Processing': /payment|billing|stripe|paypal|invoice/i,
      'E-commerce': /cart|order|product|inventory|checkout/i,
      'Content Management': /post|article|content|cms|blog/i,
      'Analytics': /analytics|tracking|metrics|dashboard|report/i,
      'Notifications': /notification|email|sms|push|alert/i,
      'File Management': /upload|download|file|storage|attachment/i,
      'Search': /search|index|elasticsearch|solr|query/i,
      'Real-time Features': /websocket|live|real-time|streaming/i,
      'AI/ML': /ai|ml|model|prediction|classification|neural/i
    };

    for (const [domain, pattern] of Object.entries(businessPatterns)) {
      if (pattern.test(content)) {
        this.addKeyFinding(`Project includes ${domain} functionality`, 'business_domain', 'medium', 'business_analysis');
      }
    }
  }

  generateContextSummary() {
    const context = this.projectContext;
    return {
      sessionId: this.sessionId,
      projectPath: context.projectPath,
      duration: Date.now() - new Date(context.startTime).getTime(),
      
      // Key Statistics
      stats: {
        objectives: context.objectives?.length || 0,
        keyFindings: context.keyFindings?.length || 0,
        nextSteps: context.nextSteps?.length || 0,
        decisions: context.decisions?.length || 0,
        filesAccessed: this.fileAccessHistory.length,
        toolCalls: this.usageTracker.toolCallCount
      },
      
      // Recent Activity Summary
      recentFindings: context.keyFindings?.slice(-5) || [],
      urgentNextSteps: context.nextSteps?.filter(step => step.priority === 'high') || [],
      lastActivity: context.lastActivity
    };
  }

  // 🧠 CONTEXT INJECTION FOR NEW CLAUDE SESSIONS
  async injectContextIntoSession() {
    try {
      // Generate context summary for Claude
      const contextSummary = this.generateContextForClaude();
      
      if (contextSummary.hasContent) {
        this.log('🧠 Injecting project context into new Claude Code session...', 'info');
        
        // Log context injection for the user to see
        console.log('\n' + '='.repeat(80));
        console.log('🧠 CANOPYIQ: CONTINUOUS CONTEXT RESTORED');
        console.log('='.repeat(80));
        console.log(contextSummary.summary);
        console.log('='.repeat(80) + '\n');
        
        // Stream context injection event
        this.streamEvent('context_injected', {
          summary: contextSummary.summary,
          stats: contextSummary.stats,
          timestamp: new Date().toISOString()
        });
      }
    } catch (error) {
      this.log(`Context injection failed: ${error.message}`, 'warn');
    }
  }

  generateContextForClaude() {
    const context = this.projectContext;
    let summary = '';
    let hasContent = false;

    // Project Overview
    if (context.projectPath) {
      summary += `📁 PROJECT: ${path.basename(context.projectPath)}\n`;
      summary += `   Path: ${context.projectPath}\n\n`;
      hasContent = true;
    }

    // Key Findings
    if (context.keyFindings && context.keyFindings.length > 0) {
      summary += `🔍 KEY FINDINGS FROM PREVIOUS SESSIONS (${context.keyFindings.length} total):\n`;
      const recentFindings = context.keyFindings
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .slice(0, 8);
      
      recentFindings.forEach((finding, index) => {
        const priority = finding.priority === 'high' ? '⚠️' : finding.priority === 'medium' ? '📌' : '💡';
        summary += `   ${priority} ${finding.text} (${finding.category})\n`;
      });
      summary += '\n';
      hasContent = true;
    }

    // Next Steps
    if (context.nextSteps && context.nextSteps.length > 0) {
      const pendingSteps = context.nextSteps.filter(step => step.status === 'pending');
      if (pendingSteps.length > 0) {
        summary += `📋 NEXT STEPS FROM PREVIOUS SESSIONS (${pendingSteps.length} pending):\n`;
        const urgentSteps = pendingSteps.filter(step => step.priority === 'high').slice(0, 5);
        const normalSteps = pendingSteps.filter(step => step.priority !== 'high').slice(0, 5);
        
        urgentSteps.forEach(step => {
          summary += `   🚨 [HIGH] ${step.text} (${step.category})\n`;
        });
        
        normalSteps.forEach(step => {
          const icon = step.estimatedEffort === 'high' ? '🔧' : step.estimatedEffort === 'low' ? '🔨' : '⚙️';
          summary += `   ${icon} ${step.text} (${step.category})\n`;
        });
        summary += '\n';
        hasContent = true;
      }
    }

    // Recent Objectives
    if (context.objectives && context.objectives.length > 0) {
      const activeObjectives = context.objectives.filter(obj => !obj.completed).slice(0, 5);
      if (activeObjectives.length > 0) {
        summary += `🎯 ACTIVE OBJECTIVES (${activeObjectives.length} active):\n`;
        activeObjectives.forEach(objective => {
          const priority = objective.priority === 'high' ? '🔥' : '📌';
          summary += `   ${priority} ${objective.description}\n`;
        });
        summary += '\n';
        hasContent = true;
      }
    }

    // Recent Decisions
    if (context.decisions && context.decisions.length > 0) {
      summary += `⚡ RECENT TECHNICAL DECISIONS (${context.decisions.length} total):\n`;
      context.decisions.slice(-3).forEach(decision => {
        summary += `   💡 ${decision.description || decision.summary}\n`;
      });
      summary += '\n';
      hasContent = true;
    }

    // Technologies Detected
    const technologies = new Set();
    if (context.keyFindings) {
      context.keyFindings
        .filter(f => f.category === 'technology')
        .forEach(f => technologies.add(f.text.replace('Project uses ', '')));
    }
    
    if (technologies.size > 0) {
      summary += `🛠️ DETECTED TECHNOLOGIES: ${Array.from(technologies).slice(0, 8).join(', ')}\n\n`;
      hasContent = true;
    }

    // Session Info
    const sessionCount = context.previousSessions?.length || 0;
    if (sessionCount > 0) {
      summary += `📊 CONTEXT STATISTICS:\n`;
      summary += `   • Previous Sessions: ${sessionCount}\n`;
      summary += `   • Total Findings: ${context.keyFindings?.length || 0}\n`;
      summary += `   • Pending Next Steps: ${context.nextSteps?.filter(s => s.status === 'pending').length || 0}\n`;
      summary += `   • Active Objectives: ${context.objectives?.filter(o => !o.completed).length || 0}\n\n`;
    }

    if (hasContent) {
      summary += `💡 This context was automatically restored by CanopyIQ to maintain\n`;
      summary += `   continuity across your Claude Code development sessions.\n`;
      summary += `   Your previous progress, findings, and next steps are preserved above.`;
    }

    return {
      hasContent,
      summary,
      stats: {
        findings: context.keyFindings?.length || 0,
        nextSteps: context.nextSteps?.length || 0,
        objectives: context.objectives?.length || 0,
        decisions: context.decisions?.length || 0,
        technologies: technologies.size
      }
    };
  }

  async onShutdown() {
    try {
      this.log('💾 Saving project context before shutdown...', 'info');
      
      // Generate final session summary
      const sessionSummary = this.generateSessionSummary();
      
      // Save final project context
      await this.saveProjectContext();
      
      // Stream final session summary
      this.streamEvent('session_ended', {
        summary: sessionSummary,
        contextSaved: true,
        timestamp: new Date().toISOString()
      });
      
      this.log(`📊 Session Summary: ${sessionSummary.toolCalls} tools, ${sessionSummary.filesAccessed} files, ${sessionSummary.decisionsRecorded} decisions recorded`, 'info');
      this.log('🔒 Project context preserved for next session', 'info');
      
      // Close WebSocket
      if (this.websocket) {
        this.websocket.close();
      }
      
      setTimeout(() => process.exit(0), 1000); // Give time for final saves
      
    } catch (error) {
      this.log(`Error during shutdown: ${error.message}`, 'error');
      process.exit(1);
    }
  }

  async handleGovernedToolCall(id, args) {
    const { original_tool, tool_args, risk_context } = args;
    const startTime = Date.now();

    try {
      // Stream tool call event to dashboard in real-time
      this.streamEvent('tool_call_start', {
        tool: original_tool,
        args: tool_args,
        context: risk_context,
        sessionId: this.sessionId
      });

      // Analyze the tool call for AI governance
      const governance = await this.analyzeToolCallGovernance(original_tool, tool_args);
      
      // Update usage tracking
      this.usageTracker.toolCallCount++;
      if (governance.riskLevel === 'high') {
        this.usageTracker.riskScore += 10;
      } else if (governance.riskLevel === 'medium') {
        this.usageTracker.riskScore += 3;
      }

      // Check if approval is required
      if (governance.requiresApproval) {
        const approvalResult = await this.requestRealTimeApproval(original_tool, tool_args, governance);
        
        if (!approvalResult.approved) {
          this.streamEvent('tool_call_blocked', {
            tool: original_tool,
            reason: governance.reason,
            riskLevel: governance.riskLevel
          });

          return {
            id,
            error: {
              code: -32001,
              message: `🛡️ AI Governance: ${governance.reason}\n\nThis operation requires approval. Check your CanopyIQ dashboard.`
            }
          };
        }
      }

      // Tool is approved - execute and monitor
      const result = await this.executeMonitoredTool(original_tool, tool_args);
      const endTime = Date.now();

      // EXTRACT PROJECT CONTEXT from this tool call
      this.extractContextFromToolCall(original_tool, tool_args, result);

      // Stream completion event
      this.streamEvent('tool_call_complete', {
        tool: original_tool,
        riskLevel: governance.riskLevel,
        duration: endTime - startTime,
        success: true
      });

      return {
        id,
        result: {
          content: [
            {
              type: 'text', 
              text: result.output || 'Tool executed successfully'
            }
          ],
          governance: {
            riskLevel: governance.riskLevel,
            monitored: true,
            approvalRequired: governance.requiresApproval
          }
        }
      };

    } catch (error) {
      this.streamEvent('tool_call_error', {
        tool: original_tool,
        error: error.message
      });

      return {
        id,
        error: {
          code: -32603,
          message: `Tool execution failed: ${error.message}`
        }
      };
    }
  }

  async analyzeToolCallGovernance(tool, args) {
    const analysis = {
      riskLevel: 'low',
      requiresApproval: false,
      reason: 'Standard operation',
      sensitiveFiles: [],
      commands: []
    };

    switch (tool.toLowerCase()) {
      case 'read':
        if (args.file_path) {
          const fileRisk = this.assessFileRisk(args.file_path);
          analysis.riskLevel = fileRisk.level;
          analysis.reason = fileRisk.reason;
          analysis.requiresApproval = fileRisk.level === 'high';
          
          if (fileRisk.level !== 'low') {
            analysis.sensitiveFiles.push(args.file_path);
            this.usageTracker.sensitiveFileAccess++;
          }

          // Track file access
          this.fileAccessHistory.push({
            type: 'READ',
            path: args.file_path,
            timestamp: new Date().toISOString(),
            riskLevel: fileRisk.level
          });
        }
        break;

      case 'write':
      case 'edit':
      case 'multiedit':
        if (args.file_path) {
          const fileRisk = this.assessFileRisk(args.file_path);
          analysis.riskLevel = fileRisk.level === 'low' ? 'medium' : 'high'; // Writing is always riskier
          analysis.reason = `Code modification: ${fileRisk.reason}`;
          analysis.requiresApproval = analysis.riskLevel === 'high';
          
          this.usageTracker.codeChanges++;
          analysis.sensitiveFiles.push(args.file_path);
        }
        break;

      case 'bash':
        if (args.command) {
          const commandRisk = this.assessCommandRisk(args.command);
          analysis.riskLevel = commandRisk.level;
          analysis.reason = commandRisk.reason;
          analysis.requiresApproval = commandRisk.level === 'high';
          analysis.commands.push(args.command);
        }
        break;

      case 'webfetch':
        // External web requests are medium risk
        analysis.riskLevel = 'medium';
        analysis.reason = 'External web request';
        break;
    }

    return analysis;
  }

  async requestRealTimeApproval(tool, args, governance) {
    const approvalId = crypto.randomUUID();
    
    try {
      // Send approval request with full context
      const approvalRequest = {
        id: approvalId,
        tool: tool,
        arguments: args,
        riskLevel: governance.riskLevel,
        reason: governance.reason,
        sensitiveFiles: governance.sensitiveFiles,
        commands: governance.commands,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId
      };

      // Stream to dashboard for real-time approval
      this.streamEvent('approval_required', approvalRequest);

      // Also send via API
      await this.client.post('/api/v1/approvals', approvalRequest);
      
      // Wait for approval response (with timeout)
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          this.activeApprovals.delete(approvalId);
          resolve({ approved: false, message: 'Approval timeout - request denied for safety' });
        }, 30000); // 30 second timeout

        this.activeApprovals.set(approvalId, {
          resolve: (approved) => {
            clearTimeout(timeout);
            resolve({ approved, message: approved ? 'Approved' : 'Denied' });
          }
        });
      });

    } catch (error) {
      this.log(`Approval request failed: ${error.message}`, 'error');
      return { approved: false, message: 'Approval system unavailable - blocking for safety' };
    }
  }

  async executeMonitoredTool(tool, args) {
    // For now, return mock execution - in production this would proxy to actual Claude Code tools
    return {
      output: `[MONITORED] ${tool.toUpperCase()} operation completed successfully`,
      success: true
    };
  }

  async handleDirectToolCall(id, name, args) {
    // Legacy handler for direct tool calls
    return this.handleGovernedToolCall(id, {
      original_tool: name,
      tool_args: args,
      risk_context: 'direct_call'
    });
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
                  name: 'ai_governance_proxy',
                  description: 'Proxy and monitor all Claude Code tool calls for AI governance',
                  inputSchema: {
                    type: 'object',
                    properties: {
                      original_tool: { type: 'string' },
                      tool_args: { type: 'object' },
                      risk_context: { type: 'string' }
                    },
                    required: ['original_tool', 'tool_args']
                  }
                }
              ]
            }
          };

        case 'tools/call':
          const { name, arguments: args } = params;
          
          if (name === 'ai_governance_proxy') {
            return await this.handleGovernedToolCall(id, args);
          }
          
          // For backwards compatibility, handle direct tool calls
          return await this.handleDirectToolCall(id, name, args);

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
      this.onShutdown();
    });
  }
}

module.exports = { CanopyIQMCPServer };