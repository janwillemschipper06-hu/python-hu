"""Database access helpers for Azure SQL with managed identity.

The backend reaches the database only through stored procedures (``docs/adr/0002``,
``docs/adr/0008``). Two stored-procedure-only primitives share a single execution
core (:func:`_run_procedure`):

* :func:`execute_procedure` returns the procedure's rows as a ``pandas.DataFrame``.
* :func:`query_procedure` validates those rows into a Pydantic model and returns
  ``list[Model]`` — convenient for handing a result set straight to an API
  response.

Neither composes ad-hoc SQL; both only ``EXEC`` a named procedure with bound
parameters. In Azure the app authenticates with its user-assigned managed
identity (no password).
"""

from __future__ import annotations

import json
import logging
import os
import struct
import time
import urllib.request
from contextlib import closing
from typing import TYPE_CHECKING

import pandas as pd
import pyodbc
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ODBC connection attribute that carries a pre-fetched Azure AD access token.
SQL_COPT_SS_ACCESS_TOKEN = 1256

# Access-token connections must not reuse a busy pooled connection. This is a
# global pyodbc setting and must be set before the first connection is made.
pyodbc.pooling = False

# Cached (packed token, expiry as epoch seconds).
_token_cache: tuple[bytes, float] | None = None


def _get_msi_token() -> bytes:
    """Fetch (and cache) an Azure AD access token for Azure SQL via managed identity.

    Reads the Container Apps managed-identity endpoint from ``IDENTITY_ENDPOINT``
    / ``IDENTITY_HEADER``. When ``AZURE_CLIENT_ID`` is set it is passed as
    ``client_id`` so the user-assigned identity is selected explicitly.

    Returns:
        The token packed as the little-endian length-prefixed UTF-16LE byte
        string that the ODBC driver expects for ``SQL_COPT_SS_ACCESS_TOKEN``.
    """
    global _token_cache  # noqa: PLW0603

    now = time.time()
    if _token_cache is not None and now < _token_cache[1]:
        return _token_cache[0]

    url = (
        f"{os.environ['IDENTITY_ENDPOINT']}"
        "?resource=https://database.windows.net/&api-version=2019-08-01"
    )
    # A Container App with a user-assigned identity must name it explicitly, or
    # the endpoint cannot tell which identity to mint the token for.
    client_id = os.environ.get("AZURE_CLIENT_ID")
    if client_id:
        url += f"&client_id={client_id}"

    req = urllib.request.Request(  # noqa: S310
        url,
        headers={"X-IDENTITY-HEADER": os.environ["IDENTITY_HEADER"]},
    )
    # The URL is the trusted Container Apps managed-identity endpoint.
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        token = str(json.loads(resp.read())["access_token"])

    raw = token.encode("utf-16-le")
    packed = struct.pack("<i", len(raw)) + raw

    # Cache for 50 minutes, safely below the 1-hour token lifetime.
    _token_cache = (packed, now + 50 * 60)
    return packed


def _run_procedure(
    proc: str, params: Sequence[object]
) -> tuple[list[str], list[tuple[object, ...]]]:
    """Execute a stored procedure and return its ``(columns, rows)``.

    The single execution core shared by :func:`execute_procedure` and
    :func:`query_procedure`: it opens the managed-identity connection, ``EXEC``s
    the named procedure with bound ODBC parameters, and returns the raw column
    names and row tuples (both empty when the procedure yields no result set).

    Requires ``SQL_SERVER`` and ``SQL_DATABASE``. Runs with autocommit, so the
    procedure must handle its own transaction if it needs atomicity.
    """
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={os.environ['SQL_SERVER']};"
        f"Database={os.environ['SQL_DATABASE']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )
    placeholders = ", ".join("?" for _ in params)
    sql = f"EXEC {proc} {placeholders}".strip()

    try:
        with closing(
            pyodbc.connect(
                conn_str,
                attrs_before={SQL_COPT_SS_ACCESS_TOKEN: _get_msi_token()},
                autocommit=True,
            )
        ) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            if (
                cur.description is None
            ):  # pyright: ignore[reportUnnecessaryComparison]  # stub says non-optional
                return [], []
            cols = [c[0] for c in cur.description]
            rows = [tuple(r) for r in cur.fetchall()]
            return cols, rows
    except Exception:
        logger.exception("Stored procedure %s failed", proc)
        raise


def call_procedure(proc: str, params: Sequence[object] = ()) -> None:
    """Execute a stored procedure for its side effect, discarding any result set.

    Use this for the write-path procedures (``UpsertUser``, ``AppendAuditEvent`` …) whose returned rows, if any, are not needed. Scope and
    history integrity are enforced inside the procedure (``docs/adr/0002``,
    ``docs/adr/0008``); this helper only invokes it.

    Args:
        proc: The schema-qualified stored-procedure name.
        params: Positional parameters bound to the procedure, in declaration order.

    Raises:
        pyodbc.Error: On any database error (surfaced by the app as a JSON 500).
    """
    _run_procedure(proc, params)


def execute_procedure_pandas(proc: str, params: Sequence[object] = ()) -> pd.DataFrame:
    """Run a stored procedure and return its rows as a ``pandas.DataFrame``.

    Returns an empty frame when the procedure yields no result set. Use this when
    you need tabular data for further processing; use :func:`query_procedure` to
    get validated Pydantic models straight back.
    """
    cols, rows = _run_procedure(proc, params)
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame.from_records(rows, columns=cols)


def execute_procedure_pydantic[ModelT: BaseModel](
    proc: str,
    model: type[ModelT],
    params: Sequence[object] = (),
) -> list[ModelT]:
    """Run a stored procedure and validate each row into ``model``.

    Maps every result row to a ``dict`` keyed by the procedure's output column
    names and validates it with ``model.model_validate``, returning ``list[model]``
    (empty when the procedure returns no rows). Column names must match the
    model's field names or their ``validation_alias`` — which lets a service hand
    a result set straight to an API response without a hand-written column map.
    """
    cols, rows = _run_procedure(proc, params)
    return [model.model_validate(dict(zip(cols, row, strict=True))) for row in rows]
