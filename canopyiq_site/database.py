"""
CanopyIQ Database Models and Configuration
"""
import os
import enum
from datetime import datetime
from typing import Optional, AsyncGenerator
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum, 
    create_engine, BigInteger, Boolean, Index
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Get database URL from environment, fallback to SQLite for development
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("CP_DB_URL", "sqlite+aiosqlite:///./canopyiq.db")

# Convert postgres:// to postgresql+asyncpg:// if needed (Railway compatibility)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    AUDITOR = "auditor" 
    VIEWER = "viewer"

class ApprovalStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"

class Submission(Base):
    """Contact form submissions table"""
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(BigInteger, nullable=False)  # Unix timestamp
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    source_ip = Column(String(45), nullable=True)  # IPv4/IPv6
    user_agent = Column(Text, nullable=True)

class AuditLog(Base):
    """Audit log for tracking user actions"""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(BigInteger, nullable=False)  # Unix timestamp
    actor = Column(String(255), nullable=False)  # User ID or system
    action = Column(String(255), nullable=False)  # CREATE, READ, UPDATE, DELETE
    resource = Column(String(255), nullable=False)  # Resource type/name
    attributes = Column(JSON, nullable=True)  # Additional context

class User(Base):
    """User accounts table"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    provider_id = Column(String(255), nullable=True)  # OIDC subject ID
    password_hash = Column(String(255), nullable=True)  # For local auth
    auth_provider = Column(String(50), nullable=False, default="local")  # "local" or "oidc"
    is_active = Column(String(5), nullable=False, default="true")  # SQLite doesn't support boolean
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    """User sessions table"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

class Setting(Base):
    """Application settings key-value store"""
    __tablename__ = "settings"
    
    key = Column(String(255), primary_key=True)
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Company(Base):
    """Companies/Tenants table for multi-tenant support"""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # Company display name
    domain = Column(String(255), unique=True, nullable=False)  # Primary domain (e.g., "acme.com")
    slug = Column(String(100), unique=True, nullable=False)  # URL-safe identifier
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Configuration
    settings = Column(JSON, nullable=True)  # Company-specific settings
    
    # Relationships
    users = relationship("CompanyUser", back_populates="company", cascade="all, delete-orphan")

class CompanyUser(Base):
    """Company users with role-based access"""
    __tablename__ = "company_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), nullable=False)  # OIDC subject or local user ID
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    roles = Column(JSON, nullable=False, default=list)  # ["admin", "user", "auditor"]
    groups = Column(JSON, nullable=False, default=list)  # ["engineering", "security"]
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    company = relationship("Company", back_populates="users")
    
    # Unique constraint for user per company
    __table_args__ = (Index("idx_company_user", "company_id", "user_id", unique=True),)

class Approval(Base):
    """Approval workflows table"""
    __tablename__ = "approvals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    actor = Column(String(255), nullable=False)  # User ID requesting approval
    action = Column(String(255), nullable=False)  # Action type (e.g., "deploy", "access_grant")
    status = Column(Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING)
    payload = Column(JSON, nullable=True)  # Additional context/data
    approved_by = Column(String(255), nullable=True)  # User ID who approved/denied
    approved_at = Column(DateTime, nullable=True)
    slack_ts = Column(String(255), nullable=True)  # Slack message timestamp for updates

# Database engine and session configuration
if DATABASE_URL.startswith("sqlite"):
    # SQLite for development
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    # PostgreSQL for production
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
    )

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Dependency for getting database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Initialize database tables (for development)
async def init_db():
    """Create all tables (development only)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)