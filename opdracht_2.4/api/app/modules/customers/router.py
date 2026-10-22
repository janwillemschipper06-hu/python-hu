"""HTTP router for the customers module — the read-only customer picker.

A bare :data:`router`: :mod:`app.api` mounts it under the **portal** tier. The
lookup is further restricted to Admin/PM by :func:`require_staff`, since customer
users must not enumerate the other customers. There is no customer resource and no
write path (``docs/adr/0013``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.security import require_staff
from app.modules.customers import service
from app.modules.customers.schemas import CustomerLookup

router = APIRouter()


@router.get(
    "/customers/lookup",
    response_model=list[CustomerLookup],
    dependencies=[Depends(require_staff)],
)
def lookup_customers(
    q: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[CustomerLookup]:
    """Search customers by name for the Project customer dropdown.

    Args:
        q: Optional case-insensitive name fragment.
        limit: Maximum number of options to return (1-100).

    Returns:
        Matching customers as ``{id, name}`` pairs, ordered by name.
    """
    return service.search_customers(q, limit)
