"""Tests for the admin invitation (invite + provision) endpoint.

No external systems are touched: the Microsoft Graph client and the
stored-procedure repository are monkeypatched so the router and the service's
orchestration (invite -> upsert -> role -> audit) are exercised without a live
Graph app or an ODBC driver. The platform authentication seam
(:func:`app.core.security.validated_token`) is overridden with an admin principal
so the router's ``require_admin`` guard admits the request; real end-to-end auth
is verified by the human on the dev deployment, not asserted here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from app.core import audit
from app.core.security import ClientPrincipal, validated_token
from app.integrations import graph
from app.integrations.graph import B2BInvitation
from app.main import app
from app.modules.users import repository as users_repository

if TYPE_CHECKING:
    from collections.abc import Iterator

_GUEST_OID = "99999999-9999-9999-9999-999999999999"
_ADMIN_OID = "00000000-0000-0000-0000-000000000001"


def _admin_principal() -> ClientPrincipal:
    return ClientPrincipal(oid=_ADMIN_OID, roles=("Admin",))


@pytest.fixture
def admin_auth() -> Iterator[None]:
    app.dependency_overrides[validated_token] = _admin_principal
    try:
        yield
    finally:
        app.dependency_overrides.pop(validated_token, None)


@pytest.fixture
def fake_provisioning(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, list[tuple[object, ...]]]:
    """Replace Graph + repository seams with recorders and return the call log."""
    calls: dict[str, list[tuple[object, ...]]] = {
        "invite": [],
        "assign": [],
        "upsert": [],
        "audit": [],
    }

    def _create_invitation(
        email: str, redirect_url: str, message_body: str
    ) -> B2BInvitation:
        calls["invite"].append((email, redirect_url, message_body))
        return B2BInvitation(
            invited_user_id=_GUEST_OID,
            status="PendingAcceptance",
            redeem_url="https://invitations.example/redeem",
        )

    def _assign(principal_id: str, role: str) -> None:
        calls["assign"].append((principal_id, role))

    def _upsert(oid: str, email: str, _invited_utc: object) -> None:
        calls["upsert"].append((oid, email))

    def _audit(
        action: str,
        actor_oid: str | None,
        target_type: str,
        target_id: str,
        detail: str | None,
    ) -> None:
        calls["audit"].append((action, actor_oid, target_type, target_id, detail))

    monkeypatch.setenv("INVITE_REDIRECT_URL", "https://portal.example")
    monkeypatch.setattr(graph, "create_b2b_invitation", _create_invitation)
    monkeypatch.setattr(graph, "assign_app_role", _assign)
    monkeypatch.setattr(users_repository, "upsert_user", _upsert)
    monkeypatch.setattr(audit, "append_audit_event", _audit)
    return calls


@pytest.mark.usefixtures("admin_auth")
def test_invite_user_provisions_user_role(
    fake_provisioning: dict[str, list[tuple[object, ...]]],
) -> None:
    response = TestClient(app).post(
        "/api/v1/admin/invitations",
        json={"email": "guest@contoso.com", "role": "user"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entra_oid"] == _GUEST_OID
    assert body["role"] == "user"
    assert body["invitation_status"] == "PendingAcceptance"

    assert fake_provisioning["upsert"] == [(_GUEST_OID, "guest@contoso.com")]
    assert fake_provisioning["assign"] == [(_GUEST_OID, "User")]
    # One audit row, attributed to the acting admin, value-free detail.
    assert len(fake_provisioning["audit"]) == 1
    action, actor_oid, target_type, target_id, _detail = fake_provisioning["audit"][0]
    assert (action, actor_oid, target_type, target_id) == (
        "InviteUser",
        _ADMIN_OID,
        "User",
        _GUEST_OID,
    )


@pytest.mark.usefixtures("admin_auth")
def test_invite_admin_assigns_app_role(
    fake_provisioning: dict[str, list[tuple[object, ...]]],
) -> None:
    response = TestClient(app).post(
        "/api/v1/admin/invitations",
        json={"email": "newadmin@contoso.com", "role": "admin"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "admin"

    assert fake_provisioning["assign"] == [(_GUEST_OID, "Admin")]
    assert fake_provisioning["upsert"] == [(_GUEST_OID, "newadmin@contoso.com")]


@pytest.mark.usefixtures("admin_auth")
def test_invite_pm_assigns_pm_app_role(
    fake_provisioning: dict[str, list[tuple[object, ...]]],
) -> None:
    response = TestClient(app).post(
        "/api/v1/admin/invitations",
        json={"email": "pm@contoso.com", "role": "pm"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "pm"
    assert fake_provisioning["assign"] == [(_GUEST_OID, "PM")]
    assert fake_provisioning["upsert"] == [(_GUEST_OID, "pm@contoso.com")]


@pytest.mark.usefixtures("admin_auth")
def test_invite_ignores_customer_ids(
    fake_provisioning: dict[str, list[tuple[object, ...]]],
) -> None:
    response = TestClient(app).post(
        "/api/v1/admin/invitations",
        json={"email": "guest@contoso.com", "role": "user", "customer_ids": [1]},
    )

    assert response.status_code == 201
    assert "customer_ids" not in response.json()
    assert fake_provisioning["assign"] == [(_GUEST_OID, "User")]


@pytest.mark.usefixtures("admin_auth")
def test_invite_bad_email_is_rejected(
    fake_provisioning: dict[str, list[tuple[object, ...]]],
) -> None:
    response = TestClient(app).post(
        "/api/v1/admin/invitations",
        json={"email": "not-an-email", "role": "admin"},
    )

    assert response.status_code == 422
    assert fake_provisioning["invite"] == []


@pytest.mark.usefixtures("admin_auth")
def test_graph_failure_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object) -> B2BInvitation:
        raise RuntimeError("graph down")

    monkeypatch.setenv("INVITE_REDIRECT_URL", "https://portal.example")
    monkeypatch.setattr(graph, "create_b2b_invitation", _boom)

    error_client = TestClient(app, raise_server_exceptions=False)
    response = error_client.post(
        "/api/v1/admin/invitations",
        json={"email": "a@contoso.com", "role": "admin"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_invitations_is_in_openapi_schema() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/v1/admin/invitations" in schema["paths"]
