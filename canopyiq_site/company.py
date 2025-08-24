"""
Company/Tenant Management System
"""
import os
from typing import List, Optional, Dict, Any
from fastapi import Request
from .auth.models import User
from .auth.rbac import extract_roles_from_claims, extract_groups_from_claims

class CompanyManager:
    """Manages company/tenant information and user access"""
    
    def __init__(self):
        self.default_domain = os.getenv("DEFAULT_COMPANY_DOMAIN", "localhost")
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@localhost")
    
    def extract_company_from_email(self, email: str) -> str:
        """Extract company domain from email address"""
        if "@" in email:
            return email.split("@")[1].lower()
        return self.default_domain
    
    def get_company_slug(self, domain: str) -> str:
        """Convert domain to URL-safe slug"""
        return domain.replace(".", "-").lower()
    
    def create_company_user(self, claims: Dict[str, Any], company_domain: str = None) -> User:
        """Create a User with company context from OIDC claims"""
        email = claims.get("email", "")
        if not company_domain:
            company_domain = self.extract_company_from_email(email)
        
        # Determine roles based on company and claims
        roles = extract_roles_from_claims(claims)
        
        # Auto-assign admin role if this is the configured admin email
        if email == self.admin_email:
            if "admin" not in roles:
                roles.append("admin")
            if "super_admin" not in roles:
                roles.append("super_admin")
        
        # Default role assignment for company users
        if not roles:
            roles = ["user"]
        
        return User(
            id=f"{company_domain}:{claims['sub']}",  # Namespace by company
            email=email,
            name=claims.get("name", claims.get("preferred_username", "")),
            roles=roles,
            groups=extract_groups_from_claims(claims),
            company=company_domain,
            created_at=claims.get("iat"),
            last_login=claims.get("iat"),
            is_active=True
        )
    
    def is_super_admin(self, user: User) -> bool:
        """Check if user is a super admin (cross-company access)"""
        return user.has_role("super_admin")
    
    def is_company_admin(self, user: User) -> bool:
        """Check if user is an admin for their company"""
        return user.has_role("admin", "super_admin")
    
    def get_company_from_user(self, user: User) -> str:
        """Get company domain from user"""
        return getattr(user, 'company', self.default_domain)
    
    def can_access_company(self, user: User, target_company: str) -> bool:
        """Check if user can access a specific company's data"""
        if self.is_super_admin(user):
            return True  # Super admins can access all companies
        
        user_company = self.get_company_from_user(user)
        return user_company == target_company
    
    def get_available_companies(self, user: User) -> List[Dict[str, Any]]:
        """Get list of companies user has access to"""
        user_company = self.get_company_from_user(user)
        
        companies = [
            {
                "domain": user_company,
                "slug": self.get_company_slug(user_company),
                "name": user_company.title().replace(".", " ").replace("-", " "),
                "is_primary": True
            }
        ]
        
        # Super admins can see all companies (in a real implementation, 
        # this would query the database)
        if self.is_super_admin(user):
            # For now, just add a few example companies
            example_companies = [
                "acme.com", "globodyne.com", "initech.com"
            ]
            for domain in example_companies:
                if domain != user_company:
                    companies.append({
                        "domain": domain,
                        "slug": self.get_company_slug(domain),
                        "name": domain.title().replace(".", " ").replace("-", " "),
                        "is_primary": False
                    })
        
        return companies
    
    def get_company_users(self, user: User, company_domain: str = None) -> List[Dict[str, Any]]:
        """Get users for a company (requires admin access)"""
        if not self.is_company_admin(user):
            return []
        
        if not company_domain:
            company_domain = self.get_company_from_user(user)
        
        if not self.can_access_company(user, company_domain):
            return []
        
        # In a real implementation, this would query the database
        # For now, return mock data
        mock_users = [
            {
                "id": f"{company_domain}:user1",
                "email": f"john.doe@{company_domain}",
                "name": "John Doe",
                "roles": ["admin"],
                "groups": ["engineering"],
                "is_active": True,
                "last_login": "2025-01-15T10:30:00Z"
            },
            {
                "id": f"{company_domain}:user2", 
                "email": f"jane.smith@{company_domain}",
                "name": "Jane Smith",
                "roles": ["user"],
                "groups": ["security"],
                "is_active": True,
                "last_login": "2025-01-14T15:45:00Z"
            }
        ]
        
        return mock_users

# Global company manager instance
company_manager = CompanyManager()