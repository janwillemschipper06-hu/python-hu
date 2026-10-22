"""HTTP router for the lookups module — the read-only dropdown options.

A bare router mounted under the **portal** tier; restricted to staff because the
options only feed the Project forms. Admin lookup editing is a later stage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_staff
from app.modules.lookups import repository
from app.modules.lookups.schemas import LookupKind, LookupOption

router = APIRouter()


@router.get(
    "/lookups",
    response_model=list[LookupOption],
    dependencies=[Depends(require_staff)],
)
def list_lookups(kind: LookupKind | None = None) -> list[LookupOption]:
    """Return the active dropdown options, optionally of a single kind."""
    return repository.list_lookup_options(kind)
