"""FastAPI application entry point for the Customer Onboarding Portal API.

Composes the feature modules behind a single deny-by-default authentication seam.
Database access reaches Azure SQL only through the EXECUTE-only stored procedures
(``docs/adr/0002``, ``docs/adr/0008``); the ``/health`` and ``/api/v1/ping``
probes below intentionally have no database dependency so the container's health
checks stay fast and the test suite runs without an ODBC driver installed.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.errors import CatchAllErrorsMiddleware

# When the app is served behind the shared APIM gateway under a path prefix such
# as ``/cop`` that the gateway strips before forwarding, FastAPI must know that
# prefix so the Swagger UI and generated ``servers`` reference
# ``<prefix>/openapi.json`` instead of ``/openapi.json`` at the domain root.
# Defaults to empty so local development and direct container access are
# unaffected.
root_path = os.environ.get("ROOT_PATH", "")

app = FastAPI(title="Customer Onboarding Portal API", root_path=root_path)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Report liveness/readiness for the container platform's health probes.

    Returns:
        A minimal JSON payload confirming the process is up and serving
        requests. Intentionally avoids any external dependency (e.g. the
        database) so probes stay fast and don't fail due to unrelated downstream
        outages.
    """
    return {"status": "ok"}


@app.get("/api/v1/ping")
async def ping() -> dict[str, str]:
    """Return a trivial payload confirming the API routes end to end.

    Used as the smoke test the Static Web App calls after deploy to verify the
    browser -> APIM -> Container App path is wired correctly.

    Returns:
        A JSON payload with a fixed ``pong`` message.
    """
    return {"message": "pong"}


# Order matters: the error-catching middleware is added first so it sits *inside*
# CORSMiddleware (added last = outermost among app middleware). That way the JSON
# 500 it returns flows back out through CORS and receives the CORS headers.
app.add_middleware(CatchAllErrorsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[url for url in (os.environ.get("STATIC_WEBAPP_URL"),) if url],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Authentication is declared **once**, in `app.api`: every feature router is a
# bare `APIRouter` mounted under a single deny-by-default `api_router` that runs
# `validated_token` for all of its routes. Adding a new feature router there
# secures it automatically — there is no per-router authentication guard to
# forget. The `/health` and `/api/v1/ping` routes are registered directly on
# `app` above, deliberately **outside** `api_router`, because the platform's
# health probes and the post-deploy smoke test reach them with no authenticated
# token.
#
# Layered on top, `app.api` declares the three **role** tiers once — the
# three-router authorization model (docs/authentication-and-access.md §4.2):
# admin (`require_admin`), portal (`require_portal_user`), and extract
# (`require_extract_client`) — and mounts each module's bare router under the
# right tier. Those guards also depend on `validated_token`, which FastAPI caches
# per request, so it still runs only once per call.
app.include_router(api_router)
