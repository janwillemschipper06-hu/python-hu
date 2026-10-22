"""HTTP router for the projects module — Project header CRUD.

A bare router mounted under the **portal** tier (any portal role). Reads are open
to every portal role because the database filters by visibility; writes require
internal staff (:func:`~app.core.security.require_staff`). A Project that is not
visible to the caller is indistinguishable from one that does not exist (404).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.security import (
    PortalPrincipal,
    require_portal_admin,
    require_portal_user,
    require_staff,
)
from app.modules.projects import service
from app.modules.projects.schemas import (
    InstallationDefinition,
    MigrationDefinition,
    Project,
    ProjectCreate,
    ProjectDefinition,
    ProjectState,
    ProjectType,
    ProjectUpdate,
    Requester,
)

router = APIRouter()

Portal = Annotated[PortalPrincipal, Depends(require_portal_user)]
Staff = Annotated[PortalPrincipal, Depends(require_staff)]
AdminOnly = Annotated[PortalPrincipal, Depends(require_portal_admin)]


@router.get("/projects", response_model=list[Project])
def list_projects(
    principal: Portal,
    state: ProjectState | None = None,
    type: ProjectType | None = None,  # noqa: A002 - API name
    customer_id: int | None = None,
) -> list[Project]:
    """List the Projects the caller may see, optionally filtered."""
    return service.list_projects(principal, state, type, customer_id)


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(principal: Staff, body: ProjectCreate) -> Project:
    """Create a ``Draft`` Project authored by the caller (PM or Admin)."""
    return service.create_project(principal, body)


@router.get(
    "/projects/requesters",
    response_model=list[Requester],
    dependencies=[Depends(require_staff)],
)
def list_requesters() -> list[Requester]:
    """List the active PMs and Admins a Project's requester may be set to."""
    return service.list_requesters()


@router.get("/projects/{project_id}", response_model=Project)
def get_project(principal: Portal, project_id: int) -> Project:
    """Return one Project, or 404 when missing or not visible to the caller."""
    return service.get_project(principal, project_id)


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(principal: Staff, project_id: int, body: ProjectUpdate) -> Project:
    """Update the Project header: author in ``Draft``, otherwise Admin (audited)."""
    return service.update_project(principal, project_id, body)


@router.get("/projects/{project_id}/definition", response_model=ProjectDefinition)
def get_definition(principal: Portal, project_id: int) -> ProjectDefinition:
    """Return the Installation or Migration definition of a visible Project."""
    return service.get_definition(principal, project_id)


@router.put("/projects/{project_id}/installation", response_model=ProjectDefinition)
def save_installation(
    principal: Staff, project_id: int, body: InstallationDefinition
) -> ProjectDefinition:
    """Replace an Installation Project's definition: author in ``Draft``, else Admin."""
    return service.save_definition(principal, project_id, installation=body)


@router.put("/projects/{project_id}/migration", response_model=ProjectDefinition)
def save_migration(
    principal: Staff, project_id: int, body: MigrationDefinition
) -> ProjectDefinition:
    """Replace a Migration Project's definition: author in ``Draft``, else Admin."""
    return service.save_definition(principal, project_id, migration=body)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(principal: AdminOnly, project_id: int) -> Response:
    """Delete a ``Draft`` Project the caller (an Admin) authored."""
    service.delete_project(principal, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
