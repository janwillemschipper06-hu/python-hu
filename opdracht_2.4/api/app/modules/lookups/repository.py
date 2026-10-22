"""Stored-procedure data access for the lookups module."""

from __future__ import annotations

from app.core.db import execute_procedure_pydantic
from app.modules.lookups.schemas import LookupOption


def list_lookup_options(kind: str | None) -> list[LookupOption]:
    """Return the active options of one kind (or every kind when ``None``).

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    return execute_procedure_pydantic(
        "onboarding.ListLookupOptions", LookupOption, (kind, False)
    )
