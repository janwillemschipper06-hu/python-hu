"""API schema for the session (``whoami``) module."""

from __future__ import annotations

from pydantic import BaseModel


class WhoAmI(BaseModel):
    """The caller's identity as the API sees it after platform authentication.

    A diagnostic projection of the validated ``X-MS-CLIENT-PRINCIPAL`` claims.
    ``is_admin`` is derived from the authoritative ``roles`` claim — the same
    signal every router-level guard authorizes on — so a human can confirm the
    role reaches the API, not just the browser.
    """

    oid: str | None
    tid: str | None
    app_id: str | None
    audience: str | list[str] | None
    roles: list[str]
    is_admin: bool
