# Basic policy engine for CanopyIQ MCP
from typing import Dict, Any, List, Optional

class Decision:
    def __init__(self, outcome: str, rule: str=None, reason: str=None, approver_group:str=None, required_approvals:int=1):
        self.outcome = outcome
        self.rule = rule
        self.reason = reason
        self.approver_group = approver_group
        self.required_approvals = required_approvals

class PolicyEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.defaults = config.get("defaults", {"decision": "deny"})
        self.rules = config.get("rules", [])
    
    def evaluate(self, tool: str, args: Dict[str, Any]) -> Decision:
        """Evaluate a tool call against policy rules"""
        # Check each rule in order
        for rule in self.rules:
            if self._matches_rule(rule, tool, args):
                action = rule.get("action", "deny")
                return Decision(
                    outcome=action,
                    rule=rule.get("name"),
                    reason=rule.get("reason"),
                    approver_group=rule.get("approver_group"),
                    required_approvals=int(rule.get("required_approvals", 1))
                )
        
        # No rule matched, use default
        default_decision = self.defaults.get("decision", "deny")
        return Decision(
            outcome=default_decision,
            rule="default",
            reason="No matching rule found"
        )
    
    def _matches_rule(self, rule: Dict[str, Any], tool: str, args: Dict[str, Any]) -> bool:
        """Check if a rule matches the given tool and arguments"""
        # Simple match by tool name for now
        match_pattern = rule.get("match")
        if match_pattern and match_pattern != tool:
            return False
        
        # Check where conditions if present
        where = rule.get("where", {})
        for condition, value in where.items():
            if not self._check_condition(condition, value, args):
                return False
        
        return True
    
    def _check_condition(self, condition: str, expected: Any, args: Dict[str, Any]) -> bool:
        """Check a single where condition"""
        if condition == "method":
            return args.get("method") == expected
        elif condition == "host_in":
            host = args.get("url", "").split("/")[2] if args.get("url") else ""
            return host in expected
        elif condition == "path_not_under":
            path = args.get("path", "")
            return not any(path.startswith(prefix) for prefix in expected)
        elif condition == "body_bytes_over":
            body_size = len(str(args.get("body", "")))
            return body_size > expected
        elif condition == "estimated_cost_usd_over":
            cost = float(args.get("estimated_cost_usd", 0))
            return cost > float(expected)
        
        return True
    
    def evaluate_with_trace(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate policy with detailed trace for debugging"""
        trace = []
        for r in self.rules:
            if r.get("match") != tool:
                trace.append({"rule": r.get("name"), "skipped": True, "why": "tool-mismatch"})
                continue
            ok, why = self._match_where_explain(r.get("where", {}), args)
            trace.append({"rule": r.get("name"), "match": ok, "explain": why})
            if ok:
                act = r.get("action")
                return {
                    "decision": act,
                    "rule": r.get("name"),
                    "reason": r.get("reason"),
                    "required_approvals": int(r.get("required_approvals", 1)),
                    "trace": trace
                }
        # default
        d = self.defaults.get("decision","deny")
        trace.append({"rule": "__default__", "match": True, "explain": "no rules matched"})
        return {"decision": d, "rule": "__default__", "reason": None, "required_approvals": 1, "trace": trace}

    def _match_where_explain(self, where: Dict[str, Any], args: Dict[str, Any]):
        """Check where conditions with detailed explanation"""
        if not where: 
            return True, "no conditions"
        
        why = []
        def fail(msg): 
            why.append({"ok": False, "msg": msg})
            return False, why
        def ok(msg):
            why.append({"ok": True, "msg": msg})

        # host_in
        if "host_in" in where:
            host = self._extract_host(args.get("url",""))
            if host not in set(where["host_in"]):
                return fail(f"host '{host}' not in allowlist")
            ok(f"host '{host}' allowed")

        if where.get("method") and where["method"] != args.get("method"):
            return fail(f"method != {where['method']}")

        if "body_bytes_over" in where:
            import json as _json
            sz = len(_json.dumps(args.get("body","") or ""))
            if sz <= int(where["body_bytes_over"]):
                return fail(f"body size {sz} <= threshold {where['body_bytes_over']}")
            ok(f"body {sz} exceeds threshold")

        if "path_not_under" in where and args.get("path"):
            ok_under = False
            for p in where["path_not_under"]:
                if args["path"].startswith(p):
                    ok_under = True
            if not ok_under:
                return fail("path is outside permitted prefixes")
            ok("path under permitted prefixes")

        if "estimated_cost_usd_over" in where:
            cost = float(args.get("estimated_cost_usd",0))
            threshold = float(where["estimated_cost_usd_over"])
            if cost <= threshold:
                return fail(f"estimated_cost_usd {cost} <= {threshold}")
            ok(f"estimated cost {cost} exceeds threshold {threshold}")

        return True, why
    
    def _extract_host(self, url: str) -> str:
        """Extract host from URL"""
        try:
            if "://" in url:
                return url.split("://")[1].split("/")[0]
            return url.split("/")[0]
        except:
            return ""