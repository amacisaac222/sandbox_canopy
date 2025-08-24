# Basic settings for CanopyIQ MCP
import os

class Settings:
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    
    # OIDC settings
    OIDC_ISSUER: str = os.getenv("OIDC_ISSUER", "")
    OIDC_AUDIENCE: str = os.getenv("OIDC_AUDIENCE", "canopyiq-mcp")
    OIDC_JWKS_URL: str = os.getenv("OIDC_JWKS_URL", "")
    
    # Dev JWT settings
    DEV_JWT_SECRET: str = os.getenv("DEV_JWT_SECRET", "change-me-dev-secret")
    DEV_ISSUER: str = os.getenv("DEV_ISSUER", "canopyiq-dev")

settings = Settings()