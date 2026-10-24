"""
Tests for BrandSentry AI Health Check API
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check_status_code():
    """Verify that GET /health returns HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_payload():
    """Verify that GET /health returns expected service metadata."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert data["service"] == "BrandSentry AI"
    assert "version" in data
    assert "environment" in data


def test_root_endpoint():
    """Verify that GET / returns 200 operational message."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "docs" in data


def test_cors_headers_for_onrender_origin():
    """Regression test: verify CORS headers are allowed for https://brandsentry-web.onrender.com."""
    headers = {"Origin": "https://brandsentry-web.onrender.com"}
    response = client.get("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://brandsentry-web.onrender.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_for_onrender_origin():
    """Regression test: verify OPTIONS preflight request succeeds for Render frontend domain."""
    headers = {
        "Origin": "https://brandsentry-web.onrender.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/api/guidelines/upload", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://brandsentry-web.onrender.com"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
