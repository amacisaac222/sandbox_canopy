#!/usr/bin/env python3
import argparse, time, json, os
from jose import jwt

def mint(args):
    iss = os.getenv("DEV_ISSUER","canopyiq-dev")
    aud = os.getenv("OIDC_AUDIENCE","canopyiq-mcp")
    sec = os.getenv("DEV_JWT_SECRET","change-me-dev-secret")
    now = int(time.time())
    claims = {
        "iss": iss,
        "aud": aud,
        "iat": now,
        "exp": now + int(args.ttl),
        "sub": args.subject,
        "tenant": args.tenant,
        "roles": args.roles.split(",") if args.roles else []
    }
    token = jwt.encode(claims, sec, algorithm="HS256")
    print(token)

def main():
    p = argparse.ArgumentParser("canopy-admin")
    s = p.add_subparsers(dest="cmd", required=True)
    m = s.add_parser("mint-token")
    m.add_argument("--tenant", required=True)
    m.add_argument("--subject", required=True)
    m.add_argument("--roles", default="admin")
    m.add_argument("--ttl", default="3600")
    m.set_defaults(func=mint)
    args = p.parse_args(); args.func(args)

if __name__ == "__main__":
    main()