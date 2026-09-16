"""Tenants, rental contracts, room assignments, and advance-payment account links."""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from .calculations import parse_date
from .domain import Money


def _money(value: object, field_name: str) -> str:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        amount = Decimal(str(value))
    except Exception as error:  # Decimal raises several subclasses
        raise ValueError(f"{field_name} must be numeric") from error
    return str(Money(amount).amount)


class Tenancy:
    """Manage tenants and leases on a caller-owned SQLite transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_tenancy(self) -> dict[str, list[dict]]:
        tenants = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT id, full_name, email, phone,
                       alternate_street, alternate_postal_code, alternate_city
                FROM tenants ORDER BY id
                """
            ).fetchall()
        ]
        leases = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT l.*, u.label AS unit_label, r.label AS room_label,
                       t.full_name AS tenant_name,
                       CASE WHEN l.room_id IS NOT NULL THEN 'room' ELSE 'unit'
                       END AS rental_object_type,
                       CASE WHEN l.room_id IS NOT NULL
                            THEN r.label || ' (' || u.label || ')'
                            ELSE u.label
                       END AS rental_object_label
                FROM leases l
                JOIN units u ON u.id = l.unit_id
                LEFT JOIN rooms r ON r.id = l.room_id
                JOIN tenants t ON t.id = l.tenant_id
                ORDER BY l.id
                """
            ).fetchall()
        ]
        return {"tenants": tenants, "leases": leases}

    def create_tenant(self, payload: dict) -> dict:
        full_name = str(payload.get("full_name") or "").strip()
        if not full_name:
            raise ValueError("full_name is required")
        values = (
            full_name,
            payload.get("email"),
            payload.get("phone"),
            payload.get("alternate_street"),
            payload.get("alternate_postal_code"),
            payload.get("alternate_city"),
        )
        cursor = self.connection.execute(
            """
            INSERT INTO tenants (
                full_name, email, phone, alternate_street, alternate_postal_code, alternate_city
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return self._tenant_response(int(cursor.lastrowid), values)

    def update_tenant(self, tenant_id: int, payload: dict) -> dict:
        self._require_tenant(tenant_id)
        full_name = str(payload.get("full_name") or "").strip()
        if not full_name:
            raise ValueError("full_name is required")
        values = (
            full_name,
            payload.get("email"),
            payload.get("phone"),
            payload.get("alternate_street"),
            payload.get("alternate_postal_code"),
            payload.get("alternate_city"),
        )
        self.connection.execute(
            """
            UPDATE tenants SET full_name = ?, email = ?, phone = ?, alternate_street = ?,
                               alternate_postal_code = ?, alternate_city = ?
            WHERE id = ?
            """,
            (*values, tenant_id),
        )
        return self._tenant_response(tenant_id, values)

    def delete_tenant(self, tenant_id: int) -> dict:
        self._require_tenant(tenant_id)
        lease_count = self.connection.execute(
            "SELECT COUNT(*) FROM leases WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()[0]
        if lease_count:
            raise ValueError("tenant cannot be deleted while leases exist")
        payment_count = self.connection.execute(
            "SELECT COUNT(*) FROM gnucash_payments WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()[0]
        if payment_count:
            raise ValueError("tenant cannot be deleted while GnuCash payments exist")
        self.connection.execute("DELETE FROM tenant_documents WHERE tenant_id = ?", (tenant_id,))
        self.connection.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        return {"resource": "tenants", "id": tenant_id, "deleted": True}

    def create_lease(self, payload: dict) -> dict:
        normalized = self._normalize_lease(payload)
        cursor = self.connection.execute(
            """
            INSERT INTO leases (
                unit_id, room_id, tenant_id, rent_cold, additional_charges_advance,
                occupant_count, start_date, end_date, status,
                gnucash_nk_account_guid, gnucash_nk_account_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(normalized.values()),
        )
        return {"id": int(cursor.lastrowid), **normalized}

    def update_lease(self, lease_id: int, payload: dict) -> dict:
        self._require_lease(lease_id)
        normalized = self._normalize_lease(payload, lease_id)
        self.connection.execute(
            """
            UPDATE leases SET unit_id = ?, room_id = ?, tenant_id = ?, rent_cold = ?,
                              additional_charges_advance = ?, occupant_count = ?,
                              start_date = ?, end_date = ?, status = ?,
                              gnucash_nk_account_guid = ?, gnucash_nk_account_name = ?
            WHERE id = ?
            """,
            (*normalized.values(), lease_id),
        )
        return {"id": lease_id, **normalized}

    def delete_lease(self, lease_id: int) -> dict:
        self._require_lease(lease_id)
        payment_count = self.connection.execute(
            "SELECT COUNT(*) FROM gnucash_payments WHERE lease_id = ?", (lease_id,)
        ).fetchone()[0]
        if payment_count:
            raise ValueError("lease cannot be deleted while GnuCash payments exist")
        self.connection.execute("DELETE FROM lease_documents WHERE lease_id = ?", (lease_id,))
        self.connection.execute("DELETE FROM leases WHERE id = ?", (lease_id,))
        return {"resource": "leases", "id": lease_id, "deleted": True}

    def _require_tenant(self, tenant_id: int) -> None:
        row = self.connection.execute(
            "SELECT id FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
        if row is None:
            raise ValueError("tenant not found")

    def _require_lease(self, lease_id: int) -> None:
        row = self.connection.execute(
            "SELECT id FROM leases WHERE id = ?", (lease_id,)
        ).fetchone()
        if row is None:
            raise ValueError("lease not found")

    @staticmethod
    def _tenant_response(tenant_id: int, values: tuple) -> dict:
        return dict(
            zip(
                ("id", "full_name", "email", "phone", "alternate_street",
                 "alternate_postal_code", "alternate_city"),
                (tenant_id, *values),
                strict=True,
            )
        )

    def _normalize_lease(self, payload: dict, lease_id: int | None = None) -> dict:
        raw_tenant_id = payload.get("tenant_id")
        if raw_tenant_id in (None, ""):
            raise ValueError("lease requires tenant_id")
        tenant_id = int(raw_tenant_id)
        if self.connection.execute(
            "SELECT id FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone() is None:
            raise ValueError("lease requires existing tenant_id")

        raw_unit_id = payload.get("unit_id")
        raw_room_id = payload.get("room_id")
        unit_id = None if raw_unit_id in (None, "") else int(raw_unit_id)
        room_id = None if raw_room_id in (None, "") else int(raw_room_id)
        if unit_id is None and room_id is None:
            raise ValueError("lease requires unit_id or room_id")
        if room_id is not None:
            room = self.connection.execute(
                "SELECT unit_id, COALESCE(is_archived, 0) AS is_archived FROM rooms WHERE id = ?",
                (room_id,),
            ).fetchone()
            if room is None:
                raise ValueError("lease requires existing room_id")
            if room["is_archived"]:
                raise ValueError("archived room cannot be assigned to lease")
            if unit_id is not None and unit_id != room["unit_id"]:
                raise ValueError("room_id must belong to unit_id")
            unit_id = int(room["unit_id"])
        unit = self.connection.execute(
            "SELECT COALESCE(is_archived, 0) AS is_archived FROM units WHERE id = ?",
            (unit_id,),
        ).fetchone()
        if unit is None:
            raise ValueError("lease requires existing unit_id")
        if unit["is_archived"]:
            raise ValueError("archived unit cannot be assigned to lease")

        start_date = parse_date(str(payload["start_date"])).isoformat()
        raw_end_date = payload.get("end_date")
        end_date = (
            None if raw_end_date in (None, "") else parse_date(str(raw_end_date)).isoformat()
        )
        if end_date is not None and end_date < start_date:
            raise ValueError("end_date must be after or equal to start_date")
        occupant_count = int(payload["occupant_count"])
        if occupant_count < 1:
            raise ValueError("occupant_count must be at least 1")

        account_guid = str(payload.get("gnucash_nk_account_guid") or "").strip() or None
        account_name = str(payload.get("gnucash_nk_account_name") or "").strip() or None
        if account_guid is not None:
            linked = self.connection.execute(
                "SELECT id FROM leases WHERE gnucash_nk_account_guid = ?",
                (account_guid,),
            ).fetchone()
            if linked is not None and linked["id"] != lease_id:
                raise ValueError("a GnuCash NK account can only be assigned to one lease")

        return {
            "unit_id": unit_id,
            "room_id": room_id,
            "tenant_id": tenant_id,
            "rent_cold": _money(payload.get("rent_cold"), "rent_cold"),
            "additional_charges_advance": _money(
                payload.get("additional_charges_advance"), "additional_charges_advance"
            ),
            "occupant_count": occupant_count,
            "start_date": start_date,
            "end_date": end_date,
            "status": payload.get("status", "active"),
            "gnucash_nk_account_guid": account_guid,
            "gnucash_nk_account_name": account_name,
        }
