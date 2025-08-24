#!/usr/bin/env python3
# canopyiq-mcp/app/stdio_runner.py
import sys, os, json, time, traceback
from typing import Dict, Any

# Reuse your existing code
from policies.engine import PolicyEngine, Decision   # relative to this file when run from repo root
from tools.registry import list_tools, get_handler
import yaml

PROTOCOL_VERSION = "2025-06-18"

def load_policy() -> PolicyEngine:
    policy_path = os.getenv("CANOPYIQ_POLICY_FILE", "./app/policies/samples.yaml")
    with open(policy_path, "r") as f:
        return PolicyEngine(yaml.safe_load(f))

POLICY = load_policy()

def _write(msg: Dict[str, Any]):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def _error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}

def _result(id_, obj):
    return {"jsonrpc": "2.0", "id": id_, "result": obj}

def _initialize_notice():
    # Optional: some MCP clients expect an initial "server capabilities" handshake (out-of-band)
    # You can print a banner or a no-op notice if your client supports it.
    pass

def main():
    _initialize_notice()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            _write(_error(None, -32700, "parse error"))
            continue

        jsonrpc = req.get("jsonrpc")
        mid     = req.get("id")
        method  = req.get("method")
        params  = req.get("params") or {}

        if jsonrpc != "2.0":
            _write(_error(mid, -32600, "invalid request"))
            continue

        t0 = time.time()

        try:
            # Minimal capability/handshake (optional)
            if method == "initialize" or method == "server/initialize":
                _write(_result(mid, {
                    "capabilities": {"tools": {"listChanged": True}},
                    "protocolVersion": PROTOCOL_VERSION
                }))
                continue

            if method == "tools/list":
                _write(_result(mid, {"tools": list_tools(), "nextCursor": None}))
                continue

            if method == "tools/call":
                name = params.get("name")
                args = params.get("arguments") or {}

                # Policy
                dec: Decision = POLICY.evaluate(name, args)
                if dec.outcome == "deny":
                    _write(_result(mid, {
                        "content":[{"type":"text","text": dec.reason or "Blocked by policy"}],
                        "isError": True
                    }))
                    continue
                if dec.outcome == "approval":
                    _write(_result(mid, {
                        "content":[{"type":"text","text":"Approval required; check approver channel"}],
                        "isError": True
                    }))
                    continue

                try:
                    handler = get_handler(name)
                except KeyError:
                    _write(_error(mid, -32602, f"Unknown tool: {name}"))
                    continue

                try:
                    result = handler(args, {"tenant":"local","subject":"stdio-client"})
                except PermissionError as pe:
                    _write(_result(mid, {
                        "content":[{"type":"text","text": str(pe)}],
                        "isError": True
                    }))
                    continue
                except Exception as e:
                    _write(_result(mid, {
                        "content":[{"type":"text","text": f"Tool error: {e}"}],
                        "isError": True
                    }))
                    continue

                _write(_result(mid, {
                    "content":[{"type":"text","text": json.dumps(result)}],
                    "structuredContent": result,
                    "isError": False
                }))
                continue

            if method == "shutdown" or method == "server/shutdown":
                _write(_result(mid, {"ok": True}))
                break

            # Unknown method
            _write(_error(mid, -32601, f"method not found: {method}"))

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            _write(_error(mid, -32000, f"internal error: {e}"))

if __name__ == "__main__":
    main()