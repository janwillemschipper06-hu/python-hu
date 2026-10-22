"""Invite-and-provision orchestration for the users module.

One admin action provisions a portal identity atomically in intent: issue the
Entra B2B invitation (Microsoft Graph), record the ``Users`` row, grant the portal
role (the direct Entra app-role assignment), and append
an audit entry. Authentication/MFA and email delivery are Entra's job
(``docs/authentication-and-access.md`` §3); this module only coordinates
provisioning (router -> service -> repository / graph).

Ordering matters: the invitation comes first because every later step is keyed by
the guest ``oid`` it returns.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

from app.core import audit
from app.integrations import graph
from app.modules.users import repository
from app.modules.users.schemas import (
    DeactivationRequest,
    InvitationRequest,
    InvitationResult,
    LifecycleResult,
    PortalUser,
    RoleUpdateRequest,
)

logger = logging.getLogger(__name__)

_ACTION_INVITE = "InviteUser"
_ACTION_RESEND = "ResendInvitation"
_ACTION_REVOKE = "RevokePendingInvitation"
_ACTION_CHANGE_ROLE = "ChangeUserRole"
_ACTION_DEACTIVATE = "DeactivateUser"
_ACTION_REACTIVATE = "ReactivateUser"
_ACTION_DELETE = "DeleteUser"
_TARGET_TYPE_USER = "User"


def _redirect_url() -> str:
    """Return the portal URL an invite redemption lands on.

    Reuses the SPA origin unless overridden, so one value configures both CORS
    and invitations.
    """
    return os.environ.get("INVITE_REDIRECT_URL") or os.environ["STATIC_WEBAPP_URL"]


def _invitation_message(redirect_url: str) -> str:
    """Build the plain, secret-free notice shown in the Entra invitation email."""
    return (
        "You have been invited to the 9altitudes Customer Onboarding Portal. "
        "Accept this invitation, then sign in at "
        f"{redirect_url} to get started."
    )


def invite_user(request: InvitationRequest, actor_oid: str | None) -> InvitationResult:
    """Invite and provision a portal user from an admin request.

    Steps, in order: create the B2B invitation; upsert the ``Users`` row; assign
    the app role; append one audit entry.

    Args:
        request: The validated invitation (email and role).
        actor_oid: The inviting admin's Entra object id, recorded as the audit
            actor.

    Returns:
        The :class:`InvitationResult` describing the provisioned identity.
    """
    # The invite redirect reuses the SPA origin unless overridden, so one value
    # configures both CORS and invitations.
    redirect_url = _redirect_url()
    invitation = graph.create_b2b_invitation(
        request.email, redirect_url, _invitation_message(redirect_url)
    )
    oid = invitation.invited_user_id

    invited_utc = datetime.now(UTC).replace(tzinfo=None)
    repository.upsert_user(oid, request.email, invited_utc)

    graph.assign_app_role(oid, request.role.app_role)

    audit.append_audit_event(
        _ACTION_INVITE,
        actor_oid,
        _TARGET_TYPE_USER,
        oid,
        json.dumps({"role": request.role.value}),
    )

    return InvitationResult(
        email=request.email,
        role=request.role,
        entra_oid=oid,
        invitation_status=invitation.status,
        redeem_url=invitation.redeem_url,
    )


def list_users() -> list[PortalUser]:
    """Return every portal user, each with their current role read live from Entra."""
    users = repository.list_users()
    roles = graph.list_role_assignments()
    return [
        user.model_copy(update={"role": roles.get(user.entra_oid)}) for user in users
    ]


def get_user(oid: str) -> PortalUser | None:
    """Return a single portal user by Entra oid, or ``None`` when unknown."""
    return repository.get_user(oid)


def record_sign_in(oid: str | None) -> None:
    """Register a portal sign-in: add unknown users, redeem pending ones.

    A user assigned a role directly in Entra (e.g. the first admin) has no
    ``Users`` row, so one is created from their directory email, already
    redeemed. A known user whose invitation is still pending is stamped redeemed;
    an already-redeemed user costs a single read.

    Best effort: lifecycle bookkeeping must never block a sign-in, so failures
    are logged and swallowed. Only callers that passed the portal role guard
    should reach this (the portal tier enforces an assigned role).

    Args:
        oid: The signed-in caller's Entra object id, or ``None`` when absent.
    """
    if not oid:
        return
    try:
        user = repository.get_user(oid)
        if user is None:
            now = datetime.now(UTC).replace(tzinfo=None)
            repository.upsert_user(oid, graph.get_user_email(oid), None, now)
        elif user.redeemed_utc is None:
            repository.mark_user_redeemed(oid)
    except Exception:
        logger.exception("Could not record sign-in for user %s", oid)


def resend_invitation(user: PortalUser, actor_oid: str | None) -> LifecycleResult:
    """Re-issue a user's B2B invitation email via Graph and audit it.

    Graph returns the existing guest for a known email, so re-inviting never
    duplicates the identity (``docs/authentication-and-access.md`` §6).

    Args:
        user: The target user (already resolved by the router).
        actor_oid: The acting admin's Entra object id, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult`, carrying the fresh invitation status/link.
    """
    redirect_url = _redirect_url()
    invitation = graph.create_b2b_invitation(
        user.email, redirect_url, _invitation_message(redirect_url)
    )
    audit.append_audit_event(
        _ACTION_RESEND,
        actor_oid,
        _TARGET_TYPE_USER,
        user.entra_oid,
        json.dumps({"status": invitation.status}),
    )
    return LifecycleResult(
        entra_oid=user.entra_oid,
        action=_ACTION_RESEND,
        invitation_status=invitation.status,
        redeem_url=invitation.redeem_url,
    )


def set_role(
    oid: str, request: RoleUpdateRequest, actor_oid: str | None
) -> LifecycleResult:
    """Change a user's portal role in Entra; audited.

    The new app-role assignment is created first and the user's other portal
    assignments are then removed, so the user is never left without a role
    mid-change (``docs/adr/0012``). Nothing is stored locally: Entra is the only
    source of truth for roles.

    Args:
        oid: The target user's Entra object id.
        request: The desired role (``admin``, ``pm`` or ``user``).
        actor_oid: The acting admin's Entra object id, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` for the role change.
    """
    graph.assign_app_role(oid, request.role.app_role)
    graph.remove_app_roles(oid, keep=request.role.app_role)
    audit.append_audit_event(
        _ACTION_CHANGE_ROLE,
        actor_oid,
        _TARGET_TYPE_USER,
        oid,
        json.dumps({"role": request.role.value}),
    )
    return LifecycleResult(entra_oid=oid, action=_ACTION_CHANGE_ROLE)


def set_deactivated(
    oid: str, request: DeactivationRequest, actor_oid: str | None
) -> LifecycleResult:
    """Deactivate (soft) or reactivate a user; audited.

    Deactivation strips every portal app-role assignment,
    and stamps ``DeactivatedUtc`` — CAE then cuts access
    near-real-time while the Entra guest is retained for audit
    (``docs/authentication-and-access.md`` §6). Reactivation only clears the
    stamp; it does not restore prior scope.

    Args:
        oid: The target user's Entra object id.
        request: Whether to deactivate (``true``) or reactivate (``false``).
        actor_oid: The acting admin's Entra object id, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` for the deactivate/reactivate.
    """
    if request.deactivate:
        graph.remove_app_roles(oid)
        repository.set_user_deactivated(oid, datetime.now(UTC).replace(tzinfo=None))
        action = _ACTION_DEACTIVATE
    else:
        repository.set_user_deactivated(oid, None)
        action = _ACTION_REACTIVATE
    audit.append_audit_event(action, actor_oid, _TARGET_TYPE_USER, oid, None)
    return LifecycleResult(entra_oid=oid, action=action)


def delete_user(user: PortalUser, actor_oid: str | None) -> LifecycleResult:
    """Hard-delete a user: remove the Entra guest and the app records; audited.

    The audit action distinguishes a **revoke** of a never-redeemed invitation
    from a **delete** of a redeemed user (both remove the guest object — Entra
    has no separate "cancel invitation" API). The Graph deletion runs first so a
    failure leaves the app records intact for a retry; both operations are
    idempotent.

    Args:
        user: The target user (already resolved by the router).
        actor_oid: The acting admin's Entra object id, recorded as the audit actor.

    Returns:
        The :class:`LifecycleResult` for the delete/revoke.
    """
    action = _ACTION_DELETE if user.redeemed_utc else _ACTION_REVOKE
    graph.delete_guest_user(user.entra_oid)
    repository.delete_user(user.entra_oid)
    audit.append_audit_event(action, actor_oid, _TARGET_TYPE_USER, user.entra_oid, None)
    return LifecycleResult(entra_oid=user.entra_oid, action=action)
