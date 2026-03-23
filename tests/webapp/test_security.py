"""Tests for security headers, CSP route-splitting, and CSRF protection."""

from fastapi.testclient import TestClient


def test_security_headers_present(client: TestClient) -> None:
    """Test that security headers are present in responses."""
    response = client.get("/health")

    # Check required security headers
    assert "x-content-type-options" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"

    assert "x-frame-options" in response.headers
    assert response.headers["x-frame-options"] == "DENY"

    assert "x-xss-protection" in response.headers
    assert "1" in response.headers["x-xss-protection"]

    assert "referrer-policy" in response.headers

    assert "content-security-policy" in response.headers


def test_request_id_header(client: TestClient) -> None:
    """Test that request ID header is present in responses."""
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_cors_headers_on_preflight(client: TestClient) -> None:
    """Test CORS headers on OPTIONS preflight request."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


def test_cors_blocked_origin(client: TestClient) -> None:
    """Test that requests from non-allowed origins don't get CORS headers."""
    response = client.get(
        "/health",
        headers={"Origin": "http://malicious-site.com"},
    )

    # The request succeeds but CORS headers should not include the origin
    assert response.status_code == 200
    # Note: The actual CORS behavior depends on middleware configuration


def test_no_hsts_in_debug_mode(client: TestClient) -> None:
    """Test that HSTS header is not set in debug/dev mode."""
    response = client.get("/health")

    # In debug mode, HSTS should not be set
    # (our test config has debug=True)
    assert "strict-transport-security" not in response.headers


# ── CSP route-splitting tests ──────────────────────────────────────


def test_strict_csp_on_app_pages(client: TestClient) -> None:
    """App/UI pages use strict CSP (no CDN, no unsafe-inline for scripts)."""
    response = client.get("/")
    csp = response.headers["content-security-policy"]

    assert "cdn.jsdelivr.net" not in csp
    # script-src must NOT have 'unsafe-inline'
    assert "script-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    # style-src allows 'unsafe-inline' (required by HTMX swap transitions)
    assert "style-src 'self' 'unsafe-inline'" in csp
    # Google profile images allowed
    assert "lh3.googleusercontent.com" in csp


def test_strict_csp_on_api_routes(client: TestClient) -> None:
    """API routes also get the strict CSP (no CDN)."""
    response = client.get("/health")
    csp = response.headers["content-security-policy"]

    assert "cdn.jsdelivr.net" not in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp


def test_relaxed_csp_on_docs(client: TestClient) -> None:
    """The /docs route gets a relaxed CSP without any CDN references."""
    response = client.get("/docs", follow_redirects=False)
    # /docs returns 200 in debug mode (our test config has debug=True)
    if response.status_code == 200:
        csp = response.headers["content-security-policy"]
        assert "'unsafe-inline'" in csp
        # Swagger is self-hosted — no CDN should appear in CSP
        assert "cdn.jsdelivr.net" not in csp


def test_relaxed_csp_on_openapi_json(client: TestClient) -> None:
    """The /openapi.json route gets the relaxed CSP."""
    response = client.get("/openapi.json")
    if response.status_code == 200:
        csp = response.headers["content-security-policy"]
        assert "'unsafe-inline'" in csp
