"""Small, reusable builders for integration-style tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import threading
from typing import TYPE_CHECKING, cast

from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from wsgiref.simple_server import WSGIServer

from easyprent_accounting.db import SCHEMA, initialize_database
from tests.fixtures.demo_data import seed_demo_data
from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig, SenderAddress, get_global_config, set_global_config
from easyprent_accounting.integrations.gnucash import GnuCashReader
from easyprent_accounting.integrations.paperless import PaperlessAdapter
from easyprent_accounting.server import create_server


@contextmanager
def running_server(host: str = "127.0.0.1", port: int = 0) -> Iterator[WSGIServer]:
    server = create_server(host, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    try:
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)
    finally:
        server.server_close()


@contextmanager
def preserved_global_config() -> Iterator[None]:
    try:
        original = get_global_config()
    except RuntimeError:
        original = None
    try:
        yield
    finally:
        set_global_config(original)


@contextmanager
def mocked_global_config(config: AppConfig) -> Iterator[None]:
    with preserved_global_config():
        set_global_config(config)
        yield


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
        initialize_database(str(self.path))

    def seed(self) -> None:
        connection = self.connect()
        try:
            seed_demo_data(connection)
            connection.commit()
        finally:
            connection.close()


def asgi_test_client(
    database: TemporaryDatabase,
    *,
    gnucash_reader: GnuCashReader | None = None,
    paperless: PaperlessAdapter | None = None,
) -> TestClient:
    """Create an isolated HTTP client using the real ASGI composition root."""
    config = AppConfig(
        db_path=database.path,
        project_root=database.path.parent,
        sender=SenderAddress(),
    )
    return TestClient(
        create_asgi_app(config, gnucash_reader=gnucash_reader, paperless=paperless),
        raise_server_exceptions=False,
    )


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
    """Expose an isolated on-disk database."""
    with tempfile.TemporaryDirectory() as directory:
        database = TemporaryDatabase(Path(directory) / "easyprent_accounting.db")
        if initialized:
            database.initialize()
        if seeded:
            database.seed()
        yield database


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
        headers=dict(cast(list[tuple[str, str]], status_headers["headers"])),
        body=response_body,
    )
