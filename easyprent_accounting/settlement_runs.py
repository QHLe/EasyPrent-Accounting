"""Settlement runs, imported GnuCash payments, and their assignments."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, date, datetime

from .calculations import parse_date
from .integrations.gnucash import GnuCashReader, PiecashGnuCashReader
from .settings import get_gnucash_connection_settings
from .settlements import Settlements


def import_gnucash_payments_for_period(
    connection: sqlite3.Connection,
    property_id: int | None,
    period_start: str,
    period_end: str,
    unit_id: int | None = None,
    *,
    reader: GnuCashReader | None = None,
) -> dict:
    start = parse_date(period_start)
    end = parse_date(period_end)
    if start > end:
        raise ValueError("period_start must be before or equal to period_end")

    lease_rows = connection.execute(
        """
        SELECT l.id, l.tenant_id, l.start_date, l.end_date,
               l.gnucash_nk_account_guid, l.gnucash_nk_account_name
        FROM leases l
        JOIN units u ON u.id = l.unit_id
        LEFT JOIN buildings b ON b.id = u.building_id
        WHERE ((? IS NOT NULL AND b.property_id = ?) OR (? IS NOT NULL AND u.id = ?))
          AND l.start_date <= ?
          AND (l.end_date IS NULL OR l.end_date >= ?)
          AND COALESCE(l.gnucash_nk_account_guid, '') != ''
        """,
        (property_id, property_id, unit_id, unit_id, period_end, period_start),
    ).fetchall()
    accounts: dict[str, sqlite3.Row] = {}
    for lease in lease_rows:
        account_guid = str(lease["gnucash_nk_account_guid"])
        existing_lease = accounts.get(account_guid)
        if existing_lease is not None and int(existing_lease["id"]) != int(lease["id"]):
            raise ValueError("a GnuCash NK account can only be assigned to one lease")
        accounts[account_guid] = lease

    if not accounts:
        return {"imported": 0, "existing": 0, "accounts": 0}

    active_reader = reader or PiecashGnuCashReader()
    connection_settings = get_gnucash_connection_settings(connection)
    payments = active_reader.list_payments(
        connection_settings, set(accounts), start, end
    )
    imported = 0
    existing = 0
    imported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    for payment in payments:
        lease = accounts.get(payment.account_guid)
        if lease is None:
            continue
        lease_start = parse_date(str(lease["start_date"]))
        lease_end = parse_date(str(lease["end_date"])) if lease["end_date"] else None
        if payment.booking_date < lease_start or (
            lease_end is not None and payment.booking_date > lease_end
        ):
            continue
        lease_id = int(lease["id"])
        known = connection.execute(
            "SELECT id FROM gnucash_payments WHERE split_guid = ?", (payment.split_guid,)
        ).fetchone()
        if known is None:
            imported += 1
        else:
            existing += 1
        connection.execute(
            """
            INSERT INTO gnucash_payments (
                split_guid, transaction_guid, tenant_id, lease_id, account_guid, account_name,
                booking_date, amount, description, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(split_guid) DO UPDATE SET
                transaction_guid = excluded.transaction_guid,
                tenant_id = excluded.tenant_id,
                lease_id = excluded.lease_id,
                account_guid = excluded.account_guid,
                account_name = excluded.account_name,
                booking_date = excluded.booking_date,
                amount = excluded.amount,
                description = excluded.description,
                imported_at = excluded.imported_at
            """,
            (
                payment.split_guid,
                payment.transaction_guid,
                int(lease["tenant_id"]),
                lease_id,
                payment.account_guid,
                lease["gnucash_nk_account_name"],
                payment.booking_date.isoformat(),
                str(payment.amount),
                payment.description,
                imported_at,
            ),
        )
    return {"imported": imported, "existing": existing, "accounts": len(accounts)}


def get_settlement_run_overview(connection: sqlite3.Connection, settlement_id: str) -> dict:
    run = connection.execute(
        "SELECT * FROM settlement_runs WHERE id = ?", (settlement_id,)
    ).fetchone()
    if run is None:
        raise ValueError("settlement run not found")
    considered_split_guids = {
        str(row["split_guid"])
        for row in connection.execute(
            """
            SELECT split_guid FROM settlement_payment_assignments
            WHERE settlement_id = ? AND status = 'considered'
            """,
            (settlement_id,),
        ).fetchall()
    }
    settlement = Settlements(connection).for_period(
        run["property_id"],
        run["period_start"],
        run["period_end"],
        run["unit_id"],
        considered_split_guids,
    )
    target_label_row = (
        connection.execute("SELECT name FROM properties WHERE id = ?", (run["property_id"],)).fetchone()
        if run["property_id"] is not None
        else connection.execute("SELECT label FROM units WHERE id = ?", (run["unit_id"],)).fetchone()
    )
    target_label = (
        f"Immobilie: {target_label_row['name']}"
        if run["property_id"] is not None
        else f"Wohnung: {target_label_row['label']}"
    )
    payment_groups = _settlement_run_payment_groups(connection, run)
    return {
        "run": {
            "id": run["id"],
            "property_id": run["property_id"],
            "unit_id": run["unit_id"],
            "target_label": target_label,
            "year": int(str(run["period_start"])[:4]),
            "period_start": run["period_start"],
            "period_end": run["period_end"],
            "status": run["status"],
        },
        "settlement": settlement,
        **payment_groups,
    }


def _settlement_run_target_leases(
    connection: sqlite3.Connection, run: sqlite3.Row
) -> list[sqlite3.Row]:
    target_where = "b.property_id = ?" if run["unit_id"] is None else "u.id = ?"
    target_id = run["property_id"] if run["unit_id"] is None else run["unit_id"]
    return connection.execute(
        """
        SELECT l.id, l.tenant_id, l.start_date, l.end_date,
               l.gnucash_nk_account_guid, l.gnucash_nk_account_name,
               t.full_name AS tenant_name
        FROM leases l
        JOIN units u ON u.id = l.unit_id
        LEFT JOIN buildings b ON b.id = u.building_id
        JOIN tenants t ON t.id = l.tenant_id
        WHERE """ + target_where + """
        ORDER BY l.id
        """,
        (target_id,),
    ).fetchall()


def _payment_is_in_settlement_run(payment: sqlite3.Row, lease: sqlite3.Row, run: sqlite3.Row) -> bool:
    booking_date = str(payment["booking_date"])
    return (
        str(run["period_start"]) <= booking_date <= str(run["period_end"])
        and str(lease["start_date"]) <= booking_date
        and (lease["end_date"] is None or booking_date <= str(lease["end_date"]))
    )


def _settlement_run_payment_groups(connection: sqlite3.Connection, run: sqlite3.Row) -> dict:
    leases = _settlement_run_target_leases(connection, run)
    leases_by_id = {int(lease["id"]): lease for lease in leases}
    lease_ids = sorted(leases_by_id)
    if not lease_ids:
        return {
            "open_payments": [],
            "considered_payments": [],
            "outside_payments": [],
            "missing_account_leases": [],
        }
    placeholders = ", ".join("?" for _ in lease_ids)
    payments = connection.execute(
        """
        SELECT split_guid, lease_id, booking_date, amount, description
        FROM gnucash_payments
        WHERE lease_id IN (""" + placeholders + ") ORDER BY booking_date, split_guid",
        lease_ids,
    ).fetchall()
    assignments = {
        str(row["split_guid"]): row["status"]
        for row in connection.execute(
            "SELECT split_guid, status FROM settlement_payment_assignments WHERE settlement_id = ?",
            (run["id"],),
        ).fetchall()
    }
    elsewhere = {
        str(row["split_guid"]): str(row["settlement_id"])
        for row in connection.execute(
            """
            SELECT split_guid, settlement_id FROM settlement_payment_assignments
            WHERE status = 'considered' AND settlement_id != ?
            """,
            (run["id"],),
        ).fetchall()
    }
    groups = {"open_payments": [], "considered_payments": [], "outside_payments": []}
    for payment in payments:
        lease = leases_by_id[int(payment["lease_id"])]
        item = {
            "split_guid": payment["split_guid"],
            "lease_id": payment["lease_id"],
            "tenant_name": lease["tenant_name"],
            "booking_date": payment["booking_date"],
            "amount": str(payment["amount"]),
            "description": payment["description"],
        }
        is_in_run = _payment_is_in_settlement_run(payment, lease, run)
        if assignments.get(str(payment["split_guid"])) == "considered":
            if not is_in_run:
                item["warning"] = "Außerhalb berücksichtigtem Zeitraum"
            groups["considered_payments"].append(item)
        elif not is_in_run:
            groups["outside_payments"].append(item)
        elif str(payment["split_guid"]) in elsewhere:
            item["assigned_settlement_id"] = elsewhere[str(payment["split_guid"])]
            groups["outside_payments"].append(item)
        else:
            groups["open_payments"].append(item)
    return {
        **groups,
        "missing_account_leases": [
            {"lease_id": lease["id"], "tenant_name": lease["tenant_name"]}
            for lease in leases
            if not str(lease["gnucash_nk_account_guid"] or "").strip()
        ],
    }


def refresh_settlement_run_payments(
    connection: sqlite3.Connection,
    settlement_id: str,
    *,
    reader: GnuCashReader | None = None,
) -> dict:
    run = connection.execute("SELECT * FROM settlement_runs WHERE id = ?", (settlement_id,)).fetchone()
    if run is None:
        raise ValueError("settlement run not found")
    leases = _settlement_run_target_leases(connection, run)
    accounts = {
        str(lease["gnucash_nk_account_guid"]): lease
        for lease in leases
        if str(lease["gnucash_nk_account_guid"] or "").strip()
    }
    if not accounts:
        return {"imported": 0, "existing": 0, "accounts": 0}
    payments = (reader or PiecashGnuCashReader()).list_payments(
        get_gnucash_connection_settings(connection),
        set(accounts),
        date(1900, 1, 1),
        date(2100, 12, 31),
    )
    imported = 0
    existing = 0
    imported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    for payment in payments:
        lease = accounts.get(payment.account_guid)
        if lease is None:
            continue
        known = connection.execute("SELECT id FROM gnucash_payments WHERE split_guid = ?", (payment.split_guid,)).fetchone()
        imported += known is None
        existing += known is not None
        connection.execute(
            """
            INSERT INTO gnucash_payments (
                split_guid, transaction_guid, tenant_id, lease_id, account_guid, account_name,
                booking_date, amount, description, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(split_guid) DO UPDATE SET
                transaction_guid=excluded.transaction_guid, tenant_id=excluded.tenant_id,
                lease_id=excluded.lease_id, account_guid=excluded.account_guid,
                account_name=excluded.account_name, booking_date=excluded.booking_date,
                amount=excluded.amount, description=excluded.description, imported_at=excluded.imported_at
            """,
            (payment.split_guid, payment.transaction_guid, lease["tenant_id"], lease["id"], payment.account_guid,
             lease["gnucash_nk_account_name"], payment.booking_date.isoformat(), str(payment.amount),
             payment.description, imported_at),
        )
    for payment in connection.execute(
        "SELECT * FROM gnucash_payments WHERE lease_id IN (" + ", ".join("?" for _ in accounts.values()) + ")",
        [lease["id"] for lease in accounts.values()],
    ).fetchall():
        lease = next(lease for lease in accounts.values() if int(lease["id"]) == int(payment["lease_id"]))
        if not _payment_is_in_settlement_run(payment, lease, run):
            connection.execute(
                """
                INSERT INTO settlement_payment_assignments (
                    settlement_id, split_guid, lease_id, status, reason, created_at, updated_at
                ) VALUES (?, ?, ?, 'excluded', NULL, ?, ?)
                ON CONFLICT(settlement_id, split_guid) DO UPDATE SET
                    status = CASE WHEN settlement_payment_assignments.status = 'considered'
                                  THEN 'considered' ELSE 'excluded' END,
                    updated_at = excluded.updated_at
                """,
                (settlement_id, payment["split_guid"], payment["lease_id"], imported_at, imported_at),
            )
    return {"imported": imported, "existing": existing, "accounts": len(accounts)}


def set_settlement_payment_considered(
    connection: sqlite3.Connection, settlement_id: str, split_guid: str, considered: bool
) -> dict:
    run = connection.execute("SELECT * FROM settlement_runs WHERE id = ?", (settlement_id,)).fetchone()
    if run is None:
        raise ValueError("settlement run not found")
    leases_by_id = {int(lease["id"]): lease for lease in _settlement_run_target_leases(connection, run)}
    payment = connection.execute(
        "SELECT * FROM gnucash_payments WHERE split_guid = ?", (split_guid,)
    ).fetchone()
    if payment is None or int(payment["lease_id"]) not in leases_by_id:
        raise ValueError("payment does not belong to settlement target")
    lease = leases_by_id[int(payment["lease_id"])]
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    if considered:
        if not _payment_is_in_settlement_run(payment, lease, run):
            raise ValueError("payment is outside the considered period")
        other = connection.execute(
            """
            SELECT settlement_id FROM settlement_payment_assignments
            WHERE split_guid = ? AND status = 'considered' AND settlement_id != ?
            """,
            (split_guid, settlement_id),
        ).fetchone()
        if other is not None:
            raise ValueError("payment is already considered in another settlement run")
        connection.execute(
            """
            INSERT INTO settlement_payment_assignments (
                settlement_id, split_guid, lease_id, status, reason, assigned_amount, created_at, updated_at
            ) VALUES (?, ?, ?, 'considered', NULL, ?, ?, ?)
            ON CONFLICT(settlement_id, split_guid) DO UPDATE SET
                status = 'considered', reason = NULL, assigned_amount = excluded.assigned_amount,
                updated_at = excluded.updated_at
            """,
            (settlement_id, split_guid, payment["lease_id"], str(payment["amount"]), now, now),
        )
    else:
        connection.execute(
            "DELETE FROM settlement_payment_assignments WHERE settlement_id = ? AND split_guid = ? AND status = 'considered'",
            (settlement_id, split_guid),
        )
    return get_settlement_run_overview(connection, settlement_id)


def consider_all_settlement_payments(connection: sqlite3.Connection, settlement_id: str) -> dict:
    overview = get_settlement_run_overview(connection, settlement_id)
    for payment in overview["open_payments"]:
        set_settlement_payment_considered(connection, settlement_id, str(payment["split_guid"]), True)
    return get_settlement_run_overview(connection, settlement_id)


def create_or_open_settlement_run(connection: sqlite3.Connection, payload: dict) -> tuple[dict, bool]:
    try:
        year = int(payload.get("year"))
    except (TypeError, ValueError) as error:
        raise ValueError("year must be an integer") from error
    if year < 1900 or year > 9999:
        raise ValueError("year must be between 1900 and 9999")

    raw_property_id = payload.get("property_id")
    raw_unit_id = payload.get("unit_id")
    property_id = None if raw_property_id in (None, "") else int(raw_property_id)
    unit_id = None if raw_unit_id in (None, "") else int(raw_unit_id)
    if (property_id is None) == (unit_id is None):
        raise ValueError("settlement run requires exactly one property or standalone unit")
    if property_id is not None:
        target = connection.execute(
            "SELECT id, name FROM properties WHERE id = ? AND is_archived = 0", (property_id,)
        ).fetchone()
        target_label = f"Immobilie: {target['name']}" if target is not None else None
    else:
        target = connection.execute(
            """
            SELECT id, label FROM units
            WHERE id = ? AND building_id IS NULL AND is_archived = 0
            """,
            (unit_id,),
        ).fetchone()
        target_label = f"Wohnung: {target['label']}" if target is not None else None
    if target is None:
        raise ValueError("settlement target not found or unavailable")

    period_start = f"{year:04d}-01-01"
    period_end = f"{year:04d}-12-31"
    existing = connection.execute(
        """
        SELECT * FROM settlement_runs
        WHERE property_id IS ? AND unit_id IS ? AND period_start = ? AND period_end = ?
        """,
        (property_id, unit_id, period_start, period_end),
    ).fetchone()
    created = existing is None
    if existing is None:
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        run_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO settlement_runs (
                id, property_id, unit_id, period_start, period_end, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
            """,
            (run_id, property_id, unit_id, period_start, period_end, now, now),
        )
        existing = connection.execute(
            "SELECT * FROM settlement_runs WHERE id = ?", (run_id,)
        ).fetchone()
    assert existing is not None
    return {
        "id": existing["id"],
        "property_id": existing["property_id"],
        "unit_id": existing["unit_id"],
        "target_label": target_label,
        "year": year,
        "period_start": existing["period_start"],
        "period_end": existing["period_end"],
        "status": existing["status"],
    }, created


def find_settlement_run_id(
    connection: sqlite3.Connection, property_id: int | None, unit_id: int | None, year: int
) -> str | None:
    row = connection.execute(
        """
        SELECT id FROM settlement_runs
        WHERE property_id IS ? AND unit_id IS ? AND period_start = ? AND period_end = ?
        """,
        (property_id, unit_id, f"{year:04d}-01-01", f"{year:04d}-12-31"),
    ).fetchone()
    return str(row["id"]) if row is not None else None
