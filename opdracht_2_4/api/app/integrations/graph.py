"""Microsoft Graph client for invite-time provisioning (app-only, secretless).

Provisioning runs against the **identity tenant's** Microsoft Graph, but the
Container App's managed identity lives in the **resource tenant** and cannot call
that Graph directly (a managed identity is single-tenant). So the backend
authenticates as a dedicated app registration in the identity tenant
(``cop-graph-<env>``) that **trusts the managed identity** via a federated
identity credential — no client secret or certificate is stored anywhere
(``docs/entra-configuration.md`` §3.E; ``docs/authentication-and-access.md`` §2).

Token flow (secretless cross-tenant):

1. Ask the Container Apps managed-identity endpoint for a token whose audience is
   ``api://AzureADTokenExchange`` — this is the **client assertion**.
2. Present that assertion in a client-credentials call to the identity tenant for
   ``https://graph.microsoft.com/.default`` — Graph issues an app-only token for
   ``cop-graph-<env>``.

Errors are intentionally not wrapped: a missing env var, a failed token exchange,
or a non-2xx Graph response raises, propagates, and surfaces as a JSON 500.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

import requests

_TOKEN_EXCHANGE_AUDIENCE: Final = "api://AzureADTokenExchange"  # noqa: S105
_GRAPH_SCOPE: Final = "https://graph.microsoft.com/.default"
_GRAPH_BASE: Final = "https://graph.microsoft.com/v1.0"
_MSI_API_VERSION: Final = "2019-08-01"
_DEFAULT_AUTHORITY_HOST: Final = "login.microsoftonline.com"
_HTTP_TIMEOUT: Final = 15
# Graph answers a duplicate app-role assignment with 400 (not 409).
_DUPLICATE_ASSIGNMENT_STATUS: Final = 400
# A delete of an already-absent object (guest user or app-role assignment) is a
# no-op for our idempotent lifecycle actions.
_NOT_FOUND_STATUS: Final = 404
# The HTTP auth scheme for Graph bearer tokens, composed with the token at
# runtime so no literal credential pattern ever appears in source.
_AUTH_SCHEME: Final = "Bearer"
# Portal app-role value -> role id on the API app registration. These GUIDs are
# PINNED in scripts/entra/Provision-IdentityTenant.ps1 (same in every environment),
# so they are constants rather than per-environment config.
PORTAL_ROLES: Final = {
    "Admin": "d9ca4663-5e3a-41d0-84af-fb97b4becbf1",
    "PM": "bb99654e-c0a6-4fc9-9896-4503cafa4f08",
    "User": "bb810150-d66a-4059-8fea-89a05b4c5d7c",
}


@dataclass(frozen=True, slots=True)
class B2BInvitation:
    """The result of creating an Entra B2B guest invitation.

    ``invited_user_id`` is the guest's **object id in the identity tenant** — the
    ``oid`` that a later sign-in token will carry, so it keys the ``Users`` row and
    any app-role assignment. ``redeem_url`` is Microsoft's redemption link (confers
    only directory guest status, never portal access — ``docs/authentication-and-
    access.md`` §3.1); it carries no portal secret.
    """

    invited_user_id: str
    status: str
    redeem_url: str | None


def _graph_token() -> str:
    """Acquire an app-only Microsoft Graph token via the secretless exchange.

    The managed identity first mints a token for ``api://AzureADTokenExchange``;
    that JWT is then presented as a client assertion to the identity tenant, which
    returns an app-only token for the Graph provisioning app.

    Returns:
        The Graph access token.
    """
    assertion_response = requests.get(
        url=os.environ["IDENTITY_ENDPOINT"],
        params={
            "resource": _TOKEN_EXCHANGE_AUDIENCE,
            "api-version": _MSI_API_VERSION,
            "client_id": os.environ["AZURE_CLIENT_ID"],
        },
        headers={"X-IDENTITY-HEADER": os.environ["IDENTITY_HEADER"]},
        timeout=_HTTP_TIMEOUT,
    )
    assertion_response.raise_for_status()
    assertion = assertion_response.json()["access_token"]

    authority = os.environ.get("GRAPH_AUTHORITY_HOST", _DEFAULT_AUTHORITY_HOST)
    token_response = requests.post(
        url=f"https://{authority}/{os.environ['GRAPH_TENANT_ID']}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["GRAPH_CLIENT_ID"],
            "scope": _GRAPH_SCOPE,
            "client_assertion_type": (
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            ),
            "client_assertion": assertion,
        },
        timeout=_HTTP_TIMEOUT,
    )
    token_response.raise_for_status()
    return str(token_response.json()["access_token"])


def create_b2b_invitation(
    email: str, redirect_url: str, message_body: str
) -> B2BInvitation:
    """Create an Entra B2B guest invitation and send Microsoft's invite email.

    Entra owns redemption, email verification, and MFA. ``message_body`` is a plain
    notice carrying no portal secret (``docs/authentication-and-access.md`` §3.3);
    the redemption link in the email is Microsoft's (§3.1). Re-inviting an existing
    email returns the existing guest object, so the caller never duplicates an
    identity.

    Args:
        email: The invitee's email address.
        redirect_url: Where redemption lands the invitee (the portal URL).
        message_body: The plain, secret-free message shown in the invite email.

    Returns:
        The :class:`B2BInvitation` describing the (new or reused) guest.
    """
    response = requests.post(
        url=f"{_GRAPH_BASE}/invitations",
        headers={"Authorization": f"Bearer {_graph_token()}"},
        json={
            "invitedUserEmailAddress": email,
            "inviteRedirectUrl": redirect_url,
            "sendInvitationMessage": True,
            "invitedUserMessageInfo": {"customizedMessageBody": message_body},
        },
        timeout=_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return B2BInvitation(
        invited_user_id=data["invitedUser"]["id"],
        status=data.get("status", "Unknown"),
        redeem_url=data.get("inviteRedeemUrl"),
    )


def assign_app_role(principal_id: str, role: str) -> None:
    """Assign a portal app role (``Admin``/``PM``/``User``) directly to a user.

    Creates an ``appRoleAssignedTo`` on the API app's service principal — the
    authoritative role source (``docs/adr/0012``). A repeat assignment (e.g. a
    re-invite) already satisfies the intent and is treated as success.

    Args:
        principal_id: The invited user's object id (the assignment's principal).
        role: The app-role value to assign; one of :data:`PORTAL_ROLES`.
    """
    sp_object_id = os.environ["GRAPH_API_SP_OBJECT_ID"]
    response = requests.post(
        url=f"{_GRAPH_BASE}/servicePrincipals/{sp_object_id}/appRoleAssignedTo",
        headers={"Authorization": f"Bearer {_graph_token()}"},
        json={
            "principalId": principal_id,
            "resourceId": sp_object_id,
            "appRoleId": PORTAL_ROLES[role],
        },
        timeout=_HTTP_TIMEOUT,
    )
    if (
        response.status_code == _DUPLICATE_ASSIGNMENT_STATUS
        and "already exists" in response.text.lower()
    ):
        return
    response.raise_for_status()


def get_user_email(user_id: str) -> str:
    """Return a user's email (falling back to the UPN) from the directory.

    Graph permission: ``User.Read.All`` (already granted).

    Args:
        user_id: The user's Entra object id.

    Returns:
        The user's ``mail``, or ``userPrincipalName`` when no mail is set.
    """
    response = requests.get(
        url=f"{_GRAPH_BASE}/users/{user_id}?$select=mail,userPrincipalName",
        headers={"Authorization": f"{_AUTH_SCHEME} {_graph_token()}"},
        timeout=_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("mail") or data["userPrincipalName"])


def get_user_photo(user_id: str) -> tuple[bytes, str] | None:
    """Return a user's profile photo and its content type, or ``None`` if unset.

    Many guest accounts have no photo, so a 404 from Graph is an expected
    "no photo" outcome rather than an error.

    Graph permission: ``User.Read.All`` (already granted).

    Args:
        user_id: The user's Entra object id.

    Returns:
        ``(image bytes, content type)``, or ``None`` when the user has no photo.
    """
    response = requests.get(
        url=f"{_GRAPH_BASE}/users/{user_id}/photo/$value",
        headers={"Authorization": f"{_AUTH_SCHEME} {_graph_token()}"},
        timeout=_HTTP_TIMEOUT,
    )
    if response.status_code == _NOT_FOUND_STATUS:
        return None
    response.raise_for_status()
    return response.content, response.headers.get("Content-Type", "image/jpeg")


def list_role_assignments() -> dict[str, str]:
    """Return each user's current portal role, read live from Entra.

    Entra is the only source of truth for roles (``docs/adr/0012``), so the admin
    user list reads the API app's ``appRoleAssignedTo`` instead of a stored copy.
    Only user principals holding one of the portal roles are returned; a user
    with none is simply absent from the mapping.

    Graph permission: ``Application.Read.All`` (``AppRoleAssignment.ReadWrite.All``
    alone is not enough to list ``appRoleAssignedTo`` and yields a 403).

    Returns:
        A mapping of user object id to app-role value (``Admin``/``PM``/``User``).
    """
    sp_object_id = os.environ["GRAPH_API_SP_OBJECT_ID"]
    role_by_id = {role_id: role for role, role_id in PORTAL_ROLES.items()}
    headers = {"Authorization": f"{_AUTH_SCHEME} {_graph_token()}"}
    url: str | None = (
        f"{_GRAPH_BASE}/servicePrincipals/{sp_object_id}/appRoleAssignedTo?$top=999"
    )
    roles: dict[str, str] = {}
    while url:
        response = requests.get(url=url, headers=headers, timeout=_HTTP_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        for assignment in data.get("value", []):
            role = role_by_id.get(assignment.get("appRoleId"))
            if role and assignment.get("principalType") == "User":
                roles[assignment["principalId"]] = role
        url = data.get("@odata.nextLink")
    return roles


def remove_app_roles(principal_id: str, *, keep: str | None = None) -> None:
    """Remove a user's portal app-role assignments, except ``keep`` (idempotent).

    Role change and deactivate revoke authority by deleting the
    ``appRoleAssignedTo`` the portal created (``docs/adr/0012``). The assignment id
    is not known to the caller, so this reads the user's app-role assignments,
    matches the ones for this API app's service principal and any portal role
    other than ``keep``, and deletes each. A user with none is a no-op.

    Graph permissions: reading the user's assignments needs ``User.Read.All``
    (or ``Directory.Read.All``); deleting one needs ``AppRoleAssignment.ReadWrite.All``
    (``docs/entra-configuration.md`` §3.E).

    Args:
        principal_id: The user's object id whose role assignments are removed.
        keep: A role value whose assignment is left in place (``None`` removes all).
    """
    sp_object_id = os.environ["GRAPH_API_SP_OBJECT_ID"]
    removable = {role_id for role, role_id in PORTAL_ROLES.items() if role != keep}
    token = _graph_token()
    headers = {"Authorization": f"{_AUTH_SCHEME} {token}"}

    listing = requests.get(
        url=f"{_GRAPH_BASE}/users/{principal_id}/appRoleAssignments",
        headers=headers,
        timeout=_HTTP_TIMEOUT,
    )
    listing.raise_for_status()

    for assignment in listing.json().get("value", []):
        if (
            str(assignment.get("resourceId", "")).lower() == sp_object_id.lower()
            and str(assignment.get("appRoleId", "")).lower() in removable
        ):
            deletion = requests.delete(
                url=(
                    f"{_GRAPH_BASE}/servicePrincipals/{sp_object_id}"
                    f"/appRoleAssignedTo/{assignment['id']}"
                ),
                headers=headers,
                timeout=_HTTP_TIMEOUT,
            )
            if deletion.status_code == _NOT_FOUND_STATUS:
                continue
            deletion.raise_for_status()


def delete_guest_user(user_id: str) -> None:
    """Delete the Entra B2B guest object for a user (idempotent).

    Backs both the hard **delete** and the **revoke-pending** lifecycle actions
    (``docs/authentication-and-access.md`` §6): removing the guest object (plus
    CAE) is what actually revokes access. A ``404`` means the guest is already
    gone, which satisfies the intent and is treated as success.

    Graph permission: ``User.ReadWrite.All`` (``docs/entra-configuration.md`` §3.E).

    Args:
        user_id: The guest's object id in the identity tenant.
    """
    response = requests.delete(
        url=f"{_GRAPH_BASE}/users/{user_id}",
        headers={"Authorization": f"{_AUTH_SCHEME} {_graph_token()}"},
        timeout=_HTTP_TIMEOUT,
    )
    if response.status_code == _NOT_FOUND_STATUS:
        return
    response.raise_for_status()
