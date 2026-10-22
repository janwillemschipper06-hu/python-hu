"""Session router — the role-agnostic ``whoami`` identity echo (``/whoami``).

A bare :data:`router` (no prefix, no guard): :mod:`app.api` mounts it under the
**portal** authorization tier, which applies the ``/api/v1/portal`` prefix and
admits any authenticated caller (``docs/authentication-and-access.md`` §4.2). The
handler reads the full validated principal directly via
:func:`~app.core.security.validated_token` — richer than the portal principal —
so it can echo every claim (``tid``, ``audience``, app id) the diagnostic needs.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.security import ClientPrincipal, validated_token
from app.integrations import graph
from app.modules.session.schemas import WhoAmI
from app.modules.users.service import record_sign_in

# Must match the authoritative admin role in app.core.security (kept local to
# avoid importing a private module constant).
_ADMIN_ROLE = "Admin"

router = APIRouter()


@router.get("/whoami", response_model=WhoAmI)
def whoami(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> WhoAmI:
    """Return the caller's identity and roles as the API sees them.

    A diagnostic so an operator can confirm the token's role claim survives the
    browser -> APIM -> Container Apps built-in auth path and reaches the app.

    Also stamps the caller's first sign-in (invitation redemption) — the frontend
    calls this once per sign-in, and the stamp is set only once.

    Args:
        principal: The platform-validated caller.

    Returns:
        The caller's own identity claims, including the authoritative role set.
    """
    record_sign_in(principal.oid)
    return WhoAmI(
        oid=principal.oid,
        tid=principal.tid,
        app_id=principal.appid or principal.azp,
        audience=principal.audience,
        roles=list(principal.roles),
        is_admin=_ADMIN_ROLE in principal.roles,
    )


@router.get("/me/photo")
def my_photo(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> Response:
    """Return the caller's own Entra profile photo, or 404 when they have none.

    Read server-side with the portal's Graph identity so the SPA needs no extra
    Graph consent; many guest accounts have no photo and the SPA then shows
    initials.

    Args:
        principal: The platform-validated caller (only their own photo is served).

    Returns:
        The image bytes with the photo's content type.

    Raises:
        HTTPException: 404 when the caller has no oid or no profile photo.
    """
    photo = graph.get_user_photo(principal.oid) if principal.oid else None
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo")
    content, media_type = photo
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
