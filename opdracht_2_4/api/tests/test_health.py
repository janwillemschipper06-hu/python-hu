"""Tests for the health and ping endpoints."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.errors import CatchAllErrorsMiddleware
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ping_returns_pong() -> None:
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "pong"


def test_health_excluded_from_openapi_schema() -> None:
    schema = client.get("/openapi.json").json()
    assert "/health" not in schema["paths"]
    assert "/api/v1/ping" in schema["paths"]


def test_error_response_is_json_500_with_cors_headers() -> None:
    # Mirrors the middleware order in app.main so the fix is locked in: the
    # catch-all middleware sits inside CORSMiddleware, so the 500 it produces
    # still receives the Access-Control-Allow-Origin header.
    origin = "https://portal.example.com"
    isolated_app = FastAPI()

    error_message = "boom"

    @isolated_app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError(error_message)

    isolated_app.add_middleware(CatchAllErrorsMiddleware)
    isolated_app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin],
        allow_methods=["GET"],
    )

    isolated_client = TestClient(isolated_app, raise_server_exceptions=False)
    response = isolated_client.get("/boom", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers.get("access-control-allow-origin") == origin
