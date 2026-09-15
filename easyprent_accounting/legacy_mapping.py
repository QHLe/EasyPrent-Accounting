"""One-time, explicit mapping from the frozen Legacy database into schema v1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import sqlite3
from typing import Any


COPY_ORDER = (
    "organizations",
    "users",
    "memberships",
    "properties",
    "buildings",
    "units",
    "rooms",
    "tenants",
    "leases",
    "meters",
    "meter_readings",
    "expense_items",
    "paperless_settings",
    "application_settings",
    "gnucash_settings",
    "gnucash_payments",
    "settlement_runs",
    "settlement_payment_assignments",
    "expense_documents",
    "tenant_documents",
    "lease_documents",
    "depreciation_assets",
)


class LegacyMappingError(ValueError):
    """A source value or relationship has no unambiguous v1 representation."""


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY id')
    names = [description[0] for description in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor]


def _columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in connection.execute(f'PRAGMA table_info("{table}")'))


def _valid_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise LegacyMappingError(f"invalid {field}") from error


def _finite_decimal(value: Any, field: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise LegacyMappingError(f"invalid {field}") from error
    if not number.is_finite():
        raise LegacyMappingError(f"non-finite {field}")
    return number


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def resolved_lease_accounts(
    source: sqlite3.Connection,
) -> dict[int, tuple[str | None, str | None]]:
    """Move tenant-level NK links only when one lease is clearly intended."""

    leases = _rows(source, "leases")
    accounts: dict[int, tuple[str | None, str | None]] = {
        int(lease["id"]): (
            lease.get("gnucash_nk_account_guid"),
            lease.get("gnucash_nk_account_name"),
        )
        for lease in leases
    }
    if "gnucash_nk_account_guid" not in _columns(source, "tenants"):
        return accounts

    by_tenant: dict[int, list[dict[str, Any]]] = {}
    for lease in leases:
        by_tenant.setdefault(int(lease["tenant_id"]), []).append(lease)
    for tenant in _rows(source, "tenants"):
        guid = tenant.get("gnucash_nk_account_guid")
        name = tenant.get("gnucash_nk_account_name")
        if not _nonempty(guid):
            if _nonempty(name):
                raise LegacyMappingError("tenant account name has no account GUID")
            continue
        candidates = by_tenant.get(int(tenant["id"]), [])
        matching = [
            lease for lease in candidates
            if lease.get("gnucash_nk_account_guid") == guid
        ]
        if len(matching) == 1:
            chosen = matching[0]
        elif len(matching) > 1:
            raise LegacyMappingError("tenant account matches multiple leases")
        elif len(candidates) == 1 and not _nonempty(candidates[0].get("gnucash_nk_account_guid")):
            chosen = candidates[0]
        else:
            raise LegacyMappingError("tenant account cannot be assigned to one lease")
        lease_id = int(chosen["id"])
        existing_guid, existing_name = accounts[lease_id]
        if _nonempty(existing_guid) and existing_guid != guid:
            raise LegacyMappingError("tenant and lease account GUIDs conflict")
        if _nonempty(existing_name) and _nonempty(name) and existing_name != name:
            raise LegacyMappingError("tenant and lease account names conflict")
        accounts[lease_id] = (str(guid), str(name) if _nonempty(name) else existing_name)

    linked_guids = [guid for guid, _ in accounts.values() if _nonempty(guid)]
    if len(linked_guids) != len(set(linked_guids)):
        raise LegacyMappingError("NK account GUID is linked to multiple leases")
    return accounts


def resolved_payment_leases(
    source: sqlite3.Connection,
    accounts: dict[int, tuple[str | None, str | None]],
) -> dict[int, int]:
    """Resolve nullable Legacy payment links by account, then unique active period."""

    leases = _rows(source, "leases")
    by_id = {int(lease["id"]): lease for lease in leases}
    by_tenant: dict[int, list[dict[str, Any]]] = {}
    for lease in leases:
        by_tenant.setdefault(int(lease["tenant_id"]), []).append(lease)

    resolved: dict[int, int] = {}
    for payment in _rows(source, "gnucash_payments"):
        payment_id = int(payment["id"])
        tenant_id = int(payment["tenant_id"])
        explicit = payment.get("lease_id")
        if explicit is not None:
            explicit_lease = by_id.get(int(explicit))
            if explicit_lease is None or int(explicit_lease["tenant_id"]) != tenant_id:
                raise LegacyMappingError("payment lease reference is missing or belongs to another tenant")
            resolved[payment_id] = int(explicit)
            continue

        candidates = by_tenant.get(tenant_id, [])
        account_matches = [
            lease for lease in candidates
            if _nonempty(accounts[int(lease["id"])][0])
            and accounts[int(lease["id"])][0] == payment["account_guid"]
        ]
        if len(account_matches) > 1:
            raise LegacyMappingError("payment account matches multiple leases")
        if len(account_matches) == 1:
            resolved[payment_id] = int(account_matches[0]["id"])
            continue

        booking_date = _valid_date(payment["booking_date"], "payment booking_date")
        active = [
            lease for lease in candidates
            if _valid_date(lease["start_date"], "lease start_date") <= booking_date
            and (
                lease["end_date"] is None
                or booking_date <= _valid_date(lease["end_date"], "lease end_date")
            )
        ]
        if len(active) != 1:
            raise LegacyMappingError("payment has no unique lease by account or booking date")
        resolved[payment_id] = int(active[0]["id"])
    return resolved


def _object_exists(source: sqlite3.Connection, kind: str, identifier: int) -> bool:
    table = {
        "property": "properties", "building": "buildings",
        "unit": "units", "room": "rooms",
    }.get(kind)
    if table is None:
        return False
    return source.execute(f'SELECT 1 FROM "{table}" WHERE id = ?', (identifier,)).fetchone() is not None


def _parent_property(source: sqlite3.Connection, kind: str, identifier: int) -> int | None:
    if kind == "property":
        return identifier
    if kind == "building":
        row = source.execute("SELECT property_id FROM buildings WHERE id = ?", (identifier,)).fetchone()
        return row[0] if row else None
    if kind == "unit":
        row = source.execute(
            "SELECT b.property_id FROM units u LEFT JOIN buildings b ON b.id = u.building_id "
            "WHERE u.id = ?", (identifier,)
        ).fetchone()
        return row[0] if row else None
    row = source.execute(
        "SELECT b.property_id FROM rooms r JOIN units u ON u.id = r.unit_id "
        "LEFT JOIN buildings b ON b.id = u.building_id WHERE r.id = ?",
        (identifier,),
    ).fetchone()
    return row[0] if row else None


def _validate_source(source: sqlite3.Connection) -> None:
    if [row[0] for row in source.execute("PRAGMA integrity_check")] != ["ok"]:
        raise LegacyMappingError("source SQLite integrity check failed")
    if source.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise LegacyMappingError("source foreign key check failed")

    for room in _rows(source, "rooms"):
        if not source.execute("SELECT 1 FROM units WHERE id = ?", (room["unit_id"],)).fetchone():
            raise LegacyMappingError("room has a missing unit")
    for lease in _rows(source, "leases"):
        start = _valid_date(lease["start_date"], "lease start_date")
        if lease["end_date"] is not None and _valid_date(lease["end_date"], "lease end_date") < start:
            raise LegacyMappingError("lease period ends before it starts")
        if int(lease["occupant_count"]) < 1:
            raise LegacyMappingError("lease occupant_count must be positive")
        _finite_decimal(lease["rent_cold"], "rent_cold")
        _finite_decimal(lease["additional_charges_advance"], "additional_charges_advance")
        if lease["room_id"] is not None:
            room = source.execute("SELECT unit_id FROM rooms WHERE id = ?", (lease["room_id"],)).fetchone()
            if room is None or room[0] != lease["unit_id"]:
                raise LegacyMappingError("lease room does not belong to lease unit")

    for table in ("meters", "expense_items"):
        for row in _rows(source, table):
            kind = str(row["object_type"])
            identifier = int(row["object_id"])
            if not _object_exists(source, kind, identifier):
                raise LegacyMappingError(f"{table} has an invalid object target")
            source_property = row.get("property_id")
            ancestor = _parent_property(source, kind, identifier)
            if source_property is not None and source_property != ancestor:
                raise LegacyMappingError(f"{table} property_id conflicts with its object target")

    by_meter: dict[int, list[tuple[date, Decimal]]] = {}
    meter_ids = {int(row["id"]) for row in _rows(source, "meters")}
    for reading in _rows(source, "meter_readings"):
        meter_id = int(reading["meter_id"])
        if meter_id not in meter_ids:
            raise LegacyMappingError("reading has a missing meter")
        by_meter.setdefault(meter_id, []).append((
            _valid_date(reading["reading_date"], "reading_date"),
            _finite_decimal(reading["reading_value"], "reading_value"),
        ))
    for readings in by_meter.values():
        ordered = sorted(readings, key=lambda reading: reading[0])
        if any(current[0] == previous[0] or current[1] < previous[1]
               for previous, current in zip(ordered, ordered[1:])):
            raise LegacyMappingError("meter readings are duplicated or non-monotone")

    accepted_charge_types = {"one_time", "monthly", "quarterly", "yearly", "consumption"}
    for expense in _rows(source, "expense_items"):
        charge_type = str(expense["charge_type"])
        if charge_type not in accepted_charge_types:
            raise LegacyMappingError("expense has an unknown charge_type")
        start = _valid_date(expense["period_start"], "expense period_start")
        if expense["period_end"] is not None and _valid_date(expense["period_end"], "expense period_end") < start:
            raise LegacyMappingError("expense period ends before it starts")
        if expense["booking_date"] is not None:
            _valid_date(expense["booking_date"], "expense booking_date")
        _finite_decimal(expense["amount"], "expense amount")
        expected_recurrence = "recurring" if charge_type in {"monthly", "quarterly", "yearly"} else "one_time"
        if expense.get("recurrence") not in (None, "", expected_recurrence):
            raise LegacyMappingError("expense charge_type conflicts with recurrence")
        expected_interval = charge_type if expected_recurrence == "recurring" else None
        if expense.get("interval_name") not in (None, "", expected_interval):
            raise LegacyMappingError("expense charge_type conflicts with interval_name")
        linked_meter_id = expense.get("meter_id")
        if linked_meter_id is not None and int(linked_meter_id) not in meter_ids:
            raise LegacyMappingError("expense has a missing meter")

    for run in _rows(source, "settlement_runs"):
        start = _valid_date(run["period_start"], "settlement period_start")
        if _valid_date(run["period_end"], "settlement period_end") < start:
            raise LegacyMappingError("settlement period ends before it starts")
        if (run["property_id"] is None) == (run["unit_id"] is None):
            raise LegacyMappingError("settlement has zero or two object targets")


def map_legacy_data(source: sqlite3.Connection, target: sqlite3.Connection) -> None:
    """Copy all local entities and IDs in dependency order, or roll back all rows."""

    from easyprent_accounting.schema_v1 import APPLICATION_TABLES

    if set(COPY_ORDER) != set(APPLICATION_TABLES):
        raise LegacyMappingError("copy order and v1 application tables differ")
    _validate_source(source)
    accounts = resolved_lease_accounts(source)
    payment_leases = resolved_payment_leases(source, accounts)
    target.execute("PRAGMA foreign_keys = ON")
    target.execute("BEGIN IMMEDIATE")
    try:
        for table in COPY_ORDER:
            destination_columns = _columns(target, table)
            source_columns = set(_columns(source, table))
            included = tuple(column for column in destination_columns if column in source_columns)
            quoted_columns = ", ".join(f'"{column}"' for column in included)
            placeholders = ", ".join("?" for _ in included)
            insert = f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders})'
            for row in _rows(source, table):
                if table == "leases":
                    guid, name = accounts[int(row["id"])]
                    row["gnucash_nk_account_guid"] = guid
                    row["gnucash_nk_account_name"] = name
                elif table == "gnucash_payments":
                    row["lease_id"] = payment_leases[int(row["id"])]
                target.execute(insert, tuple(row[column] for column in included))
        target.commit()
    except BaseException:
        target.rollback()
        raise
