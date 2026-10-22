"""API schemas for the projects module — Project header requests and views.

The Project header plus the type-specific Installation/Migration definitions
(``docs/projects-design.md`` §5).
"""

from __future__ import annotations

import json
from datetime import date, datetime  # noqa: TC003 (pydantic needs them at runtime)
from enum import StrEnum
from uuid import UUID  # noqa: TC003 (pydantic needs it at runtime)

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_HOURS = 100_000


class ProjectType(StrEnum):
    """What the Project delivers; fixed at creation."""

    installation = "Installation"
    migration = "Migration"


class ProjectState(StrEnum):
    """Lifecycle state (``docs/projects-design.md`` §4)."""

    draft = "Draft"
    requested = "Requested"
    approved = "Approved"
    in_progress = "InProgress"
    ready = "Ready"
    on_hold = "OnHold"
    cancelled = "Cancelled"


class CustomerType(StrEnum):
    """Direct (9altitudes-SmartInsights) or Indirect (Dynalogic-Birds) customer."""

    direct = "Direct"
    indirect = "Indirect"


def _strip_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        msg = "Name must not be blank"
        raise ValueError(msg)
    return stripped


class ProjectCreate(BaseModel):
    """A PM's/Admin's request to create a ``Draft`` Project.

    ``requester_oid`` defaults to the caller; set it to hand the Project to
    another PM (the service checks that person holds the PM or Admin role).
    """

    customer_id: int = Field(ge=1)
    type: ProjectType
    name: str = Field(min_length=1, max_length=200)
    requester_oid: UUID | None = None
    department_id: int | None = Field(default=None, ge=1)
    customer_type: CustomerType | None = None
    deadline: date | None = None
    hours: int | None = Field(default=None, ge=0, le=_MAX_HOURS)
    request_notes: str | None = Field(default=None, max_length=20_000)

    _name = field_validator("name")(_strip_name)


class ProjectUpdate(BaseModel):
    """A partial update of the Project header (PATCH).

    Only fields present in the request body change; sending ``null`` for a
    nullable field clears it. ``type`` is immutable and therefore absent.
    ``consultant_oid`` is Admin-only and cannot be cleared.
    """

    customer_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    requester_oid: UUID | None = None
    consultant_oid: UUID | None = None
    department_id: int | None = Field(default=None, ge=1)
    customer_type: CustomerType | None = None
    deadline: date | None = None
    hours: int | None = Field(default=None, ge=0, le=_MAX_HOURS)
    request_notes: str | None = Field(default=None, max_length=20_000)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_name(value)


class Project(BaseModel):
    """One Project as the caller may see it.

    The ``validation_alias``es match the ``GetProject`` / ``ListProjects`` result
    columns. ``hours``, ``request_notes``, ``rejection_reason`` and the ticket ids
    are ``None`` for customer users (the procedures blank them).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(validation_alias="ProjectId")
    customer_id: int = Field(validation_alias="CustomerConfigID")
    customer_name: str | None = Field(default=None, validation_alias="CustomerName")
    type: ProjectType = Field(validation_alias="Type")
    name: str = Field(validation_alias="Name")
    state: ProjectState = Field(validation_alias="State")
    rejection_reason: str | None = Field(
        default=None, validation_alias="RejectionReason"
    )
    requester_oid: str = Field(validation_alias="RequesterOid")
    requester_email: str = Field(validation_alias="RequesterEmail")
    created_by_email: str = Field(validation_alias="CreatedByEmail")
    department_id: int | None = Field(default=None, validation_alias="DepartmentId")
    customer_type: CustomerType | None = Field(
        default=None, validation_alias="CustomerType"
    )
    deadline: date | None = Field(default=None, validation_alias="Deadline")
    hours: int | None = Field(default=None, validation_alias="Hours")
    request_notes: str | None = Field(default=None, validation_alias="RequestNotes")
    consultant_email: str | None = Field(
        default=None, validation_alias="ConsultantEmail"
    )
    request_ticket_id: int | None = Field(
        default=None, validation_alias="RequestTicketId"
    )
    communication_ticket_id: int | None = Field(
        default=None, validation_alias="CommunicationTicketId"
    )
    created_utc: datetime = Field(validation_alias="CreatedUtc")
    updated_utc: datetime = Field(validation_alias="UpdatedUtc")

    @field_validator("requester_oid")
    @classmethod
    def _lowercase_oid(cls, value: str) -> str:
        """Normalise SQL Server's uppercase GUID to Entra's lowercase form."""
        return value.lower()


class MutationResult(BaseModel):
    """The ``(Outcome, ProjectId)`` row every Project write procedure returns."""

    model_config = ConfigDict(populate_by_name=True)

    outcome: str = Field(validation_alias="Outcome")
    project_id: int | None = Field(default=None, validation_alias="ProjectId")


class Connector(BaseModel):
    """One source-system connector of an Installation (``ProjectConnector``).

    ``companies_to_extract`` applies to the AX/F&O and NAV/BC families only;
    ``content_pack_ids`` must be packs of the source system's family (none for SQL
    Server). The service enforces both. The aliases match the
    ``ListProjectConnectors`` columns.
    """

    model_config = ConfigDict(populate_by_name=True)

    source_system_id: int = Field(ge=1, validation_alias="SourceSystemId")
    license_count: int = Field(ge=1, le=5, validation_alias="LicenseCount")
    companies_to_extract: int | None = Field(
        default=None, ge=1, validation_alias="CompaniesToExtract"
    )
    content_pack_ids: list[int] = Field(
        default_factory=list, max_length=20, validation_alias="ContentPackIds"
    )

    @field_validator("content_pack_ids", mode="before")
    @classmethod
    def _parse_json_ids(cls, value: object) -> object:
        """The procedure returns the id list as a JSON string such as ``[1,2]``."""
        return json.loads(value) if isinstance(value, str) else value


class InstallationDefinition(BaseModel):
    """The Installation definition (a full replace on PUT).

    Every field is optional because a ``Draft`` may be saved half-filled; the
    submit step (Stage 5) checks completeness. The aliases match the
    ``GetProjectDefinition`` columns.
    """

    model_config = ConfigDict(populate_by_name=True)

    installation_type_id: int | None = Field(
        default=None, ge=1, validation_alias="PreferredInstallationTypeId"
    )
    power_bi_license_id: int | None = Field(
        default=None, ge=1, validation_alias="PreferredPowerBILicenseId"
    )
    env_development: bool | None = Field(
        default=None, validation_alias="EnvDevelopment"
    )
    env_test: bool | None = Field(default=None, validation_alias="EnvTest")
    env_acceptance: bool | None = Field(default=None, validation_alias="EnvAcceptance")
    env_production: bool | None = Field(default=None, validation_alias="EnvProduction")
    environment_connection_id: int | None = Field(
        default=None, ge=1, validation_alias="EnvironmentConnectionId"
    )
    environment_connection_other: str | None = Field(
        default=None, max_length=500, validation_alias="EnvironmentConnectionOther"
    )
    azure_subscription_by_us: bool | None = Field(
        default=None, validation_alias="AzureSubscriptionByUs"
    )
    power_bi_license_by_us: bool | None = Field(
        default=None, validation_alias="PowerBILicenseByUs"
    )
    power_bi_licenses_sold: int | None = Field(
        default=None, ge=0, le=_MAX_HOURS, validation_alias="PowerBILicensesSold"
    )
    azure_costs_informed: bool | None = Field(
        default=None, validation_alias="AzureCostsInformed"
    )
    signed_software_agreement: bool | None = Field(
        default=None, validation_alias="SignedSoftwareAgreement"
    )
    teams_channel_added: bool | None = Field(
        default=None, validation_alias="TeamsChannelAdded"
    )
    teams_channel_url: str | None = Field(
        default=None, max_length=2048, validation_alias="TeamsChannelUrl"
    )
    connectors: list[Connector] = Field(default_factory=list, max_length=3)

    @field_validator("environment_connection_other", "teams_channel_url")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None

    @field_validator("teams_channel_url")
    @classmethod
    def _https_url(cls, value: str | None) -> str | None:
        if value is not None and not value.lower().startswith("https://"):
            msg = "Teams channel URL must start with https://"
            raise ValueError(msg)
        return value


class MigrationDefinition(BaseModel):
    """The Migration definition (a full replace on PUT); aliases match the procedure."""

    model_config = ConfigDict(populate_by_name=True)

    migration_type_id: int | None = Field(
        default=None, ge=1, validation_alias="MigrationTypeId"
    )
    migration_information: str | None = Field(
        default=None, max_length=20_000, validation_alias="MigrationInformation"
    )

    @field_validator("migration_information")
    @classmethod
    def _blank_info_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class DefinitionRow(InstallationDefinition, MigrationDefinition):
    """The single ``GetProjectDefinition`` row: both definitions' columns plus the type."""

    type: ProjectType = Field(validation_alias="Type")


class ProjectDefinition(BaseModel):
    """The definition of a Project: ``installation`` or ``migration`` per its type."""

    type: ProjectType
    installation: InstallationDefinition | None = None
    migration: MigrationDefinition | None = None


class Requester(BaseModel):
    """A person who may be set as a Project's requester (an active PM or Admin)."""

    oid: str
    email: str
