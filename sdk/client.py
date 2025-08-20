import time, json, threading, hashlib, requests
from urllib.parse import urlparse
from .enforcement import tool_allowed, domain_allowed, validate_params
from .policy_cache import PolicyCache

class SandboxClient:
    def __init__(self, control_plane_base: str, agent_id: str, agent_api_key: str,
                 initial_policy: dict|None, tool_schemas: dict, poll_secs: int = 30):
        self.agent_id = agent_id
        self.agent_api_key = agent_api_key
        self.tool_schemas = tool_schemas
        self.count_requests = 0
        self.depth = 0
        self.policy_cache = PolicyCache(control_plane_base, agent_id, agent_api_key, initial_policy)
        self.policy_cache.start(poll_secs)

    def _hash_params(self, params: dict) -> str:
        return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()

    def tool_call(self, tool_name: str, params: dict):
        pol = self.policy_cache.get()
        allow = pol["tools"]["allow"]; deny = pol["tools"]["deny"]
        if not tool_allowed(tool_name, allow, deny):
            return {"decision":"deny","reason":f"Tool {tool_name} not permitted"}

        schema = self.tool_schemas.get(tool_name)
        if schema:
            ok, err = validate_params(schema, params)
            if not ok: return {"decision":"deny","reason":f"Param schema failed: {err}"}

        # approvals (simplified condition — implement parser later)
        for rule in pol["tools"].get("approvals", []):
            if rule["tool"] == tool_name:
                recipient = params.get("recipient","")
                if "endswith('@company.com')" in rule["condition"] and not recipient.endswith("@company.com"):
                    # create approval
                    payload = {
                        "agent_id": self.agent_id, "tool": tool_name,
                        "params_hash": self._hash_params(params),
                        "payload_redacted": {"recipient": recipient[-12:], "subject": params.get("subject","")}
                    }
                    requests.post(f"{self.policy_cache.base}/v1/approvals", json=payload, timeout=5)
                    return {"decision":"needs_approval","reason":"External recipient requires approval"}

        # budgets
        self.count_requests += 1
        return {"decision":"allow","payload":params}

    def http_request(self, method: str, url: str, **kwargs):
        pol = self.policy_cache.get()
        host = urlparse(url).hostname or ""
        net = pol["network"]
        if not domain_allowed(host, net.get("allow_domains",[]), net.get("deny_all_others", False)):
            return {"decision":"deny","reason":f"Domain not allowed: {host}"}
        
        try:
            resp = requests.request(method, url, **kwargs, timeout=10)
            self.count_requests += 1
            return {"decision":"allow","status":resp.status_code, "len":len(resp.content)}
        except requests.RequestException as e:
            self.count_requests += 1
            return {"decision":"allow","simulated":True,"reason":f"Would make request to {url} (demo network error: {str(e)[:100]})"}