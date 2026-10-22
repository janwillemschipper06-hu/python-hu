"""API schemas for the users module — invite and lifecycle requests/results."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 (pydantic needs it at runtime)
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Basic shape check only — Entra Graph is the authority on deliverability; this
# just rejects obvious typos before a cross-tenant round trip.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Role(StrEnum):
    """The portal role an invitation grants.

    Each maps to exactly one direct Entra app-role assignment on the API app
    (``docs/adr/0012``): ``admin`` -> ``Admin``, ``pm`` -> ``PM``, ``user`` ->
    ``User``. Entra is the only place the role is stored (no database copy).
    """

    admin = "admin"
    pm = "pm"
    user = "user"

    @property
    def app_role(self) -> str:
        """Return the Entra app-role value this role is assigned as."""
        return {"admin": "Admin", "pm": "PM", "user": "User"}[self.value]


class InvitationRequest(BaseModel):
    """An admin's request to invite and provision a portal user.

    Project assignment is not part of the invite; it happens when a Project is
    approved (``docs/projects-design.md``).
    """

    email: str = Field(min_length=3, max_length=256, pattern=_EMAIL_PATTERN)
    role: Role


class InvitationResult(BaseModel):
    """The outcome of a completed invite-and-provision operation.

    ``entra_oid`` is the invited guest's identity-tenant object id (the ``oid`` a
    later sign-in carries). ``redeem_url`` is Microsoft's redemption link, which
    confers only directory guest status and no portal access
    (``docs/authentication-and-access.md`` §3.1), so it is safe to return to the
    inviting admin.
    """

    email: str
    role: Role
    entra_oid: str
    invitation_status: str
    redeem_url: str | None


class PortalUser(BaseModel):
    """One portal user as the admin lifecycle view sees it.

    A projection of ``onboarding.Users`` (``ListUsers`` / ``GetUserByOid``):
    identity, invite lifecycle stamps, the     soft-``deactivated_utc`` stamp. ``role`` is not a database column: the service
    fills it live from Entra (``docs/adr/0012``).
    The ``validation_alias``es match the procedures' result columns so rows
    validate straight from the procedure output.
    """

    model_config = ConfigDict(populate_by_name=True)

    entra_oid: str = Field(validation_alias="EntraOid")
    email: str = Field(validation_alias="Email")
    role: str | None = None
    invited_utc: datetime | None = Field(default=None, validation_alias="InvitedUtc")
    redeemed_utc: datetime | None = Field(default=None, validation_alias="RedeemedUtc")
    deactivated_utc: datetime | None = Field(
        default=None, validation_alias="DeactivatedUtc"
    )
    created_utc: datetime = Field(validation_alias="CreatedUtc")

    @field_validator("entra_oid")
    @classmethod
    def _lowercase_oid(cls, value: str) -> str:
        """Normalise to Entra's lowercase GUID form.

        SQL Server renders GUIDs uppercase while Graph and tokens use lowercase,
        so every oid comparison (role lookup, "is this me") needs one form.
        """
        return value.lower()


class RoleUpdateRequest(BaseModel):
    """An admin's request to change a user's portal role (``admin``/``pm``/``user``).

    The service replaces the user's app-role assignment with the requested one via
    Graph (``docs/adr/0012``).
    """

    role: Role


class DeactivationRequest(BaseModel):
    """An admin's request to deactivate (soft) or reactivate a user.

    Deactivation removes the app-role assignment and stamps ``DeactivatedUtc``, retaining the Entra guest object for audit
    (``docs/authentication-and-access.md`` §6). ``deactivate=false`` only clears
    the stamp; it does not restore prior scope.
    """

    deactivate: bool


class LifecycleResult(BaseModel):
    """The outcome of a user-lifecycle action, echoed back to the admin UI.

    ``action`` is the audited action name recorded for the operation. The invite
    fields are populated only by **resend**; they are ``None`` for the other
    actions.
    """

    entra_oid: str
    action: str
    invitation_status: str | None = None
    redeem_url: str | None = None
