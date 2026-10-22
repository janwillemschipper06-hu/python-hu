"""Session module — the role-agnostic ``whoami`` identity echo.

A thin diagnostic that reflects the platform-validated caller
(:class:`~app.core.security.ClientPrincipal`) back to any authenticated user so
an operator can confirm the token's ``roles`` claim reaches the API end to end.
Its router is mounted under the **portal** authorization tier in :mod:`app.api`
(any authenticated caller), which is why it is a module of its own and not part
of :mod:`app.modules.users`: echoing a caller's own claims is not user
management. The SPA chooses its view from the same claim, but only the API's view
is authoritative (``docs/authentication-and-access.md`` §2.2).
"""
