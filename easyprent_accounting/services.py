from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .asset_registry import AssetRegistry
from .depreciation import Depreciation
from .metering import Metering
from .expenses import Expenses
from .tenancy import Tenancy


def _row_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def health_status() -> dict:
    return {
        "status": "ok",
        "reachable": True,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }


def list_overview(connection: sqlite3.Connection) -> dict:
    assets = AssetRegistry(connection).list_assets()
    properties = assets["properties"]
    buildings = assets["buildings"]
    units = assets["units"]
    rooms = assets["rooms"]
    tenancy = Tenancy(connection).list_tenancy()
    tenants = tenancy["tenants"]
    leases = tenancy["leases"]
    expense_data = Expenses(connection).list_expenses()
    expenses = expense_data["expenses"]
    expense_categories = expense_data["expense_categories"]
    meter_data = Metering(connection).list_meters()
    meters = meter_data["meters"]
    meter_readings = meter_data["meter_readings"]
    depreciation_assets = Depreciation(connection).list_assets()
    users = _row_dicts(
        connection.execute(
            """
            SELECT u.full_name, u.email, m.role, o.name AS organization_name
            FROM memberships m
            JOIN users u ON u.id = m.user_id
            JOIN organizations o ON o.id = m.organization_id
            ORDER BY u.id
            """
        ).fetchall()
    )

    return {
        "summary": {
            "properties": len(properties),
            "buildings": len(buildings),
            "units": len(units),
            "rooms": len(rooms),
            "meters": len(meters),
            "tenants": len(tenants),
            "leases": len(leases),
            "expenses": len(expenses),
            "depreciation_assets": len(depreciation_assets),
        },
        "roles": users,
        "properties": properties,
        "buildings": buildings,
        "units": units,
        "rooms": rooms,
        "meters": meters,
        "meter_readings": meter_readings,
        "tenants": tenants,
        "leases": leases,
        "expenses": expenses,
        "expense_categories": expense_categories,
        "depreciation_assets": depreciation_assets,
    }
