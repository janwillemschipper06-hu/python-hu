"""Users router — admin-only invite, provisioning, and user lifecycle endpoints.

A bare :data:`router` (no prefix, no guard): :mod:`app.api` mounts it under the
**admin** authorization tier, which applies the ``/api/v1/admin`` prefix and the
:func:`~app.core.security.require_admin` guard once for every route
(``docs/authentication-and-access.md`` §4.2), so no endpoint here can be left
under-protected. The role-agnostic ``whoami`` echo lives in
:mod:`app.modules.session`, not here — it is not user management.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 (FastAPI resolves the path-param type at runtime)

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AdminPrincipal, require_admin
from app.modules.users.schemas import (
    DeactivationRequest,
    InvitationRequest,
    InvitationResult,
    LifecycleResult,
    PortalUser,
    RoleUpdateRequest,
)
from app.modules.users.service import (
    delete_user,
    get_user,
    invite_user,
    list_users,
    resend_invitation,
    set_deactivated,
    set_role,
)

router = APIRouter()


@router.post(
    "/invitations",
    response_model=InvitationResult,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    request: InvitationRequest,
    principal: Annotated[AdminPrincipal, Depends(require_admin)],
) -> InvitationResult:
    """Invite and provision a portal user (admin-only, deny-by-default).

    The router-level :func:`~app.core.security.require_admin` guard enforces the
    ``Admin`` role; this handler records the acting admin as the audit actor and
    delegates the invite -> upsert -> scope -> audit sequence to the service. Any
    provisioning failure propagates and surfaces as a JSON 500.

    Args:
        request: The validated invitation (email, role, and role-shaped scope).
        principal: The acting admin, recorded as the audit actor.

    Returns:
        The :class:`InvitationResult` describing the provisioned identity.
    """
    return invite_user(request, principal.oid)


def _load_user(oid: UUID) -> PortalUser:
    """Resolve the target user named in the path, or raise 404.

    Shared by every per-user lifecycle route so an unknown oid is rejected
    uniformly before any Graph/DB side effect. The ``UUID`` path type also
    rejects a malformed oid with 422 before this runs.

    Args:
        oid: The target user's Entra object id from the request path.

    Returns:
        The resolved :class:`PortalUser`.

    Raises:
        HTTPException: 404 when no user has that oid.
    """
    user = get_user(str(oid))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.get("/users", response_model=list[PortalUser])
def list_portal_users() -> list[PortalUser]:
    """Return every portal user for the admin lifecycle view (admin-only).

    Returns:
        All portal users, each with invite stamps, role mirror, deactivation
        stamp.
    """
    return list_users()


@router.post("/users/{oid}/resend", response_model=LifecycleResult)
def resend_portal_invitation(
    user: Annotated[PortalUser, Depends(_load_user)],
    principal: Annotated[AdminPrincipal, Depends(require_admin)],
) -> LifecycleResult:
    """Re-issue the user's B2B invitation email (admin-only).

    Args:
        user: The resolved target user.
        principal: The acting admin, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` with the fresh invitation status/link.
    """
    return resend_invitation(user, principal.oid)


@router.post("/users/{oid}/role", response_model=LifecycleResult)
def change_portal_user_role(
    request: RoleUpdateRequest,
    user: Annotated[PortalUser, Depends(_load_user)],
    principal: Annotated[AdminPrincipal, Depends(require_admin)],
) -> LifecycleResult:
    """Promote or demote a user (admin-only).

    Args:
        request: The desired role (``admin`` = promote, ``user`` = demote).
        user: The resolved target user.
        principal: The acting admin, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` for the promote/demote.
    """
    return set_role(user.entra_oid, request, principal.oid)


@router.post("/users/{oid}/deactivate", response_model=LifecycleResult)
def change_portal_user_activation(
    request: DeactivationRequest,
    user: Annotated[PortalUser, Depends(_load_user)],
    principal: Annotated[AdminPrincipal, Depends(require_admin)],
) -> LifecycleResult:
    """Deactivate (soft) or reactivate a user (admin-only).

    Args:
        request: Whether to deactivate (``true``) or reactivate (``false``).
        user: The resolved target user.
        principal: The acting admin, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` for the deactivate/reactivate.
    """
    return set_deactivated(user.entra_oid, request, principal.oid)


@router.post("/users/{oid}/delete", response_model=LifecycleResult)
def delete_portal_user(
    user: Annotated[PortalUser, Depends(_load_user)],
    principal: Annotated[AdminPrincipal, Depends(require_admin)],
) -> LifecycleResult:
    """Hard-delete a user, or revoke a pending invitation (admin-only).

    Deletes the Entra guest object and the application records. The audit action
    distinguishes a revoke (never redeemed) from a delete (redeemed). Modelled as
    ``POST`` so it fits the SPA's GET/POST CORS allow-list.

    Args:
        user: The resolved target user.
        principal: The acting admin, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` for the delete/revoke.
    """
    return delete_user(user, principal.oid)
