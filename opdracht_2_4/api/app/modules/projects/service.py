"""Business logic for the projects module (router -> service -> repository).

Visibility, the Draft author-only rule and the post-Draft lock are enforced in the
stored procedures; this layer validates what only the API can know — lookup
references (``LookupOption`` kinds) and a requester's role (held in Entra) — and
turns procedure outcomes into HTTP errors.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, NoReturn

from fastapi import HTTPException, status

from app.integrations import graph
from app.modules.lookups import repository as lookups_repository
from app.modules.lookups.schemas import LookupKind
from app.modules.projects import repository
from app.modules.projects.schemas import (
    Connector,
    InstallationDefinition,
    MigrationDefinition,
    Project,
    ProjectCreate,
    ProjectDefinition,
    ProjectType,
    ProjectUpdate,
    Requester,
)
from app.modules.users import repository as users_repository

if TYPE_CHECKING:
    from app.core.security import PortalPrincipal
    from app.modules.lookups.schemas import LookupOption
    from app.modules.projects.schemas import (
        MutationResult,
        ProjectState,
    )

_REQUESTER_ROLES = frozenset({"PM", "Admin"})
_FAMILIES_WITH_COMPANIES = frozenset({"AXFO", "NAVBC"})
_FAMILIES_WITH_PACKS = frozenset({"AXFO", "NAVBC", "CE"})
_MSG_WRONG_TYPE = "The definition does not match the Project type"
_HTTP_422 = 422  # starlette renamed its constant; the number is stable
_KIND_DEPARTMENT = "Department"
_MSG_REQUESTER_ROLE = "Requester must hold the PM or Admin role"
_MSG_CONSULTANT_ROLE = "Consultant must hold the Admin role"
_ADMIN_ROLE = "Admin"
_MSG_DEPARTMENT = "Unknown department"
_MSG_NULL = "customer_id, name, requester_oid and consultant_oid cannot be null"
_NOT_NULL_FIELDS = frozenset({"customer_id", "name", "requester_oid", "consultant_oid"})

_OUTCOME_ERRORS: dict[str, tuple[int, str]] = {
    "NotFound": (status.HTTP_404_NOT_FOUND, "Project not found"),
    "Forbidden": (status.HTTP_403_FORBIDDEN, "Forbidden"),
    "UnknownActor": (status.HTTP_403_FORBIDDEN, "Caller has no active portal user"),
    "Locked": (
        status.HTTP_409_CONFLICT,
        "Only an Admin can edit a Project after it is a Draft",
    ),
    "NotDraft": (status.HTTP_409_CONFLICT, "Only a Draft can be deleted"),
    "WrongType": (status.HTTP_409_CONFLICT, _MSG_WRONG_TYPE),
    "UnknownRequester": (
        _HTTP_422,
        "Requester is not an active portal user",
    ),
    "UnknownCustomer": (_HTTP_422, "Unknown customer"),
    "UnknownConsultant": (_HTTP_422, "Consultant is not an active portal user"),
}


def _oid(principal: PortalPrincipal) -> str:
    if not principal.oid:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return principal.oid


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(_HTTP_422, detail)


def _reject(detail: str) -> NoReturn:
    raise _unprocessable(detail)


def _raise_unless_ok(result: MutationResult) -> int:
    """Return the Project id of a successful outcome, else raise its HTTP error."""
    if result.outcome == "Ok" and result.project_id is not None:
        return result.project_id
    code, detail = _OUTCOME_ERRORS.get(
        result.outcome, (status.HTTP_500_INTERNAL_SERVER_ERROR, "Unexpected outcome")
    )
    raise HTTPException(code, detail)


def _ensure_user(oid: str) -> None:
    """Make sure the caller has a ``Users`` row (a bootstrap Admin may not yet)."""
    if users_repository.get_user(oid) is None:
        users_repository.upsert_user(oid, graph.get_user_email(oid), None)


def _check_requester(requester_oid: str, caller_oid: str) -> None:
    """Reject a requester other than the caller who is not an active PM/Admin."""
    if requester_oid.lower() == caller_oid.lower():
        return
    if graph.list_role_assignments().get(requester_oid.lower()) not in _REQUESTER_ROLES:
        _reject(_MSG_REQUESTER_ROLE)


def _check_consultant(consultant_oid: str) -> None:
    """Reject a consultant who does not hold the Admin role."""
    if graph.list_role_assignments().get(consultant_oid.lower()) != _ADMIN_ROLE:
        _reject(_MSG_CONSULTANT_ROLE)


def _check_department(department_id: int | None) -> None:
    if department_id is None:
        return
    options = lookups_repository.list_lookup_options(_KIND_DEPARTMENT)
    if department_id not in {option.id for option in options}:
        _reject(_MSG_DEPARTMENT)


def list_projects(
    principal: PortalPrincipal,
    state: ProjectState | None,
    project_type: ProjectType | None,
    customer_id: int | None,
) -> list[Project]:
    """Return the Projects visible to the caller, with optional filters."""
    return repository.list_projects(
        _oid(principal),
        is_staff=principal.is_staff,
        state=state,
        project_type=project_type,
        customer_id=customer_id,
    )


def get_project(principal: PortalPrincipal, project_id: int) -> Project:
    """Return one visible Project, or raise 404 (also for a hidden one)."""
    project = repository.get_project(
        _oid(principal), is_staff=principal.is_staff, project_id=project_id
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def create_project(principal: PortalPrincipal, request: ProjectCreate) -> Project:
    """Create a Draft Project authored by the caller and return it."""
    actor = _oid(principal)
    requester = str(request.requester_oid) if request.requester_oid else None
    if requester:
        _check_requester(requester, actor)
    _check_department(request.department_id)
    _ensure_user(actor)

    result = repository.create_project(
        actor,
        requester,
        request.customer_id,
        request.type.value,
        request.name,
        request.department_id,
        request.customer_type.value if request.customer_type else None,
        request.deadline,
        request.hours,
        request.request_notes,
    )
    return get_project(principal, _raise_unless_ok(result))


def _merge_header(
    current: Project, request: ProjectUpdate, provided: set[str]
) -> tuple[dict[str, Any], list[str]]:
    """Merge the provided header fields over the current Project; list what changed."""
    merged: dict[str, Any] = {
        "customer_id": current.customer_id,
        "name": current.name,
        "requester_oid": current.requester_oid,
        "department_id": current.department_id,
        "customer_type": current.customer_type,
        "deadline": current.deadline,
        "hours": current.hours,
        "request_notes": current.request_notes,
    }
    changed: list[str] = []
    for name in sorted(provided):
        value = getattr(request, name)
        if name == "requester_oid" and value is not None:
            value = str(value)
        if value != merged[name]:
            merged[name] = value
            changed.append(name)
    return merged, changed


def update_project(
    principal: PortalPrincipal, project_id: int, request: ProjectUpdate
) -> Project:
    """Apply a partial header update and return the Project."""
    actor = _oid(principal)
    current = get_project(principal, project_id)
    if not principal.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    provided = set(request.model_fields_set)
    if any(getattr(request, name) is None for name in provided & _NOT_NULL_FIELDS):
        _reject(_MSG_NULL)

    set_consultant = "consultant_oid" in provided
    if set_consultant:
        if not principal.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        _check_consultant(str(request.consultant_oid))
        provided.discard("consultant_oid")

    merged, changed = _merge_header(current, request, provided)
    if set_consultant:
        changed.append("consultant_oid")
    if not changed:
        return current

    if "requester_oid" in changed:
        _check_requester(str(merged["requester_oid"]), actor)
    if "department_id" in changed:
        _check_department(request.department_id)

    customer_type = merged["customer_type"]
    result = repository.update_project(
        actor,
        is_staff=principal.is_staff,
        is_admin=principal.is_admin,
        project_id=project_id,
        requester_oid=str(merged["requester_oid"]),
        customer_id=int(merged["customer_id"]),
        name=str(merged["name"]),
        department_id=merged["department_id"],
        customer_type=getattr(customer_type, "value", customer_type),
        deadline=merged["deadline"],
        hours=merged["hours"],
        request_notes=merged["request_notes"],
        audit_detail=json.dumps({"fields": changed}),
        consultant_oid=str(request.consultant_oid) if set_consultant else None,
        set_consultant=set_consultant,
    )
    _raise_unless_ok(result)
    return get_project(principal, project_id)


def _options_by_id() -> dict[int, LookupOption]:
    return {
        option.id: option for option in lookups_repository.list_lookup_options(None)
    }


def _option(
    options: dict[int, LookupOption],
    option_id: int | None,
    kind: LookupKind,
    label: str,
) -> LookupOption | None:
    """Return the active option, or raise 422 if it is missing or of another kind."""
    if option_id is None:
        return None
    option = options.get(option_id)
    if option is None or option.kind != kind:
        _reject(f"Unknown {label}")
    return option


def _check_connector(
    options: dict[int, LookupOption], connector: Connector, number: int
) -> None:
    """Apply the source-system family rules to one connector."""
    source = _option(
        options, connector.source_system_id, LookupKind.source_system, "source system"
    )
    family = source.family if source else None
    where = f"connector {number}"
    if (
        connector.companies_to_extract is not None
        and family not in _FAMILIES_WITH_COMPANIES
    ):
        _reject(f"Companies to extract does not apply to {where}")

    packs = connector.content_pack_ids
    if len(set(packs)) != len(packs):
        _reject(f"Duplicate content pack in {where}")
    if packs and family not in _FAMILIES_WITH_PACKS:
        _reject(f"Content packs do not apply to {where}")
    for pack_id in packs:
        pack = _option(options, pack_id, LookupKind.content_pack, "content pack")
        if pack is not None and (
            pack.family != family
            or (source is not None and pack.excluded_source_system_id == source.id)
        ):
            _reject(f"Content pack {pack.name} is not available for {where}")


def _check_installation(definition: InstallationDefinition) -> None:
    options = _options_by_id()
    _option(
        options,
        definition.installation_type_id,
        LookupKind.installation_type,
        "installation type",
    )
    _option(
        options,
        definition.power_bi_license_id,
        LookupKind.power_bi_license,
        "Power BI license",
    )
    connection = _option(
        options,
        definition.environment_connection_id,
        LookupKind.environment_connection,
        "environment connection",
    )
    needs_text = connection is not None and connection.allows_free_text
    if needs_text and not definition.environment_connection_other:
        _reject("Describe the environment connection")
    if not needs_text and definition.environment_connection_other:
        _reject("Environment connection text only applies to Other")
    for number, connector in enumerate(definition.connectors, start=1):
        _check_connector(options, connector, number)


def _check_migration(definition: MigrationDefinition) -> None:
    _option(
        _options_by_id(),
        definition.migration_type_id,
        LookupKind.migration_type,
        "migration type",
    )


def get_definition(principal: PortalPrincipal, project_id: int) -> ProjectDefinition:
    """Return the Installation or Migration definition, or 404 if not visible."""
    actor = _oid(principal)
    row = repository.get_project_definition(
        actor, is_staff=principal.is_staff, project_id=project_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if row.type == ProjectType.migration:
        return ProjectDefinition(
            type=row.type,
            migration=MigrationDefinition.model_validate(row, from_attributes=True),
        )
    installation = InstallationDefinition.model_validate(row, from_attributes=True)
    installation.connectors = repository.list_project_connectors(
        actor, is_staff=principal.is_staff, project_id=project_id
    )
    return ProjectDefinition(type=row.type, installation=installation)


def save_definition(
    principal: PortalPrincipal,
    project_id: int,
    installation: InstallationDefinition | None = None,
    migration: MigrationDefinition | None = None,
) -> ProjectDefinition:
    """Replace the definition of the Project's type (exactly one body is given).

    The author edits a ``Draft``; after that only an Admin (audited in the procedure).
    """
    current = get_definition(principal, project_id)
    if not principal.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    new = installation or migration
    old = current.installation or current.migration
    wanted = ProjectType.installation if installation else ProjectType.migration
    if new is None or old is None or current.type != wanted:
        raise HTTPException(status.HTTP_409_CONFLICT, _MSG_WRONG_TYPE)

    if installation:
        _check_installation(installation)
    elif migration:
        _check_migration(migration)

    new_values, old_values = new.model_dump(), old.model_dump()
    changed = sorted(
        name for name in new_values if new_values[name] != old_values[name]
    )
    if not changed:
        return current

    result = repository.save_project_definition(
        _oid(principal),
        is_staff=principal.is_staff,
        is_admin=principal.is_admin,
        project_id=project_id,
        project_type=wanted.value,
        installation=installation,
        migration=migration,
        audit_detail=json.dumps({"fields": changed}),
    )
    _raise_unless_ok(result)
    return get_definition(principal, project_id)


def delete_project(principal: PortalPrincipal, project_id: int) -> None:
    """Delete a Draft the caller authored, or raise the matching HTTP error."""
    result = repository.delete_project(
        _oid(principal),
        is_staff=principal.is_staff,
        is_admin=principal.is_admin,
        project_id=project_id,
    )
    _raise_unless_ok(result)


def list_requesters() -> list[Requester]:
    """Return the active PMs and Admins who may be set as a Project's requester."""
    roles = graph.list_role_assignments()
    return [
        Requester(oid=user.entra_oid, email=user.email)
        for user in users_repository.list_users()
        if user.deactivated_utc is None
        and roles.get(user.entra_oid) in _REQUESTER_ROLES
    ]
