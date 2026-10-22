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
