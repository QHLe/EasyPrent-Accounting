"""Meter master data, readings, and consumption for rental assets."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from .asset_registry import AssetRegistry
from .calculations import parse_date

def _parse_int(value: object, field_name: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error

def _parse_decimal(value: object, field_name: str) -> Decimal:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        decimal_value = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{field_name} must be numeric") from error
    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return decimal_value

def _require_payload_value(payload: dict, field_name: str) -> str:
    value = payload.get(field_name)
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value)

def _row_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]

def interpolate_meter_reading(
    reading_points: list[tuple[date, Decimal]],
    target_date: date,
) -> Decimal | None:
    if not reading_points:
        return None

    previous_point: tuple[date, Decimal] | None = None
    for current_point in reading_points:
        current_date, current_value = current_point
        if current_date == target_date:
            return current_value
        if current_date > target_date:
            if previous_point is None:
                return current_value
            previous_date, previous_value = previous_point
            total_days = (current_date - previous_date).days
            if total_days <= 0:
                return previous_value
            elapsed_days = (target_date - previous_date).days
            return previous_value + (
                (current_value - previous_value) * Decimal(elapsed_days) / Decimal(total_days)
            )
        previous_point = current_point

    return previous_point[1] if previous_point is not None else None

def meter_consumption_for_period(
    reading_points: list[tuple[date, Decimal]],
    period_start: str,
    period_end: str,
) -> Decimal | None:
    start_date = parse_date(period_start)
    end_date = parse_date(period_end)
    if end_date < start_date:
        return None
    if len(reading_points) < 2:
        return None

    start_value = interpolate_meter_reading(reading_points, start_date)
    end_value = interpolate_meter_reading(reading_points, end_date + timedelta(days=1))
    if start_value is None or end_value is None or end_value < start_value:
        return None
    return end_value - start_value

class Metering:
    """Persist meters and provide readings to expenses and settlements."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _normalize_meter_target(
        self,
        payload: dict,
    ) -> tuple[str, int, int | None]:
        object_type = _require_payload_value(payload, "object_type")
        object_id = _parse_int(payload.get("object_id"), "object_id")
        target = AssetRegistry(self.connection).resolve_target(object_type, object_id)
        if target is None:
            raise ValueError("target object not found")
        return object_type, object_id, target.property_id

    def lookup_meter(self, meter_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT id, object_type, object_id, label, unit, is_archived
            FROM meters
            WHERE id = ?
            """,
            (meter_id,),
        ).fetchone()

    def _load_meter_reading_points(
        self,
        meter_id: int,
    ) -> list[tuple[date, Decimal]]:
        rows = self.connection.execute(
            """
            SELECT reading_date, reading_value
            FROM meter_readings
            WHERE meter_id = ?
            ORDER BY reading_date, id
            """,
            (meter_id,),
        ).fetchall()
        return [
            (parse_date(row["reading_date"]), Decimal(str(row["reading_value"])))
            for row in rows
        ]

    def consumption_for_period(
        self,
        meter_id: int,
        period_start: str,
        period_end: str,
    ) -> Decimal | None:
        if self.lookup_meter(meter_id) is None:
            raise ValueError("meter not found")
        reading_points = self._load_meter_reading_points(meter_id)
        return meter_consumption_for_period(reading_points, period_start, period_end)

    def latest_reading_date(self, meter_id: int) -> str | None:
        row = self.connection.execute(
            """
            SELECT reading_date
            FROM meter_readings
            WHERE meter_id = ?
            ORDER BY reading_date DESC, id DESC
            LIMIT 1
            """,
            (meter_id,),
        ).fetchone()
        return str(row["reading_date"]) if row is not None else None

    def list_meters(self) -> dict[str, list[dict]]:
        """Return meters with their latest readings and target names."""
        meters = _row_dicts(
            self.connection.execute(
                """
                SELECT
                    m.id, m.object_type, m.object_id, m.label, m.meter_type,
                    m.unit, m.serial_number, m.is_archived, m.archived_at,
                    CASE
                        WHEN m.object_type = 'property' THEN p_target.id
                        WHEN m.object_type = 'building' THEN b_target.property_id
                        WHEN m.object_type = 'unit' THEN b_for_unit.property_id
                        WHEN m.object_type = 'room' THEN b_for_room.property_id
                    END AS property_id,
                    p.name AS property_name,
                    CASE
                        WHEN m.object_type = 'property' THEN p_target.name
                        WHEN m.object_type = 'building' THEN b_target.name
                        WHEN m.object_type = 'unit' THEN u_target.label
                        WHEN m.object_type = 'room' THEN r_target.label
                    END AS object_name,
                    (
                        SELECT mr.reading_date
                        FROM meter_readings mr
                        WHERE mr.meter_id = m.id
                        ORDER BY mr.reading_date DESC, mr.id DESC
                        LIMIT 1
                    ) AS latest_reading_date,
                    (
                        SELECT mr.reading_value
                        FROM meter_readings mr
                        WHERE mr.meter_id = m.id
                        ORDER BY mr.reading_date DESC, mr.id DESC
                        LIMIT 1
                    ) AS latest_reading_value,
                    (
                        SELECT COUNT(*)
                        FROM meter_readings mr
                        WHERE mr.meter_id = m.id
                    ) AS reading_count
                FROM meters m
                LEFT JOIN properties p_target
                    ON m.object_type = 'property' AND p_target.id = m.object_id
                LEFT JOIN buildings b_target
                    ON m.object_type = 'building' AND b_target.id = m.object_id
                LEFT JOIN units u_target
                    ON m.object_type = 'unit' AND u_target.id = m.object_id
                LEFT JOIN rooms r_target
                    ON m.object_type = 'room' AND r_target.id = m.object_id
                LEFT JOIN buildings b_for_unit ON b_for_unit.id = u_target.building_id
                LEFT JOIN units u_for_room ON u_for_room.id = r_target.unit_id
                LEFT JOIN buildings b_for_room ON b_for_room.id = u_for_room.building_id
                LEFT JOIN properties p ON p.id = CASE
                    WHEN m.object_type = 'property' THEN p_target.id
                    WHEN m.object_type = 'building' THEN b_target.property_id
                    WHEN m.object_type = 'unit' THEN b_for_unit.property_id
                    WHEN m.object_type = 'room' THEN b_for_room.property_id
                END
                ORDER BY m.id
                """
            ).fetchall()
        )
        meter_readings = _row_dicts(
            self.connection.execute(
                """
                SELECT
                    mr.*,
                    m.label AS meter_label,
                    m.unit AS meter_unit,
                    m.object_type,
                    m.object_id,
                    p.name AS property_name,
                    CASE
                        WHEN m.object_type = 'property' THEN p_target.name
                        WHEN m.object_type = 'building' THEN b_target.name
                        WHEN m.object_type = 'unit' THEN u_target.label
                        WHEN m.object_type = 'room' THEN r_target.label
                    END AS object_name
                FROM meter_readings mr
                JOIN meters m ON m.id = mr.meter_id
                LEFT JOIN properties p_target
                    ON m.object_type = 'property' AND p_target.id = m.object_id
                LEFT JOIN buildings b_target
                    ON m.object_type = 'building' AND b_target.id = m.object_id
                LEFT JOIN units u_target
                    ON m.object_type = 'unit' AND u_target.id = m.object_id
                LEFT JOIN rooms r_target
                    ON m.object_type = 'room' AND r_target.id = m.object_id
                LEFT JOIN buildings b_for_unit ON b_for_unit.id = u_target.building_id
                LEFT JOIN units u_for_room ON u_for_room.id = r_target.unit_id
                LEFT JOIN buildings b_for_room ON b_for_room.id = u_for_room.building_id
                LEFT JOIN properties p ON p.id = CASE
                    WHEN m.object_type = 'property' THEN p_target.id
                    WHEN m.object_type = 'building' THEN b_target.property_id
                    WHEN m.object_type = 'unit' THEN b_for_unit.property_id
                    WHEN m.object_type = 'room' THEN b_for_room.property_id
                END
                ORDER BY mr.meter_id, mr.reading_date, mr.id
                """
            ).fetchall()
        )
        return {"meters": meters, "meter_readings": meter_readings}

    def create_meter(self, payload: dict) -> dict:
        object_type, object_id, property_id = self._normalize_meter_target(payload)
        label = _require_payload_value(payload, "label")
        unit = _require_payload_value(payload, "unit")
        cursor = self.connection.execute(
            """
            INSERT INTO meters (object_type, object_id, label, meter_type, unit, serial_number)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                object_type,
                object_id,
                label,
                payload.get("meter_type"),
                unit,
                payload.get("serial_number"),
            ),
        )
        return {
            "id": cursor.lastrowid,
            **payload,
            "object_type": object_type,
            "object_id": object_id,
            "property_id": property_id,
            "label": label,
            "unit": unit,
        }

    def update_meter(self, meter_id: int, payload: dict) -> dict:
        row = self.connection.execute(
            """
            SELECT id, object_type, object_id, label, meter_type, unit,
                   serial_number, is_archived
            FROM meters
            WHERE id = ?
            """,
            (meter_id,),
        ).fetchone()
        if row is None:
            raise ValueError("meter not found")
        if row["is_archived"]:
            raise ValueError("archived meter cannot be edited")

        object_type, object_id, property_id = self._normalize_meter_target(payload)
        label = _require_payload_value(payload, "label")
        unit = _require_payload_value(payload, "unit")
        target_changed = object_type != row["object_type"] or object_id != row["object_id"]
        unit_changed = unit != row["unit"]
        if target_changed or unit_changed:
            reading_count = self.connection.execute(
                "SELECT COUNT(*) FROM meter_readings WHERE meter_id = ?", (meter_id,)
            ).fetchone()[0]
            expense_count = self.connection.execute(
                "SELECT COUNT(*) FROM expense_items WHERE meter_id = ?", (meter_id,)
            ).fetchone()[0]
            if reading_count or expense_count:
                raise ValueError(
                    "object assignment or unit cannot be changed while meter has readings or dependent expenses"
                )

        self.connection.execute(
            """
            UPDATE meters
            SET object_type = ?, object_id = ?, label = ?,
                meter_type = ?, unit = ?, serial_number = ?
            WHERE id = ?
            """,
            (
                object_type,
                object_id,
                label,
                payload.get("meter_type"),
                unit,
                payload.get("serial_number"),
                meter_id,
            ),
        )
        return {
            "id": meter_id,
            "property_id": property_id,
            "object_type": object_type,
            "object_id": object_id,
            "label": label,
            "meter_type": payload.get("meter_type"),
            "unit": unit,
            "serial_number": payload.get("serial_number"),
        }

    def create_reading(self, payload: dict) -> dict:
        meter_id = _parse_int(payload.get("meter_id"), "meter_id")
        meter_row = self.lookup_meter(meter_id)
        if meter_row is None:
            raise ValueError("meter_id not found")
        if meter_row["is_archived"]:
            raise ValueError("meter_id must reference an active meter")

        reading_date = _require_payload_value(payload, "reading_date")
        parse_date(reading_date)
        reading_value = _parse_decimal(payload.get("reading_value"), "reading_value")
        existing_row = self.connection.execute(
            """
            SELECT id
            FROM meter_readings
            WHERE meter_id = ? AND reading_date = ?
            LIMIT 1
            """,
            (meter_id, reading_date),
        ).fetchone()
        if existing_row is not None:
            raise ValueError("reading_date already exists for meter")

        previous_row = self.connection.execute(
            """
            SELECT reading_date, reading_value
            FROM meter_readings
            WHERE meter_id = ? AND reading_date < ?
            ORDER BY reading_date DESC, id DESC
            LIMIT 1
            """,
            (meter_id, reading_date),
        ).fetchone()
        if previous_row is not None and reading_value < Decimal(str(previous_row["reading_value"])):
            raise ValueError("reading_value must not be lower than previous reading")

        next_row = self.connection.execute(
            """
            SELECT reading_date, reading_value
            FROM meter_readings
            WHERE meter_id = ? AND reading_date > ?
            ORDER BY reading_date ASC, id ASC
            LIMIT 1
            """,
            (meter_id, reading_date),
        ).fetchone()
        if next_row is not None and reading_value > Decimal(str(next_row["reading_value"])):
            raise ValueError("reading_value must not be higher than later reading")

        cursor = self.connection.execute(
            """
            INSERT INTO meter_readings (meter_id, reading_date, reading_value)
            VALUES (?, ?, ?)
            """,
            (meter_id, reading_date, str(reading_value)),
        )
        return {
            "id": cursor.lastrowid,
            "meter_id": meter_id,
            "reading_date": reading_date,
            "reading_value": str(reading_value),
        }

    def delete_reading(self, reading_id: int) -> dict:
        row = self.connection.execute(
            "SELECT id FROM meter_readings WHERE id = ?",
            (reading_id,),
        ).fetchone()
        if row is None:
            raise ValueError("meter reading not found")

        self.connection.execute("DELETE FROM meter_readings WHERE id = ?", (reading_id,))
        return {"resource": "meter_readings", "id": reading_id, "deleted": True}

    def archive_meter(self, meter_id: int) -> dict:
        row = self.connection.execute(
            "SELECT is_archived, archived_at FROM meters WHERE id = ?", (meter_id,)
        ).fetchone()
        if row is None:
            raise ValueError("meter not found")
        if row["is_archived"]:
            return {
                "resource": "meters", "id": meter_id,
                "is_archived": row["is_archived"], "archived_at": row["archived_at"],
            }

        archived_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.connection.execute(
            "UPDATE meters SET is_archived = 1, archived_at = ? WHERE id = ?",
            (archived_at, meter_id),
        )
        return {"resource": "meters", "id": meter_id, "is_archived": 1, "archived_at": archived_at}

    def restore_meter(self, meter_id: int) -> dict:
        row = self.connection.execute(
            "SELECT is_archived FROM meters WHERE id = ?", (meter_id,)
        ).fetchone()
        if row is None:
            raise ValueError("meter not found")
        if row["is_archived"]:
            self.connection.execute(
                "UPDATE meters SET is_archived = 0, archived_at = NULL WHERE id = ?",
                (meter_id,),
            )
        return {"resource": "meters", "id": meter_id, "is_archived": 0, "archived_at": None}

    def delete_meter(self, meter_id: int) -> dict:
        row = self.connection.execute(
            "SELECT is_archived FROM meters WHERE id = ?", (meter_id,)
        ).fetchone()
        if row is None:
            raise ValueError("meter not found")
        if not row["is_archived"]:
            raise ValueError("meter must be archived before deletion")

        reading_count = self.connection.execute(
            "SELECT COUNT(*) FROM meter_readings WHERE meter_id = ?", (meter_id,)
        ).fetchone()[0]
        expense_count = self.connection.execute(
            "SELECT COUNT(*) FROM expense_items WHERE meter_id = ?", (meter_id,)
        ).fetchone()[0]
        dependencies = []
        if reading_count:
            dependencies.append(f"meter_readings:{reading_count}")
        if expense_count:
            dependencies.append(f"expenses:{expense_count}")
        if dependencies:
            raise ValueError("dependencies prevent deletion of meter: " + ", ".join(dependencies))

        self.connection.execute("DELETE FROM meters WHERE id = ?", (meter_id,))
        return {"resource": "meters", "id": meter_id, "deleted": True}
