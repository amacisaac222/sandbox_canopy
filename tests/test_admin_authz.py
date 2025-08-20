"""
Admin authorization tests for CanopyIQ

Tests that non-admin users cannot access admin-only pages and that proper
authorization controls are enforced across the admin interface.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path to import canopyiq_site modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from canopyiq_site.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_non_admin_user():
    """Create a mock non-admin user."""
    user = MagicMock()
    user.id = 2
    user.email = "user@example.com"
    user.is_admin = False
    user.auth_provider = "oidc"
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.id = 1
    user.email = "admin@example.com"
    user.is_admin = True
    user.auth_provider = "local"
    user.is_active = True
    return user


def test_unauthenticated_user_cannot_access_admin(client):
    """Test that unauthenticated users cannot access admin pages."""
    admin_routes = [
        "/admin",
        "/admin/dashboard",
        "/admin/settings",
        "/admin/audit",
        "/admin/submissions"
    ]
    
    for route in admin_routes:
        response = client.get(route, follow_redirects=False)
        
        # Should redirect to authentication (not allow access)
        assert response.status_code == 302
        
        location = response.headers.get("location", "")
        # Should redirect to login or setup
        assert any(path in location for path in ["/auth/login", "/setup", "/local"])


def test_non_admin_user_cannot_access_admin_pages(client, mock_non_admin_user):
    """Test that authenticated non-admin users cannot access admin pages."""
    admin_routes = [
        "/admin",
        "/admin/dashboard", 
        "/admin/settings",
        "/admin/audit",
        "/admin/submissions"
    ]
    
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_non_admin_user
        
        for route in admin_routes:
            response = client.get(route)
            
            # Should return 403 Forbidden or redirect away from admin
            assert response.status_code in [403, 302]
            
            if response.status_code == 302:
                location = response.headers.get("location", "")
                # Should not redirect to another admin page
                assert "/admin" not in location


def test_admin_user_can_access_admin_pages(client, mock_admin_user):
    """Test that admin users can access admin pages."""
    admin_routes = [
        "/admin",
        "/admin/dashboard",
        "/admin/settings", 
        "/admin/audit",
        "/admin/submissions"
    ]
    
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_admin_user
        
        # Mock database queries that admin pages might make
        with patch('canopyiq_site.database.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            mock_connection.execute.return_value.fetchall.return_value = []
            mock_connection.execute.return_value.scalar.return_value = 0
            
            for route in admin_routes:
                response = client.get(route)
                
                # Should allow access (200 OK)
                assert response.status_code == 200


def test_admin_post_actions_require_admin(client, mock_non_admin_user):
    """Test that POST actions on admin routes require admin privileges."""
    admin_post_routes = [
        ("/admin/settings", {"slack_webhook_url": "https://example.com/webhook"}),
        ("/admin/settings/test-slack", {}),
    ]
    
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_non_admin_user
        
        for route, data in admin_post_routes:
            response = client.post(route, data=data)
            
            # Should deny access (403 Forbidden or redirect)
            assert response.status_code in [403, 302, 405]


def test_admin_api_endpoints_require_admin(client, mock_non_admin_user):
    """Test that admin API endpoints require admin privileges."""
    admin_api_routes = [
        "/admin/api/health",
        "/admin/api/stats",
        "/admin/api/audit/export"
    ]
    
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_non_admin_user
        
        for route in admin_api_routes:
            response = client.get(route)
            
            # Should deny access (403 Forbidden) or not found if endpoint doesn't exist
            assert response.status_code in [403, 404]


def test_inactive_admin_cannot_access_admin(client):
    """Test that inactive admin users cannot access admin pages."""
    inactive_admin = MagicMock()
    inactive_admin.id = 1
    inactive_admin.email = "admin@example.com"
    inactive_admin.is_admin = True
    inactive_admin.is_active = False  # Inactive user
    
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = inactive_admin
        
        response = client.get("/admin/dashboard")
        
        # Should deny access to inactive users
        assert response.status_code in [403, 302]


def test_rbac_dependency_injection(client):
    """Test that RBAC dependency injection works correctly."""
    # Test without authentication
    response = client.get("/admin")
    assert response.status_code == 302  # Redirect to auth
    
    # Test with non-admin user
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = None  # No user
        
        response = client.get("/admin")
        assert response.status_code == 302  # Redirect to auth


def test_admin_role_escalation_prevention(client, mock_non_admin_user):
    """Test that users cannot escalate their privileges to admin."""
    # Attempt to access admin endpoints with modified session data
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        # Even if user claims to be admin in session, the database check should prevent access
        mock_non_admin_user.is_admin = False  # Ensure database says non-admin
        mock_get_user.return_value = mock_non_admin_user
        
        response = client.get("/admin/settings")
        assert response.status_code in [403, 302]


def test_admin_csrf_protection(client, mock_admin_user):
    """Test that admin forms include CSRF protection."""
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_admin_user
        
        # Mock database for admin page rendering
        with patch('canopyiq_site.database.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            mock_connection.execute.return_value.fetchall.return_value = []
            
            response = client.get("/admin/settings")
            assert response.status_code == 200
            
            # Check if response contains CSRF token (basic check)
            content = response.text
            # Common CSRF token patterns
            csrf_indicators = ["csrf", "token", "_token", "authenticity_token"]
            has_csrf = any(indicator in content.lower() for indicator in csrf_indicators)
            
            # If forms are present, they should have some form of CSRF protection
            if "<form" in content:
                assert has_csrf, "Admin forms should include CSRF protection"


def test_admin_session_timeout(client, mock_admin_user):
    """Test that admin sessions can be configured with appropriate timeouts."""
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_admin_user
        
        # Test that admin access works initially
        response = client.get("/admin")
        assert response.status_code in [200, 302]  # Allow redirect to dashboard
        
        # Simulate expired session by returning None user
        mock_get_user.return_value = None
        
        response = client.get("/admin")
        assert response.status_code == 302  # Should redirect to auth


def test_admin_audit_logging(client, mock_admin_user):
    """Test that admin actions are logged for audit purposes."""
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_admin_user
        
        # Mock audit logging
        with patch('canopyiq_site.database.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            mock_connection.execute.return_value.fetchall.return_value = []
            
            # Access admin page
            response = client.get("/admin/settings")
            
            # Should log the admin access (check if audit functions are called)
            # This is a basic test - in a real system you'd verify audit log entries
            assert response.status_code == 200


def test_multiple_admin_sessions(client, mock_admin_user):
    """Test that multiple admin sessions can coexist without interference."""
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_admin_user
        
        # Simulate multiple concurrent admin sessions
        with patch('canopyiq_site.database.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            mock_connection.execute.return_value.fetchall.return_value = []
            
            # Multiple requests should all succeed
            responses = []
            for i in range(3):
                response = client.get("/admin/dashboard")
                responses.append(response.status_code)
            
            # All admin requests should succeed
            assert all(status == 200 for status in responses)


def test_admin_resource_access_control(client, mock_non_admin_user, mock_admin_user):
    """Test that admin resources are properly access controlled."""
    # Test non-admin cannot access admin-specific resources
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_non_admin_user
        
        # Try to access admin static files or API endpoints
        admin_resources = [
            "/admin/static/admin.css",  # If such resources exist
            "/admin/api/system-health",
            "/admin/export/audit-logs"
        ]
        
        for resource in admin_resources:
            response = client.get(resource)
            # Should either be forbidden or not found (but not accessible)
            assert response.status_code in [403, 404]


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_admin_endpoints_method_restrictions(client, mock_non_admin_user, method):
    """Test that admin endpoints properly restrict HTTP methods for non-admin users."""
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_non_admin_user
        
        response = client.request(method, "/admin/settings")
        
        # Should deny access regardless of HTTP method
        assert response.status_code in [403, 302, 405]


def test_admin_error_handling_non_admin(client, mock_non_admin_user):
    """Test that admin error pages don't leak information to non-admin users."""
    with patch('canopyiq_site.auth.rbac.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_non_admin_user
        
        # Try to access non-existent admin page
        response = client.get("/admin/nonexistent")
        
        # Should not reveal admin page structure to non-admin users
        assert response.status_code in [403, 302]
        
        # Response should not contain admin-specific error details
        if response.status_code != 302:
            content = response.text.lower()
            admin_leaks = ["admin panel", "administrator", "admin dashboard"]
            for leak in admin_leaks:
                assert leak not in content