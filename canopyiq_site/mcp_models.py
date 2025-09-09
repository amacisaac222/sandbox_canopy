"""
MCP-specific database models for CanopyIQ
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum, Boolean, Float, Index
from sqlalchemy.orm import relationship
from database import Base, RiskLevel, ToolCallStatus
import enum
from datetime import datetime

class MCPSessionStatus(enum.Enum):
    ACTIVE = "active"
    DISCONNECTED = "disconnected" 
    COMPLETED = "completed"

class MCPSession(Base):
    """Track MCP client sessions (Claude Code instances)"""
    __tablename__ = "mcp_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False)
    api_key_hash = Column(String(255), nullable=False)  # Demo key identifier
    project_path = Column(String(500), nullable=True)
    project_name = Column(String(255), nullable=True)
    user_identifier = Column(String(255), nullable=True)  # Developer identifier
    status = Column(Enum(MCPSessionStatus), default=MCPSessionStatus.ACTIVE)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - note: tool_calls points to existing MCPToolCall in database.py
    file_accesses = relationship("MCPFileAccess", back_populates="session", cascade="all, delete-orphan")

class MCPFileAccess(Base):
    """Track file access patterns from MCP clients"""
    __tablename__ = "mcp_file_accesses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), ForeignKey("mcp_sessions.session_id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    operation = Column(String(50), nullable=False)  # read, write, edit, create, delete
    file_size_bytes = Column(Integer, nullable=True)
    is_sensitive = Column(Boolean, default=False)
    sensitivity_patterns = Column(JSON, nullable=True)  # Which patterns matched
    risk_level = Column(Enum(RiskLevel), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("MCPSession", back_populates="file_accesses")

class MCPProjectContext(Base):
    """Track project context and objectives across sessions"""
    __tablename__ = "mcp_project_contexts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), ForeignKey("mcp_sessions.session_id"), nullable=False)
    project_name = Column(String(255), nullable=False)
    project_path = Column(String(1000), nullable=False)
    objectives = Column(JSON, nullable=True)  # Array of objectives
    decisions = Column(JSON, nullable=True)   # Array of key decisions
    next_steps = Column(JSON, nullable=True)  # Array of next steps
    file_relationships = Column(JSON, nullable=True)  # File dependency map
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Note: MCPMetrics already exists in database.py