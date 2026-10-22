"""The portal's single append-only audit trail (a cross-cutting concern).

Any module that performs an audited action (provisioning, scope changes, template
publishing, …) records it here, so this lives in ``core`` rather than inside one
feature module. The write goes through an EXECUTE-only stored procedure via
:func:`app.core.db.call_procedure`; the app principal has no direct table DML
(``docs/adr/0008``, ``docs/security-design.md`` §12). The procedure owns the
append-only guarantee — this module only binds parameters.
"""

from __future__ import annotations

from app.core.db import call_procedure


def append_audit_event(
    action: str,
    actor_oid: str | None,
    target_type: str,
    target_id: str,
    detail: str | None,
) -> None:
    """Append one row to the append-only audit trail (the only write path).

    Args:
        action: The audited action name (``@Action``).
        actor_oid: The acting principal's Entra object id (``@ActorOid``).
        target_type: The kind of entity acted on (``@TargetType``).
        target_id: The identifier of the entity acted on (``@TargetId``).
        detail: VALUE-FREE metadata only — identifiers/counts, never a secret,
            token, or request body (``@Detail``; ``docs/security-design.md`` §11.3).

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    call_procedure(
        "onboarding.AppendAuditEvent",
        (action, actor_oid, target_type, target_id, detail),
    )
