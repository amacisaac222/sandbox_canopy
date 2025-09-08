"""
CanopyIQ Local Authentication
"""
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Tuple
from datetime import datetime
import secrets
import re

from database import User, UserRole
from .models import User as AuthUser

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets security requirements
    Returns (is_valid, error_message)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>?]', password):
        return False, "Password must contain at least one special character"
    
    # Check for common patterns
    if password.lower() in ['password123!', 'admin123456!', 'welcome123!', 'letmein123!']:
        return False, "Please choose a less common password"
    
    return True, ""

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

async def create_local_user(
    db: AsyncSession,
    email: str,
    name: str,
    password: str,
    role: UserRole = UserRole.ADMIN
) -> User:
    """Create a new local user account"""
    password_hash = hash_password(password)
    
    user = User(
        email=email,
        name=name,
        role=role,
        password_hash=password_hash,
        auth_provider="local",
        is_active="true"
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user

async def authenticate_local_user(
    db: AsyncSession,
    email: str,
    password: str
) -> Optional[User]:
    """Authenticate a local user with email and password"""
    result = await db.execute(
        select(User).where(
            User.email == email,
            User.auth_provider == "local",
            User.is_active == "true"
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return user

async def has_any_admin_users(db: AsyncSession) -> bool:
    """Check if there are any admin users in the database"""
    result = await db.execute(
        select(User).where(
            User.role == UserRole.ADMIN,
            User.is_active == "true"
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None

def db_user_to_auth_user(db_user: User) -> AuthUser:
    """Convert database User to auth User model"""
    roles = [db_user.role.value.lower()] if db_user.role else []
    
    return AuthUser(
        id=str(db_user.id),
        email=db_user.email,
        name=db_user.name,
        roles=roles,
        groups=[],  # TODO: Implement groups for local users
        created_at=db_user.created_at,
        last_login=db_user.last_login or db_user.created_at,
        is_active=db_user.is_active == "true"
    )