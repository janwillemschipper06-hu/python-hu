"""Stored-procedure data access for the customers module.

The query goes through the EXECUTE-only ``onboarding.SearchCustomers`` procedure
via the typed data-access primitive (``docs/adr/0008``); no ad-hoc SQL lives here.
"""

from __future__ import annotations

from app.core.db import execute_procedure_pydantic
from app.modules.customers.schemas import CustomerLookup


def search_customers(query: str | None, limit: int) -> list[CustomerLookup]:
    """Return customers whose name contains ``query``, ordered by name.

    Args:
        query: Case-insensitive name fragment (``@Query``); ``None`` or empty
            matches every customer. The procedure escapes LIKE wildcards.
        limit: Maximum rows to return (``@Top``).

    Returns:
        The matching customers (id + name only).

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    return execute_procedure_pydantic(
        "onboarding.SearchCustomers", CustomerLookup, (query, limit)
    )
