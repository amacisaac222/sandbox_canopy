import os, yaml, hashlib, psycopg2, psycopg2.extras
from functools import lru_cache
from typing import Dict, Optional
from .engine import PolicyEngine

def _cs(conn_str:str):
    return conn_str

class PolicyManager:
    def __init__(self, db_url:str):
        self.db_url = db_url
        self._cache: Dict[str, PolicyEngine] = {}  # version -> engine

    def _db(self):
        return psycopg2.connect(self.db_url)

    def _load_engine(self, version:str, path:str)->PolicyEngine:
        if version in self._cache:
            return self._cache[version]
        with open(path, "r") as f:
            eng = PolicyEngine(yaml.safe_load(f))
        self._cache[version] = eng
        return eng

    def _rollout(self):
        with self._db() as cx, cx.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM policy_rollout WHERE id=1")
            row = cur.fetchone()
            if not row:
                # bootstrap: pick newest policy_version as active
                cur.execute("SELECT version FROM policy_version ORDER BY created_at DESC LIMIT 1")
                pv = cur.fetchone()
                if pv:
                    cur.execute("INSERT INTO policy_rollout(id,active_version,canary_percent,seed) VALUES (1,%s,0,1)", (pv["version"],))
                    cx.commit()
                    return {"active_version": pv["version"], "canary_version": None, "canary_percent": 0, "seed": 1}
                else:
                    # fallback: use bundled sample file
                    return {"active_version": "__builtin__", "canary_version": None, "canary_percent": 0, "seed": 1}
            return dict(row)

    def _version_path(self, version:str)->Optional[str]:
        with self._db() as cx, cx.cursor() as cur:
            cur.execute("SELECT path FROM policy_version WHERE version=%s", (version,))
            r = cur.fetchone()
            return r[0] if r else None

    def engine_for(self, tenant:str) -> PolicyEngine:
        # tenant override?
        with self._db() as cx, cx.cursor() as cur:
            cur.execute("SELECT version FROM tenant_policy_override WHERE tenant=%s", (tenant,))
            ov = cur.fetchone()
        if ov:
            v = ov[0]
            p = self._version_path(v)
            if not p: raise RuntimeError(f"Override version not found: {v}")
            return self._load_engine(v, p)

        ro = self._rollout()
        active = ro["active_version"]
        canary = ro.get("canary_version")
        percent = int(ro.get("canary_percent") or 0)
        seed = int(ro.get("seed") or 1)

        if canary and percent > 0 and _bucket(tenant, seed) < percent:
            p = self._version_path(canary)
            if p:
                return self._load_engine(canary, p)

        if active == "__builtin__":
            # built-in sample
            with open(os.getenv("CANOPYIQ_POLICY_FILE","./app/policies/samples.yaml"), "r") as f:
                eng = PolicyEngine(yaml.safe_load(f))
            return eng

        p = self._version_path(active)
        if not p: raise RuntimeError("Active policy version not found")
        return self._load_engine(active, p)

def _bucket(tenant:str, seed:int)->int:
    h = hashlib.sha256(f"{seed}:{tenant}".encode()).digest()
    # map first 2 bytes to 0..99
    n = int.from_bytes(h[:2],"big") % 100
    return n