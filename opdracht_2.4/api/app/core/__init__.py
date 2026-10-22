"""Cross-cutting infrastructure shared by every feature module.

Holds the database-access primitives (:mod:`app.core.db`), the authentication
and authorization seam (:mod:`app.core.security`), and the error-handling
middleware (:mod:`app.core.errors`) — no HTTP routing and no feature business
rules of its own.
"""
