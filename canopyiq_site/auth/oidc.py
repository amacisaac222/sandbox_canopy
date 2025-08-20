"""
CanopyIQ OIDC (OpenID Connect) Client
Supports Okta, Azure AD, Google Workspace, and other OIDC providers
"""
import os
import httpx
from jose import jwt
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlencode, urljoin
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken
from authlib.jose import JsonWebKey

from .models import User, OIDCConfig, TokenResponse
from .rbac import extract_roles_from_claims, extract_groups_from_claims

class OIDCClient:
    """OIDC Client for enterprise authentication"""
    
    def __init__(self):
        self.config = self._load_config()
        self.client: Optional[AsyncOAuth2Client] = None
        self.discovery_doc: Optional[Dict[str, Any]] = None
        self.jwks: Optional[JsonWebKey] = None
    
    def _load_config(self) -> Optional[OIDCConfig]:
        """Load OIDC configuration from environment variables"""
        issuer = os.getenv("OIDC_ISSUER")
        client_id = os.getenv("OIDC_CLIENT_ID") 
        client_secret = os.getenv("OIDC_CLIENT_SECRET")
        redirect_url = os.getenv("OIDC_REDIRECT_URL")
        
        if not all([issuer, client_id, client_secret, redirect_url]):
            return None
            
        return OIDCConfig(
            issuer=issuer,
            client_id=client_id,
            client_secret=client_secret,
            redirect_url=redirect_url,
            scopes=os.getenv("OIDC_SCOPES", "openid email profile groups").split()
        )
    
    async def initialize(self):
        """Initialize OIDC client with discovery document"""
        if not self.config:
            return False
            
        try:
            # Fetch OIDC discovery document
            async with httpx.AsyncClient() as client:
                well_known_url = urljoin(self.config.issuer, "/.well-known/openid-configuration")
                response = await client.get(well_known_url)
                response.raise_for_status()
                self.discovery_doc = response.json()
                
                # Fetch JWKS for token verification
                jwks_response = await client.get(self.discovery_doc["jwks_uri"])
                jwks_response.raise_for_status()
                self.jwks = JsonWebKey.import_key_set(jwks_response.json())
            
            # Initialize OAuth2 client
            self.client = AsyncOAuth2Client(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scope=" ".join(self.config.scopes),
            )
            
            return True
        except Exception as e:
            print(f"OIDC initialization failed: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if OIDC is properly configured"""
        return self.config is not None and self.discovery_doc is not None
    
    def get_authorization_url(self, state: str) -> str:
        """Generate authorization URL for login redirect"""
        if not self.client or not self.discovery_doc:
            raise ValueError("OIDC client not initialized")
        
        auth_url = self.client.create_authorization_url(
            self.discovery_doc["authorization_endpoint"],
            redirect_uri=self.config.redirect_url,
            state=state
        )
        return auth_url[0]  # authlib returns (url, state)
    
    async def exchange_code(self, code: str, state: str) -> TokenResponse:
        """Exchange authorization code for tokens"""
        if not self.client or not self.discovery_doc:
            raise ValueError("OIDC client not initialized")
        
        token = await self.client.fetch_token(
            self.discovery_doc["token_endpoint"],
            code=code,
            redirect_uri=self.config.redirect_url
        )
        
        return TokenResponse(
            access_token=token["access_token"],
            id_token=token["id_token"],
            token_type=token.get("token_type", "Bearer"),
            expires_in=token.get("expires_in"),
            refresh_token=token.get("refresh_token")
        )
    
    def verify_id_token(self, id_token: str) -> Dict[str, Any]:
        """Verify and decode ID token"""
        if not self.jwks:
            raise ValueError("JWKS not loaded")
        
        claims = jwt.decode(
            id_token,
            self.jwks,
            algorithms=["RS256"],
            audience=self.config.client_id,
            issuer=self.config.issuer
        )
        
        return claims
    
    def create_user_from_claims(self, claims: Dict[str, Any]) -> User:
        """Create User object from OIDC claims"""
        return User(
            id=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("preferred_username", "")),
            roles=extract_roles_from_claims(claims),
            groups=extract_groups_from_claims(claims),
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
            is_active=True
        )
    
    def get_logout_url(self, redirect_url: str = None) -> Optional[str]:
        """Get logout URL if provider supports it"""
        if not self.discovery_doc:
            return None
        
        logout_endpoint = self.discovery_doc.get("end_session_endpoint")
        if not logout_endpoint:
            return None
        
        params = {}
        if redirect_url:
            params["post_logout_redirect_uri"] = redirect_url
        
        if params:
            return f"{logout_endpoint}?{urlencode(params)}"
        return logout_endpoint

# Global OIDC client instance
oidc_client = OIDCClient()

async def init_oidc():
    """Initialize OIDC client on startup"""
    if oidc_client.config:
        success = await oidc_client.initialize()
        if success:
            print("[OK] OIDC authentication initialized")
        else:
            print("[ERROR] OIDC authentication failed to initialize")
    else:
        print("[INFO] OIDC authentication not configured (missing environment variables)")