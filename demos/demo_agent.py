import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yaml import safe_load
from sdk.client import SandboxClient
from sdk.tool_registry import DEFAULT_SCHEMAS
import json

def main():
    # Load policy
    policy_yaml = open("policies/examples/sales_agent.yaml").read()
    policy = safe_load(policy_yaml)

    # Create sandbox client
    client = SandboxClient(
        control_plane_base="http://localhost:8080",
        agent_id="sales_assistant",
        agent_api_key="DEV-AGENT-KEY-123",
        initial_policy=policy,
        tool_schemas=DEFAULT_SCHEMAS,
    )

    print("=== Agent Sandbox Demo ===\n")

    print("1) crm.read (should allow)")
    result = client.tool_call("crm.read", {"account_id":"123"})
    print(json.dumps(result, indent=2))
    print()

    print("2) email.send external (should need approval)")
    result = client.tool_call("email.send", {
        "recipient":"user@gmail.com", 
        "subject":"Hey", 
        "body":"hi there"
    })
    print(json.dumps(result, indent=2))
    print()

    print("3) email.send internal (should allow)")
    result = client.tool_call("email.send", {
        "recipient":"colleague@company.com", 
        "subject":"Internal update", 
        "body":"Status report"
    })
    print(json.dumps(result, indent=2))
    print()

    print("4) payments.charge (should deny)")
    result = client.tool_call("payments.charge", {"amount": 100})
    print(json.dumps(result, indent=2))
    print()

    print("5) GET allowed domain (should allow)")
    result = client.http_request("GET","https://api.company.com/customers?limit=5")
    print(json.dumps(result, indent=2))
    print()

    print("6) GET blocked domain (should deny)")
    result = client.http_request("GET","https://example.com/")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()