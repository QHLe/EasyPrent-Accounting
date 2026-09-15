"""Validate a completed out-of-place Legacy-to-v1 database migration.

The report contains hashes and aggregate monetary values, never document contents,
credentials, or GnuCash identifiers. A failed validation raises with the same report
so a dry run or cutover can still persist a machine-readable diagnosis.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import sqlite3
from typing import Any

from easyprent_accounting.legacy_mapping import (
    resolved_lease_accounts,
    resolved_payment_leases,
)
from easyprent_accounting.schema_runner import MigrationError, schema_version


EXPECTED_VERSION = 1
_TRANSFORMED_COLUMNS = {
    "leases": {"gnucash_nk_account_guid", "gnucash_nk_account_name"},
    "gnucash_payments": {"lease_id"},
}


class MigrationValidationError(ValueError):
    """The destination cannot be activated; ``report`` explains why."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(f"migration validation failed ({len(report['errors'])} errors)")


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        if row[0] != "sqlite_sequence"
    }


def _columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
    )


def _canonical(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"blob_sha256": sha256(value).hexdigest(), "size": len(value)}
    if isinstance(value, float):
        return format(Decimal(str(value)).normalize(), "f")
    return value


def _checksum(
    connection: sqlite3.Connection, table: str, columns: tuple[str, ...]
) -> str:
    digest = sha256()
    selected = ", ".join(_quote(column) for column in columns)
    for row in connection.execute(
        f"SELECT {selected} FROM {_quote(table)} ORDER BY id"
    ):
        encoded = json.dumps(
            [_canonical(value) for value in row],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    return digest.hexdigest()


def _foreign_key_violations(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {"table": str(row[0]), "rowid": row[1], "parent": str(row[2]), "fkid": row[3]}
        for row in connection.execute("PRAGMA foreign_key_check")
    ]


def _money(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("invalid monetary value") from error
    if not amount.is_finite():
        raise ValueError("non-finite monetary value")
    return amount


def _year(value: Any) -> str:
    try:
        return str(date.fromisoformat(str(value)).year)
    except ValueError as error:
        raise ValueError("invalid monetary grouping date") from error


def _money_groups(connection: sqlite3.Connection) -> dict[tuple[str, ...], Decimal]:
    """Group local business money by year, object, and category using Decimal."""

    totals: dict[tuple[str, ...], Decimal] = defaultdict(Decimal)
    for period, object_type, object_id, category, amount in connection.execute(
        "SELECT period_start, object_type, object_id, expense_category, amount "
        "FROM expense_items"
    ):
        key = ("expenses", _year(period), str(object_type), str(object_id), str(category))
        totals[key] += _money(amount)

    for started, unit_id, rent, advance in connection.execute(
        "SELECT start_date, unit_id, rent_cold, additional_charges_advance FROM leases"
    ):
        prefix = ("leases", _year(started), "unit", str(unit_id))
        totals[(*prefix, "rent_cold")] += _money(rent)
        totals[(*prefix, "additional_charges_advance")] += _money(advance)

    for booked, tenant_id, amount in connection.execute(
        "SELECT booking_date, tenant_id, amount FROM gnucash_payments"
    ):
        totals[("payments", _year(booked), "tenant", str(tenant_id), "amount")] += _money(amount)

    for period, lease_id, status, amount in connection.execute(
        "SELECT sr.period_start, spa.lease_id, spa.status, spa.assigned_amount "
        "FROM settlement_payment_assignments spa "
        "JOIN settlement_runs sr ON sr.id = spa.settlement_id"
    ):
        totals[("assignments", _year(period), "lease", str(lease_id), str(status))] += _money(amount)

    for placed, property_id, amount in connection.execute(
        "SELECT placed_in_service, property_id, acquisition_cost FROM depreciation_assets"
    ):
        totals[("depreciation", _year(placed), "property", str(property_id), "acquisition_cost")] += _money(amount)
    return totals


def _link_errors(source: sqlite3.Connection, target: sqlite3.Connection) -> list[dict[str, Any]]:
    """Compare transformed links to the explicit mapping, without logging GUIDs."""

    expected_accounts = resolved_lease_accounts(source)
    expected_payments = resolved_payment_leases(source, expected_accounts)
    target_accounts = {
        int(row[0]): (row[1], row[2])
        for row in target.execute(
            "SELECT id, gnucash_nk_account_guid, gnucash_nk_account_name FROM leases"
        )
    }
    target_payments = {
        int(row[0]): int(row[1])
        for row in target.execute("SELECT id, lease_id FROM gnucash_payments")
        if row[1] is not None
    }
    errors: list[dict[str, Any]] = []
    for lease_id, expected in expected_accounts.items():
        if target_accounts.get(lease_id) != expected:
            errors.append({"code": "lease_account_link", "lease_id": lease_id})
    for payment_id, expected_lease_id in expected_payments.items():
        if target_payments.get(payment_id) != expected_lease_id:
            errors.append({"code": "payment_lease_link", "payment_id": payment_id})
    return errors


def _validate_migration(
    source: sqlite3.Connection, target: sqlite3.Connection
) -> dict[str, Any]:
    """Return a JSON-safe report or raise ``MigrationValidationError`` with it.

    Both connections are read only for the duration of this function. The caller
    must keep the destination inactive until this report succeeds.
    """

    from easyprent_accounting.legacy_schema import (
        SOURCE_TABLES, SUPPORTED_LEGACY_FINGERPRINTS, schema_fingerprint,
    )
    from easyprent_accounting.schema_v1 import (
        APPLICATION_TABLES, EXPECTED_COLUMNS, EXPECTED_SCHEMA_FINGERPRINT,
    )

    report: dict[str, Any] = {
        "schema_version": {"source": None, "target": None, "expected": EXPECTED_VERSION},
        "schema_fingerprint": {},
        "table_counts": {},
        "foreign_key_check": {},
        "integrity_check": {},
        "checksums": {},
        "monetary_totals": [],
        "link_checks": {"errors": []},
        "errors": [],
        "success": False,
    }
    errors: list[dict[str, Any]] = report["errors"]
    source_tables = _tables(source)
    target_tables = _tables(target)
    required_source = set(SOURCE_TABLES)
    required_target = set(APPLICATION_TABLES) | {"schema_migrations"}
    if source_tables != required_source:
        errors.append({"code": "source_tables", "missing": sorted(required_source - source_tables),
                       "extra": sorted(source_tables - required_source)})
    if target_tables != required_target:
        errors.append({"code": "target_tables", "missing": sorted(required_target - target_tables),
                       "extra": sorted(target_tables - required_target)})

    source_fingerprint = schema_fingerprint(source)
    target_fingerprint = schema_fingerprint(target)
    report["schema_fingerprint"] = {
        "source": source_fingerprint,
        "source_supported": source_fingerprint in SUPPORTED_LEGACY_FINGERPRINTS,
        "target": target_fingerprint,
        "expected_target": EXPECTED_SCHEMA_FINGERPRINT,
        "target_match": target_fingerprint == EXPECTED_SCHEMA_FINGERPRINT,
    }
    if source_fingerprint not in SUPPORTED_LEGACY_FINGERPRINTS:
        errors.append({"code": "source_schema_fingerprint"})
    if target_fingerprint != EXPECTED_SCHEMA_FINGERPRINT:
        errors.append({"code": "target_schema_fingerprint"})

    report["schema_version"]["source"] = int(source.execute("PRAGMA user_version").fetchone()[0])
    if report["schema_version"]["source"] != 0:
        errors.append({"code": "source_schema_version"})
    try:
        report["schema_version"]["target"] = schema_version(target)
    except MigrationError as error:
        errors.append({"code": "target_schema_version", "reason": str(error)})
    if report["schema_version"]["target"] != EXPECTED_VERSION:
        errors.append({"code": "wrong_target_schema_version"})

    for table in APPLICATION_TABLES:
        if table not in source_tables or table not in target_tables:
            continue
        actual_columns = _columns(target, table)
        if actual_columns != EXPECTED_COLUMNS[table]:
            errors.append({"code": "target_columns", "table": table,
                           "expected": list(EXPECTED_COLUMNS[table]), "actual": list(actual_columns)})
        source_count = int(source.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0])
        target_count = int(target.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()[0])
        matches = source_count == target_count
        report["table_counts"][table] = {"source": source_count, "target": target_count,
                                          "match": matches}
        if not matches:
            errors.append({"code": "row_count", "table": table})
        source_columns = set(_columns(source, table))
        stable_columns = tuple(
            column for column in EXPECTED_COLUMNS[table]
            if column in source_columns and column in actual_columns
            and column not in _TRANSFORMED_COLUMNS.get(table, ())
        )
        if not stable_columns or "id" not in stable_columns:
            errors.append({"code": "uncheckable_rows", "table": table})
            continue
        source_hash = _checksum(source, table, stable_columns)
        target_hash = _checksum(target, table, stable_columns)
        checksum_matches = source_hash == target_hash
        report["checksums"][table] = {"columns": list(stable_columns),
                                       "source": source_hash, "target": target_hash,
                                       "match": checksum_matches}
        if not checksum_matches:
            errors.append({"code": "row_checksum", "table": table})

    for label, connection in (("source", source), ("target", target)):
        violations = _foreign_key_violations(connection)
        report["foreign_key_check"][label] = violations
        if violations:
            errors.append({"code": "foreign_key", "database": label})
        integrity = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
        report["integrity_check"][label] = integrity
        if integrity != ["ok"]:
            errors.append({"code": "sqlite_integrity", "database": label})

    if required_source <= source_tables and set(APPLICATION_TABLES) <= target_tables:
        try:
            source_money = _money_groups(source)
            target_money = _money_groups(target)
            for key in sorted(source_money.keys() | target_money.keys()):
                source_total = source_money.get(key, Decimal(0))
                target_total = target_money.get(key, Decimal(0))
                matches = source_total == target_total
                report["monetary_totals"].append({
                    "family": key[0], "year": key[1], "object_type": key[2],
                    "object_id": key[3],
                    "category_sha256": sha256(key[4].encode("utf-8")).hexdigest(),
                    "source": format(source_total, "f"),
                    "target": format(target_total, "f"), "match": matches,
                })
                if not matches:
                    errors.append({
                        "code": "monetary_total", "family": key[0], "year": key[1],
                        "object_type": key[2], "object_id": key[3],
                        "category_sha256": sha256(key[4].encode("utf-8")).hexdigest(),
                    })
            link_errors = _link_errors(source, target)
            report["link_checks"]["errors"] = link_errors
            errors.extend(link_errors)
        except (sqlite3.DatabaseError, ValueError) as error:
            errors.append({"code": "business_checks_unavailable", "reason": str(error)})

    report["success"] = not errors
    if errors:
        raise MigrationValidationError(report)
    return report


def validate_migration(
    source: sqlite3.Connection, target: sqlite3.Connection
) -> dict[str, Any]:
    """Return a JSON-safe report, or raise with a JSON-safe failed report."""

    try:
        return _validate_migration(source, target)
    except sqlite3.DatabaseError as error:
        report = {
            "schema_version": {"source": None, "target": None, "expected": EXPECTED_VERSION},
            "schema_fingerprint": {},
            "table_counts": {}, "foreign_key_check": {}, "integrity_check": {},
            "checksums": {}, "monetary_totals": [], "link_checks": {"errors": []},
            "errors": [{"code": "sqlite_check_unavailable", "reason": type(error).__name__}],
            "success": False,
        }
        raise MigrationValidationError(report) from error
