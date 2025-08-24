# canopyiq-mcp/app/policies/diff.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import copy

def _key(rule: Dict[str, Any]) -> str:
    # unique-ish key: "<match>/<name>"
    return f"{rule.get('match','*')}/{rule.get('name','_unnamed_')}"

def index_rules(doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return { _key(r): r for r in (doc.get("rules") or []) }

def compare(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    ia, ib = index_rules(a), index_rules(b)
    keys_a, keys_b = set(ia), set(ib)
    added = sorted(list(keys_b - keys_a))
    removed = sorted(list(keys_a - keys_b))
    common = sorted(list(keys_a & keys_b))

    modified: List[Dict[str, Any]] = []
    for k in common:
        ra, rb = ia[k], ib[k]
        if _rule_equal(ra, rb): 
            continue
        changes = _rule_changes(ra, rb)
        modified.append({"id": k, "before": ra, "after": rb, "changes": changes})

    headline = risk_headline(added, removed, modified, ib)
    return {
        "added": [{"id": k, "rule": ib[k]} for k in added],
        "removed": [{"id": k, "rule": ia[k]} for k in removed],
        "modified": modified,
        "defaults": {
            "from": a.get("defaults",{}),
            "to":   b.get("defaults",{})
        },
        "headline": headline
    }

def _rule_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    # shallow compare of relevant fields
    fields = ["match","where","action","required_approvals","reason"]
    return all((a.get(f) == b.get(f)) for f in fields)

def _rule_changes(a: Dict[str, Any], b: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for f in ["match","where","action","required_approvals","reason"]:
        if a.get(f) != b.get(f):
            out.append({"field": f, "from": a.get(f), "to": b.get(f)})
    return out

def risk_headline(added, removed, modified, ib) -> List[str]:
    notes: List[str] = []
    # New ALLOW rules
    for k in added:
        if ib[k].get("action") == "allow":
            notes.append(f"New allow: {k}")
        if ib[k].get("action") == "approval":
            notes.append(f"New approval flow: {k}")
    for ch in modified:
        a = ch["before"]; b = ch["after"]
        if a.get("action") != b.get("action"):
            notes.append(f"Action change {ch['id']}: {a.get('action')} → {b.get('action')}")
        # simple heuristic: egress allowlist widened
        if a.get("where",{}).get("host_in") != b.get("where",{}).get("host_in"):
            notes.append(f"Changed host_in: {ch['id']}")
        if a.get("required_approvals") != b.get("required_approvals"):
            notes.append(f"Approval quorum change {ch['id']}: {a.get('required_approvals')} → {b.get('required_approvals')}")
    if not notes:
        notes.append("No high-risk changes detected.")
    return notes