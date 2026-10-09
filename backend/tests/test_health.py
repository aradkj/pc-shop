import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.main import app

ALLOWED_ORIGIN = "http://localhost:5500"  # CORS_ORIGINS in conftest


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_application_starts_and_stops_cleanly():
    with TestClient(app) as running:  # runs the lifespan: startup logging, engine disposal on shutdown
        assert running.get("/health").status_code == 200


def test_health_db(client):
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_db_reports_503_without_leaking_details(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection to 10.0.0.5 failed: password authentication failed"))

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
    assert "10.0.0.5" not in response.text


def test_interactive_docs_and_openapi_schema(client):
    docs = client.get("/docs")
    schema = client.get("/openapi.json").json()

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert schema["info"]["title"] == "Arad Store API"
    assert "/api/v1/auth/login" in schema["paths"]
    assert "OAuth2PasswordBearer" in schema["components"]["securitySchemes"]
    assert "jsdelivr" not in docs.text
    assert "/static/swagger-ui/swagger-ui-bundle.js" in docs.text
    assert "/static/swagger-ui/swagger-ui.css" in docs.text
    assert "/static/swagger-ui/favicon.png" in docs.text

    assert client.get("/static/swagger-ui/swagger-ui-bundle.js").status_code == 200
    assert client.get("/static/swagger-ui/swagger-ui.css").status_code == 200
    assert client.get("/static/swagger-ui/favicon.png").status_code == 200


# ------------------------------------------------------------------------------ CORS


def test_cors_preflight_allows_the_configured_origin(client):
    response = client.options(
        "/api/v1/products",
        headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Authorization"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"  # HttpOnly cookies require credentials



def test_cors_rejects_other_origins(client):
    preflight = client.options(
        "/api/v1/products", headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"}
    )
    simple = client.get("/health", headers={"Origin": "http://evil.example.com"})

    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-origin" not in simple.headers


def test_cors_header_on_normal_responses(client):
    response = client.get("/api/v1/products", headers={"Origin": ALLOWED_ORIGIN})

    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


# ------------------------------------------------------------------- error handling


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_wrong_method_returns_405(client):
    response = client.delete("/health")

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}


def test_unhandled_errors_return_a_generic_500_and_are_logged(caplog):
    broken = FastAPI()
    register_exception_handlers(broken)

    @broken.get("/boom")
    def boom():
        raise RuntimeError("internal detail: password=hunter2")

    with caplog.at_level(logging.ERROR):
        response = TestClient(broken, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text
    assert "Unhandled error on GET /boom" in caplog.text  # the operator still gets the traceback
