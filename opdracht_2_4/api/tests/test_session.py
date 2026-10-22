"""Tests for the session whoami endpoint.

Like the customers tests, the platform authentication seam
(:func:`app.core.security.validated_token`) is overridden with a crafted
principal so the deny-by-default umbrella admits the request; the real
end-to-end authentication is verified by a human on the dev deployment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from app.core.security import ClientPrincipal, validated_token
from app.integrations import graph
from app.main import app
from app.modules.users import repository as users_repository
from app.modules.users.schemas import PortalUser

if TYPE_CHECKING:
    from collections.abc import Iterator


def _override(principal: ClientPrincipal) -> Iterator[None]:
    app.dependency_overrides[validated_token] = lambda: principal
    try:
        yield
    finally:
        app.dependency_overrides.pop(validated_token, None)


@pytest.fixture
def admin_auth() -> Iterator[None]:
    yield from _override(
        ClientPrincipal(
            oid="00000000-0000-0000-0000-000000000001",
            tid="11111111-1111-1111-1111-111111111111",
            audience="api://example",
            roles=("Admin",),
        )
    )


@pytest.fixture
def guest_auth() -> Iterator[None]:
    yield from _override(
        ClientPrincipal(oid="00000000-0000-0000-0000-000000000002", roles=("User",))
    )


@pytest.fixture
def roleless_auth() -> Iterator[None]:
    yield from _override(ClientPrincipal(oid="00000000-0000-0000-0000-000000000003"))


@pytest.fixture(autouse=True)
def recorded_sign_ins(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(users_repository, "get_user", lambda _oid: _user(None))
    monkeypatch.setattr(users_repository, "mark_user_redeemed", calls.append)
    return calls


def _user(redeemed_utc: datetime | None) -> PortalUser:
    return PortalUser.model_validate(
        {
            "EntraOid": "00000000-0000-0000-0000-000000000001",
            "Email": "a@example.com",
            "RedeemedUtc": redeemed_utc,
            "CreatedUtc": datetime(2026, 1, 1, tzinfo=UTC),
        }
    )


@pytest.mark.usefixtures("admin_auth")
def test_whoami_skips_write_for_redeemed_user(
    monkeypatch: pytest.MonkeyPatch, recorded_sign_ins: list[str]
) -> None:
    redeemed = _user(datetime(2026, 1, 2, tzinfo=UTC))
    monkeypatch.setattr(users_repository, "get_user", lambda _oid: redeemed)

    TestClient(app).get("/api/v1/portal/whoami")

    assert recorded_sign_ins == []


@pytest.mark.usefixtures("admin_auth")
def test_whoami_adds_unknown_user_as_redeemed(
    monkeypatch: pytest.MonkeyPatch, recorded_sign_ins: list[str]
) -> None:
    upserts: list[tuple[str, str, datetime | None, datetime | None]] = []
    monkeypatch.setattr(users_repository, "get_user", lambda _oid: None)
    monkeypatch.setattr(graph, "get_user_email", lambda _oid: "me@example.com")
    monkeypatch.setattr(
        users_repository, "upsert_user", lambda *args: upserts.append(args)
    )

    TestClient(app).get("/api/v1/portal/whoami")

    assert recorded_sign_ins == []
    [(oid, email, invited, redeemed)] = upserts
    assert oid == "00000000-0000-0000-0000-000000000001"
    assert email == "me@example.com"
    assert invited is None
    assert redeemed is not None


@pytest.mark.usefixtures("admin_auth")
def test_whoami_reports_admin_role(recorded_sign_ins: list[str]) -> None:
    response = TestClient(app).get("/api/v1/portal/whoami")

    assert response.status_code == 200
    assert recorded_sign_ins == ["00000000-0000-0000-0000-000000000001"]
    body = response.json()
    assert body["oid"] == "00000000-0000-0000-0000-000000000001"
    assert body["tid"] == "11111111-1111-1111-1111-111111111111"
    assert body["audience"] == "api://example"
    assert body["roles"] == ["Admin"]
    assert body["is_admin"] is True


@pytest.mark.usefixtures("guest_auth")
def test_whoami_reports_user_role() -> None:
    response = TestClient(app).get("/api/v1/portal/whoami")

    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["User"]
    assert body["is_admin"] is False


@pytest.mark.usefixtures("roleless_auth")
def test_portal_rejects_token_without_a_portal_role() -> None:
    response = TestClient(app).get("/api/v1/portal/whoami")

    assert response.status_code == 403


@pytest.mark.usefixtures("guest_auth")
def test_my_photo_returns_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph, "get_user_photo", lambda _oid: (b"img", "image/png"))

    response = TestClient(app).get("/api/v1/portal/me/photo")

    assert response.status_code == 200
    assert response.content == b"img"
    assert response.headers["content-type"] == "image/png"


@pytest.mark.usefixtures("guest_auth")
def test_my_photo_404_when_user_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph, "get_user_photo", lambda _oid: None)

    assert TestClient(app).get("/api/v1/portal/me/photo").status_code == 404


def test_whoami_requires_authentication() -> None:
    response = TestClient(app).get("/api/v1/portal/whoami")

    assert response.status_code == 401


def test_whoami_is_in_openapi_schema() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/v1/portal/whoami" in schema["paths"]
