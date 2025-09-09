"""
MCP Event Processor for CanopyIQ
Handles incoming MCP events and updates database/dashboard
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from mcp_models import (
    MCPSession, MCPFileAccess, MCPProjectContext, MCPSessionStatus
)
from database import MCPToolCall, MCPMetrics, RiskLevel, ToolCallStatus

logger = logging.getLogger(__name__)

class MCPEventProcessor:
    """Process MCP events and update database/dashboard"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Create a hash of API key for storage (privacy)"""
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    async def process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point for processing MCP events"""
        event_type = event_data.get('type')
        session_id = event_data.get('sessionId', 'unknown')
        timestamp_str = event_data.get('timestamp')
        data = event_data.get('data', {})
        
        logger.info(f"Processing MCP event: {event_type} from {session_id}")
        
        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        # Route to appropriate handler
        dashboard_updates = {}
        
        if event_type == 'session_start':
            dashboard_updates = await self._handle_session_start(session_id, data, timestamp)
        elif event_type == 'tool_call':
            dashboard_updates = await self._handle_tool_call(session_id, data, timestamp)
        elif event_type == 'file_access':
            dashboard_updates = await self._handle_file_access(session_id, data, timestamp)
        elif event_type == 'approval_request':
            dashboard_updates = await self._handle_approval_request(session_id, data, timestamp)
        elif event_type == 'project_context':
            dashboard_updates = await self._handle_project_context(session_id, data, timestamp)
        elif event_type == 'log':
            # Handle log events (less critical)
            pass
        else:
            logger.warning(f"Unknown MCP event type: {event_type}")
        
        # Update daily metrics
        await self._update_daily_metrics(session_id, event_type, data, timestamp)
        
        return dashboard_updates
    
    async def _handle_session_start(self, session_id: str, data: Dict, timestamp: datetime) -> Dict:
        """Handle MCP session start events"""
        api_key = data.get('api_key', 'unknown')
        api_key_hash = self.hash_api_key(api_key)
        
        # Create or update session
        session = await self._get_or_create_session(session_id, api_key_hash, data, timestamp)
        
        return {
            'type': 'session_started',
            'session_id': session_id,
            'project': data.get('projectPath', 'Unknown Project'),
            'timestamp': timestamp.isoformat()
        }
    
    async def _handle_tool_call(self, session_id: str, data: Dict, timestamp: datetime) -> Dict:
        """Handle tool execution events"""
        tool_name = data.get('tool', 'unknown')
        arguments = data.get('arguments', {})
        result = data.get('result', '')
        risk_level = data.get('riskLevel', 'LOW')
        risk_score = data.get('riskScore', 0)
        risk_factors = data.get('riskFactors', [])
        success = data.get('success', True)
        
        # Determine status
        if success:
            status = ToolCallStatus.EXECUTED
        else:
            status = ToolCallStatus.FAILED
            
        # Create tool call record
        tool_call = MCPToolCall(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            result=str(result)[:5000],  # Limit result size
            status=status,
            risk_level=RiskLevel(risk_level.lower()),
            risk_score=risk_score,
            risk_factors=risk_factors,
            execution_time_ms=data.get('duration', 0),
            timestamp=timestamp
        )
        
        self.db.add(tool_call)
        
        # Update session last activity
        await self._update_session_activity(session_id, timestamp)
        
        return {
            'type': 'tool_executed',
            'session_id': session_id,
            'tool': tool_name,
            'risk_level': risk_level,
            'risk_score': risk_score,
            'timestamp': timestamp.isoformat()
        }
    
    async def get_dashboard_summary(self, api_key_hash: str = None) -> Dict[str, Any]:
        """Get summary data for dashboard display"""
        # Get recent activity (last 24 hours)
        since = datetime.utcnow() - timedelta(hours=24)
        
        recent_tool_calls = await self.db.scalar(
            select(func.count(MCPToolCall.id)).where(MCPToolCall.timestamp >= since)
        )
        
        recent_files = await self.db.scalar(
            select(func.count(MCPFileAccess.id)).where(MCPFileAccess.timestamp >= since)
        )
        
        return {
            'recent_tool_calls': recent_tool_calls or 0, 
            'recent_files_accessed': recent_files or 0,
            'timestamp': datetime.utcnow().isoformat()
        }