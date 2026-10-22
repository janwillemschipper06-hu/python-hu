"""Stored-procedure data access for user provisioning.

Every write goes through an EXECUTE-only stored procedure via
:func:`app.core.db.call_procedure`; the app principal has no direct table DML
(``docs/adr/0008``, ``docs/security-design.md`` §12). The procedures own
idempotency and user resolution — this module only binds parameters. The shared
audit trail lives in :mod:`app.core.audit` because it is not identity-specific.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.db import call_procedure, execute_procedure_pydantic
from app.modules.users.schemas import PortalUser

if TYPE_CHECKING:
    from datetime import datetime


def upsert_user(
    oid: str,
    email: str,
    invited_utc: datetime | None,
    redeemed_utc: datetime | None = None,
) -> None:
    """Insert or update the ``Users`` row for an identity, keyed by ``oid``.

    Re-inviting is safe: ``onboarding.UpsertUser`` overwrites the email and
    advances ``InvitedUtc`` without clearing a prior ``RedeemedUtc``.

    Args:
        oid: The guest's Entra object id (``@EntraOid``).
        email: The user's email (``@Email``).
        invited_utc: The invitation timestamp as a naive UTC datetime
            (``@InvitedUtc``; pyodbc binds ``DATETIME2`` from a naive value), or
            ``None`` for a user who was assigned in Entra without an invite.
        redeemed_utc: The first sign-in timestamp (``@RedeemedUtc``), if known.

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    call_procedure("onboarding.UpsertUser", (oid, email, invited_utc, redeemed_utc))


def set_user_deactivated(oid: str, deactivated_utc: datetime | None) -> None:
    """Set or clear a user's soft-deactivation stamp.

    Args:
        oid: The user's Entra object id (``@EntraOid``).
        deactivated_utc: A naive UTC datetime to deactivate, or ``None`` to
            reactivate (``@DeactivatedUtc``).

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    call_procedure("onboarding.SetUserDeactivated", (oid, deactivated_utc))


def mark_user_redeemed(oid: str) -> None:
    """Stamp a user's first sign-in (``RedeemedUtc``); a no-op once already set.

    Args:
        oid: The user's Entra object id (``@EntraOid``); unknown oids are ignored.

    Raises:
        pyodbc.Error: On any database error.
    """
    call_procedure("onboarding.MarkUserRedeemed", (oid,))


def delete_user(oid: str) -> None:
    """Hard-delete a user's application records (links then the ``Users`` row).

    Removes only the application-side mirror; the Entra guest object is deleted
    separately via Graph. Idempotent — a no-op for an unknown oid.

    Args:
        oid: The user's Entra object id (``@EntraOid``).

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    call_procedure("onboarding.DeleteUser", (oid,))


def list_users() -> list[PortalUser]:
    """Return every portal user for the admin lifecycle view.

    Each row carries the invite lifecycle stamps, the role mirror, the
    soft-deactivation stamp.

    Returns:
        The portal users, ordered by email.

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    return execute_procedure_pydantic("onboarding.ListUsers", PortalUser)


def get_user(oid: str) -> PortalUser | None:
    """Return a single portal user by Entra oid, or ``None`` when unknown.

    Args:
        oid: The user's Entra object id, bound to ``GetUserByOid``'s ``@EntraOid``.

    Returns:
        The :class:`PortalUser` or ``None`` when no row matches.

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    rows = execute_procedure_pydantic("onboarding.GetUserByOid", PortalUser, (oid,))
    return rows[0] if rows else None
