"""Tests for the Project header endpoints (``/api/v1/portal/projects``).

The database and Microsoft Graph are not touched: the repositories and the Graph
client are monkeypatched, so routing, role guards, validation, the PATCH merge and
the outcome -> HTTP mapping are exercised. The visibility/lock rules themselves live
in the stored procedures and are covered by
``database/Scripts/tests/project-visibility-tests.sql``. The platform auth seam
(:func:`app.core.security.validated_token`) is overridden with the role under test.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from app.core.security import ClientPrincipal, validated_token
from app.integrations import graph
from app.main import app
from app.modules.lookups import repository as lookups_repository
from app.modules.lookups.schemas import LookupKind, LookupOption
from app.modules.projects import repository
from app.modules.projects.schemas import MutationResult, Project
from app.modules.users import repository as users_repository

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_BASE = "/api/v1/portal/projects"
_ME = "00000000-0000-0000-0000-000000000001"
_OTHER_PM = "00000000-0000-0000-0000-000000000002"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _as_role(role: str) -> Callable[[], Iterator[None]]:
    def _fixture() -> Iterator[None]:
        app.dependency_overrides[validated_token] = lambda: ClientPrincipal(
            oid=_ME, roles=(role,)
        )
        try:
            yield
        finally:
            app.dependency_overrides.pop(validated_token, None)

    return _fixture


admin_auth = pytest.fixture(_as_role("Admin"))
pm_auth = pytest.fixture(_as_role("PM"))
user_auth = pytest.fixture(_as_role("User"))


def _project(**overrides: Any) -> Project:
    values: dict[str, Any] = {
        "id": 5,
        "customer_id": 7,
        "customer_name": "Contoso",
        "type": "Installation",
        "name": "Go-live",
        "state": "Draft",
        "requester_oid": _ME,
        "requester_email": "pm@9a.test",
        "created_by_email": "pm@9a.test",
        "created_utc": _NOW,
        "updated_utc": _NOW,
    }
    values.update(overrides)
    return Project(**values)


class Calls:
    """Records repository calls and serves canned results."""

    def __init__(self) -> None:
        self.created: list[tuple[Any, ...]] = []
        self.updated: list[dict[str, Any]] = []
        self.deleted: list[tuple[str, bool, bool, int]] = []
        self.current: Project | None = _project()
        self.outcome = "Ok"
        self.listed: dict[str, Any] = {}
        self.upserts: list[str] = []


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    log = Calls()

    def _create(*args: Any) -> MutationResult:
        log.created.append(args)
        return MutationResult(outcome=log.outcome, project_id=5)

    def _update(actor: str, **kwargs: Any) -> MutationResult:
        log.updated.append({"actor": actor, **kwargs})
        return MutationResult(outcome=log.outcome, project_id=5)

    def _delete(
        actor: str, *, is_staff: bool, is_admin: bool, project_id: int
    ) -> MutationResult:
        log.deleted.append((actor, is_staff, is_admin, project_id))
        return MutationResult(outcome=log.outcome, project_id=project_id)

    def _list(actor: str, **kwargs: Any) -> list[Project]:
        log.listed = {"actor": actor, **kwargs}
        return [_project()]

    monkeypatch.setattr(repository, "create_project", _create)
    monkeypatch.setattr(repository, "update_project", _update)
    monkeypatch.setattr(repository, "delete_project", _delete)
    monkeypatch.setattr(repository, "list_projects", _list)
    monkeypatch.setattr(repository, "get_project", lambda *_a, **_k: log.current)
    monkeypatch.setattr(
        lookups_repository,
        "list_lookup_options",
        lambda _kind: [
            LookupOption(
                id=3,
                kind=LookupKind.department,
                name="Consulting",
                allows_free_text=False,
                sort_order=0,
                is_active=True,
            )
        ],
    )
    monkeypatch.setattr(users_repository, "get_user", lambda _oid: object())
    monkeypatch.setattr(
        users_repository, "upsert_user", lambda oid, *_a: log.upserts.append(oid)
    )
    monkeypatch.setattr(graph, "get_user_email", lambda _oid: "me@9a.test")
    monkeypatch.setattr(
        graph, "list_role_assignments", lambda: {_OTHER_PM: "PM", _ME: "Admin"}
    )
    return log


_CREATE_BODY = {"customer_id": 7, "type": "Installation", "name": "  Go-live  "}


# --- role gating -----------------------------------------------------------


@pytest.mark.usefixtures("user_auth")
def test_customer_user_cannot_write(calls: Calls) -> None:
    client = TestClient(app)

    assert client.post(_BASE, json=_CREATE_BODY).status_code == 403
    assert client.patch(f"{_BASE}/5", json={"name": "x"}).status_code == 403
    assert client.delete(f"{_BASE}/5").status_code == 403
    assert client.get(f"{_BASE}/requesters").status_code == 403
    assert not calls.created
    assert not calls.updated
    assert not calls.deleted


@pytest.mark.usefixtures("user_auth")
def test_customer_user_reads_with_staff_flag_off(calls: Calls) -> None:
    response = TestClient(app).get(_BASE)

    assert response.status_code == 200
    assert calls.listed["is_staff"] is False
    assert calls.listed["actor"] == _ME


@pytest.mark.parametrize(
    ("fixture", "expected"), [("pm_auth", True), ("admin_auth", True)]
)
def test_staff_reads_with_staff_flag_on(
    request: pytest.FixtureRequest, calls: Calls, fixture: str, *, expected: bool
) -> None:
    request.getfixturevalue(fixture)

    assert TestClient(app).get(_BASE, params={"state": "Draft"}).status_code == 200
    assert calls.listed["is_staff"] is expected
    assert calls.listed["state"] == "Draft"


def test_projects_require_authentication() -> None:
    assert TestClient(app).get(_BASE).status_code == 401


@pytest.mark.usefixtures("pm_auth")
def test_list_rejects_unknown_state(calls: Calls) -> None:
    assert TestClient(app).get(_BASE, params={"state": "Nope"}).status_code == 422
    assert calls.listed == {}


# --- create ----------------------------------------------------------------


@pytest.mark.usefixtures("pm_auth")
def test_create_returns_201_and_defaults_requester(calls: Calls) -> None:
    response = TestClient(app).post(_BASE, json=_CREATE_BODY)

    assert response.status_code == 201
    assert response.json()["id"] == 5
    actor, requester, customer_id, ptype, name, *_ = calls.created[0]
    assert (actor, requester, customer_id, ptype, name) == (
        _ME,
        None,
        7,
        "Installation",
        "Go-live",
    )


@pytest.mark.usefixtures("pm_auth")
def test_create_makes_sure_the_caller_has_a_user_row(
    monkeypatch: pytest.MonkeyPatch, calls: Calls
) -> None:
    monkeypatch.setattr(users_repository, "get_user", lambda _oid: None)

    assert TestClient(app).post(_BASE, json=_CREATE_BODY).status_code == 201
    assert calls.upserts == [_ME]


@pytest.mark.usefixtures("pm_auth")
def test_create_with_another_pm_as_requester(calls: Calls) -> None:
    body = {**_CREATE_BODY, "requester_oid": _OTHER_PM}

    assert TestClient(app).post(_BASE, json=body).status_code == 201
    assert calls.created[0][1] == _OTHER_PM


@pytest.mark.usefixtures("pm_auth")
def test_create_rejects_requester_without_pm_role(
    monkeypatch: pytest.MonkeyPatch, calls: Calls
) -> None:
    monkeypatch.setattr(graph, "list_role_assignments", lambda: {_OTHER_PM: "User"})
    body = {**_CREATE_BODY, "requester_oid": _OTHER_PM}

    assert TestClient(app).post(_BASE, json=body).status_code == 422
    assert calls.created == []


@pytest.mark.usefixtures("pm_auth")
def test_create_rejects_unknown_department(calls: Calls) -> None:
    body = {**_CREATE_BODY, "department_id": 999}

    assert TestClient(app).post(_BASE, json=body).status_code == 422
    assert calls.created == []


@pytest.mark.usefixtures("pm_auth")
@pytest.mark.parametrize(
    "bad",
    [
        {"name": "   "},
        {"type": "Other"},
        {"hours": -1},
        {"customer_type": "Both"},
        {"customer_id": 0},
    ],
)
def test_create_validates_body(calls: Calls, bad: dict[str, object]) -> None:
    response = TestClient(app).post(_BASE, json={**_CREATE_BODY, **bad})

    assert response.status_code == 422
    assert calls.created == []


@pytest.mark.usefixtures("pm_auth")
@pytest.mark.parametrize(
    ("outcome", "status_code"), [("UnknownCustomer", 422), ("UnknownRequester", 422)]
)
def test_create_maps_procedure_outcomes(
    calls: Calls, outcome: str, status_code: int
) -> None:
    calls.outcome = outcome

    assert TestClient(app).post(_BASE, json=_CREATE_BODY).status_code == status_code


# --- get / hidden ------------------------------------------------------------


@pytest.mark.usefixtures("pm_auth")
def test_hidden_project_is_404(calls: Calls) -> None:
    calls.current = None
    client = TestClient(app)

    assert client.get(f"{_BASE}/5").status_code == 404
    assert client.patch(f"{_BASE}/5", json={"name": "x"}).status_code == 404


# --- update ------------------------------------------------------------------


@pytest.mark.usefixtures("pm_auth")
def test_patch_merges_and_audits_changed_fields(calls: Calls) -> None:
    calls.current = _project(hours=10, request_notes="keep", deadline=date(2026, 6, 1))

    response = TestClient(app).patch(
        f"{_BASE}/5", json={"name": "Renamed", "hours": None}
    )

    assert response.status_code == 200
    sent = calls.updated[0]
    assert sent["name"] == "Renamed"
    assert sent["hours"] is None
    assert sent["request_notes"] == "keep"
    assert sent["deadline"] == date(2026, 6, 1)
    assert sent["customer_id"] == 7
    assert sent["is_admin"] is False
    assert json.loads(sent["audit_detail"]) == {"fields": ["hours", "name"]}


@pytest.mark.usefixtures("admin_auth")
def test_patch_by_admin_sets_admin_flag(calls: Calls) -> None:
    calls.current = _project(state="Approved")

    assert TestClient(app).patch(f"{_BASE}/5", json={"hours": 3}).status_code == 200
    assert calls.updated[0]["is_admin"] is True


@pytest.mark.usefixtures("pm_auth")
def test_patch_without_changes_skips_the_write(calls: Calls) -> None:
    response = TestClient(app).patch(f"{_BASE}/5", json={"name": "Go-live"})

    assert response.status_code == 200
    assert calls.updated == []


@pytest.mark.usefixtures("pm_auth")
@pytest.mark.parametrize("field", ["name", "customer_id", "requester_oid"])
def test_patch_rejects_null_for_required_fields(calls: Calls, field: str) -> None:
    response = TestClient(app).patch(f"{_BASE}/5", json={field: None})

    assert response.status_code == 422
    assert calls.updated == []


@pytest.mark.usefixtures("pm_auth")
def test_patch_locked_after_draft_is_409(calls: Calls) -> None:
    calls.current = _project(state="Requested")
    calls.outcome = "Locked"

    assert TestClient(app).patch(f"{_BASE}/5", json={"hours": 3}).status_code == 409


# --- delete ------------------------------------------------------------------


@pytest.mark.usefixtures("admin_auth")
def test_admin_sets_consultant(calls: Calls) -> None:
    response = TestClient(app).patch(f"{_BASE}/5", json={"consultant_oid": _ME})

    assert response.status_code == 200
    assert calls.updated[0]["set_consultant"] is True
    assert calls.updated[0]["consultant_oid"] == _ME
    assert "consultant_oid" in calls.updated[0]["audit_detail"]


@pytest.mark.usefixtures("pm_auth")
def test_pm_cannot_set_consultant(calls: Calls) -> None:
    response = TestClient(app).patch(f"{_BASE}/5", json={"consultant_oid": _ME})

    assert response.status_code == 403
    assert not calls.updated


@pytest.mark.usefixtures("admin_auth")
def test_consultant_must_be_admin(calls: Calls) -> None:
    # _OTHER_PM holds the PM role in the fixture, so is not a valid consultant.
    response = TestClient(app).patch(f"{_BASE}/5", json={"consultant_oid": _OTHER_PM})

    assert response.status_code == 422
    assert not calls.updated


@pytest.mark.usefixtures("admin_auth")
def test_consultant_cannot_be_cleared(calls: Calls) -> None:
    response = TestClient(app).patch(f"{_BASE}/5", json={"consultant_oid": None})

    assert response.status_code == 422
    assert not calls.updated


@pytest.mark.usefixtures("admin_auth")
def test_delete_draft_is_204(calls: Calls) -> None:
    response = TestClient(app).delete(f"{_BASE}/5")

    assert response.status_code == 204
    assert calls.deleted == [(_ME, True, True, 5)]


@pytest.mark.usefixtures("pm_auth")
def test_pm_cannot_delete(calls: Calls) -> None:
    assert TestClient(app).delete(f"{_BASE}/5").status_code == 403
    assert not calls.deleted


@pytest.mark.usefixtures("admin_auth")
@pytest.mark.parametrize(
    ("outcome", "status_code"), [("NotDraft", 409), ("NotFound", 404)]
)
def test_delete_maps_outcomes(calls: Calls, outcome: str, status_code: int) -> None:
    calls.outcome = outcome

    assert TestClient(app).delete(f"{_BASE}/5").status_code == status_code


# --- requesters / lookups ----------------------------------------------------


@pytest.mark.usefixtures("pm_auth")
def test_requesters_lists_active_pms_and_admins(
    monkeypatch: pytest.MonkeyPatch, calls: Calls
) -> None:
    from app.modules.users.schemas import PortalUser  # noqa: PLC0415

    def _user(oid: str, email: str, deactivated: datetime | None = None) -> PortalUser:
        return PortalUser(
            entra_oid=oid, email=email, deactivated_utc=deactivated, created_utc=_NOW
        )

    monkeypatch.setattr(
        users_repository,
        "list_users",
        lambda: [
            _user(_OTHER_PM, "pm@9a.test"),
            _user("00000000-0000-0000-0000-000000000009", "cust@x.test"),
            _user(_ME, "old@9a.test", _NOW),
        ],
    )
    monkeypatch.setattr(
        graph,
        "list_role_assignments",
        lambda: {
            _OTHER_PM: "PM",
            "00000000-0000-0000-0000-000000000009": "User",
            _ME: "Admin",
        },
    )

    response = TestClient(app).get(f"{_BASE}/requesters")

    assert response.json() == [{"oid": _OTHER_PM, "email": "pm@9a.test"}]
    assert calls.created == []


@pytest.mark.usefixtures("pm_auth")
def test_lookups_are_staff_only_and_filterable(calls: Calls) -> None:
    response = TestClient(app).get(
        "/api/v1/portal/lookups", params={"kind": "Department"}
    )

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Consulting"
    assert calls.created == []


@pytest.mark.usefixtures("user_auth")
def test_lookups_forbidden_to_customer_users(calls: Calls) -> None:
    assert TestClient(app).get("/api/v1/portal/lookups").status_code == 403
    assert calls.created == []
