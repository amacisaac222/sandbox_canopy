import pytest
from sdk.enforcement import tool_allowed, domain_allowed, validate_params

def test_tool_patterns():
    """Test tool pattern matching with allow/deny lists"""
    # Should allow crm.* but deny payments.*
    assert tool_allowed("crm.read", ["crm.*"], ["payments.*"])
    assert tool_allowed("crm.update", ["crm.*"], ["payments.*"])
    assert not tool_allowed("payments.charge", ["crm.*"], ["payments.*"])
    assert not tool_allowed("payments.refund", ["crm.*"], ["payments.*"])
    
    # Test specific tool names
    assert tool_allowed("email.send", ["email.send"], [])
    assert not tool_allowed("email.send", [], ["email.send"])

def test_domain_allowlist():
    """Test domain allowlist functionality"""
    # When deny_all_others is True, only allow_domains should work
    assert domain_allowed("api.company.com", ["api.company.com"], True)
    assert domain_allowed("sub.api.company.com", ["api.company.com"], True)  # subdomain
    assert not domain_allowed("evil.com", ["api.company.com"], True)
    
    # When deny_all_others is False, everything should be allowed
    assert domain_allowed("anything.com", ["api.company.com"], False)
    assert domain_allowed("evil.com", [], False)

def test_json_schema_validation():
    """Test JSON schema parameter validation"""
    email_schema = {
        "type": "object",
        "properties": {
            "recipient": {"type": "string", "maxLength": 254},
            "subject": {"type": "string", "maxLength": 120},
            "body": {"type": "string", "maxLength": 1000}
        },
        "required": ["recipient", "subject", "body"],
        "additionalProperties": False
    }
    
    # Valid params should pass
    valid_params = {
        "recipient": "test@company.com",
        "subject": "Test",
        "body": "Test message"
    }
    ok, err = validate_params(email_schema, valid_params)
    assert ok
    assert err is None
    
    # Missing required field should fail
    invalid_params = {
        "recipient": "test@company.com",
        "subject": "Test"
        # missing body
    }
    ok, err = validate_params(email_schema, invalid_params)
    assert not ok
    assert "body" in str(err)
    
    # Extra field should fail
    extra_params = {
        "recipient": "test@company.com",
        "subject": "Test",
        "body": "Test message",
        "extra": "not allowed"
    }
    ok, err = validate_params(email_schema, extra_params)
    assert not ok
    assert "additional" in str(err).lower()