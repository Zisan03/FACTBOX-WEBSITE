"""Tests for public route accessibility and security headers."""


def test_public_pages_render(client):
    """Verify that all four approved public routes render with HTTP 200."""
    routes = ["/", "/about", "/services", "/work", "/contact"]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, f"Route {route} failed with status {response.status_code}"
        assert b"FACT BOX CONSULT" in response.data


def test_security_headers_present(client):
    """Verify that mandatory security headers are attached to responses."""
    response = client.get("/")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_custom_404_page(client):
    """Verify that 404 returns the branded template without error leak."""
    response = client.get("/non-existent-page-url")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data
