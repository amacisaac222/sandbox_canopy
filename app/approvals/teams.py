# Teams-style signed approval callback (for CI testing)
import hmac
import hashlib
import base64
import time
from fastapi import HTTPException

def verify_teams_signature(pending_id: str, decision: str, ts: str, signature: str, secret: str) -> None:
    """Verify signed approval decision for Teams-style callback"""
    try:
        ts_int = int(ts)
        if abs(int(time.time()) - ts_int) > 300:  # 5 minute tolerance
            raise HTTPException(status_code=401, detail="Signature expired")
        
        msg = f"{ts}:{pending_id}:{decision}".encode()
        expected = base64.urlsafe_b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode()
        
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp")