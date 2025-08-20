import hmac, hashlib, json, base64

def sign_payload(obj: dict, secret: str) -> str:
    data = json.dumps(obj, sort_keys=True).encode()
    sig = hmac.new(secret.encode(), data, hashlib.sha256).digest()
    return base64.b64encode(sig).decode()

def verify_signature(obj: dict, signature: str, secret: str) -> bool:
    return hmac.compare_digest(sign_payload(obj, secret), signature)