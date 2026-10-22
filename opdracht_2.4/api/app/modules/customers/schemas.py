"""API schemas for the customers module."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CustomerLookup(BaseModel):
    """One customer option for the Project customer picker (id + name only).

    The ``validation_alias``es match the ``onboarding.SearchCustomers`` result
    columns so rows validate directly from the procedure output.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(validation_alias="Id")
    name: str = Field(validation_alias="Name")
