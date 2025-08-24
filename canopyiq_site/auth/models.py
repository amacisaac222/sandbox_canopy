"""
CanopyIQ Authentication Models
"""
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import json

class User(BaseModel):
    """User model for RBAC authentication"""
    id: str  # OIDC subject ID
    email: EmailStr
    name: str
    roles: List[str] = []
    groups: List[str] = []
    company: Optional[str] = None  # Company domain (e.g., "acme.com")
    created_at: datetime = None
    last_login: datetime = None
    is_active: bool = True
    
    def has_role(self, *required_roles: str) -> bool:
        """Check if user has any of the required roles"""
        return any(role in self.roles for role in required_roles)
    
    def has_group(self, *required_groups: str) -> bool:
        """Check if user belongs to any of the required groups"""
        return any(group in self.groups for group in required_groups)
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges"""
        return self.has_role('admin', 'super_admin')
    
    def can_audit(self) -> bool:
        """Check if user can access audit features"""
        return self.has_role('admin', 'auditor', 'compliance')

class SessionData(BaseModel):
    """Session data stored in signed cookies"""
    user_id: str
    email: str
    name: str
    roles: List[str]
    groups: List[str]
    company: Optional[str] = None
    expires_at: datetime
    
    def to_user(self) -> User:
        """Convert session data back to User object"""
        return User(
            id=self.user_id,
            email=self.email,
            name=self.name,
            roles=self.roles,
            groups=self.groups,
            company=self.company,
            last_login=datetime.utcnow(),
            is_active=True
        )

class OIDCConfig(BaseModel):
    """OIDC configuration"""
    issuer: str
    client_id: str
    client_secret: str
    redirect_url: str
    scopes: List[str] = ["openid", "email", "profile", "groups"]
    
class TokenResponse(BaseModel):
    """OIDC token response"""
    access_token: str
    id_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None