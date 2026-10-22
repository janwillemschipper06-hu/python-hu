"""Business logic for the customers module (router -> service -> repository)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.customers import repository

if TYPE_CHECKING:
    from app.modules.customers.schemas import CustomerLookup


def search_customers(query: str | None, limit: int) -> list[CustomerLookup]:
    """Return the customer options matching a name fragment (blank = all)."""
    return repository.search_customers((query or "").strip() or None, limit)
