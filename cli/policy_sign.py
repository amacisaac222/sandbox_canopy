#!/usr/bin/env python3
# canopyiq-mcp/cli/policy_sign.py
import argparse, base64, json, os, sys, datetime
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder
import hashlib

def sha256_bytes(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def cmd_gen_key(args):
    sk = SigningKey.generate()
    vk = sk.verify_key
    priv_b64 = base64.b64encode(bytes(sk)).decode()
    pub_b64  = base64.b64encode(bytes(vk)).decode()
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "canopyiq_policy_private.key"), "w") as f:
        f.write(priv_b64)
    with open(os.path.join(args.out_dir, "canopyiq_policy_public.key"), "w") as f:
        f.write(pub_b64)
    print("Wrote keys to", args.out_dir)

def cmd_sign(args):
    with open(args.private_key, "r") as f:
        priv_b64 = f.read().strip()
    sk = SigningKey(base64.b64decode(priv_b64))
    with open(args.bundle, "rb") as f:
        data = f.read()
    digest = sha256_bytes(data)
    sig = sk.sign(digest).signature
    meta = {
        "alg": "Ed25519",
        "created": datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z",
        "sha256": base64.b64encode(digest).decode(),
        "sig": base64.b64encode(sig).decode(),
        "pubkey_fingerprint": "canopyiq:v1:"+sha256_bytes(base64.b64decode(priv_b64))[:4].hex()
    }
    out = args.out or (args.bundle + ".sig")
    with open(out, "w") as f:
        json.dump(meta, f, indent=2)
    print("Wrote signature:", out)

def cmd_verify(args):
    from nacl.signing import VerifyKey
    with open(args.public_key, "r") as f:
        pub_b64 = f.read().strip()
    with open(args.bundle, "rb") as f:
        data = f.read()
    with open(args.signature, "r") as f:
        meta = json.load(f)
    digest = sha256_bytes(data)
    if base64.b64decode(meta["sha256"]) != digest:
        print("SHA256 mismatch", file=sys.stderr); sys.exit(2)
    vk = VerifyKey(base64.b64decode(pub_b64))
    try:
        vk.verify(digest, base64.b64decode(meta["sig"]))
        print("OK")
    except Exception as e:
        print(f"Signature verification failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    p = argparse.ArgumentParser("canopyiq-policy")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen-key"); g.add_argument("--out-dir", required=True); g.set_defaults(func=cmd_gen_key)
    s = sub.add_parser("sign")
    s.add_argument("bundle"); s.add_argument("--private-key", required=True); s.add_argument("--out")
    s.set_defaults(func=cmd_sign)
    v = sub.add_parser("verify")
    v.add_argument("bundle"); v.add_argument("--public-key", required=True); v.add_argument("--signature", required=True)
    v.set_defaults(func=cmd_verify)

    args = p.parse_args(); args.func(args)

if __name__ == "__main__":
    main()