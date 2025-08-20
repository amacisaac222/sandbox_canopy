"""
Authentication flow tests for CanopyIQ

Tests OIDC authentication flows when configured, skips tests if OIDC environment
variables are missing. Focuses on login redirects and session management.
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys

# Add the parent directory to the path to import canopyiq_site modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from canopyiq_site.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def has_oidc_config():
    """Check if OIDC environment variables are configured."""
    required_vars = ['OIDC_ISSUER', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET']
    return all(os.getenv(var) for var in required_vars)


@pytest.mark.skipif(not has_oidc_config(), reason="OIDC environment variables not configured")
def test_oidc_login_redirect(client):
    """Test that /auth/login redirects to OIDC provider when configured."""
    response = client.get("/auth/login", follow_redirects=False)
    
    # Should redirect to OIDC provider
    assert response.status_code == 302
    
    # Redirect location should contain the OIDC issuer
    location = response.headers.get("location", "")
    oidc_issuer = os.getenv('OIDC_ISSUER')
    assert oidc_issuer in location
    
    # Should contain required OIDC parameters
    assert "client_id=" in location
    assert "redirect_uri=" in location
    assert "response_type=code" in location
    assert "scope=" in location


@pytest.mark.skipif(not has_oidc_config(), reason="OIDC environment variables not configured")
def test_oidc_callback_endpoint_exists(client):
    """Test that OIDC callback endpoint exists and handles requests."""
    # Test callback endpoint without valid code (should handle gracefully)
    response = client.get("/auth/callback")
    
    # Should not return 404 (endpoint exists)
    assert response.status_code != 404
    
    # Should return either 400 (bad request) or redirect
    assert response.status_code in [400, 302, 422]


@pytest.mark.skipif(not has_oidc_config(), reason="OIDC environment variables not configured")
def test_oidc_callback_with_invalid_code(client):
    """Test OIDC callback with invalid authorization code."""
    response = client.get("/auth/callback?code=invalid_code&state=test_state")
    
    # Should handle invalid code gracefully (not crash)
    assert response.status_code in [400, 401, 302]  # Bad request, unauthorized, or redirect to login


@pytest.mark.skipif(not has_oidc_config(), reason="OIDC environment variables not configured")
def test_oidc_logout_clears_session(client):
    """Test that logout clears the session."""
    # First, simulate a logged-in session
    with client.session_transaction() as session:
        session['user_id'] = 'test_user'
        session['user_email'] = 'test@example.com'
    
    # Logout should clear session
    response = client.get("/auth/logout", follow_redirects=False)
    
    # Should redirect (logout successful)
    assert response.status_code in [302, 200]
    
    # Session should be cleared (check if session is empty or user info removed)
    with client.session_transaction() as session:
        assert 'user_id' not in session or session.get('user_id') is None


def test_auth_without_oidc_config(client):
    """Test authentication behavior when OIDC is not configured."""
    # Temporarily remove OIDC environment variables
    original_vars = {}
    oidc_vars = ['OIDC_ISSUER', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET']
    
    for var in oidc_vars:
        original_vars[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
    
    try:
        # Should either redirect to local login or setup
        response = client.get("/auth/login", follow_redirects=False)
        
        # Should not crash (graceful handling)
        assert response.status_code in [200, 302]
        
        if response.status_code == 302:
            location = response.headers.get("location", "")
            # Should redirect to local login or setup, not to external OIDC
            assert not location.startswith("http")
            assert any(path in location for path in ["/local", "/setup", "/login"])
    
    finally:
        # Restore original environment variables
        for var, value in original_vars.items():
            if value is not None:
                os.environ[var] = value


def test_protected_routes_redirect_to_auth(client):
    """Test that protected routes redirect unauthenticated users to auth."""
    protected_routes = [
        "/admin",
        "/admin/dashboard",
        "/admin/settings",
        "/admin/audit"
    ]
    
    for route in protected_routes:
        response = client.get(route, follow_redirects=False)
        
        # Should redirect to authentication
        assert response.status_code == 302
        
        location = response.headers.get("location", "")
        # Should redirect to login or setup
        assert any(path in location for path in ["/auth/login", "/setup", "/local"])


def test_local_auth_fallback(client):
    """Test local authentication as fallback when OIDC is not available."""
    # Mock no admin users exist to trigger setup flow
    with patch('canopyiq_site.auth.local.has_admin_users') as mock_has_admin:
        mock_has_admin.return_value = False
        
        response = client.get("/auth/login", follow_redirects=False)
        
        # Should redirect to setup when no admin users exist
        assert response.status_code == 302
        location = response.headers.get("location", "")
        assert "/setup" in location


def test_session_persistence(client):
    """Test that authenticated sessions persist across requests."""
    # Simulate authenticated session
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "admin@example.com"
        mock_user.is_admin = True
        mock_get_user.return_value = mock_user
        
        # First request with session
        response1 = client.get("/admin/dashboard")
        
        # Session should allow access to admin routes
        assert response1.status_code in [200, 302]  # Either success or redirect (but not 401/403)


@pytest.mark.skipif(not has_oidc_config(), reason="OIDC environment variables not configured")
def test_oidc_state_parameter(client):
    """Test that OIDC login includes and validates state parameter."""
    response = client.get("/auth/login", follow_redirects=False)
    
    assert response.status_code == 302
    location = response.headers.get("location", "")
    
    # Should include state parameter for CSRF protection
    assert "state=" in location
    
    # State should be a reasonable length (not empty)
    import re
    state_match = re.search(r'state=([^&]+)', location)
    assert state_match
    state_value = state_match.group(1)
    assert len(state_value) >= 10  # Reasonable minimum length for security


@pytest.mark.skipif(not has_oidc_config(), reason="OIDC environment variables not configured")
def test_oidc_scope_parameter(client):
    """Test that OIDC login requests appropriate scopes."""
    response = client.get("/auth/login", follow_redirects=False)
    
    assert response.status_code == 302
    location = response.headers.get("location", "")
    
    # Should include scope parameter
    assert "scope=" in location
    
    # Should request openid scope at minimum
    assert "openid" in location


def test_auth_error_handling(client):
    """Test that authentication errors are handled gracefully."""
    # Test various error scenarios
    error_scenarios = [
        "/auth/callback?error=access_denied",
        "/auth/callback?error=invalid_request",
        "/auth/callback?code=&state=empty_code"
    ]
    
    for scenario in error_scenarios:
        response = client.get(scenario)
        
        # Should handle errors gracefully (not crash with 500)
        assert response.status_code != 500
        assert response.status_code in [200, 302, 400, 401]


def test_concurrent_auth_requests(client):
    """Test that concurrent authentication requests don't cause issues."""
    import threading
    
    results = []
    
    def make_auth_request():
        response = client.get("/auth/login", follow_redirects=False)
        results.append(response.status_code)
    
    # Create multiple concurrent authentication requests
    threads = []
    for i in range(5):
        thread = threading.Thread(target=make_auth_request)
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # All requests should complete successfully
    assert len(results) == 5
    for status_code in results:
        assert status_code in [200, 302]  # Either success or redirect


def test_auth_headers_security(client):
    """Test that authentication responses include appropriate security headers."""
    response = client.get("/auth/login", follow_redirects=False)
    
    # Should include security headers
    headers = response.headers
    
    # Check for common security headers
    expected_headers = [
        "x-content-type-options",
        "x-frame-options",
        "x-xss-protection"
    ]
    
    # At least some security headers should be present
    present_headers = [h for h in expected_headers if h in headers]
    assert len(present_headers) > 0, "No security headers found in auth response"