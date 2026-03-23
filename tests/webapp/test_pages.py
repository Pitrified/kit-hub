"""Tests for HTML page routes (landing, dashboard, error, partials)."""

from fastapi.testclient import TestClient
from fastapi_tools.schemas.auth import SessionData


class TestLandingPage:
    """Tests for GET / (landing page)."""

    def test_landing_returns_html(self, client: TestClient) -> None:
        """Landing page returns 200 with HTML content type."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_landing_contains_login_link(self, client: TestClient) -> None:
        """Landing page contains a Google login link."""
        response = client.get("/")
        assert response.status_code == 200
        assert "/auth/google/login" in response.text

    def test_landing_contains_app_name(self, client: TestClient) -> None:
        """Landing page renders the application name."""
        response = client.get("/")
        assert "Test API" in response.text

    def test_landing_with_error_param(self, client: TestClient) -> None:
        """Landing page displays flash message for OAuth error."""
        response = client.get("/?error=auth_failed")
        assert response.status_code == 200
        assert "Authentication failed" in response.text

    def test_landing_with_unknown_error(self, client: TestClient) -> None:
        """Landing page handles unknown error codes gracefully."""
        response = client.get("/?error=something_weird")
        assert response.status_code == 200
        assert "something_weird" in response.text

    def test_landing_redirects_when_authenticated(
        self,
        authenticated_client: TestClient,
    ) -> None:
        """Authenticated users are redirected to /dashboard."""
        response = authenticated_client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"


class TestDashboardPage:
    """Tests for GET /dashboard."""

    def test_dashboard_authenticated(
        self,
        authenticated_client: TestClient,
        mock_session_data: SessionData,
    ) -> None:
        """Authenticated users see the dashboard with their info."""
        response = authenticated_client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert mock_session_data.name in response.text

    def test_dashboard_unauthenticated_redirects(
        self,
        client: TestClient,
    ) -> None:
        """Unauthenticated users are redirected to landing page."""
        response = client.get(
            "/dashboard",
            follow_redirects=False,
            headers={"accept": "text/html"},
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/"

    def test_dashboard_contains_logout(
        self,
        authenticated_client: TestClient,
    ) -> None:
        """Dashboard contains a logout form/button."""
        response = authenticated_client.get("/dashboard")
        assert response.status_code == 200
        assert "/auth/logout" in response.text

    def test_dashboard_contains_htmx_partial(
        self,
        authenticated_client: TestClient,
    ) -> None:
        """Dashboard loads user card via HTMX partial."""
        response = authenticated_client.get("/dashboard")
        assert response.status_code == 200
        assert "hx-get" in response.text
        assert "/pages/partials/user-card" in response.text


class TestUserCardPartial:
    """Tests for GET /pages/partials/user-card."""

    def test_user_card_authenticated(
        self,
        authenticated_client: TestClient,
        mock_session_data: SessionData,
    ) -> None:
        """Partial returns user card HTML fragment (no full page)."""
        response = authenticated_client.get("/pages/partials/user-card")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert mock_session_data.name in response.text
        assert mock_session_data.email in response.text
        # Should be a fragment, not a full page
        assert "<!DOCTYPE html>" not in response.text

    def test_user_card_unauthenticated(self, client: TestClient) -> None:
        """Unauthenticated request to partial returns 401 or redirect."""
        response = client.get(
            "/pages/partials/user-card",
            follow_redirects=False,
        )
        # API client gets 401, browser would get redirect
        assert response.status_code in {302, 401}


class TestErrorPage:
    """Tests for GET /error/{status_code}."""

    def test_error_404(self, client: TestClient) -> None:
        """404 error page renders correctly."""
        response = client.get("/error/404")
        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]
        assert "404" in response.text
        # Jinja2 auto-escapes the apostrophe to &#39;
        assert "looking for" in response.text

    def test_error_500(self, client: TestClient) -> None:
        """500 error page renders correctly."""
        response = client.get("/error/500")
        assert response.status_code == 500
        assert "500" in response.text

    def test_error_unknown_code(self, client: TestClient) -> None:
        """Unknown error code shows generic message."""
        response = client.get("/error/418")
        assert response.status_code == 418
        assert "418" in response.text


class TestStaticAssets:
    """Tests for static file serving."""

    def test_bulma_css_served(self, client: TestClient) -> None:
        """Bulma CSS is served from /vendor/css/bulma.min.css."""
        response = client.get("/vendor/css/bulma.min.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_htmx_js_served(self, client: TestClient) -> None:
        """HTMX JS is served from /vendor/js/htmx.min.js."""
        response = client.get("/vendor/js/htmx.min.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    def test_app_css_served(self, client: TestClient) -> None:
        """Custom app CSS is served from /static/css/app.css."""
        response = client.get("/static/css/app.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_logo_served(self, client: TestClient) -> None:
        """Logo is served from /static/img/logo.svg."""
        response = client.get("/static/img/logo.svg")
        assert response.status_code == 200

    def test_swagger_js_served(self, client: TestClient) -> None:
        """Swagger UI JS is served from /vendor/swagger/swagger-ui-bundle.js."""
        response = client.get("/vendor/swagger/swagger-ui-bundle.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    def test_swagger_css_served(self, client: TestClient) -> None:
        """Swagger UI CSS is served from /vendor/swagger/swagger-ui.css."""
        response = client.get("/vendor/swagger/swagger-ui.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_redoc_js_served(self, client: TestClient) -> None:
        """ReDoc JS is served from /vendor/swagger/redoc.standalone.js."""
        response = client.get("/vendor/swagger/redoc.standalone.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
