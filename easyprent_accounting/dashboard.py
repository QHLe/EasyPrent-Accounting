"""Dashboard read-model: lightweight aggregate summary for the UI landing page."""

from __future__ import annotations

import sqlite3


def _row_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


class Dashboard:
    """Produces a summary snapshot for the dashboard view.

    Unlike the former ``list_overview()`` this intentionally returns only
    aggregate counts and user-role metadata — full entity lists belong to
    their respective domain modules.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def summary(self) -> dict:
        counts = self.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM properties)          AS properties,
                (SELECT COUNT(*) FROM buildings)           AS buildings,
                (SELECT COUNT(*) FROM units)               AS units,
                (SELECT COUNT(*) FROM rooms)               AS rooms,
                (SELECT COUNT(*) FROM meters)              AS meters,
                (SELECT COUNT(*) FROM tenants)             AS tenants,
                (SELECT COUNT(*) FROM leases)              AS leases,
                (SELECT COUNT(*) FROM expense_items)       AS expenses,
                (SELECT COUNT(*) FROM depreciation_assets) AS depreciation_assets
            """
        ).fetchone()

        roles = _row_dicts(
            self.connection.execute(
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
            "summary": dict(counts),
            "roles": roles,
        }
