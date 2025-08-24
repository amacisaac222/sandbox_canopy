# canopyiq-mcp/app/approvals/state.py
from __future__ import annotations
import json, time, uuid
from typing import Optional, Dict, Any, List, Literal
import redis
from ..settings import settings

r = redis.from_url(settings.REDIS_URL, decode_responses=True)

Decision = Literal["pending","allow","deny"]

def _key(pid: str) -> str: return f"appr:{pid}"
def _chan(pid: str) -> str: return f"appr:notify:{pid}"

def new_pending_id() -> str:
    return uuid.uuid4().hex

def create_pending(
    pending_id: str,
    tenant: str,
    requester: str,
    tool: str,
    args: Dict[str, Any],
    required_approvals: int = 1,
    ttl_sec: int = 900,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    data = {
        "pending_id": pending_id,
        "ts_created": int(time.time()),
        "ts_decided": 0,
        "tenant": tenant,
        "requester": requester,
        "tool": tool,
        "args_json": json.dumps(args, ensure_ascii=False),
        "status": "pending",
        "required_approvals": int(required_approvals),
        "approvals": json.dumps([]),    # list[str] approver ids
        "rejections": json.dumps([]),   # list[str] approver ids
        "reason": reason or "",
    }
    r.hset(_key(pending_id), mapping=data)
    r.expire(_key(pending_id), ttl_sec)
    return data

def get(pending_id: str) -> Optional[Dict[str, Any]]:
    if not r.exists(_key(pending_id)): return None
    d = r.hgetall(_key(pending_id))
    d["args"] = json.loads(d.get("args_json") or "{}")
    d["approvals"] = json.loads(d.get("approvals") or "[]")
    d["rejections"] = json.loads(d.get("rejections") or "[]")
    d["required_approvals"] = int(d.get("required_approvals") or 1)
    d["ts_created"] = int(d.get("ts_created") or 0)
    d["ts_decided"] = int(d.get("ts_decided") or 0)
    return d

def record_decision(pending_id: str, approver: str, decision: Literal["allow","deny"], reason: str = "") -> Dict[str, Any]:
    d = get(pending_id)
    if not d: raise KeyError("pending approval not found")

    # If already decided, keep idempotent
    if d["status"] in ("allow","deny"): return d

    approvals: List[str] = d["approvals"]
    rejections: List[str] = d["rejections"]
    # Remove approver from either list first to allow change of mind
    approvals = [a for a in approvals if a != approver]
    rejections = [a for a in rejections if a != approver]

    if decision == "deny":
        rejections.append(approver)
        status: Decision = "deny"
    else:
        approvals.append(approver)
        status = "allow" if len(set(approvals)) >= d["required_approvals"] else "pending"

    fields = {
        "approvals": json.dumps(list(set(approvals))),
        "rejections": json.dumps(list(set(rejections))),
        "status": status,
        "reason": reason or d.get("reason") or "",
    }
    if status in ("allow","deny"):
        fields["ts_decided"] = int(time.time())

    r.hset(_key(pending_id), mapping=fields)
    # notify waiters
    r.publish(_chan(pending_id), json.dumps({"pending_id": pending_id, "status": status}))
    return get(pending_id)

def wait_for_resolution(pending_id: str, timeout_sec: int = 60) -> Optional[Dict[str, Any]]:
    """Block until allow/deny or timeout. Returns final record or None."""
    d = get(pending_id)
    if not d: return None
    if d["status"] in ("allow","deny"): return d

    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(_chan(pending_id))
    t0 = time.time()
    try:
        while time.time() - t0 < timeout_sec:
            msg = pubsub.get_message(timeout=1.0)
            if not msg: 
                # poll in case of missed message
                d = get(pending_id)
                if d and d["status"] in ("allow","deny"): return d
                continue
            # any message -> re-read status
            d = get(pending_id)
            if d and d["status"] in ("allow","deny"):
                return d
        return None
    finally:
        try: pubsub.close()
        except: pass