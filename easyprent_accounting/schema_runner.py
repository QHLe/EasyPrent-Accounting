"""Apply numbered SQLite schema changes with a transaction and a version ledger."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import sqlite3


LEDGER_TABLE = "schema_migrations"


class MigrationError(ValueError):
    """A database cannot safely advance through the supplied migrations."""


class MigrationSession:
    """Narrow SQL seam that keeps transaction control with the runner."""

    __slots__ = ("__connection",)

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.__connection = connection

    def execute(
        self, sql: str, parameters: Sequence[object] | dict[str, object] = ()
    ) -> sqlite3.Cursor:
        self._reject_transaction_sql(sql)
        return self.__connection.execute(sql, parameters)

    def executemany(
        self, sql: str, parameters: Iterable[Sequence[object] | dict[str, object]]
    ) -> sqlite3.Cursor:
        self._reject_transaction_sql(sql)
        return self.__connection.executemany(sql, parameters)

    @staticmethod
    def _reject_transaction_sql(sql: str) -> None:
        statement = sql.lstrip()
        while statement.startswith(("--", "/*")):
            if statement.startswith("--"):
                statement = statement.partition("\n")[2].lstrip()
            else:
                statement = statement.partition("*/")[2].lstrip()
        verb = statement.split(None, 1)[0].rstrip(";").upper() if statement else ""
        if verb in {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}:
            raise MigrationError("migration callback cannot control its transaction")

    def commit(self) -> None:
        raise MigrationError("migration callback cannot commit its transaction")

    def rollback(self) -> None:
        raise MigrationError("migration callback cannot roll back its transaction")

    def executescript(self, _: str) -> None:
        raise MigrationError("migration callback cannot use executescript")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[MigrationSession], None]


def _application_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        if row[0] not in ("sqlite_sequence", LEDGER_TABLE)
    }


def _history(connection: sqlite3.Connection) -> list[tuple[int, str]]:
    tables = _application_tables(connection)
    ledger_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (LEDGER_TABLE,),
    ).fetchone()
    if ledger_exists is None:
        if tables:
            raise MigrationError(
                "unversioned database cannot use the versioned migration runner"
            )
        return []
    try:
        rows = connection.execute(
            f"SELECT version, name FROM {LEDGER_TABLE} ORDER BY version"
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise MigrationError("schema migration ledger is unreadable") from error
    try:
        history = [(int(row[0]), str(row[1])) for row in rows]
    except (TypeError, ValueError) as error:
        raise MigrationError("schema migration ledger has an invalid entry") from error
    if [version for version, _ in history] != list(range(1, len(history) + 1)):
        raise MigrationError("schema migration ledger has a gap or invalid version")
    if any(not name.strip() for _, name in history):
        raise MigrationError("schema migration ledger has an unnamed entry")
    if tables and not history:
        raise MigrationError("database has application tables but no schema version")
    return history


def schema_version(connection: sqlite3.Connection) -> int:
    """Return the latest recorded version, or zero for an empty database."""

    return len(_history(connection))


def run_migrations(
    connection: sqlite3.Connection, migrations: Sequence[Migration]
) -> list[int]:
    """Apply pending migrations, each atomically with its ledger entry.

    Callbacks receive only the SQL operations they need. SQLite's
    ``executescript`` commits an open transaction before running a script, so
    the callback cannot call it or control the runner's transaction.
    """

    if connection.in_transaction:
        raise MigrationError(
            "migration runner requires a connection outside a transaction"
        )
    if [migration.version for migration in migrations] != list(range(1, len(migrations) + 1)):
        raise MigrationError("migrations must be consecutively numbered from version 1")
    if any(not migration.name.strip() for migration in migrations):
        raise MigrationError("migration names must be non-empty")

    history = _history(connection)
    if len(history) > len(migrations):
        raise MigrationError("database schema version is newer than supplied migrations")
    if any(
        recorded_name != migrations[version - 1].name
        for version, recorded_name in history
    ):
        raise MigrationError("recorded migration differs from supplied history")

    applied: list[int] = []
    for migration in migrations[len(history) :]:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            migration.apply(MigrationSession(connection))
            if not connection.in_transaction:
                raise MigrationError("migration callback ended its transaction")
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, datetime.now(UTC).isoformat()),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        applied.append(migration.version)
    return applied
