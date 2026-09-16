"""Expense validation, targets, cost categories, pricing and lifecycle."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from .asset_registry import AssetRegistry
from .calculations import parse_date
from .domain import Money
from .expense_pricer import ExpensePricer
from .metering import Metering

OPEN_ENDED_PERIOD_END = "9999-12-31"

def _derive_charge_fields(payload: dict) -> tuple[str, str, str | None]:
    explicit_charge_type = payload.get("charge_type")
    recurrence = payload.get("recurrence")
    interval_name = payload.get("interval") or payload.get("interval_name")

    if explicit_charge_type == "consumption":
        return "consumption", "one_time", None

    if recurrence == "recurring":
        if interval_name not in {"monthly", "quarterly", "yearly"}:
            raise ValueError("interval must be monthly, quarterly or yearly")
        if interval_name == "yearly":
            return "yearly", "recurring", "yearly"
        if interval_name == "quarterly":
            return "quarterly", "recurring", "quarterly"
        return "monthly", "recurring", "monthly"

    charge_type = explicit_charge_type or "one_time"
    if charge_type not in {"one_time", "total", "monthly", "quarterly", "yearly"}:
        raise ValueError("charge_type is unsupported")
    if charge_type in {"monthly", "quarterly", "yearly"}:
        return charge_type, "recurring", charge_type
    return "one_time", "one_time", None

def _parse_decimal(value: object, field_name: str) -> Decimal:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        return Decimal(str(value))
    except Exception as error:  # pragma: no cover - Decimal raises multiple subclasses
        raise ValueError(f"{field_name} must be numeric") from error

def _parse_int(value: object, field_name: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error

def _require_payload_value(payload: dict, field_name: str) -> str:
    value = payload.get(field_name)
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value)

def _decimal_places(value: Decimal) -> int:
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    return -exponent if exponent < 0 else 0

def _normalize_expense_amount(raw_value: object, charge_type: str) -> Decimal:
    amount = Money(_parse_decimal(raw_value, "amount")).amount
    max_places = 10
    if _decimal_places(amount) > max_places:
        raise ValueError(f"amount supports max {max_places} decimal places")
    return amount

def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")

def _normalize_expense_target(
    connection: sqlite3.Connection,
    payload: dict,
) -> tuple[str, int, int | None]:
    object_type = payload.get("object_type")
    object_id = payload.get("object_id")
    if object_type in (None, "") and payload.get("property_id") not in (None, ""):
        object_type = "property"
        object_id = payload.get("property_id")

    if object_type in (None, ""):
        raise ValueError("object_type is required")

    object_type = str(object_type)
    object_id = _parse_int(object_id, "object_id")
    target = AssetRegistry(connection).resolve_target(object_type, object_id)
    if target is None:
        raise ValueError("target object not found")
    return object_type, object_id, target.property_id

def _normalize_meter_link(
    connection: sqlite3.Connection,
    payload: dict,
    expense_object_type: str,
    expense_object_id: int,
    expense_property_id: int | None,
    charge_type: str,
) -> tuple[int | None, str | None, str | None, str]:
    meter_id = payload.get("meter_id")
    if meter_id in (None, ""):
        if charge_type == "consumption":
            consumption_unit = payload.get("consumption_unit")
            if consumption_unit in (None, ""):
                raise ValueError("consumption_unit or meter_id is required for consumption expenses")
            return None, str(consumption_unit), None, "1"
        return None, payload.get("consumption_unit"), None, "1"

    if charge_type != "consumption":
        raise ValueError("meter_id is only supported for consumption expenses")

    normalized_meter_id = _parse_int(meter_id, "meter_id")
    meter_row = Metering(connection).lookup_meter(normalized_meter_id)
    if meter_row is None:
        raise ValueError("meter_id not found")
    if meter_row["is_archived"]:
        raise ValueError("meter_id must reference an active meter")

    if (
        meter_row["object_type"] != expense_object_type
        or meter_row["object_id"] != expense_object_id
    ):
        raise ValueError("meter_id must belong to the same target object")

    meter_unit = str(meter_row["unit"])
    consumption_unit = str(payload.get("consumption_unit") or meter_unit)
    conversion_factor_value = payload.get("conversion_factor")
    if consumption_unit != meter_unit and conversion_factor_value in (None, ""):
        raise ValueError("conversion_factor is required when consumption_unit differs from meter unit")

    conversion_factor = (
        Money(_parse_decimal(conversion_factor_value, "conversion_factor")).amount
        if conversion_factor_value not in (None, "")
        else Decimal("1")
    )
    if conversion_factor <= 0:
        raise ValueError("conversion_factor must be greater than zero")

    return normalized_meter_id, consumption_unit, meter_unit, _decimal_to_string(conversion_factor) or "1"

def _normalize_consumption_value(payload: dict, charge_type: str, meter_id: int | None) -> str | None:
    raw_value = payload.get("consumption_value")
    if charge_type != "consumption":
        if raw_value in (None, ""):
            return None
        return _decimal_to_string(Money(_parse_decimal(raw_value, "consumption_value")).amount)

    if meter_id is not None:
        return None

    if raw_value in (None, ""):
        raise ValueError("consumption_value is required when meter_id is not provided")
    return _decimal_to_string(Money(_parse_decimal(raw_value, "consumption_value")).amount)

def _effective_consumption_quantity(
    connection: sqlite3.Connection,
    expense_payload: dict,
    period_start: str,
    period_end: str,
) -> tuple[str | None, Decimal | None]:
    if expense_payload["charge_type"] != "consumption":
        return expense_payload.get("meter_unit"), None

    meter_unit = expense_payload.get("meter_unit") or expense_payload.get("consumption_unit")
    meter_id = expense_payload.get("meter_id")
    if meter_id is not None:
        if meter_unit in (None, ""):
            meter_row = Metering(connection).lookup_meter(int(meter_id))
            meter_unit = str(meter_row["unit"]) if meter_row is not None else None
        raw_quantity = Metering(connection).consumption_for_period(int(meter_id), period_start, period_end)
    else:
        raw_quantity = (
            Decimal(str(expense_payload["consumption_value"]))
            if expense_payload.get("consumption_value") not in (None, "")
            else None
        )
        expense_start = expense_payload.get("period_start")
        expense_end = expense_payload.get("period_end")
        if raw_quantity is not None and expense_start and expense_end:
            overlap = ExpensePricer.overlap(
                parse_date(str(expense_start)), parse_date(str(expense_end)),
                parse_date(period_start), parse_date(period_end),
            )
            if overlap is None:
                return meter_unit, None
            overlap_start, overlap_end = overlap
            total_days = Decimal(
                (parse_date(str(expense_end)) - parse_date(str(expense_start))).days + 1
            )
            overlap_days = Decimal(
                (overlap_end - overlap_start).days + 1
            )
            raw_quantity = raw_quantity * overlap_days / total_days

    if raw_quantity is None:
        return meter_unit, None

    conversion_factor = Decimal(str(expense_payload.get("conversion_factor") or "1"))
    return meter_unit, raw_quantity * conversion_factor

def _total_amount_for_expense_period(
    connection: sqlite3.Connection,
    expense_payload: dict,
    period_start: str,
    period_end: str,
) -> tuple[str | None, str | None]:
    meter_unit, effective_consumption_value = _effective_consumption_quantity(
        connection,
        expense_payload,
        period_start,
        period_end,
    )
    total_amount = ExpensePricer.amount_for_period(
        amount=Decimal(str(expense_payload["amount"])),
        charge_type=str(expense_payload["charge_type"]),
        expense_start=parse_date(str(expense_payload.get("period_start") or period_start)),
        expense_end=parse_date(str(expense_payload.get("period_end") or period_end)),
        period_start=parse_date(period_start),
        period_end=parse_date(period_end),
        consumption_value=effective_consumption_value,
    )
    return meter_unit, None if total_amount is None else f"{total_amount:.2f}"

def _normalize_expense_dates(
    connection: sqlite3.Connection,
    payload: dict,
    charge_type: str,
    meter_id: int | None,
) -> tuple[str | None, str, str, bool]:
    booking_date = payload.get("booking_date")
    period_start = payload.get("period_start")
    period_end = payload.get("period_end")

    if charge_type == "one_time":
        has_period_start = period_start not in (None, "")
        has_period_end = period_end not in (None, "")
        if has_period_start != has_period_end:
            raise ValueError(
                "period_start and period_end must both be provided when setting an optional one_time period"
            )

        if has_period_start and has_period_end:
            start_text = str(period_start)
            end_text = str(period_end)
            start_date = parse_date(start_text)
            end_date = parse_date(end_text)
            if start_date > end_date:
                raise ValueError("period_start must be before or equal to period_end")
            normalized_booking_date = (
                str(booking_date)
                if booking_date not in (None, "")
                else start_text
            )
            parse_date(normalized_booking_date)
            return normalized_booking_date, start_text, end_text, False

        effective_booking_date = booking_date
        if effective_booking_date in (None, ""):
            raise ValueError("booking_date is required for one_time expenses")
        parse_date(str(effective_booking_date))
        normalized_date = str(effective_booking_date)
        return normalized_date, normalized_date, normalized_date, False

    if period_start in (None, ""):
        raise ValueError("period_start is required for recurring expenses")
    if period_end in (None, ""):
        if charge_type in {"monthly", "quarterly", "yearly"}:
            parse_date(str(period_start))
            return None, str(period_start), OPEN_ENDED_PERIOD_END, True
        if charge_type != "consumption" or meter_id is None:
            raise ValueError("period_end is required for recurring expenses")
        latest_reading_date = Metering(connection).latest_reading_date(meter_id)
        if latest_reading_date is None:
            raise ValueError("period_end requires at least one meter reading when omitted")
        period_end = (parse_date(latest_reading_date) - timedelta(days=1)).isoformat()
    start_date = parse_date(str(period_start))
    end_date = parse_date(str(period_end))
    if start_date > end_date:
        raise ValueError("period_start must be before or equal to period_end")
    return None, str(period_start), str(period_end), False

def _normalize_expense_payload(connection: sqlite3.Connection, payload: dict) -> dict:
    object_type, object_id, property_id = _normalize_expense_target(connection, payload)
    charge_type, recurrence, interval_name = _derive_charge_fields(payload)
    meter_id, consumption_unit, meter_unit, conversion_factor = _normalize_meter_link(
        connection,
        payload,
        object_type,
        object_id,
        property_id,
        charge_type,
    )
    booking_date, period_start, period_end, is_open_ended = _normalize_expense_dates(
        connection,
        payload,
        charge_type,
        meter_id,
    )
    amount = _normalize_expense_amount(payload.get("amount"), charge_type)
    explicit_label = str(payload.get("label") or "").strip()
    explicit_expense_category = str(payload.get("expense_category") or "").strip()
    expense_category = explicit_expense_category or explicit_label
    label = explicit_label or expense_category
    beneficiary_name = str(payload.get("beneficiary_name") or "Nicht gepflegt").strip()
    if expense_category == "":
        raise ValueError("expense_category is required")
    if beneficiary_name == "":
        raise ValueError("beneficiary_name is required")
    allocation_method = _require_payload_value(payload, "allocation_method")
    consumption_value = _normalize_consumption_value(payload, charge_type, meter_id)
    return {
        "property_id": property_id,
        "object_type": object_type,
        "object_id": object_id,
        "expense_category": expense_category,
        "beneficiary_name": beneficiary_name,
        "label": label,
        "amount": str(amount),
        "allocation_method": allocation_method,
        "charge_type": charge_type,
        "recurrence": recurrence,
        "interval_name": interval_name,
        "meter_id": meter_id,
        "meter_unit": meter_unit,
        "consumption_unit": consumption_unit,
        "conversion_factor": conversion_factor,
        "consumption_value": consumption_value,
        "booking_date": booking_date,
        "period_start": period_start,
        "period_end": period_end,
        "is_open_ended": is_open_ended,
    }

def _expense_response_payload(
    connection: sqlite3.Connection,
    expense_id: int,
    normalized_payload: dict,
) -> dict:
    if normalized_payload["is_open_ended"]:
        meter_unit, total_amount, effective_consumption_value = None, None, None
    else:
        meter_unit, total_amount = _total_amount_for_expense_period(
            connection, normalized_payload, normalized_payload["period_start"], normalized_payload["period_end"]
        )
        _, effective_consumption_value = _effective_consumption_quantity(
            connection, normalized_payload, normalized_payload["period_start"], normalized_payload["period_end"]
        )
    return {
        "id": expense_id,
        "object_type": normalized_payload["object_type"],
        "object_id": normalized_payload["object_id"],
        "expense_category": normalized_payload["expense_category"],
        "beneficiary_name": normalized_payload["beneficiary_name"],
        "label": normalized_payload["label"],
        "amount": normalized_payload["amount"],
        "allocation_method": normalized_payload["allocation_method"],
        "charge_type": normalized_payload["charge_type"],
        "recurrence": normalized_payload["recurrence"],
        "interval": normalized_payload["interval_name"],
        "meter_id": normalized_payload["meter_id"],
        "meter_unit": meter_unit,
        "consumption_unit": normalized_payload["consumption_unit"],
        "conversion_factor": normalized_payload["conversion_factor"],
        "consumption_value": normalized_payload["consumption_value"],
        "effective_consumption_value": _decimal_to_string(effective_consumption_value),
        "total_amount": total_amount,
        "booking_date": normalized_payload["booking_date"],
        "period_start": normalized_payload["period_start"],
        "period_end": None if normalized_payload["is_open_ended"] else normalized_payload["period_end"],
        "is_open_ended": normalized_payload["is_open_ended"],
    }

def create_expense(connection: sqlite3.Connection, payload: dict) -> dict:
    normalized_payload = _normalize_expense_payload(connection, payload)
    cursor = connection.execute(
        """
        INSERT INTO expense_items (
            property_id, object_type, object_id, expense_category, beneficiary_name, label, amount,
            allocation_method, charge_type, recurrence, interval_name, meter_id, consumption_unit,
            consumption_value, conversion_factor, booking_date, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_payload["property_id"],
            normalized_payload["object_type"],
            normalized_payload["object_id"],
            normalized_payload["expense_category"],
            normalized_payload["beneficiary_name"],
            normalized_payload["label"],
            normalized_payload["amount"],
            normalized_payload["allocation_method"],
            normalized_payload["charge_type"],
            normalized_payload["recurrence"],
            normalized_payload["interval_name"],
            normalized_payload["meter_id"],
            normalized_payload["consumption_unit"],
            normalized_payload["consumption_value"],
            normalized_payload["conversion_factor"],
            normalized_payload["booking_date"],
            normalized_payload["period_start"],
            normalized_payload["period_end"],
        ),
    )
    return _expense_response_payload(connection, cursor.lastrowid, normalized_payload)

def update_expense(connection: sqlite3.Connection, expense_id: int, payload: dict) -> dict:
    existing_expense = connection.execute(
        """
        SELECT id, is_archived
        FROM expense_items
        WHERE id = ?
        """,
        (expense_id,),
    ).fetchone()
    if existing_expense is None:
        raise ValueError("expense not found")
    if existing_expense["is_archived"]:
        raise ValueError("archived expenses cannot be edited")

    normalized_payload = _normalize_expense_payload(connection, payload)
    connection.execute(
        """
        UPDATE expense_items
        SET property_id = ?,
            object_type = ?,
            object_id = ?,
            expense_category = ?,
            beneficiary_name = ?,
            label = ?,
            amount = ?,
            allocation_method = ?,
            charge_type = ?,
            recurrence = ?,
            interval_name = ?,
            meter_id = ?,
            consumption_unit = ?,
            consumption_value = ?,
            conversion_factor = ?,
            booking_date = ?,
            period_start = ?,
            period_end = ?
        WHERE id = ?
        """,
        (
            normalized_payload["property_id"],
            normalized_payload["object_type"],
            normalized_payload["object_id"],
            normalized_payload["expense_category"],
            normalized_payload["beneficiary_name"],
            normalized_payload["label"],
            normalized_payload["amount"],
            normalized_payload["allocation_method"],
            normalized_payload["charge_type"],
            normalized_payload["recurrence"],
            normalized_payload["interval_name"],
            normalized_payload["meter_id"],
            normalized_payload["consumption_unit"],
            normalized_payload["consumption_value"],
            normalized_payload["conversion_factor"],
            normalized_payload["booking_date"],
            normalized_payload["period_start"],
            normalized_payload["period_end"],
            expense_id,
        ),
    )
    return _expense_response_payload(connection, expense_id, normalized_payload)


class Expenses:
    """Persist expenses and expose period prices at the accounting seam."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(self, payload: dict) -> dict:
        return create_expense(self.connection, payload)

    def update(self, expense_id: int, payload: dict) -> dict:
        return update_expense(self.connection, expense_id, payload)

    def amount_for_period(
        self, expense: dict, period_start: str, period_end: str
    ) -> tuple[str | None, str | None]:
        return _total_amount_for_expense_period(
            self.connection, expense, period_start, period_end
        )

    def effective_consumption_quantity(
        self, expense: dict, period_start: str, period_end: str
    ) -> tuple[str | None, Decimal | None]:
        return _effective_consumption_quantity(
            self.connection, expense, period_start, period_end
        )

    def list_expenses(self) -> dict[str, list[dict]]:
        rows = self.connection.execute(
            """
            SELECT e.*, m.label AS meter_label, m.unit AS meter_unit,
                CASE
                    WHEN e.object_type = 'property' THEN p_target.name
                    WHEN e.object_type = 'building' THEN b_target.name
                    WHEN e.object_type = 'unit' THEN u_target.label
                    WHEN e.object_type = 'room' THEN r_target.label
                END AS object_name
            FROM expense_items e
            LEFT JOIN properties p_target
                ON e.object_type = 'property' AND p_target.id = e.object_id
            LEFT JOIN buildings b_target
                ON e.object_type = 'building' AND b_target.id = e.object_id
            LEFT JOIN units u_target
                ON e.object_type = 'unit' AND u_target.id = e.object_id
            LEFT JOIN rooms r_target
                ON e.object_type = 'room' AND r_target.id = e.object_id
            LEFT JOIN meters m ON m.id = e.meter_id
            ORDER BY e.id
            """
        ).fetchall()
        expenses = [dict(row) for row in rows]
        for expense in expenses:
            expense["is_open_ended"] = expense["period_end"] == OPEN_ENDED_PERIOD_END
            if expense["is_open_ended"]:
                expense["effective_consumption_value"] = None
                expense["total_amount"] = None
                expense["period_end"] = None
                continue
            meter_unit, total_amount = self.amount_for_period(
                expense, expense["period_start"], expense["period_end"]
            )
            _, effective_value = self.effective_consumption_quantity(
                expense, expense["period_start"], expense["period_end"]
            )
            expense["meter_unit"] = meter_unit
            expense["effective_consumption_value"] = _decimal_to_string(effective_value)
            expense["total_amount"] = total_amount
        categories = [
            dict(row) for row in self.connection.execute(
                """
                SELECT expense_category, beneficiary_name, COUNT(*) AS expense_count
                FROM expense_items
                GROUP BY expense_category, beneficiary_name
                ORDER BY expense_category, beneficiary_name
                """
            ).fetchall()
        ]
        return {"expenses": expenses, "expense_categories": categories}

    def archive(self, expense_id: int) -> dict:
        row = self.connection.execute(
            "SELECT id, is_archived, archived_at FROM expense_items WHERE id = ?",
            (expense_id,),
        ).fetchone()
        if row is None:
            raise ValueError("expense not found")
        if row["is_archived"]:
            return {"resource": "expenses", "id": expense_id, "is_archived": 1, "archived_at": row["archived_at"]}
        archived_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.connection.execute(
            "UPDATE expense_items SET is_archived = 1, archived_at = ? WHERE id = ?",
            (archived_at, expense_id),
        )
        return {"resource": "expenses", "id": expense_id, "is_archived": 1, "archived_at": archived_at}

    def restore(self, expense_id: int) -> dict:
        row = self.connection.execute(
            "SELECT id, is_archived, archived_at FROM expense_items WHERE id = ?",
            (expense_id,),
        ).fetchone()
        if row is None:
            raise ValueError("expense not found")
        if not row["is_archived"]:
            return {"resource": "expenses", "id": expense_id, "is_archived": 0, "archived_at": None}
        self.connection.execute(
            "UPDATE expense_items SET is_archived = 0, archived_at = NULL WHERE id = ?",
            (expense_id,),
        )
        return {"resource": "expenses", "id": expense_id, "is_archived": 0, "archived_at": None}

    def delete(self, expense_id: int) -> dict:
        row = self.connection.execute(
            "SELECT is_archived FROM expense_items WHERE id = ?", (expense_id,)
        ).fetchone()
        if row is None:
            raise ValueError("expense not found")
        if not row["is_archived"]:
            raise ValueError("expense must be archived before deletion")
        document_count = self.connection.execute(
            "SELECT COUNT(*) FROM expense_documents WHERE expense_id = ?",
            (expense_id,),
        ).fetchone()[0]
        if document_count:
            raise ValueError(f"dependencies prevent deletion of expense: expense_documents:{document_count}")
        self.connection.execute("DELETE FROM expense_items WHERE id = ?", (expense_id,))
        return {"resource": "expenses", "id": expense_id, "deleted": True}
