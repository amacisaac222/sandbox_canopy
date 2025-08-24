# canopyiq-mcp/app/policies/verify.py
import base64, hashlib, json
from typing import Tuple
from nacl.signing import VerifyKey

def sha256_bytes(blob: bytes) -> bytes:
    import hashlib
    return hashlib.sha256(blob).digest()

def verify_bundle(policy_path: str, sig_path: str, public_key_b64: str) -> Tuple[bool, str]:
    """
    Returns (ok, msg). Signature file format (JSON):
    {
      "alg":"Ed25519",
      "created":"2025-08-21T12:34:56Z",
      "sha256":"<base64>",
      "sig":"<base64>",
      "pubkey_fingerprint":"canopyiq:v1:<8-hex>"
    }
    """
    try:
        with open(policy_path, "rb") as f:
            data = f.read()
        with open(sig_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        if meta.get("alg") != "Ed25519":
            return False, "Unsupported algorithm"
        claimed = base64.b64decode(meta.get("sha256",""))
        actual  = sha256_bytes(data)
        if claimed != actual:
            return False, "SHA256 mismatch"

        sig = base64.b64decode(meta.get("sig",""))
        vk = VerifyKey(base64.b64decode(public_key_b64))
        try:
            vk.verify(actual, sig)
        except Exception as e:
            return False, f"Signature invalid: {e}"

        return True, "OK"
    except Exception as e:
        return False, f"Verification error: {e}"