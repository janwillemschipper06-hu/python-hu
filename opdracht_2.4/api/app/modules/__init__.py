"""Feature modules — one package per domain (feature-first).

Each module groups its own HTTP router, Pydantic schemas, data-access
repository, and service logic together, so a feature is changed in one place
rather than spread across layer-first folders. New domains (projects, tasks,
templates, secrets, notifications, audit, reports, …) each get their own package
here.
"""
