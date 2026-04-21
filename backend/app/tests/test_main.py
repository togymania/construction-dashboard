"""Basic smoke tests for API setup."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """Health endpoint should return ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root():
    """Root endpoint should return API info."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
