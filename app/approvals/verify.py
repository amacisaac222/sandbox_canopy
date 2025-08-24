# Slack request signature verification
# https://api.slack.com/authentication/verifying-requests-from-slack
import hmac, hashlib, time
from fastapi import HTTPException
from ..settings import settings

def verify_slack_request(ts: str, signature: str, body: bytes, tolerance: int = 60 * 5) -> None:
    if not settings.SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=500, detail="Slack signing secret not configured")

    # 1) Timestamp freshness
    try:
        ts_int = int(ts)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid timestamp")
    if abs(int(time.time()) - ts_int) > tolerance:
        raise HTTPException(status_code=401, detail="Stale request")

    # 2) Compute signature
    basestring = f"v0:{ts}:{body.decode('utf-8')}"
    digest = hmac.new(
        settings.SLACK_SIGNING_SECRET.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    expected = f"v0={digest}"

    # 3) Constant-time compare
    if not hmac.compare_digest(expected, signature or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")