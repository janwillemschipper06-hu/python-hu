"""Extraction router — machine-only reporting endpoints (currently none).

A bare :data:`router` (no prefix, no guard): :mod:`app.api` mounts it under the
**extract** authorization tier, which applies the ``/api/v1/extract`` prefix and
the :func:`~app.core.security.require_extract_client` guard once for every route
(``docs/authentication-and-access.md`` §4.2). The feed is machine-only: it
carries **no user context** and is reached solely by the separate reporting
client (the ``Extract.Read`` app role, ``appid`` allow-listed by Container Apps
built-in auth — ``docs/adr/0010``).

The former ``/customers`` feed was removed with the customer module
(``docs/adr/0013``); the extraction API is out of scope until it is redesigned.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
