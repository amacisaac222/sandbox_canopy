"""
Health endpoint tests for CanopyIQ

Tests the /healthz and /readyz endpoints to ensure they return expected status codes.
These tests verify basic application health and readiness.
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


def test_healthz_endpoint(client):
    """Test that /healthz endpoint returns 200 OK."""
    response = client.get("/healthz")
    assert response.status_code == 200
    
    # Check response contains expected health status
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "ok"]
    assert "timestamp" in data


def test_readyz_endpoint_with_db_connection(client):
    """Test that /readyz endpoint returns 200 when database is available."""
    # Mock database connection to be successful
    with patch('canopyiq_site.database.engine') as mock_engine:
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = MagicMock()
        
        response = client.get("/readyz")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["ready", "ok"]
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"] == "ok"


def test_readyz_endpoint_with_db_failure(client):
    """Test that /readyz endpoint returns 503 when database is unavailable."""
    # Mock database connection to fail
    with patch('canopyiq_site.database.engine') as mock_engine:
        mock_engine.connect.side_effect = Exception("Database connection failed")
        
        response = client.get("/readyz")
        assert response.status_code == 503
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "not ready"
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"] == "error"


def test_health_endpoints_content_type(client):
    """Test that health endpoints return JSON content type."""
    for endpoint in ["/healthz", "/readyz"]:
        response = client.get(endpoint)
        assert "application/json" in response.headers.get("content-type", "")


def test_health_endpoints_no_cache(client):
    """Test that health endpoints include no-cache headers."""
    for endpoint in ["/healthz", "/readyz"]:
        response = client.get(endpoint)
        # Health endpoints should not be cached
        cache_control = response.headers.get("cache-control", "")
        assert "no-cache" in cache_control.lower() or "no-store" in cache_control.lower()


def test_healthz_fast_response(client):
    """Test that /healthz responds quickly (basic liveness check)."""
    import time
    
    start_time = time.time()
    response = client.get("/healthz")
    end_time = time.time()
    
    # Health check should be fast (< 1 second)
    assert (end_time - start_time) < 1.0
    assert response.status_code == 200


def test_readyz_includes_version_info(client):
    """Test that /readyz includes application version information."""
    with patch('canopyiq_site.database.engine') as mock_engine:
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = MagicMock()
        
        response = client.get("/readyz")
        assert response.status_code == 200
        
        data = response.json()
        # Should include version or build info
        assert "version" in data or "build" in data or "app" in data


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_health_endpoints_only_support_get(client, method):
    """Test that health endpoints only support GET method."""
    for endpoint in ["/healthz", "/readyz"]:
        response = client.request(method, endpoint)
        # Should return 405 Method Not Allowed or 404 if routing doesn't support the method
        assert response.status_code in [405, 404]


def test_health_endpoints_structure(client):
    """Test that health endpoints return expected JSON structure."""
    # Test /healthz structure
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    
    required_fields = ["status", "timestamp"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Test /readyz structure with mocked database
    with patch('canopyiq_site.database.engine') as mock_engine:
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = MagicMock()
        
        response = client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["status", "checks"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Checks should be a dictionary
        assert isinstance(data["checks"], dict)


def test_health_endpoints_concurrent_requests(client):
    """Test that health endpoints handle concurrent requests properly."""
    import threading
    import time
    
    results = []
    
    def make_request(endpoint):
        response = client.get(endpoint)
        results.append(response.status_code)
    
    # Create multiple threads to test concurrent access
    threads = []
    for i in range(5):
        for endpoint in ["/healthz", "/readyz"]:
            thread = threading.Thread(target=make_request, args=(endpoint,))
            threads.append(thread)
            thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # All requests should succeed (even if readyz fails, it should return 503, not crash)
    assert len(results) == 10  # 5 threads × 2 endpoints
    for status_code in results:
        assert status_code in [200, 503]  # Either healthy or not ready, but not crashed