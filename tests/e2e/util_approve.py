#!/usr/bin/env python3
import sys, time, hmac, hashlib, base64, urllib.parse, requests

BASE = "http://localhost:8080"
SECRET = "ci-secret"

def sig(ts, pid, decision):
    msg = f"{ts}:{pid}:{decision}".encode()
    return base64.urlsafe_b64encode(hmac.new(SECRET.encode(), msg, hashlib.sha256).digest()).decode()

def approve(pending_id, decision="approve"):
    ts = str(int(time.time()))
    s  = sig(ts, pending_id, decision)
    url = f"{BASE}/approvals/teams/decision?{urllib.parse.urlencode({'pending_id':pending_id,'decision':decision,'ts':ts,'sig':s})}"
    r = requests.get(url, timeout=5)
    print("decision response:", r.status_code, r.text.strip())

if __name__ == "__main__":
    approve(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else "approve")