"""Users module — admin-only invite, provisioning, and user lifecycle.

The admin surface for managing portal users: invite-and-provision, list, resend,
customer-scope changes, promote/demote, (de)activate, and delete. Its router is
mounted under the **admin** authorization tier in :mod:`app.api`, so every
endpoint is admin-only (``docs/authentication-and-access.md`` §4.2). The
role-agnostic ``whoami`` echo lives in :mod:`app.modules.session` — it is not
user management.

Layers: :mod:`~app.modules.users.schemas` (API models),
:mod:`~app.modules.users.repository` (stored-procedure calls),
:mod:`~app.modules.users.service` (orchestration), and
:mod:`~app.modules.users.router` (the admin HTTP endpoints).
"""
