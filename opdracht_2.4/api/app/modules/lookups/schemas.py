"""API schemas for the lookups module."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LookupKind(StrEnum):
    """Which dropdown an option belongs to (``LookupOption.Kind``)."""

    department = "Department"
    source_system = "SourceSystem"
    content_pack = "ContentPack"
    installation_type = "InstallationType"
    power_bi_license = "PowerBILicense"
    environment_connection = "EnvironmentConnection"
    migration_type = "MigrationType"


class LookupOption(BaseModel):
    """One dropdown option; aliases match the ``ListLookupOptions`` columns."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(validation_alias="Id")
    kind: LookupKind = Field(validation_alias="Kind")
    name: str = Field(validation_alias="Name")
    family: str | None = Field(default=None, validation_alias="Family")
    pack_kind: str | None = Field(default=None, validation_alias="PackKind")
    excluded_source_system_id: int | None = Field(
        default=None, validation_alias="ExcludedSourceSystemId"
    )
    allows_free_text: bool = Field(validation_alias="AllowsFreeText")
    sort_order: int = Field(validation_alias="SortOrder")
    is_active: bool = Field(validation_alias="IsActive")
