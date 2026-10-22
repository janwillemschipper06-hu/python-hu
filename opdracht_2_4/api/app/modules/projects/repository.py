"""Stored-procedure data access for the projects module.

Every call is an EXECUTE-only procedure (``docs/adr/0002``, ``docs/adr/0008``).
Visibility and the Draft/lock rules live in the procedures; the caller's ``oid``
and role flags are passed to each so scope is resolved in the database.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.db import execute_procedure_pydantic
from app.modules.projects.schemas import (
    Connector,
    DefinitionRow,
    InstallationDefinition,
    MigrationDefinition,
    MutationResult,
    Project,
)

if TYPE_CHECKING:
    from datetime import date


def _one(rows: list[MutationResult]) -> MutationResult:
    return rows[0]


def list_projects(
    actor_oid: str,
    *,
    is_staff: bool,
    state: str | None,
    project_type: str | None,
    customer_id: int | None,
) -> list[Project]:
    """Return the Projects the caller may see, newest activity first.

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    return execute_procedure_pydantic(
        "onboarding.ListProjects",
        Project,
        (actor_oid, is_staff, state, project_type, customer_id),
    )


def get_project(actor_oid: str, *, is_staff: bool, project_id: int) -> Project | None:
    """Return one visible Project, or ``None`` when missing or not visible."""
    rows = execute_procedure_pydantic(
        "onboarding.GetProject", Project, (actor_oid, is_staff, project_id)
    )
    return rows[0] if rows else None


def create_project(  # noqa: PLR0913, PLR0917 - one parameter per procedure parameter
    actor_oid: str,
    requester_oid: str | None,
    customer_id: int,
    project_type: str,
    name: str,
    department_id: int | None,
    customer_type: str | None,
    deadline: date | None,
    hours: int | None,
    request_notes: str | None,
) -> MutationResult:
    """Create a Draft Project; the outcome says whether it succeeded."""
    return _one(
        execute_procedure_pydantic(
            "onboarding.CreateProject",
            MutationResult,
            (
                actor_oid,
                requester_oid,
                customer_id,
                project_type,
                name,
                department_id,
                customer_type,
                deadline,
                hours,
                request_notes,
            ),
        )
    )


def update_project(  # noqa: PLR0913 - one parameter per procedure parameter
    actor_oid: str,
    *,
    is_staff: bool,
    is_admin: bool,
    project_id: int,
    requester_oid: str,
    customer_id: int,
    name: str,
    department_id: int | None,
    customer_type: str | None,
    deadline: date | None,
    hours: int | None,
    request_notes: str | None,
    audit_detail: str | None,
    consultant_oid: str | None = None,
    set_consultant: bool = False,
) -> MutationResult:
    """Replace the editable header fields; the outcome says whether it succeeded."""
    return _one(
        execute_procedure_pydantic(
            "onboarding.UpdateProject",
            MutationResult,
            (
                actor_oid,
                is_staff,
                is_admin,
                project_id,
                requester_oid,
                customer_id,
                name,
                department_id,
                customer_type,
                deadline,
                hours,
                request_notes,
                audit_detail,
                consultant_oid,
                set_consultant,
            ),
        )
    )


def get_project_definition(
    actor_oid: str, *, is_staff: bool, project_id: int
) -> DefinitionRow | None:
    """Return the definition columns of a visible Project, else ``None``."""
    rows = execute_procedure_pydantic(
        "onboarding.GetProjectDefinition",
        DefinitionRow,
        (actor_oid, is_staff, project_id),
    )
    return rows[0] if rows else None


def list_project_connectors(
    actor_oid: str, *, is_staff: bool, project_id: int
) -> list[Connector]:
    """Return the connectors of a visible Installation Project in order."""
    return execute_procedure_pydantic(
        "onboarding.ListProjectConnectors",
        Connector,
        (actor_oid, is_staff, project_id),
    )


def save_project_definition(  # noqa: PLR0913 - one parameter per procedure parameter
    actor_oid: str,
    *,
    is_staff: bool,
    is_admin: bool,
    project_id: int,
    project_type: str,
    installation: InstallationDefinition | None,
    migration: MigrationDefinition | None,
    audit_detail: str | None,
) -> MutationResult:
    """Replace the definition of one type; the outcome says whether it succeeded."""
    i = installation or InstallationDefinition()
    m = migration or MigrationDefinition()
    connectors = json.dumps(
        [
            {
                "position": position,
                "source_system_id": c.source_system_id,
                "license_count": c.license_count,
                "companies_to_extract": c.companies_to_extract,
                "content_pack_ids": c.content_pack_ids,
            }
            for position, c in enumerate(i.connectors, start=1)
        ]
    )
    return _one(
        execute_procedure_pydantic(
            "onboarding.SaveProjectDefinition",
            MutationResult,
            (
                actor_oid,
                is_staff,
                is_admin,
                project_id,
                project_type,
                i.installation_type_id,
                i.power_bi_license_id,
                i.env_development,
                i.env_test,
                i.env_acceptance,
                i.env_production,
                i.environment_connection_id,
                i.environment_connection_other,
                i.azure_subscription_by_us,
                i.power_bi_license_by_us,
                i.power_bi_licenses_sold,
                i.azure_costs_informed,
                i.signed_software_agreement,
                i.teams_channel_added,
                i.teams_channel_url,
                connectors,
                m.migration_type_id,
                m.migration_information,
                audit_detail,
            ),
        )
    )


def delete_project(
    actor_oid: str, *, is_staff: bool, is_admin: bool, project_id: int
) -> MutationResult:
    """Delete an Admin's own Draft; the outcome says whether it succeeded."""
    return _one(
        execute_procedure_pydantic(
            "onboarding.DeleteProject",
            MutationResult,
            (actor_oid, is_staff, is_admin, project_id),
        )
    )
