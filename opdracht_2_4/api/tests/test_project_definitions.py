"""Tests for the Installation/Migration definition endpoints (Stage 4).

Repositories are monkeypatched (no database), so routing, role guards, the
per-type validation matrix (lookup kinds, source-system family rules) and the
outcome -> HTTP mapping are exercised. Locking and audit live in the
``SaveProjectDefinition`` procedure. The platform auth seam is overridden.
"""

# ruff: noqa: C408 (dict(Alias=...) keeps the SQL column names readable)
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from app.core.security import ClientPrincipal, validated_token
from app.main import app
from app.modules.lookups import repository as lookups_repository
from app.modules.lookups.schemas import LookupKind, LookupOption
from app.modules.projects import repository
from app.modules.projects.schemas import (
    Connector,
    DefinitionRow,
    InstallationDefinition,
    MigrationDefinition,
    MutationResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_BASE = "/api/v1/portal/projects/5"
_ME = "00000000-0000-0000-0000-000000000001"

# Lookup ids used below.
_AX, _FO, _BC, _SQL, _CE = 1, 2, 3, 4, 5
_PACK_AXFO, _PACK_ADV_MFG, _PACK_BC, _PACK_CE = 10, 11, 12, 13
_INST_TYPE, _LICENSE, _CONN, _CONN_OTHER, _MIG_TYPE = 20, 21, 22, 23, 30


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


def _option(option_id: int, kind: LookupKind, name: str, **extra: Any) -> LookupOption:
    return LookupOption(
        id=option_id,
        kind=kind,
        name=name,
        allows_free_text=extra.pop("allows_free_text", False),
        sort_order=0,
        is_active=True,
        **extra,
    )


_OPTIONS = [
    _option(_AX, LookupKind.source_system, "AX", family="AXFO"),
    _option(_FO, LookupKind.source_system, "F&O", family="AXFO"),
    _option(_BC, LookupKind.source_system, "BC", family="NAVBC"),
    _option(_SQL, LookupKind.source_system, "SQL", family="SQL"),
    _option(_CE, LookupKind.source_system, "CE", family="CE"),
    _option(_PACK_AXFO, LookupKind.content_pack, "Finance", family="AXFO"),
    _option(
        _PACK_ADV_MFG,
        LookupKind.content_pack,
        "Advanced Manufacturing",
        family="AXFO",
        excluded_source_system_id=_AX,
    ),
    _option(_PACK_BC, LookupKind.content_pack, "BC Finance", family="NAVBC"),
    _option(_PACK_CE, LookupKind.content_pack, "Events", family="CE"),
    _option(_INST_TYPE, LookupKind.installation_type, "Azure Cloud"),
    _option(_LICENSE, LookupKind.power_bi_license, "Pro"),
    _option(_CONN, LookupKind.environment_connection, "All production"),
    _option(
        _CONN_OTHER, LookupKind.environment_connection, "Other", allows_free_text=True
    ),
    _option(_MIG_TYPE, LookupKind.migration_type, "Server Migration"),
]


class Calls:
    """Records repository calls and serves canned results."""

    def __init__(self) -> None:
        self.row = DefinitionRow.model_validate(dict(Type="Installation"))
        self.connectors: list[Connector] = []
        self.saved: list[dict[str, Any]] = []
        self.outcome = "Ok"


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    log = Calls()

    def _save(actor: str, **kwargs: Any) -> MutationResult:
        log.saved.append({"actor": actor, **kwargs})
        return MutationResult(outcome=log.outcome, project_id=5)

    monkeypatch.setattr(repository, "get_project_definition", lambda *_a, **_k: log.row)
    monkeypatch.setattr(
        repository, "list_project_connectors", lambda *_a, **_k: log.connectors
    )
    monkeypatch.setattr(repository, "save_project_definition", _save)
    monkeypatch.setattr(lookups_repository, "list_lookup_options", lambda _k: _OPTIONS)
    return log


def _connector(source: int, **extra: Any) -> dict[str, Any]:
    return {"source_system_id": source, "license_count": 1, **extra}


def _put(body: dict[str, Any]) -> Any:
    return TestClient(app).put(f"{_BASE}/installation", json=body)


# --- read ----------------------------------------------------------------------


@pytest.mark.usefixtures("user_auth")
def test_customer_user_can_read_the_definition(calls: Calls) -> None:
    calls.row = DefinitionRow.model_validate(
        dict(Type="Installation", PreferredInstallationTypeId=_INST_TYPE)
    )
    calls.connectors = [
        Connector.model_validate(
            dict(SourceSystemId=_AX, LicenseCount=2, ContentPackIds="[10]")
        )
    ]

    response = TestClient(app).get(f"{_BASE}/definition")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Installation"
    assert body["migration"] is None
    assert body["installation"]["installation_type_id"] == _INST_TYPE
    assert body["installation"]["connectors"][0]["content_pack_ids"] == [10]


@pytest.mark.usefixtures("pm_auth")
def test_migration_definition_is_returned_for_a_migration_project(
    calls: Calls,
) -> None:
    calls.row = DefinitionRow.model_validate(
        dict(
            Type="Migration", MigrationTypeId=_MIG_TYPE, MigrationInformation="Move it"
        )
    )

    body = TestClient(app).get(f"{_BASE}/definition").json()

    assert body["installation"] is None
    assert body["migration"] == {
        "migration_type_id": _MIG_TYPE,
        "migration_information": "Move it",
    }


@pytest.mark.usefixtures("pm_auth")
def test_hidden_project_is_404(monkeypatch: pytest.MonkeyPatch, calls: Calls) -> None:
    monkeypatch.setattr(repository, "get_project_definition", lambda *_a, **_k: None)
    client = TestClient(app)

    assert client.get(f"{_BASE}/definition").status_code == 404
    assert client.put(f"{_BASE}/installation", json={}).status_code == 404
    assert calls.saved == []


# --- role gating and type match ---------------------------------------------------


@pytest.mark.usefixtures("user_auth")
def test_customer_user_cannot_save(calls: Calls) -> None:
    client = TestClient(app)

    assert client.put(f"{_BASE}/installation", json={}).status_code == 403
    assert client.put(f"{_BASE}/migration", json={}).status_code == 403
    assert calls.saved == []


@pytest.mark.usefixtures("pm_auth")
def test_installation_body_on_a_migration_project_is_409(calls: Calls) -> None:
    calls.row = DefinitionRow.model_validate(dict(Type="Migration"))

    assert _put({"teams_channel_added": True}).status_code == 409
    assert calls.saved == []


@pytest.mark.usefixtures("pm_auth")
def test_migration_body_on_an_installation_project_is_409(calls: Calls) -> None:
    response = TestClient(app).put(f"{_BASE}/migration", json={"migration_type_id": 30})

    assert response.status_code == 409
    assert calls.saved == []


# --- installation save -------------------------------------------------------------


@pytest.mark.usefixtures("pm_auth")
def test_save_installation_passes_connectors_and_audit_fields(calls: Calls) -> None:
    body = {
        "installation_type_id": _INST_TYPE,
        "env_production": True,
        "signed_software_agreement": False,
        "connectors": [
            _connector(
                _FO,
                companies_to_extract=3,
                content_pack_ids=[_PACK_AXFO, _PACK_ADV_MFG],
            ),
            _connector(_SQL),
        ],
    }

    response = _put(body)

    assert response.status_code == 200
    sent = calls.saved[0]
    assert sent["project_type"] == "Installation"
    assert sent["is_admin"] is False
    assert [c.source_system_id for c in sent["installation"].connectors] == [_FO, _SQL]
    assert json.loads(sent["audit_detail"]) == {
        "fields": [
            "connectors",
            "env_production",
            "installation_type_id",
            "signed_software_agreement",
        ]
    }


@pytest.mark.usefixtures("admin_auth")
def test_admin_save_sets_admin_flag(calls: Calls) -> None:
    assert _put({"env_test": True}).status_code == 200
    assert calls.saved[0]["is_admin"] is True


@pytest.mark.usefixtures("pm_auth")
def test_save_without_changes_skips_the_write(calls: Calls) -> None:
    assert _put({}).status_code == 200
    assert calls.saved == []


@pytest.mark.usefixtures("pm_auth")
def test_locked_outcome_is_409(calls: Calls) -> None:
    calls.outcome = "Locked"

    assert _put({"env_test": True}).status_code == 409


@pytest.mark.usefixtures("pm_auth")
@pytest.mark.parametrize(
    "bad",
    [
        {"installation_type_id": _MIG_TYPE},  # wrong lookup kind
        {"installation_type_id": 999},  # unknown / inactive
        {"power_bi_license_id": _INST_TYPE},
        {"environment_connection_id": _CONN_OTHER},  # "Other" needs text
        {"environment_connection_id": _CONN, "environment_connection_other": "x"},
        {"environment_connection_other": "x"},
        {"teams_channel_url": "http://teams.test/x"},
        {"power_bi_licenses_sold": -1},
        {"connectors": [_connector(_AX)] * 4},  # more than three
        {"connectors": [_connector(_AX, license_count=6)]},
        {"connectors": [_connector(_AX, license_count=0)]},
        {"connectors": [_connector(_PACK_AXFO)]},  # not a source system
        {"connectors": [_connector(_SQL, companies_to_extract=2)]},
        {"connectors": [_connector(_CE, companies_to_extract=2)]},
        {"connectors": [_connector(_AX, companies_to_extract=0)]},
        {"connectors": [_connector(_SQL, content_pack_ids=[_PACK_AXFO])]},
        {"connectors": [_connector(_BC, content_pack_ids=[_PACK_AXFO])]},
        {"connectors": [_connector(_AX, content_pack_ids=[_PACK_ADV_MFG])]},
        {"connectors": [_connector(_AX, content_pack_ids=[_PACK_AXFO, _PACK_AXFO])]},
        {"connectors": [_connector(_AX, content_pack_ids=[_INST_TYPE])]},
    ],
)
def test_installation_validation_matrix_rejects(
    calls: Calls, bad: dict[str, object]
) -> None:
    assert _put(bad).status_code == 422
    assert calls.saved == []


@pytest.mark.usefixtures("pm_auth")
@pytest.mark.parametrize(
    "good",
    [
        {
            "environment_connection_id": _CONN_OTHER,
            "environment_connection_other": " VPN ",
        },
        {"teams_channel_url": "https://teams.microsoft.com/l/channel/1"},
        {"connectors": [_connector(_AX, companies_to_extract=2)]},
        {"connectors": [_connector(_FO, content_pack_ids=[_PACK_ADV_MFG])]},
        {
            "connectors": [
                _connector(_BC, companies_to_extract=1, content_pack_ids=[_PACK_BC])
            ]
        },
        {"connectors": [_connector(_CE, content_pack_ids=[_PACK_CE])]},
        {"connectors": [_connector(_SQL)]},
    ],
)
def test_installation_validation_matrix_accepts(
    calls: Calls, good: dict[str, object]
) -> None:
    assert _put(good).status_code == 200
    assert len(calls.saved) == 1


@pytest.mark.usefixtures("pm_auth")
def test_free_text_connection_is_trimmed(calls: Calls) -> None:
    _put(
        {
            "environment_connection_id": _CONN_OTHER,
            "environment_connection_other": " VPN ",
        }
    )

    assert calls.saved[0]["installation"].environment_connection_other == "VPN"


# --- migration save ------------------------------------------------------------------


@pytest.mark.usefixtures("pm_auth")
def test_save_migration(calls: Calls) -> None:
    calls.row = DefinitionRow.model_validate(dict(Type="Migration"))

    response = TestClient(app).put(
        f"{_BASE}/migration",
        json={"migration_type_id": _MIG_TYPE, "migration_information": "  Move  "},
    )

    assert response.status_code == 200
    sent = calls.saved[0]
    assert sent["project_type"] == "Migration"
    assert sent["migration"] == MigrationDefinition(
        migration_type_id=_MIG_TYPE, migration_information="Move"
    )
    assert sent["installation"] is None


@pytest.mark.usefixtures("pm_auth")
@pytest.mark.parametrize(
    "bad", [{"migration_type_id": _INST_TYPE}, {"migration_information": "x" * 20_001}]
)
def test_migration_validation_rejects(calls: Calls, bad: dict[str, object]) -> None:
    calls.row = DefinitionRow.model_validate(dict(Type="Migration"))

    response = TestClient(app).put(f"{_BASE}/migration", json=bad)

    assert response.status_code == 422
    assert calls.saved == []


def test_installation_defaults_are_empty() -> None:
    assert InstallationDefinition().connectors == []
