"""Extraction module — the machine-only reporting feed (``Extract.Read``).

Kept apart from the interactive admin/portal surface because it has a different
auth model (an allow-listed application identity, no user context) and read-only
query patterns (``docs/authentication-and-access.md`` §4).
"""
