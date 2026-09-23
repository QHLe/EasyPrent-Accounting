"""Version-one database preflight for application startup."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import sqlite3

from .legacy_schema import schema_fingerprint
from .schema_runner import Migration, MigrationError, run_migrations, schema_version
from .schema_v1 import EXPECTED_SCHEMA_FINGERPRINT, apply_schema_v1


MIGRATIONS = (Migration(1, "initial schema v1", apply_schema_v1),)


def _migration_instruction(path: Path) -> str:
    database = shlex.quote(str(path))
    return (
        f"Database {path} is not schema version 1. "
        f"Run `easyprent-accounting migrate --database {database} --dry-run` "
        f"to validate it, then `easyprent-accounting migrate --database {database} "
        "--cutover` to activate the migrated database."
    )


def _initialize_empty_database(path: Path, *, newly_created: bool) -> None:
    try:
        connection = sqlite3.connect(path)
        try:
            run_migrations(connection, MIGRATIONS)
        finally:
            connection.close()
    except BaseException:
        if newly_created:
            path.unlink(missing_ok=True)
        raise


def prepare_database(path: Path) -> None:
    """Accept v1, create v1 for an empty path, and never write to legacy data."""

    path = path.expanduser().resolve()
    if not path.exists():
        if not path.parent.is_dir():
            raise RuntimeError(f"Database directory does not exist: {path.parent}")
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return prepare_database(path)
        os.close(descriptor)
        _initialize_empty_database(path, newly_created=True)
        return

    if not path.is_file():
        raise RuntimeError(f"Database path is not a file: {path}")

    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            version = schema_version(connection)
            if version == 1:
                run_migrations(connection, MIGRATIONS)
                if schema_fingerprint(connection) != EXPECTED_SCHEMA_FINGERPRINT:
                    raise RuntimeError(f"Database {path} has an unexpected schema v1 layout.")
                return
            if version != 0:
                raise RuntimeError(f"Database {path} has unsupported schema version {version}.")
        finally:
            connection.close()
    except MigrationError as error:
        raise RuntimeError(_migration_instruction(path)) from error
    except sqlite3.DatabaseError as error:
        raise RuntimeError(f"Database {path} could not be read: {error}") from error

    # schema_version == 0 means there are no application tables. The runner
    # checks again before writing, so a concurrent schema change is rejected.
    try:
        _initialize_empty_database(path, newly_created=False)
    except MigrationError as error:
        raise RuntimeError(_migration_instruction(path)) from error
