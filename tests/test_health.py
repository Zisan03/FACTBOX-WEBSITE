"""Tests for health check endpoint."""
from unittest.mock import patch
from sqlalchemy.exc import OperationalError


def test_health_check_healthy(client):
    """Verify that /health returns 200 and connected status when database is reachable."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    # Ensure no internal hostnames or credentials leaked
    assert "factbox_user" not in str(data)
    assert "localhost" not in str(data)


def test_health_check_database_failure(client):
    """Verify that /health returns 503 degraded status without leaking database errors."""
    with patch("app.blueprints.health.routes.db.session.execute", side_effect=OperationalError("connection failed", None, None)):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "degraded"
        assert data["database"] == "unavailable"
        assert "connection failed" not in str(data)
