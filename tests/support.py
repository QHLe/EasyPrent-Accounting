"""Small, reusable builders for integration-style tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import sqlite3
import tempfile

from src.easyprent_accounting.db import SCHEMA, initialize_database, seed_demo_data


@dataclass(frozen=True)
class WsgiResponse:
    status: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class TemporaryDatabase:
    path: Path

    def connect(self, *, rows: bool = False) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        if rows:
            connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        initialize_database()

    def seed(self) -> None:
        connection = self.connect()
        try:
            seed_demo_data(connection)
            connection.commit()
        finally:
            connection.close()


def in_memory_database(*, seeded: bool = True) -> sqlite3.Connection:
    """Create a schema-ready SQLite connection for a test's exclusive use."""

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    if seeded:
        seed_demo_data(connection)
        connection.commit()
    return connection


@contextmanager
def temporary_database(
    *, initialized: bool = True, seeded: bool = False
) -> Iterator[TemporaryDatabase]:
    """Expose an isolated on-disk database through the application's config seam."""

    original_database_path = os.environ.get("EASYPRENT_DB_PATH")
    with tempfile.TemporaryDirectory() as directory:
        database = TemporaryDatabase(Path(directory) / "easyprent_accounting.db")
        os.environ["EASYPRENT_DB_PATH"] = str(database.path)
        try:
            if initialized:
                database.initialize()
            if seeded:
                database.seed()
            yield database
        finally:
            if original_database_path is None:
                os.environ.pop("EASYPRENT_DB_PATH", None)
            else:
                os.environ["EASYPRENT_DB_PATH"] = original_database_path


def call_wsgi_application(
    application: Callable[..., Iterator[bytes]],
    *,
    method: str,
    path: str,
    body: bytes = b"",
    query_string: str = "",
    content_type: str = "application/json",
) -> WsgiResponse:
    """Call a WSGI application and collect its observable HTTP response."""

    status_headers: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        status_headers["status"] = status
        status_headers["headers"] = headers

    response_iterable = application(
        {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": content_type,
            "wsgi.input": BytesIO(body),
        },
        start_response,
    )
    try:
        response_body = b"".join(response_iterable)
    finally:
        close = getattr(response_iterable, "close", None)
        if close is not None:
            close()

    return WsgiResponse(
        status=str(status_headers["status"]),
        headers=dict(status_headers["headers"]),
        body=response_body,
    )
