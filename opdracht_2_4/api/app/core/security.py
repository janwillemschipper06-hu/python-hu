"""Authentication & authorization seam: the validated caller and the role guards.

Token *validation* is the platform's job — Azure Container Apps built-in
authentication (``docs/adr/0010``). By the time a request reaches the app, the
platform has validated the caller's Entra token and injected its claims as the
Base64-encoded JSON header ``X-MS-CLIENT-PRINCIPAL`` (client-supplied copies are
stripped, so the header is proof of a validated token). The app performs **no**
token cryptography.

This module holds two things:

* **The validated caller.** :class:`ClientPrincipal` is the typed, immutable view
  of the injected claims the app authorizes on; :func:`validated_token` is the
  FastAPI dependency (the shared deny-by-default authentication seam) that turns
  the header into a ``ClientPrincipal`` or raises 401.
* **The role checks.** The three router-level guards
  (``docs/authentication-and-access.md`` §4) — :func:`require_admin`,
  :func:`require_portal_user`, and :func:`require_extract_client` — each depend on
  ``validated_token`` (cached per request), check the caller's **role** claim, and
  return a typed role principal (admin and portal) carrying identity and role only. Customer scope is
  **not** resolved here: each portal endpoint passes the caller's ``oid`` and admin
  flag to its stored procedure, which enforces scope in the database on every
  read/write (``docs/adr/0002``).

| Router | Guard | Accepts | Principal |
|---|---|---|---|
| ``/api/v1/admin``   | :func:`require_admin`          | ``Admin`` role (all-scope)            | :class:`AdminPrincipal` |
| ``/api/v1/portal``  | :func:`require_portal_user`    | any authenticated caller (admin or customer) | :class:`PortalPrincipal` |
| ``/api/v1/extract`` | :func:`require_extract_client` | machine client with ``Extract.Read``  | none (no user context) |
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

# --------------------------------------------------------------- principal --

# Container Apps built-in auth can emit a few claims under WS-*/SOAP schema URIs
# instead of their short JWT names. Map the ones the app authorizes on back to
# the short names; every other claim type passes through unchanged.
_CLAIM_ALIASES = {
    "http://schemas.microsoft.com/identity/claims/objectidentifier": "oid",
    "http://schemas.microsoft.com/identity/claims/tenantid": "tid",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": "roles",
}

_ROLES = "roles"
_PRINCIPAL_HEADER = "X-MS-CLIENT-PRINCIPAL"
_DETAIL_MISSING = "Missing client principal"
_DETAIL_MALFORMED = "Malformed client principal"


class MalformedPrincipalError(ValueError):
    """The ``X-MS-CLIENT-PRINCIPAL`` header could not be decoded."""


@dataclass(frozen=True, slots=True)
class ClientPrincipal:
    """The identifying claims of a platform-validated caller.

    Immutable by design: a principal is derived once per request from the
    injected header and never mutated. ``roles`` is always a (possibly empty)
    tuple so authorization guards can test membership uniformly.
    """

    oid: str | None = None
    tid: str | None = None
    azp: str | None = None
    appid: str | None = None
    audience: str | list[str] | None = None
    roles: tuple[str, ...] = ()

    @classmethod
    def parse(cls, header_value: str) -> ClientPrincipal:
        """Decode a Base64 ``X-MS-CLIENT-PRINCIPAL`` header into a principal.

        Args:
            header_value: The raw header the platform injected.

        Returns:
            The typed caller principal.

        Raises:
            MalformedPrincipalError: When the header is not Base64-encoded JSON
                describing a principal object.
        """
        return _to_principal(_decode(header_value))


def _decode(header_value: str) -> dict[str, object]:
    """Base64-decode and JSON-parse the header into a principal object."""
    try:
        # The platform may omit '=' padding; restore it before decoding.
        padded = header_value + "=" * (-len(header_value) % 4)
        decoded = json.loads(base64.b64decode(padded))
    except (binascii.Error, ValueError) as exc:
        raise MalformedPrincipalError from exc
    if not isinstance(decoded, dict):
        raise MalformedPrincipalError
    return decoded


def _single(values: list[str] | None) -> str | None:
    """Return the first value, or ``None`` when the claim is absent."""
    return values[0] if values else None


def _one_or_many(values: list[str] | None) -> str | list[str] | None:
    """Collapse a repeated claim to a scalar, list, or ``None``."""
    if not values:
        return None
    return values[0] if len(values) == 1 else values


def _to_principal(principal: dict[str, object]) -> ClientPrincipal:
    """Project a decoded principal's ``claims`` array onto :class:`ClientPrincipal`."""
    role_type = principal.get("role_typ")
    raw_claims = principal.get("claims")
    values: dict[str, list[str]] = {}
    roles: list[str] = []
    for entry in raw_claims if isinstance(raw_claims, list) else []:
        if not isinstance(entry, dict):
            continue
        typ = entry.get("typ")
        val = entry.get("val")
        if not isinstance(typ, str) or not isinstance(val, str):
            continue
        name = _CLAIM_ALIASES.get(typ, typ)
        if name == _ROLES or typ == role_type:
            if val not in roles:
                roles.append(val)
        else:
            values.setdefault(name, []).append(val)
    return ClientPrincipal(
        oid=_single(values.get("oid")),
        tid=_single(values.get("tid")),
        azp=_single(values.get("azp")),
        appid=_single(values.get("appid")),
        audience=_one_or_many(values.get("aud")),
        roles=tuple(roles),
    )


def _unauthorized(detail: str) -> HTTPException:
    """Build a 401 with a ``WWW-Authenticate: Bearer`` challenge."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def validated_token(
    principal: Annotated[str | None, Header(alias=_PRINCIPAL_HEADER)] = None,
) -> ClientPrincipal:
    """Return the platform-validated caller principal, or raise 401.

    Args:
        principal: The ``X-MS-CLIENT-PRINCIPAL`` header the platform injects for
            an authenticated caller, or ``None`` when absent.

    Returns:
        The typed caller :class:`ClientPrincipal`.

    Raises:
        HTTPException: 401 when the header is absent or cannot be decoded.
    """
    if not principal:
        raise _unauthorized(_DETAIL_MISSING)
    try:
        return ClientPrincipal.parse(principal)
    except MalformedPrincipalError as exc:
        raise _unauthorized(_DETAIL_MALFORMED) from exc


# -------------------------------------------------------------- role guards --

# App-role values from the API app registration (Stage 1). Membership in the
# live token claim — never a database flag — is the source of truth for role
# (``docs/authentication-and-access.md`` §2.2).
_ADMIN_ROLE = "Admin"
_PM_ROLE = "PM"
_USER_ROLE = "User"
_EXTRACT_ROLE = "Extract.Read"
# Interactive portal roles; any of them admits a caller to the portal tier.
_PORTAL_ROLES = frozenset({_ADMIN_ROLE, _PM_ROLE, _USER_ROLE})
# Internal staff: see every non-Draft Project and may author Projects.
_STAFF_ROLES = frozenset({_ADMIN_ROLE, _PM_ROLE})


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    """An authenticated admin acting on the **admin** router (all-scope)."""

    oid: str | None


@dataclass(frozen=True, slots=True)
class PortalPrincipal:
    """A caller on the **portal** router.

    Carries only identity and role — ``oid``, whether the caller holds the
    ``Admin`` app role, and whether they are internal staff (Admin or PM). It deliberately holds **no** customer scope: scope is
    resolved per request **inside the stored procedures** from these two values
    (``docs/adr/0002``, ``docs/adr/0013``), so the auth layer never loads domain data.
    """

    oid: str | None
    is_admin: bool
    is_staff: bool = False


def _forbidden() -> HTTPException:
    """Build a 403 for an authenticated caller lacking the required role/scope."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def require_admin(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> AdminPrincipal:
    """Admit only callers carrying the ``Admin`` app-role claim.

    Args:
        principal: The platform-validated caller.

    Returns:
        The :class:`AdminPrincipal` for the admin router's endpoints.

    Raises:
        HTTPException: 403 when the caller is not an admin.
    """
    if _ADMIN_ROLE not in principal.roles:
        raise _forbidden()
    return AdminPrincipal(oid=principal.oid)


def require_portal_user(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> PortalPrincipal:
    """Admit callers holding one of the interactive portal roles (Admin/PM/User).

    The guard resolves **identity and role only** — it does not touch the
    database. Entra already refuses tokens for users with no assigned role
    (assignment required, ``docs/adr/0012``); this check is the API's own
    defense in depth against a token that carries none of the portal roles
    (e.g. a machine token). Customer scope, where still used, is applied per
    request inside each endpoint's stored procedure (``docs/adr/0002``).

    Args:
        principal: The platform-validated caller.

    Returns:
        A :class:`PortalPrincipal` carrying the caller's ``oid`` and admin flag.

    Raises:
        HTTPException: 403 when the caller holds none of the portal roles.
    """
    if not _PORTAL_ROLES.intersection(principal.roles):
        raise _forbidden()
    return PortalPrincipal(
        oid=principal.oid,
        is_admin=_ADMIN_ROLE in principal.roles,
        is_staff=bool(_STAFF_ROLES.intersection(principal.roles)),
    )


def require_staff(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> PortalPrincipal:
    """Admit only internal staff: callers holding the ``Admin`` or ``PM`` role.

    Args:
        principal: The platform-validated caller.

    Returns:
        A :class:`PortalPrincipal` for the caller.

    Raises:
        HTTPException: 403 when the caller is neither Admin nor PM.
    """
    if not _STAFF_ROLES.intersection(principal.roles):
        raise _forbidden()
    return PortalPrincipal(
        oid=principal.oid, is_admin=_ADMIN_ROLE in principal.roles, is_staff=True
    )


def require_portal_admin(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> PortalPrincipal:
    """Admit only ``Admin`` callers on the portal tier (e.g. Project deletion).

    Args:
        principal: The platform-validated caller.

    Returns:
        A :class:`PortalPrincipal` for the admin caller.

    Raises:
        HTTPException: 403 when the caller is not an admin.
    """
    if _ADMIN_ROLE not in principal.roles:
        raise _forbidden()
    return PortalPrincipal(oid=principal.oid, is_admin=True, is_staff=True)


def require_extract_client(
    principal: Annotated[ClientPrincipal, Depends(validated_token)],
) -> None:
    """Admit only the machine reporting client (``Extract.Read``, app identity).

    Requires the ``Extract.Read`` role and an application identity (``appid`` on
    v1 tokens, ``azp`` on v2) — a user token carries neither, so it can never
    reach the extract router. The extract feed has no user context, so nothing is
    returned.

    Args:
        principal: The platform-validated caller.

    Raises:
        HTTPException: 403 when the caller lacks the role or an app identity.
    """
    app_id = principal.appid or principal.azp
    if _EXTRACT_ROLE not in principal.roles or app_id is None:
        raise _forbidden()
