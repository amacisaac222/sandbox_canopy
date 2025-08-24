from jose import jwt
import httpx, time, os
from functools import lru_cache
from typing import Dict, Any, Optional
from .settings import settings

@lru_cache(maxsize=1)
def _jwks()->Dict[str,Any]:
    if not settings.OIDC_JWKS_URL: 
        return {}
    try:
        with httpx.Client(timeout=5) as c:
            return c.get(settings.OIDC_JWKS_URL).json()
    except:
        return {}

def verify_token(authz: str) -> Dict[str, Any]:
    if not authz or not authz.startswith("Bearer "):
        raise PermissionError("Missing bearer token")
    token = authz.split(" ",1)[1]

    # OIDC path
    if settings.OIDC_JWKS_URL and settings.OIDC_ISSUER:
        try:
            claims = jwt.get_unverified_claims(token)
            kid = jwt.get_unverified_header(token).get("kid")
            key = None
            for k in _jwks().get("keys",[]):
                if k.get("kid")==kid: 
                    key = k; break
            if not key:
                raise PermissionError("Key not found")
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=settings.OIDC_AUDIENCE, issuer=str(settings.OIDC_ISSUER))
            if claims.get("exp",0) < time.time(): 
                raise PermissionError("Token expired")
            return claims
        except Exception as e:
            # Fall through to dev mode if OIDC fails
            pass

    # Dev HS256 fallback
    try:
        claims = jwt.decode(token, settings.DEV_JWT_SECRET, algorithms=["HS256"], audience=settings.OIDC_AUDIENCE, issuer=settings.DEV_ISSUER)
        if claims.get("exp",0) < time.time(): 
            raise PermissionError("Token expired")
        return claims
    except Exception as e:
        raise PermissionError(f"Invalid token: {e}")