"""Tests for authentication endpoints."""

from fastapi.testclient import TestClient
from fastapi_tools.schemas.auth import SessionData


def test_google_login_redirect(client: TestClient) -> None:
    """Test Google login redirects to Google OAuth."""
    response = client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    assert "accounts.google.com" in response.headers["location"]


def test_google_login_no_redirect(client: TestClient) -> None:
    """Test Google login returns URL when redirect=false."""
    response = client.get("/auth/google/login?redirect=false")
    assert response.status_code == 200

    data = response.json()
    assert "auth_url" in data
    assert "state" in data
    assert "accounts.google.com" in data["auth_url"]


def test_auth_status_unauthenticated(client: TestClient) -> None:
    """Test auth status when not authenticated."""
    response = client.get("/auth/status")
    assert response.status_code == 200

    data = response.json()
    assert data["authenticated"] is False
    assert data["user"] is None


def test_auth_status_authenticated(
    authenticated_client: TestClient,
    mock_session_data: SessionData,
) -> None:
    """Test auth status when authenticated."""
    response = authenticated_client.get("/auth/status")
    assert response.status_code == 200

    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["email"] == mock_session_data.email


def test_get_current_user_unauthenticated(client: TestClient) -> None:
    """Test /auth/me returns 401 when not authenticated."""
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_current_user_authenticated(
    authenticated_client: TestClient,
    mock_session_data: SessionData,
) -> None:
    """Test /auth/me returns user info when authenticated."""
    response = authenticated_client.get("/auth/me")
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == mock_session_data.email
    assert data["name"] == mock_session_data.name


def test_logout_unauthenticated(client: TestClient) -> None:
    """Test logout returns 401 when not authenticated."""
    response = client.post("/auth/logout")
    assert response.status_code == 401


def test_logout_authenticated(
    authenticated_client: TestClient,
    mock_session_data: SessionData,
) -> None:
    """Test logout clears session when authenticated."""
    # API client (no Accept: text/html) gets JSON
    response = authenticated_client.post(
        "/auth/logout",
        headers={"accept": "application/json"},
    )
    assert response.status_code == 200

    # Verify session is cleared
    status_response = authenticated_client.get("/auth/status")
    assert status_response.json()["authenticated"] is False


def test_google_callback_invalid_state(client: TestClient) -> None:
    """Test callback with invalid state parameter."""
    response = client.get(
        "/auth/google/callback?code=test_code&state=invalid_state",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "error=invalid_state" in response.headers["location"]


def test_google_callback_with_error(client: TestClient) -> None:
    """Test callback when Google returns an error."""
    # code and state are required even when error is present
    response = client.get(
        "/auth/google/callback?code=test&state=test&error=access_denied",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "error=access_denied" in response.headers["location"]


def test_logout_browser_redirects(
    authenticated_client: TestClient,
) -> None:
    """Test browser logout redirects to landing page."""
    response = authenticated_client.post(
        "/auth/logout",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_logout_htmx_returns_hx_redirect(
    authenticated_client: TestClient,
) -> None:
    """Test HTMX logout returns HX-Redirect header."""
    response = authenticated_client.post(
        "/auth/logout",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/"
