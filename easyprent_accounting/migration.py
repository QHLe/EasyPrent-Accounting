"""Explicit, out-of-place migration of the one frozen pre-v1 SQLite schema."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
from collections.abc import Iterator
import uuid


@dataclass(frozen=True)
class MigrationOutcome:
    report: dict[str, object]
    backup_path: Path
    report_path: Path
    activated: bool


@dataclass(frozen=True)
class RestoreOutcome:
    pre_restore_backup: Path | None
    report_path: Path
    directory_synced: bool
    report_update_failed: bool


class MigrationFailure(RuntimeError):
    def __init__(self, message: str, report: dict[str, object] | None = None):
        super().__init__(message)
        self.report = report or {
            "success": False, "errors": [{"code": "migration_failed", "reason": message}],
        }


@contextmanager
def _readonly_connection(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def _content_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for statement in connection.iterdump():
        digest.update(statement.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _check_integrity(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise MigrationFailure(f"SQLite integrity_check failed: {result}")


def _wal_sidecars_or_mode(active: Path, connection: sqlite3.Connection) -> bool:
    """A main-file rename cannot atomically replace SQLite WAL sidecars."""

    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    return journal_mode == "wal" or any(
        Path(str(active) + suffix).exists() for suffix in ("-wal", "-shm")
    )


def _dated_sidecar(database: Path, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = uuid.uuid4().hex[:12]
    return database.with_name(f"{database.name}.{label}-{stamp}-{token}.db")


def _dated_report(database: Path, label: str = "migration-report") -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = uuid.uuid4().hex[:12]
    return database.with_name(f"{database.name}.{label}-{stamp}-{token}.json")


def _persist_report(path: Path, report: dict[str, object]) -> None:
    """Persist and sync validation evidence before any active-path replacement."""

    if not path.parent.is_dir():
        raise MigrationFailure("validation report directory does not exist")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _persist_failure_report(path: Path, report: dict[str, object]) -> None:
    """Keep machine-readable failure evidence when the destination is writable."""

    report["success"] = False
    report["report_path"] = str(path)
    try:
        _persist_report(path, report)
    except (OSError, MigrationFailure):
        # Preserve the original migration failure if report storage also fails.
        report["report_persist_failed"] = True


def _reserve_database_file(path: Path) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)


def _backup_database(source: sqlite3.Connection, backup_path: Path) -> None:
    """Snapshot via SQLite's Backup API and prove that it can be restored."""
    _reserve_database_file(backup_path)
    try:
        backup = sqlite3.connect(backup_path)
        try:
            source.backup(backup)
        finally:
            backup.close()
        source_digest = _content_digest(source)
        with _readonly_connection(backup_path) as saved:
            _check_integrity(saved)
            if _content_digest(saved) != source_digest:
                raise MigrationFailure("Backup does not match the source snapshot")
        proof_path = _dated_sidecar(backup_path, "restore-proof")
        _reserve_database_file(proof_path)
        try:
            with _readonly_connection(backup_path) as saved:
                restored = sqlite3.connect(proof_path)
                try:
                    saved.backup(restored)
                finally:
                    restored.close()
            with _readonly_connection(proof_path) as proof:
                _check_integrity(proof)
                if _content_digest(proof) != source_digest:
                    raise MigrationFailure("Backup restore verification failed")
        finally:
            proof_path.unlink(missing_ok=True)
    except BaseException:
        backup_path.unlink(missing_ok=True)
        raise


def _fsync_database(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _preserve_active_metadata(candidate: Path, template: Path) -> None:
    """Keep the existing database owner and mode after an atomic rename."""

    original = template.stat()
    staging = candidate.stat()
    if (staging.st_uid, staging.st_gid) != (original.st_uid, original.st_gid):
        os.chown(candidate, original.st_uid, original.st_gid)
    os.chmod(candidate, stat.S_IMODE(original.st_mode))


def _activate_database(candidate: Path, active: Path) -> bool:
    _fsync_database(candidate)
    directory = os.open(active.parent, os.O_RDONLY)
    try:
        # Verify directory syncing before rename so any preflight failure leaves
        # the active path alone. Once rename succeeds, it is the activation point.
        os.fsync(directory)
        os.replace(candidate, active)
        try:
            os.fsync(directory)
        except OSError:
            return False
        return True
    finally:
        try:
            os.close(directory)
        except OSError:
            # A failed close after rename must not be reported as an aborted
            # cutover: the replacement has already happened.
            pass


def migrate_database(
    active_path: str | Path,
    *,
    cutover: bool = False,
    target_path: str | Path | None = None,
    report_path: str | Path | None = None,
) -> MigrationOutcome:
    """Validate a new v1 database from one recognized Legacy snapshot.

    Dry runs keep the active database byte-for-byte intact. A cutover is a single
    atomic rename after every validation has succeeded and the source still
    matches the saved snapshot. The dated, verified backup is retained either way.
    """

    from easyprent_accounting.legacy_mapping import map_legacy_data
    from easyprent_accounting.legacy_schema import (
        SUPPORTED_LEGACY_FINGERPRINTS, schema_fingerprint,
    )
    from easyprent_accounting.migration_validation import (
        MigrationValidationError, validate_migration,
    )
    from easyprent_accounting.schema_runner import Migration, run_migrations
    from easyprent_accounting.schema_v1 import apply_schema_v1

    active = Path(active_path).expanduser().absolute()
    if not active.is_file() or active.is_symlink():
        raise MigrationFailure("active Legacy database must be a regular file")
    if target_path is None:
        candidate = _dated_sidecar(active, "v1-staging")
    else:
        candidate = Path(target_path).expanduser().absolute()
        if candidate.parent != active.parent:
            raise MigrationFailure("target must be beside active database for atomic cutover")
    if candidate == active or candidate.exists() or candidate.is_symlink():
        raise MigrationFailure("target database already exists or is the active database")
    report_destination = (
        Path(report_path).expanduser().absolute() if report_path is not None
        else _dated_report(active)
    )
    if report_destination in (active, candidate):
        raise MigrationFailure("report path must differ from active and staging databases")
    if not report_destination.parent.is_dir():
        raise MigrationFailure("validation report directory does not exist")

    # Reject unknown layouts before creating a backup or destination file.
    with _readonly_connection(active) as original:
        fingerprint = schema_fingerprint(original)
        if fingerprint not in SUPPORTED_LEGACY_FINGERPRINTS:
            raise MigrationFailure("unknown Legacy schema fingerprint", {
                "success": False, "errors": [{"code": "unknown_schema_fingerprint", "fingerprint": fingerprint}],
            })
        if cutover and _wal_sidecars_or_mode(active, original):
            raise MigrationFailure("WAL mode or sidecars make main-file cutover unsafe", {
                "success": False, "errors": [{"code": "wal_cutover_unsafe"}],
            })
        # The peak footprint is the saved snapshot plus a restore proof or v1
        # staging database. Leave room for SQLite journals and schema growth.
        minimum_free = max(active.stat().st_size * 3, 1024 * 1024)
        if shutil.disk_usage(active.parent).free < minimum_free:
            raise MigrationFailure("insufficient free space for verified migration", {
                "success": False, "errors": [{"code": "insufficient_space"}],
            })
        backup_path = _dated_sidecar(active, "legacy-backup")
        try:
            _backup_database(original, backup_path)
        except (OSError, sqlite3.DatabaseError, MigrationFailure) as error:
            raise MigrationFailure(f"verified SQLite backup failed: {error}") from error

    report: dict[str, object] = {
        "success": False, "errors": [], "backup_path": str(backup_path), "activated": False,
    }
    try:
        _reserve_database_file(candidate)
        with _readonly_connection(backup_path) as snapshot:
            target = sqlite3.connect(candidate)
            target.row_factory = sqlite3.Row
            try:
                target.execute("PRAGMA foreign_keys = ON")
                run_migrations(target, [Migration(1, "initial schema v1", apply_schema_v1)])
                map_legacy_data(snapshot, target)
                try:
                    report = validate_migration(snapshot, target)
                except MigrationValidationError as error:
                    report = error.report
                    raise
                report["backup_path"] = str(backup_path)
                report["report_path"] = str(report_destination)
                report["cutover_requested"] = cutover
                report["activated"] = False
            finally:
                target.close()

        _persist_report(report_destination, report)
        if cutover:
            with _readonly_connection(active) as still_active, _readonly_connection(backup_path) as snapshot:
                if (schema_fingerprint(still_active) != fingerprint
                        or _content_digest(still_active) != _content_digest(snapshot)):
                    raise MigrationFailure("active database changed since the verified backup")
                if _wal_sidecars_or_mode(active, still_active):
                    raise MigrationFailure("WAL mode or sidecars appeared before cutover")
            _preserve_active_metadata(candidate, active)
            report["directory_synced"] = _activate_database(candidate, active)
            report["activated"] = True
            try:
                _persist_report(report_destination, report)
            except (OSError, MigrationFailure):
                # Validation evidence already exists. A failed status update
                # after rename must not claim that activation was aborted.
                report["report_update_failed"] = True
        return MigrationOutcome(report, backup_path, report_destination, cutover)
    except MigrationValidationError as error:
        report = error.report
        report["backup_path"] = str(backup_path)
        report["activated"] = False
        _persist_failure_report(report_destination, report)
        raise MigrationFailure("migration validation failed", report) from error
    except (OSError, sqlite3.DatabaseError, ValueError, MigrationFailure) as error:
        if isinstance(error, MigrationFailure):
            report = error.report
        else:
            report["errors"] = [{"code": "migration_failed", "reason": str(error)}]
        report["success"] = False
        report["backup_path"] = str(backup_path)
        report["activated"] = False
        _persist_failure_report(report_destination, report)
        raise MigrationFailure(str(error), report) from error
    finally:
        candidate.unlink(missing_ok=True)


def restore_database(
    backup_path: str | Path, active_path: str | Path,
    *, report_path: str | Path | None = None,
) -> RestoreOutcome:
    """Atomically restore a verified backup, retaining any pre-restore database."""
    from easyprent_accounting.legacy_schema import (
        SUPPORTED_LEGACY_FINGERPRINTS, schema_fingerprint,
    )
    from easyprent_accounting.schema_v1 import EXPECTED_SCHEMA_FINGERPRINT

    backup = Path(backup_path).expanduser().absolute()
    active = Path(active_path).expanduser().absolute()
    if not backup.is_file():
        raise MigrationFailure(f"Backup file does not exist: {backup}")
    if backup == active:
        raise MigrationFailure("Backup and active database must be different paths")
    if active.is_symlink():
        raise MigrationFailure("active database path must not be a symlink")
    if not active.parent.is_dir():
        raise MigrationFailure(f"Active database directory does not exist: {active.parent}")
    report_destination = (
        Path(report_path).expanduser().absolute() if report_path is not None
        else _dated_report(active, "restore-report")
    )
    if report_destination in (active, backup):
        raise MigrationFailure("restore report path must differ from active and backup databases")
    if not report_destination.parent.is_dir():
        raise MigrationFailure("restore report directory does not exist")
    if active.exists():
        with _readonly_connection(active) as current:
            if _wal_sidecars_or_mode(active, current):
                raise MigrationFailure("WAL mode or sidecars make main-file restore unsafe")

    with _readonly_connection(backup) as saved:
        _check_integrity(saved)
        if schema_fingerprint(saved) not in (SUPPORTED_LEGACY_FINGERPRINTS | {EXPECTED_SCHEMA_FINGERPRINT}):
            raise MigrationFailure("backup schema is neither frozen Legacy nor schema v1")
        expected_digest = _content_digest(saved)
        candidate = _dated_sidecar(active, "restore-staging")
        _reserve_database_file(candidate)
        try:
            destination = sqlite3.connect(candidate)
            try:
                saved.backup(destination)
            finally:
                destination.close()
            with _readonly_connection(candidate) as restored:
                _check_integrity(restored)
                if _content_digest(restored) != expected_digest:
                    raise MigrationFailure("Restored database does not match backup")

            preserved: Path | None = None
            if active.exists():
                preserved = _dated_sidecar(active, "pre-restore")
                with _readonly_connection(active) as current:
                    _backup_database(current, preserved)
            report: dict[str, object] = {
                "success": True,
                "restore_requested": True,
                "restored_from": str(backup),
                "active_database": str(active),
                "pre_restore_backup": str(preserved) if preserved is not None else None,
                "report_path": str(report_destination),
                "activated": False,
            }
            _persist_report(report_destination, report)
            _preserve_active_metadata(candidate, active if active.exists() else backup)
            synced = _activate_database(candidate, active)
            report["directory_synced"] = synced
            report["activated"] = True
            update_failed = False
            try:
                _persist_report(report_destination, report)
            except (OSError, MigrationFailure):
                update_failed = True
            return RestoreOutcome(preserved, report_destination, synced, update_failed)
        finally:
            candidate.unlink(missing_ok=True)
