"""
CanopyIQ Company Management
Basic stub implementation for company functionality
"""

from typing import List, Dict, Any, Optional
from auth.models import User


class CompanyManager:
    """Company management functionality"""
    
    def create_company_user(self, claims: dict) -> User:
        """Create a user from OIDC claims with company context"""
        # Extract user info from claims
        user_id = claims.get("sub", "unknown")
        email = claims.get("email", "unknown@example.com")
        name = claims.get("name", claims.get("preferred_username", "Unknown User"))
        
        # For now, return a basic user - in production this would handle company mapping
        return User(
            id=user_id,
            email=email,
            name=name,
            roles=["user"],
            groups=[],
            company=claims.get("company", "default"),
            created_at=None,
            last_login=None,
            is_active=True
        )
    
    def get_available_companies(self, user: User) -> List[Dict[str, Any]]:
        """Get companies available to the user"""
        # Stub implementation
        return [
            {
                "id": "default",
                "name": "Default Company",
                "domain": "default.canopyiq.ai",
                "is_active": True
            }
        ]
    
    def get_company_users(self, user: User, company_domain: str = None) -> List[Dict[str, Any]]:
        """Get users for a company"""
        # Stub implementation
        return [
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "roles": user.roles,
                "company": getattr(user, 'company', 'default'),
                "is_active": user.is_active
            }
        ]
    
    def is_super_admin(self, user: User) -> bool:
        """Check if user is a super admin"""
        return "admin" in user.roles or "super_admin" in user.roles
    
    def can_access_company(self, user: User, company_domain: str) -> bool:
        """Check if user can access company data"""
        # For now, allow admin users to access all companies
        return self.is_super_admin(user)


# Global instance
company_manager = CompanyManager()