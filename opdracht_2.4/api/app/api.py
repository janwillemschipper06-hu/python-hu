"""Central API composition — the authorization tiers, declared once.

Every feature module exposes a **bare** ``APIRouter`` (no prefix, no guard). This
module is the single place that gives each router its URL prefix and its
router-level role guard, so the three-tier authorization model
(``docs/authentication-and-access.md`` §4.2) is declared exactly once and a new
module is secured simply by mounting it under the right tier — there is no
per-module prefix/guard to copy or forget:

| Tier | Prefix | Guard | Modules |
|---|---|---|---|
| **admin**   | ``/api/v1/admin``   | :func:`~app.core.security.require_admin`          | ``users`` |
| **portal**  | ``/api/v1/portal``  | :func:`~app.core.security.require_portal_user`    | ``customers`` (lookup), ``lookups``, ``projects``, ``session`` |
| **extract** | ``/api/v1/extract`` | :func:`~app.core.security.require_extract_client` | ``extraction`` |

The three tiers are themselves mounted under a single deny-by-default
:data:`api_router` that runs :func:`~app.core.security.validated_token` for all of
them, so authentication is applied once and a newly added tier cannot be left
unauthenticated. ``app.main`` includes :data:`api_router`; the only anonymous
routes (``/health``, ``/api/v1/ping``) are registered directly on the app,
outside this router. A future public tier (if ever needed) would mount **outside**
:data:`api_router` and also requires a matching ``excludedPaths`` entry in the
platform auth config (``infra/resources.bicep``), since Container Apps built-in
auth returns 401 before an anonymous request can reach the app (``docs/adr/0010``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import (
    require_admin,
    require_extract_client,
    require_portal_user,
    validated_token,
)
from app.modules.customers.router import router as customers_router
from app.modules.extraction.router import router as extraction_router
from app.modules.lookups.router import router as lookups_router
from app.modules.projects.router import router as projects_router
from app.modules.session.router import router as session_router
from app.modules.users.router import router as users_router

# --- admin tier: only callers holding the Admin app role ---
admin_tier = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)
admin_tier.include_router(users_router)

# --- portal tier: any authenticated caller (admin or customer-scoped guest) ---
portal_tier = APIRouter(
    prefix="/api/v1/portal",
    tags=["portal"],
    dependencies=[Depends(require_portal_user)],
)
portal_tier.include_router(customers_router)
portal_tier.include_router(lookups_router)
portal_tier.include_router(projects_router)
portal_tier.include_router(session_router)

# --- extract tier: the machine reporting client only (Extract.Read) ---
extract_tier = APIRouter(
    prefix="/api/v1/extract",
    tags=["extract"],
    dependencies=[Depends(require_extract_client)],
)
extract_tier.include_router(extraction_router)

# Deny-by-default authentication umbrella: every tier runs validated_token once.
api_router = APIRouter(dependencies=[Depends(validated_token)])
api_router.include_router(admin_tier)
api_router.include_router(portal_tier)
api_router.include_router(extract_tier)
