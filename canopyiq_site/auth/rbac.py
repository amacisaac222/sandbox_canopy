"""
CanopyIQ Role-Based Access Control (RBAC)
"""
from fastapi import HTTPException, Request, Depends
from functools import wraps
from typing import List, Optional, Callable, Any
import os
from datetime import datetime, timedelta
from jose import jwt
import json

from .models import User, SessionData

# Session configuration
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-in-production")
SESSION_COOKIE_NAME = "canopyiq_session"
SESSION_DURATION_HOURS = int(os.getenv("SESSION_DURATION_HOURS", "8"))

def create_session_token(user: User) -> str:
    """Create a signed JWT session token"""
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
    
    session_data = SessionData(
        user_id=user.id,
        email=user.email,
        name=user.name,
        roles=user.roles,
        groups=user.groups,
        company=getattr(user, 'company', None),
        expires_at=expires_at
    )
    
    payload = session_data.dict()
    payload['expires_at'] = payload['expires_at'].isoformat()
    
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")

def verify_session_token(token: str) -> Optional[SessionData]:
    """Verify and decode session token"""
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        payload['expires_at'] = datetime.fromisoformat(payload['expires_at'])
        
        session_data = SessionData(**payload)
        
        # Check if session has expired
        if session_data.expires_at < datetime.utcnow():
            return None
            
        return session_data
    except (jwt.InvalidTokenError, ValueError, KeyError):
        return None

def get_current_user(request: Request) -> Optional[User]:
    """Get current user from session cookie"""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_cookie:
        return None
    
    session_data = verify_session_token(session_cookie)
    if not session_data:
        return None
    
    return session_data.to_user()

def require_auth(request: Request) -> User:
    """FastAPI dependency that requires authentication"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

def require_role(*allowed_roles: str) -> Callable:
    """
    FastAPI dependency factory that requires specific roles
    Usage: @app.get("/admin", dependencies=[Depends(require_role("admin", "auditor"))])
    """
    def role_checker(request: Request) -> User:
        user = require_auth(request)
        
        if not user.has_role(*allowed_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return user
    
    return role_checker

def require_group(*allowed_groups: str) -> Callable:
    """
    FastAPI dependency factory that requires specific groups
    Usage: @app.get("/team", dependencies=[Depends(require_group("engineering", "security"))])
    """
    def group_checker(request: Request) -> User:
        user = require_auth(request)
        
        if not user.has_group(*allowed_groups):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required groups: {', '.join(allowed_groups)}"
            )
        return user
    
    return group_checker

def require_admin(request: Request) -> User:
    """FastAPI dependency that requires admin privileges"""
    return require_role("admin", "super_admin")(request)

def require_auditor(request: Request) -> User:
    """FastAPI dependency that requires auditor privileges"""
    return require_role("admin", "auditor", "compliance")(request)

# Role mapping from OIDC claims
def extract_roles_from_claims(claims: dict) -> List[str]:
    """Extract roles from OIDC claims"""
    roles = []
    
    # Common role claim locations
    role_claims = [
        claims.get("roles", []),
        claims.get("groups", []),
        claims.get("realm_access", {}).get("roles", []),
        claims.get("resource_access", {}).get("canopyiq", {}).get("roles", [])
    ]
    
    for role_claim in role_claims:
        if isinstance(role_claim, list):
            roles.extend(role_claim)
        elif isinstance(role_claim, str):
            roles.append(role_claim)
    
    # Normalize role names
    normalized_roles = []
    for role in roles:
        role = role.lower().strip()
        if role:
            normalized_roles.append(role)
    
    return list(set(normalized_roles))  # Remove duplicates

def extract_groups_from_claims(claims: dict) -> List[str]:
    """Extract groups from OIDC claims"""
    groups = []
    
    # Common group claim locations
    group_claims = [
        claims.get("groups", []),
        claims.get("memberOf", []),
        claims.get("teams", [])
    ]
    
    for group_claim in group_claims:
        if isinstance(group_claim, list):
            groups.extend(group_claim)
        elif isinstance(group_claim, str):
            groups.append(group_claim)
    
    return list(set(groups))  # Remove duplicates