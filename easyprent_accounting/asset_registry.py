"""Asset Registry for properties, buildings, units, and rooms."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from .domain import Percentage


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


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def _normalize_optional_decimal_string(value: object, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return _decimal_to_string(_parse_decimal(value, field_name))


def _normalize_area_share_percent(value: object) -> str | None:
    return _normalize_percentage(value, "area_share_percent")


def _normalize_percentage(value: object, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    percentage = Percentage(_parse_decimal(value, field_name)).value
    return _decimal_to_string(percentage)


def _asset_rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def _expense_dependency_query(object_type: str) -> str:
    return (
        "SELECT COUNT(*) FROM expense_items "
        f"WHERE object_type = '{object_type}' AND object_id = ?"
    )


def _meter_dependency_query(object_type: str) -> str:
    return "SELECT COUNT(*) FROM meters " f"WHERE object_type = '{object_type}' AND object_id = ?"


OBJECT_LIFECYCLE = {
    "properties": {
        "table": "properties",
        "label": "property",
        "dependencies": [
            {"table": "buildings", "foreign_key": "property_id", "label": "buildings"},
            {"query": _meter_dependency_query("property"), "label": "meters"},
            {"query": _expense_dependency_query("property"), "label": "expenses"},
            {"table": "depreciation_assets", "foreign_key": "property_id", "label": "depreciation_assets"},
        ],
    },
    "buildings": {
        "table": "buildings",
        "label": "building",
        "dependencies": [
            {"table": "units", "foreign_key": "building_id", "label": "units"},
            {"query": _meter_dependency_query("building"), "label": "meters"},
            {"query": _expense_dependency_query("building"), "label": "expenses"},
        ],
    },
    "units": {
        "table": "units",
        "label": "unit",
        "dependencies": [
            {"table": "rooms", "foreign_key": "unit_id", "label": "rooms"},
            {"table": "leases", "foreign_key": "unit_id", "label": "leases"},
            {"query": _meter_dependency_query("unit"), "label": "meters"},
            {"query": _expense_dependency_query("unit"), "label": "expenses"},
        ],
    },
    "rooms": {
        "table": "rooms",
        "label": "room",
        "dependencies": [
            {"query": _meter_dependency_query("room"), "label": "meters"},
            {"query": _expense_dependency_query("room"), "label": "expenses"},
        ],
    },
}

def _get_lifecycle_config(resource_name: str) -> dict:
    config = OBJECT_LIFECYCLE.get(resource_name)
    if config is None:
        raise ValueError(f"unsupported resource: {resource_name}")
    return config


def _archive_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _count_lifecycle_dependency(
    connection: sqlite3.Connection,
    dependency: dict,
    object_id: int,
) -> int:
    if "query" in dependency:
        return connection.execute(dependency["query"], (object_id,)).fetchone()[0]
    return connection.execute(
        f"SELECT COUNT(*) FROM {dependency['table']} WHERE {dependency['foreign_key']} = ?",
        (object_id,),
    ).fetchone()[0]


@dataclass(frozen=True, slots=True)
class AssetTarget:
    property_id: int | None


class AssetRegistry:
    """Persist and manage the lifecycle of rental assets."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _require_organization(self, organization_id: int) -> None:
        if self.connection.execute(
            "SELECT id FROM organizations WHERE id = ?", (organization_id,)
        ).fetchone() is None:
            raise ValueError("organization_id not found")

    def _require_property(self, property_id: int | None) -> None:
        if property_id is not None and self.connection.execute(
            "SELECT id FROM properties WHERE id = ?", (property_id,)
        ).fetchone() is None:
            raise ValueError("property_id not found")

    def resolve_target(self, object_type: str, object_id: int) -> AssetTarget | None:
        if object_type == "property":
            row = self.connection.execute(
                "SELECT id AS property_id FROM properties WHERE id = ?",
                (object_id,),
            ).fetchone()
        elif object_type == "building":
            row = self.connection.execute(
                "SELECT property_id FROM buildings WHERE id = ?",
                (object_id,),
            ).fetchone()
        elif object_type == "unit":
            row = self.connection.execute(
                """
                SELECT b.property_id
                FROM units u LEFT JOIN buildings b ON b.id = u.building_id
                WHERE u.id = ?
                """,
                (object_id,),
            ).fetchone()
        elif object_type == "room":
            row = self.connection.execute(
                """
                SELECT b.property_id
                FROM rooms r JOIN units u ON u.id = r.unit_id
                LEFT JOIN buildings b ON b.id = u.building_id
                WHERE r.id = ?
                """,
                (object_id,),
            ).fetchone()
        else:
            raise ValueError("object_type must be property, building, unit or room")
        if row is None:
            return None
        return AssetTarget(
            property_id=None if row["property_id"] is None else int(row["property_id"]),
        )

    def list_assets(self) -> dict[str, list[dict]]:
        """Return asset rows and their display relationships for the overview."""
        properties = _asset_rows(
            self.connection.execute(
                """
                SELECT
                    p.*,
                    o.name AS organization_name,
                    COUNT(DISTINCT b.id) AS building_count,
                    COUNT(DISTINCT u.id) AS unit_count,
                    COUNT(DISTINCT r.id) AS room_count,
                    COUNT(DISTINCT e.id) AS expense_count
                FROM properties p
                JOIN organizations o ON o.id = p.organization_id
                LEFT JOIN buildings b ON b.property_id = p.id
                LEFT JOIN units u ON u.building_id = b.id
                LEFT JOIN rooms r ON r.unit_id = u.id
                LEFT JOIN expense_items e ON
                    (e.object_type = 'property' AND e.object_id = p.id)
                    OR (e.object_type = 'building' AND e.object_id = b.id)
                    OR (e.object_type = 'unit' AND e.object_id = u.id)
                    OR (e.object_type = 'room' AND e.object_id = r.id)
                GROUP BY p.id, o.name
                ORDER BY p.id
                """
            ).fetchall()
        )
        buildings = _asset_rows(
            self.connection.execute(
                """
                SELECT
                    b.*,
                    p.name AS property_name,
                    COUNT(DISTINCT u.id) AS unit_count,
                    COUNT(DISTINCT r.id) AS room_count
                FROM buildings b
                LEFT JOIN properties p ON p.id = b.property_id
                LEFT JOIN units u ON u.building_id = b.id
                LEFT JOIN rooms r ON r.unit_id = u.id
                GROUP BY b.id, p.name
                ORDER BY b.id
                """
            ).fetchall()
        )
        units = _asset_rows(
            self.connection.execute(
                """
                SELECT
                    u.*,
                    b.property_id AS property_id,
                    b.name AS building_name,
                    p.name AS property_name,
                    COUNT(r.id) AS actual_room_count
                FROM units u
                LEFT JOIN buildings b ON b.id = u.building_id
                LEFT JOIN properties p ON p.id = b.property_id
                LEFT JOIN rooms r ON r.unit_id = u.id
                GROUP BY u.id, b.property_id, b.name, p.name
                ORDER BY u.id
                """
            ).fetchall()
        )
        rooms = _asset_rows(
            self.connection.execute(
                """
                SELECT
                    r.*,
                    u.label AS unit_label,
                    u.building_id AS building_id,
                    b.property_id AS property_id,
                    b.name AS building_name,
                    p.name AS property_name
                FROM rooms r
                JOIN units u ON u.id = r.unit_id
                LEFT JOIN buildings b ON b.id = u.building_id
                LEFT JOIN properties p ON p.id = b.property_id
                ORDER BY r.id
                """
            ).fetchall()
        )
        for room in rooms:
            room["area_sqm"] = _normalize_optional_decimal_string(
                room.get("area_sqm"), "area_sqm"
            )
            room["area_share_percent"] = _normalize_area_share_percent(
                room.get("area_share_percent")
            )
        organizations = _asset_rows(
            self.connection.execute(
                "SELECT id, name FROM organizations ORDER BY name, id"
            ).fetchall()
        )
        return {
            "organizations": organizations,
            "properties": properties,
            "buildings": buildings,
            "units": units,
            "rooms": rooms,
        }

    def create_property(self, payload: dict) -> dict:
        self._require_organization(payload["organization_id"])
        cursor = self.connection.execute(
            """
            INSERT INTO properties (organization_id, name, street, city, postal_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["organization_id"],
                payload["name"],
                payload["street"],
                payload["city"],
                payload["postal_code"],
            ),
        )
        return {"id": cursor.lastrowid, **payload}


    def create_building(self, payload: dict) -> dict:
        self._require_property(payload.get("property_id"))
        cursor = self.connection.execute(
            """
            INSERT INTO buildings (property_id, name, year_built, street, city, postal_code)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("property_id"),
                payload["name"],
                payload.get("year_built"),
                payload["street"],
                payload["city"],
                payload["postal_code"],
            ),
        )
        return {"id": cursor.lastrowid, **payload}


    def _unit_address(self, payload: dict) -> tuple[str, str, str]:
        building_id = payload.get("building_id")
        if building_id is None:
            return payload["street"], payload["city"], payload["postal_code"]

        building = self.connection.execute(
            "SELECT street, city, postal_code FROM buildings WHERE id = ?",
            (building_id,),
        ).fetchone()
        if building is None:
            raise ValueError("building not found")
        return building["street"], building["city"], building["postal_code"]


    def create_unit(self, payload: dict) -> dict:
        street, city, postal_code = self._unit_address(payload)
        mea_percent = _normalize_percentage(
            _require_payload_value(payload, "mea_percent"), "mea_percent"
        )
        cursor = self.connection.execute(
            """
            INSERT INTO units (building_id, label, area_sqm, mea_percent, room_count, street, city, postal_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("building_id"),
                payload["label"],
                str(Decimal(str(payload["area_sqm"]))),
                mea_percent,
                payload["room_count"],
                street,
                city,
                postal_code,
            ),
        )
        return {
            "id": cursor.lastrowid,
            **payload,
            "street": street,
            "city": city,
            "postal_code": postal_code,
        }


    def create_room(self, payload: dict) -> dict:
        unit_id = _parse_int(payload.get("unit_id"), "unit_id")
        label = _require_payload_value(payload, "label")
        area_sqm = _normalize_optional_decimal_string(payload.get("area_sqm"), "area_sqm")
        area_share_percent = _normalize_area_share_percent(payload.get("area_share_percent"))

        unit_row = self.connection.execute(
            """
            SELECT u.room_count, COUNT(r.id) AS actual_room_count
            FROM units u
            LEFT JOIN rooms r ON r.unit_id = u.id
            WHERE u.id = ?
            GROUP BY u.id, u.room_count
            """,
            (unit_id,),
        ).fetchone()
        if unit_row is None:
            raise ValueError("room requires existing unit_id")
        if unit_row["actual_room_count"] >= unit_row["room_count"]:
            raise ValueError("room_count limit reached for unit")

        cursor = self.connection.execute(
            "INSERT INTO rooms (unit_id, label, area_sqm, area_share_percent) VALUES (?, ?, ?, ?)",
            (unit_id, label, area_sqm, area_share_percent),
        )
        return {
            "id": cursor.lastrowid,
            "unit_id": unit_id,
            "label": label,
            "area_sqm": area_sqm,
            "area_share_percent": area_share_percent,
        }


    def update_property(self, property_id: int, payload: dict) -> dict:
        row = self.connection.execute(
            "SELECT id, is_archived FROM properties WHERE id = ?",
            (property_id,),
        ).fetchone()
        if row is None:
            raise ValueError("property not found")
        if row["is_archived"]:
            raise ValueError("archived property cannot be edited")

        self._require_organization(payload["organization_id"])

        self.connection.execute(
            """
            UPDATE properties
            SET organization_id = ?, name = ?, street = ?, city = ?, postal_code = ?
            WHERE id = ?
            """,
            (
                payload["organization_id"],
                payload["name"],
                payload["street"],
                payload["city"],
                payload["postal_code"],
                property_id,
            ),
        )
        return {"id": property_id, **payload}


    def update_building(self, building_id: int, payload: dict) -> dict:
        row = self.connection.execute(
            "SELECT id, is_archived FROM buildings WHERE id = ?",
            (building_id,),
        ).fetchone()
        if row is None:
            raise ValueError("building not found")
        if row["is_archived"]:
            raise ValueError("archived building cannot be edited")

        self._require_property(payload.get("property_id"))

        self.connection.execute(
            """
            UPDATE buildings
            SET property_id = ?, name = ?, year_built = ?, street = ?, city = ?, postal_code = ?
            WHERE id = ?
            """,
            (
                payload.get("property_id"),
                payload["name"],
                payload.get("year_built"),
                payload["street"],
                payload["city"],
                payload["postal_code"],
                building_id,
            ),
        )
        return {"id": building_id, **payload}


    def update_unit(self, unit_id: int, payload: dict) -> dict:
        row = self.connection.execute(
            "SELECT id, is_archived FROM units WHERE id = ?",
            (unit_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unit not found")
        if row["is_archived"]:
            raise ValueError("archived unit cannot be edited")

        requested_room_count = int(payload["room_count"])
        room_count_row = self.connection.execute(
            """
            SELECT COUNT(*) AS actual_room_count
            FROM rooms
            WHERE unit_id = ?
            """,
            (unit_id,),
        ).fetchone()
        if room_count_row is not None and room_count_row["actual_room_count"] > requested_room_count:
            raise ValueError("room_count cannot be lower than existing rooms")

        street, city, postal_code = self._unit_address(payload)
        mea_percent = _normalize_percentage(
            _require_payload_value(payload, "mea_percent"), "mea_percent"
        )
        self.connection.execute(
            """
            UPDATE units
            SET building_id = ?, label = ?, area_sqm = ?, mea_percent = ?, room_count = ?, street = ?, city = ?, postal_code = ?
            WHERE id = ?
            """,
            (
                payload.get("building_id"),
                payload["label"],
                str(Decimal(str(payload["area_sqm"]))),
                mea_percent,
                requested_room_count,
                street,
                city,
                postal_code,
                unit_id,
            ),
        )
        return {
            "id": unit_id,
            **payload,
            "street": street,
            "city": city,
            "postal_code": postal_code,
        }


    def update_room(self, room_id: int, payload: dict) -> dict:
        row = self.connection.execute(
            "SELECT id, is_archived FROM rooms WHERE id = ?",
            (room_id,),
        ).fetchone()
        if row is None:
            raise ValueError("room not found")
        if row["is_archived"]:
            raise ValueError("archived room cannot be edited")

        unit_id = _parse_int(payload.get("unit_id"), "unit_id")
        label = _require_payload_value(payload, "label")
        area_sqm = _normalize_optional_decimal_string(payload.get("area_sqm"), "area_sqm")
        area_share_percent = _normalize_area_share_percent(payload.get("area_share_percent"))
        unit_row = self.connection.execute(
            """
            SELECT u.room_count, COUNT(r.id) AS actual_room_count
            FROM units u
            LEFT JOIN rooms r ON r.unit_id = u.id AND r.id != ?
            WHERE u.id = ?
            GROUP BY u.id, u.room_count
            """,
            (room_id, unit_id),
        ).fetchone()
        if unit_row is None:
            raise ValueError("room requires existing unit_id")
        if unit_row["actual_room_count"] >= unit_row["room_count"]:
            raise ValueError("room_count limit reached for unit")

        self.connection.execute(
            "UPDATE rooms SET unit_id = ?, label = ?, area_sqm = ?, area_share_percent = ? WHERE id = ?",
            (unit_id, label, area_sqm, area_share_percent, room_id),
        )
        return {
            "id": room_id,
            "unit_id": unit_id,
            "label": label,
            "area_sqm": area_sqm,
            "area_share_percent": area_share_percent,
        }


    def _archive(self, resource_name: str, object_id: int) -> dict:
        config = _get_lifecycle_config(resource_name)
        row = self.connection.execute(
            f"SELECT id, is_archived, archived_at FROM {config['table']} WHERE id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"{config['label']} not found")
        if row["is_archived"]:
            return {
                "resource": resource_name,
                "id": object_id,
                "is_archived": row["is_archived"],
                "archived_at": row["archived_at"],
            }

        archived_at = _archive_timestamp()
        self.connection.execute(
            f"UPDATE {config['table']} SET is_archived = 1, archived_at = ? WHERE id = ?",
            (archived_at, object_id),
        )
        return {
            "resource": resource_name,
            "id": object_id,
            "is_archived": 1,
            "archived_at": archived_at,
        }


    def _restore(self, resource_name: str, object_id: int) -> dict:
        config = _get_lifecycle_config(resource_name)
        row = self.connection.execute(
            f"SELECT id, is_archived, archived_at FROM {config['table']} WHERE id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"{config['label']} not found")
        if not row["is_archived"]:
            return {
                "resource": resource_name,
                "id": object_id,
                "is_archived": 0,
                "archived_at": None,
            }

        self.connection.execute(
            f"UPDATE {config['table']} SET is_archived = 0, archived_at = NULL WHERE id = ?",
            (object_id,),
        )
        return {
            "resource": resource_name,
            "id": object_id,
            "is_archived": 0,
            "archived_at": None,
        }


    def _delete(self, resource_name: str, object_id: int) -> dict:
        config = _get_lifecycle_config(resource_name)
        row = self.connection.execute(
            f"SELECT id, is_archived FROM {config['table']} WHERE id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"{config['label']} not found")
        if not row["is_archived"]:
            raise ValueError(f"{config['label']} must be archived before deletion")

        dependency_counts: list[str] = []
        for dependency in config["dependencies"]:
            dependency_count = _count_lifecycle_dependency(self.connection, dependency, object_id)
            if dependency_count:
                dependency_counts.append(f"{dependency['label']}:{dependency_count}")

        if dependency_counts:
            raise ValueError(
                f"dependencies prevent deletion of {config['label']}: " + ", ".join(dependency_counts)
            )

        self.connection.execute(f"DELETE FROM {config['table']} WHERE id = ?", (object_id,))
        return {"resource": resource_name, "id": object_id, "deleted": True}


    def archive_property(self, property_id: int) -> dict:
        return self._archive("properties", property_id)

    def restore_property(self, property_id: int) -> dict:
        return self._restore("properties", property_id)

    def delete_property(self, property_id: int) -> dict:
        return self._delete("properties", property_id)

    def archive_building(self, building_id: int) -> dict:
        return self._archive("buildings", building_id)

    def restore_building(self, building_id: int) -> dict:
        return self._restore("buildings", building_id)

    def delete_building(self, building_id: int) -> dict:
        return self._delete("buildings", building_id)

    def archive_unit(self, unit_id: int) -> dict:
        return self._archive("units", unit_id)

    def restore_unit(self, unit_id: int) -> dict:
        return self._restore("units", unit_id)

    def delete_unit(self, unit_id: int) -> dict:
        return self._delete("units", unit_id)

    def archive_room(self, room_id: int) -> dict:
        return self._archive("rooms", room_id)

    def restore_room(self, room_id: int) -> dict:
        return self._restore("rooms", room_id)

    def delete_room(self, room_id: int) -> dict:
        return self._delete("rooms", room_id)
