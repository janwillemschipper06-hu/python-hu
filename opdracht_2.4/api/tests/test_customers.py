"""Tests for the read-only customer lookup (``GET /api/v1/portal/customers/lookup``).

The database is not touched: the repository is monkeypatched so the router,
service and response serialization are exercised without an ODBC driver. The
platform authentication seam (:func:`app.core.security.validated_token`) is
overridden with a principal carrying the role under test; real end-to-end
authentication is verified on the dev deployment, not asserted here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from app.core.security import ClientPrincipal, validated_token
from app.main import app
from app.modules.customers import repository
from app.modules.customers.schemas import CustomerLookup

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_URL = "/api/v1/portal/customers/lookup"


def _as_role(role: str) -> Callable[[], Iterator[None]]:
    def _fixture() -> Iterator[None]:
        app.dependency_overrides[validated_token] = lambda: ClientPrincipal(
            oid="00000000-0000-0000-0000-000000000001", roles=(role,)
        )
        try:
            yield
        finally:
            app.dependency_overrides.pop(validated_token, None)

    return _fixture


admin_auth = pytest.fixture(_as_role("Admin"))
pm_auth = pytest.fixture(_as_role("PM"))
user_auth = pytest.fixture(_as_role("User"))


def _fake_search(
    captured: dict[str, object],
) -> Callable[[str | None, int], list[CustomerLookup]]:
    def _search(query: str | None, limit: int) -> list[CustomerLookup]:
        captured["query"], captured["limit"] = query, limit
        return [CustomerLookup(id=7, name="Contoso Ltd")]

    return _search


@pytest.mark.usefixtures("admin_auth")
def test_lookup_returns_id_and_name_only(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(repository, "search_customers", _fake_search(captured))

    response = TestClient(app).get(_URL, params={"q": "contoso"})

    assert response.status_code == 200
    assert response.json() == [{"id": 7, "name": "Contoso Ltd"}]
    assert captured == {"query": "contoso", "limit": 25}


@pytest.mark.usefixtures("pm_auth")
def test_lookup_is_open_to_project_managers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(repository, "search_customers", _fake_search(captured))

    assert TestClient(app).get(_URL).status_code == 200
    assert captured["query"] is None


@pytest.mark.usefixtures("user_auth")
def test_lookup_is_forbidden_to_customer_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(repository, "search_customers", _fake_search(captured))

    assert TestClient(app).get(_URL).status_code == 403
    assert captured == {}


@pytest.mark.usefixtures("admin_auth")
def test_lookup_rejects_out_of_range_limit() -> None:
    assert TestClient(app).get(_URL, params={"limit": 0}).status_code == 422
    assert TestClient(app).get(_URL, params={"limit": 101}).status_code == 422


def test_lookup_requires_authentication() -> None:
    assert TestClient(app).get(_URL).status_code == 401


def test_removed_customer_endpoints_are_gone() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert _URL in paths
    assert "/api/v1/portal/customers" not in paths
    assert "/api/v1/portal/customers/{customer_id}" not in paths
    assert "/api/v1/extract/customers" not in paths
    assert "/api/v1/admin/users/{oid}/customers" not in paths
    assert "/api/v1/admin/users/{oid}/access" not in paths
