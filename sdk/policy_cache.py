import threading, time, requests

class PolicyCache:
    def __init__(self, base: str, agent_id: str, api_key: str, initial: dict|None):
        self.base = base.rstrip("/")
        self.agent_id = agent_id
        self.api_key = api_key
        self._policy = initial or {
            "tools":{"allow":[],"deny":[]}, "network":{"deny_all_others":False,"allow_domains":[]},
            "budgets":{"max_requests_per_day":999999,"max_usd_per_day":999999,"max_chain_depth":10}
        }
        self._lock = threading.Lock()

    def start(self, poll_secs: int):
        t = threading.Thread(target=self._poll, args=(poll_secs,), daemon=True)
        t.start()

    def _poll(self, poll_secs: int):
        while True:
            try:
                r = requests.get(f"{self.base}/v1/policies/{self.agent_id}",
                                 headers={"X-Agent-Key": self.api_key}, timeout=5)
                if r.status_code==200:
                    bundle = r.json()["bundle"]
                    with self._lock:
                        self._policy = self._compile_yaml(bundle["yaml"])
            except Exception:
                pass
            time.sleep(poll_secs)

    def _compile_yaml(self, yaml_text: str) -> dict:
        # MVP: the YAML already matches structure; later, perform full compile/validate
        import yaml
        return yaml.safe_load(yaml_text)

    def get(self) -> dict:
        with self._lock:
            return self._policy