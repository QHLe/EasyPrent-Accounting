"""Request-scoped SQLite connections and application-owned write transactions."""

from __future__ import annotations

from collections.abc import Iterator
import sqlite3
from typing import Annotated

from fastapi import Depends, Request

from .db import get_connection


def get_read_connection(request: Request) -> Iterator[sqlite3.Connection]:
    """Open one connection for a synchronous HTTP use case and close it afterwards.

    FastAPI runs synchronous dependencies and endpoints in worker threads, which
    are not guaranteed to be the same thread. The connection is confined to one
    request, but SQLite's thread ownership check must therefore be disabled.
    """

    connection = get_connection(request.app.state.config.db_path, check_same_thread=False)
    try:
        yield connection
    finally:
        connection.close()


def get_write_connection(
    connection: Annotated[sqlite3.Connection, Depends(get_read_connection, scope="function")],
) -> Iterator[sqlite3.Connection]:
    """Wrap one write use case in a single explicit transaction."""

    connection.execute("BEGIN")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


ReadConnection = Annotated[
    sqlite3.Connection, Depends(get_read_connection, scope="function")
]
WriteConnection = Annotated[
    sqlite3.Connection, Depends(get_write_connection, scope="function")
]
