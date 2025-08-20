import pytest
from sdk.client import SandboxClient
from sdk.tool_registry import DEFAULT_SCHEMAS

def test_request_counting():
    """Test that the client counts requests correctly"""
    policy = {
        "tools": {"allow": ["*"], "deny": []},
        "network": {"deny_all_others": False, "allow_domains": []},
        "budgets": {"max_requests_per_day": 3, "max_usd_per_day": 100, "max_chain_depth": 5}
    }
    
    client = SandboxClient(
        control_plane_base="http://localhost:8080",
        agent_id="test_agent",
        agent_api_key="test_key",
        initial_policy=policy,
        tool_schemas=DEFAULT_SCHEMAS,
        poll_secs=999  # Don't poll during test
    )
    
    # Should start with 0 requests
    assert client.count_requests == 0
    
    # Each tool call should increment counter
    client.tool_call("crm.read", {"account_id": "123"})
    assert client.count_requests == 1
    
    client.tool_call("crm.read", {"account_id": "456"})
    assert client.count_requests == 2

def test_tool_schema_enforcement():
    """Test that tool schemas are enforced"""
    policy = {
        "tools": {"allow": ["*"], "deny": []},
        "network": {"deny_all_others": False, "allow_domains": []},
        "budgets": {"max_requests_per_day": 1000, "max_usd_per_day": 100, "max_chain_depth": 5}
    }
    
    client = SandboxClient(
        control_plane_base="http://localhost:8080",
        agent_id="test_agent", 
        agent_api_key="test_key",
        initial_policy=policy,
        tool_schemas=DEFAULT_SCHEMAS,
        poll_secs=999
    )
    
    # Valid email should pass
    result = client.tool_call("email.send", {
        "recipient": "test@company.com",
        "subject": "Test",
        "body": "Test message"
    })
    assert result["decision"] == "allow"
    
    # Invalid email (missing body) should fail
    result = client.tool_call("email.send", {
        "recipient": "test@company.com", 
        "subject": "Test"
    })
    assert result["decision"] == "deny"
    assert "schema" in result["reason"].lower()

def test_policy_enforcement():
    """Test that policies are properly enforced"""
    policy = {
        "tools": {
            "allow": ["crm.*"], 
            "deny": ["payments.*"],
            "approvals": []
        },
        "network": {"deny_all_others": True, "allow_domains": ["api.company.com"]},
        "budgets": {"max_requests_per_day": 1000, "max_usd_per_day": 100, "max_chain_depth": 5}
    }
    
    client = SandboxClient(
        control_plane_base="http://localhost:8080",
        agent_id="test_agent",
        agent_api_key="test_key", 
        initial_policy=policy,
        tool_schemas=DEFAULT_SCHEMAS,
        poll_secs=999
    )
    
    # Allowed tool should work
    result = client.tool_call("crm.read", {"account_id": "123"})
    assert result["decision"] == "allow"
    
    # Denied tool should be blocked
    result = client.tool_call("payments.charge", {"amount": 100})
    assert result["decision"] == "deny"
    
    # Allowed domain should work
    result = client.http_request("GET", "https://api.company.com/test")
    assert result["decision"] == "allow"
    
    # Blocked domain should be denied
    result = client.http_request("GET", "https://evil.com/test")
    assert result["decision"] == "deny"