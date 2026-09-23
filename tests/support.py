"""Small, reusable builders for integration-style tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import time

from fastapi.testclient import TestClient
import uvicorn

from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig, SenderAddress, get_global_config, load_config, set_global_config
from easyprent_accounting.db import SCHEMA, initialize_database
from easyprent_accounting.runtime_schema import prepare_database
from tests.fixtures.demo_data import seed_demo_data
from easyprent_accounting.integrations.gnucash import GnuCashReader
from easyprent_accounting.integrations.paperless import PaperlessAdapter


@dataclass(frozen=True)
class RunningServer:
    server_port: int


@contextmanager
def running_server(host: str = "127.0.0.1", port: int = 0) -> Iterator[RunningServer]:
    """Serve the production ASGI app on an ephemeral local socket."""

    config = load_config(dict(os.environ))
    prepare_database(config.db_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((host, port))
    listener.listen()
    address_port = listener.getsockname()[1]
    app = create_asgi_app(config)
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=address_port, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    try:
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("ASGI server exited before startup")
            if time.monotonic() >= deadline:
                raise RuntimeError("ASGI server did not start")
            time.sleep(0.01)
        yield RunningServer(address_port)
    finally:
        server.should_exit = True
        if thread.is_alive():
            thread.join(5)
        listener.close()


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
