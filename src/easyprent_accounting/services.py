from __future__ import annotations

import base64
import binascii
import html
from io import BytesIO
import json
import os
import sqlite3
import urllib.error
import urllib.request
import uuid
from socket import timeout as socket_timeout
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .calculations import (
    SettlementExpense,
    SettlementLease,
    calculate_depreciation_schedule,
    calculate_settlement,
    parse_date,
    quantize_money,
)
from .expense_math import (
    day_accurate_recurring_amount,
    meter_consumption_for_period,
    overlap_period,
)
from .integrations.gnucash import (
    GnuCashAccount,
    GnuCashReader,
    PiecashGnuCashReader,
)
from .ods_template import render_settlement_template


APP_DATA_EXPORT_TABLES = [
    "organizations",
    "users",
    "memberships",
    "properties",
    "buildings",
    "units",
    "rooms",
    "meters",
    "meter_readings",
    "tenants",
    "leases",
    "expense_items",
    "application_settings",
    "gnucash_payments",
    "settlement_runs",
    "settlement_payment_assignments",
    "expense_documents",
    "tenant_documents",
    "lease_documents",
    "depreciation_assets",
]

DOCUMENT_EXPORT_TABLES = {
    "expense_documents",
    "tenant_documents",
    "lease_documents",
}

OPEN_ENDED_PERIOD_END = "9999-12-31"
APPLICATION_EXPORT_FORMAT_VERSION = 2


def _row_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def _derive_charge_fields(payload: dict) -> tuple[str, str, str | None]:
    explicit_charge_type = payload.get("charge_type")
    recurrence = payload.get("recurrence")
    interval_name = payload.get("interval") or payload.get("interval_name")

    if explicit_charge_type == "consumption":
        return "consumption", "one_time", None

    if recurrence == "recurring":
        if interval_name == "yearly":
            return "yearly", "recurring", "yearly"
        if interval_name == "quarterly":
            return "quarterly", "recurring", "quarterly"
        return "monthly", "recurring", "monthly"

    charge_type = explicit_charge_type or "one_time"
    if charge_type in {"monthly", "quarterly", "yearly"}:
        return charge_type, "recurring", charge_type
    return "one_time", "one_time", None


def _require_payload_value(payload: dict, field_name: str) -> str:
    value = payload.get(field_name)
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value)


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
        return Decimal(str(value))
    except Exception as error:  # pragma: no cover - Decimal raises multiple subclasses
        raise ValueError(f"{field_name} must be numeric") from error


def _decimal_places(value: Decimal) -> int:
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    return -exponent if exponent < 0 else 0


def _normalize_expense_amount(raw_value: object, charge_type: str) -> Decimal:
    amount = _parse_decimal(raw_value, "amount")
    max_places = 10
    if _decimal_places(amount) > max_places:
        raise ValueError(f"amount supports max {max_places} decimal places")
    return amount


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


def _normalize_optional_decimal_string(value: object, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return _decimal_to_string(_parse_decimal(value, field_name))


def _mask_token_last4(token: str | None) -> str | None:
    normalized = str(token or "")
    if normalized == "":
        return None
    if len(normalized) <= 4:
        return "•" * len(normalized)
    return f"{'•' * max(8, len(normalized) - 4)}{normalized[-4:]}"


def _normalize_bool(raw_value: object, field_name: str) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, int) and raw_value in (0, 1):
        return bool(raw_value)
    normalized = str(raw_value or "").strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{field_name} must be boolean")


def _normalize_paperless_base_url(raw_value: object) -> str:
    normalized = str(raw_value or "").strip().rstrip("/")
    if normalized == "":
        raise ValueError("base_url is required")
    if not (normalized.startswith("http://") or normalized.startswith("https://")):
        raise ValueError("base_url must start with http:// or https://")
    return normalized


def get_paperless_settings(connection: sqlite3.Connection) -> dict:
    row = connection.execute(
        """
        SELECT base_url, api_token, updated_at
        FROM paperless_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {
            "base_url": "",
            "token_present": False,
            "token_masked": None,
            "updated_at": None,
        }

    token = str(row["api_token"] or "")
    return {
        "base_url": str(row["base_url"] or ""),
        "token_present": token != "",
        "token_masked": _mask_token_last4(token),
        "updated_at": row["updated_at"],
    }


def get_application_settings(connection: sqlite3.Connection) -> dict:
    row = connection.execute(
        """
        SELECT show_delete_actions, updated_at
        FROM application_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {
            "show_delete_actions": True,
            "updated_at": None,
        }

    return {
        "show_delete_actions": bool(int(row["show_delete_actions"] or 0)),
        "updated_at": row["updated_at"],
    }


def _mask_password(password: str | None) -> str | None:
    normalized = str(password or "")
    if normalized == "":
        return None
    return "•" * max(8, len(normalized))


def _get_gnucash_settings_row(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT host, port, database_name, username, password, sslmode, updated_at
        FROM gnucash_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()


def get_gnucash_settings(connection: sqlite3.Connection) -> dict:
    row = _get_gnucash_settings_row(connection)
    if row is None:
        return {
            "configured": False,
            "host": "",
            "port": 5432,
            "database": "",
            "username": "",
            "password_present": False,
            "password_masked": None,
            "sslmode": "require",
            "updated_at": None,
        }
    password = str(row["password"] or "")
    return {
        "configured": True,
        "host": str(row["host"]),
        "port": int(row["port"]),
        "database": str(row["database_name"]),
        "username": str(row["username"]),
        "password_present": password != "",
        "password_masked": _mask_password(password),
        "sslmode": str(row["sslmode"] or "require"),
        "updated_at": row["updated_at"],
    }


def _gnucash_connection_settings(connection: sqlite3.Connection) -> dict:
    row = _get_gnucash_settings_row(connection)
    if row is None:
        raise ValueError("GnuCash connection is not configured")
    return {
        "host": str(row["host"]),
        "port": int(row["port"]),
        "database": str(row["database_name"]),
        "username": str(row["username"]),
        "password": str(row["password"]),
        "sslmode": str(row["sslmode"] or "require"),
    }


def update_gnucash_settings(connection: sqlite3.Connection, payload: dict) -> dict:
    host = _require_payload_value(payload, "host").strip()
    database = _require_payload_value(payload, "database").strip()
    username = _require_payload_value(payload, "username").strip()
    port = _parse_int(payload.get("port"), "port")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    sslmode = str(payload.get("sslmode") or "require").strip()
    if sslmode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ValueError("sslmode is invalid")

    existing = _get_gnucash_settings_row(connection)
    password_input = payload.get("password")
    password = str(password_input or "")
    if password == "" and existing is not None:
        password = str(existing["password"])
    if password == "":
        raise ValueError("password is required")

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    existing_id = connection.execute(
        "SELECT id FROM gnucash_settings ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if existing_id is None:
        connection.execute(
            """
            INSERT INTO gnucash_settings (
                host, port, database_name, username, password, sslmode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (host, port, database, username, password, sslmode, timestamp, timestamp),
        )
    else:
        connection.execute(
            """
            UPDATE gnucash_settings
            SET host = ?, port = ?, database_name = ?, username = ?, password = ?,
                sslmode = ?, updated_at = ?
            WHERE id = ?
            """,
            (host, port, database, username, password, sslmode, timestamp, existing_id["id"]),
        )
    connection.commit()
    return get_gnucash_settings(connection)


def list_gnucash_accounts(
    connection: sqlite3.Connection,
    reader: GnuCashReader | None = None,
) -> list[dict]:
    active_reader = reader or PiecashGnuCashReader()
    accounts: list[GnuCashAccount] = active_reader.list_accounts(
        _gnucash_connection_settings(connection)
    )
    return [
        {
            "guid": account.guid,
            "name": account.name,
            "full_name": account.full_name,
            "parent_guid": account.parent_guid,
        }
        for account in accounts
    ]


def update_application_settings(connection: sqlite3.Connection, payload: dict) -> dict:
    show_delete_actions = _normalize_bool(
        payload.get("show_delete_actions"),
        "show_delete_actions",
    )
    existing_row = connection.execute(
        """
        SELECT id
        FROM application_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    if existing_row is None:
        connection.execute(
            """
            INSERT INTO application_settings (show_delete_actions, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (1 if show_delete_actions else 0, timestamp, timestamp),
        )
    else:
        connection.execute(
            """
            UPDATE application_settings
            SET show_delete_actions = ?, updated_at = ?
            WHERE id = ?
            """,
            (1 if show_delete_actions else 0, timestamp, int(existing_row["id"])),
        )
    connection.commit()
    return get_application_settings(connection)


def update_paperless_settings(connection: sqlite3.Connection, payload: dict) -> dict:
    base_url = _normalize_paperless_base_url(payload.get("base_url"))
    token_input = payload.get("api_token")
    existing_row = connection.execute(
        """
        SELECT id, api_token
        FROM paperless_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if token_input in (None, ""):
        if existing_row is None or str(existing_row["api_token"] or "") == "":
            raise ValueError("api_token is required")
        normalized_token = str(existing_row["api_token"])
    else:
        normalized_token = str(token_input).strip()
        if normalized_token == "":
            raise ValueError("api_token is required")

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    if existing_row is None:
        connection.execute(
            """
            INSERT INTO paperless_settings (base_url, api_token, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (base_url, normalized_token, timestamp, timestamp),
        )
    else:
        connection.execute(
            """
            UPDATE paperless_settings
            SET base_url = ?, api_token = ?, updated_at = ?
            WHERE id = ?
            """,
            (base_url, normalized_token, timestamp, int(existing_row["id"])),
        )
    connection.commit()
    return get_paperless_settings(connection)


def _table_column_names(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]


def _encode_application_export_value(value: object) -> object:
    if isinstance(value, bytes):
        return {
            "__type__": "bytes",
            "base64": base64.b64encode(value).decode("ascii"),
        }
    return value


def _decode_application_import_value(value: object) -> object:
    if isinstance(value, dict) and value.get("__type__") == "bytes":
        encoded = value.get("base64")
        if encoded in (None, ""):
            return b""
        try:
            return base64.b64decode(str(encoded), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("invalid base64 payload in import data") from error
    return value


def _export_application_table_rows(connection: sqlite3.Connection, table_name: str) -> list[dict]:
    columns = _table_column_names(connection, table_name)
    if table_name in DOCUMENT_EXPORT_TABLES:
        rows = _row_dicts(
            connection.execute(
                f"""
                SELECT * FROM {table_name}
                WHERE paperless_document_id IS NOT NULL
                  AND TRIM(paperless_document_id) != ''
                ORDER BY id
                """
            ).fetchall()
        )
        return [
            {
                column_name: _encode_application_export_value(
                    b"" if column_name == "content_blob" else row.get(column_name)
                )
                for column_name in columns
            }
            for row in rows
        ]

    rows = _row_dicts(connection.execute(f"SELECT * FROM {table_name} ORDER BY id").fetchall())
    return [
        {
            column_name: _encode_application_export_value(row.get(column_name))
            for column_name in columns
        }
        for row in rows
    ]


def export_application_data(connection: sqlite3.Connection) -> dict:
    exported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    tables: dict[str, list[dict]] = {}
    total_rows = 0

    for table_name in APP_DATA_EXPORT_TABLES:
        exported_rows = _export_application_table_rows(connection, table_name)
        tables[table_name] = exported_rows
        total_rows += len(exported_rows)

    return {
        "format_version": APPLICATION_EXPORT_FORMAT_VERSION,
        "exported_at": exported_at,
        "table_count": len(APP_DATA_EXPORT_TABLES),
        "row_count": total_rows,
        "tables": tables,
    }


def _migrate_legacy_import_gnucash_accounts(tables_payload: dict) -> int:
    tenant_rows = tables_payload.get("tenants", [])
    lease_rows = tables_payload.get("leases", [])
    payment_rows = tables_payload.get("gnucash_payments", [])
    if not all(isinstance(rows, list) for rows in (tenant_rows, lease_rows, payment_rows)):
        return 0

    linked_account_guids = {
        str(lease.get("gnucash_nk_account_guid"))
        for lease in lease_rows
        if isinstance(lease, dict) and lease.get("gnucash_nk_account_guid")
    }
    migrated = 0
    for tenant in tenant_rows:
        if not isinstance(tenant, dict):
            continue
        account_guid = str(tenant.get("gnucash_nk_account_guid") or "").strip()
        if not account_guid:
            continue
        if account_guid in linked_account_guids:
            tenant["gnucash_nk_account_guid"] = None
            tenant["gnucash_nk_account_name"] = None
            continue
        candidates = [
            lease
            for lease in lease_rows
            if isinstance(lease, dict)
            and lease.get("tenant_id") == tenant.get("id")
            and not lease.get("gnucash_nk_account_guid")
        ]
        if not candidates:
            continue

        payment_lease_ids = {
            payment.get("lease_id")
            for payment in payment_rows
            if isinstance(payment, dict)
            and payment.get("tenant_id") == tenant.get("id")
            and payment.get("account_guid") == account_guid
            and payment.get("lease_id") is not None
        }
        candidates_with_payments = [
            lease for lease in candidates if lease.get("id") in payment_lease_ids
        ]
        target_candidates = candidates_with_payments or candidates
        target_lease = max(
            target_candidates,
            key=lambda lease: (str(lease.get("start_date") or ""), int(lease.get("id") or 0)),
        )
        target_lease["gnucash_nk_account_guid"] = account_guid
        target_lease["gnucash_nk_account_name"] = tenant.get("gnucash_nk_account_name")
        tenant["gnucash_nk_account_guid"] = None
        tenant["gnucash_nk_account_name"] = None
        linked_account_guids.add(account_guid)
        migrated += 1
    return migrated


def import_application_data(connection: sqlite3.Connection, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("application import payload must be an object")

    raw_format_version = payload.get("format_version", 1)
    try:
        format_version = int(raw_format_version)
    except (TypeError, ValueError) as error:
        raise ValueError("format_version must be an integer") from error
    if format_version not in (1, APPLICATION_EXPORT_FORMAT_VERSION):
        raise ValueError("unsupported import format_version")

    tables_payload = payload.get("tables")
    if not isinstance(tables_payload, dict):
        raise ValueError("tables is required")

    migrated_legacy_gnucash_accounts = 0
    if format_version == 1:
        migrated_legacy_gnucash_accounts = _migrate_legacy_import_gnucash_accounts(
            tables_payload
        )

    total_rows = 0
    skipped_legacy_gnucash_payments = 0
    try:
        connection.execute("BEGIN")
        for table_name in reversed(APP_DATA_EXPORT_TABLES):
            connection.execute(f"DELETE FROM {table_name}")

        for table_name in APP_DATA_EXPORT_TABLES:
            table_rows = tables_payload.get(table_name, [])
            if table_rows is None:
                table_rows = []
            if not isinstance(table_rows, list):
                raise ValueError(f"tables.{table_name} must be a list")

            columns = _table_column_names(connection, table_name)
            insert_sql = (
                f"INSERT INTO {table_name} ({', '.join(columns)}) "
                f"VALUES ({', '.join(['?'] * len(columns))})"
            )
            for row_index, row in enumerate(table_rows):
                if not isinstance(row, dict):
                    raise ValueError(f"tables.{table_name}[{row_index}] must be an object")
                if table_name == "gnucash_payments" and not row.get("lease_id"):
                    # Exports from before contract assignment cannot be allocated
                    # safely. They can be re-imported from GnuCash on demand.
                    skipped_legacy_gnucash_payments += 1
                    continue
                values = [
                    _decode_application_import_value(row.get(column_name))
                    for column_name in columns
                ]
                connection.execute(insert_sql, values)
                total_rows += 1
        connection.commit()
    except ValueError:
        connection.rollback()
        raise
    except sqlite3.DatabaseError as error:
        connection.rollback()
        raise ValueError("application import could not be applied") from error

    return {
        "format_version": format_version,
        "imported_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "table_count": len(APP_DATA_EXPORT_TABLES),
        "row_count": total_rows,
        "skipped_legacy_gnucash_payments": skipped_legacy_gnucash_payments,
        "migrated_legacy_gnucash_accounts": migrated_legacy_gnucash_accounts,
    }


def health_status() -> dict:
    return {
        "status": "ok",
        "reachable": True,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }


def _latest_paperless_credentials(connection: sqlite3.Connection) -> tuple[str, str]:
    row = connection.execute(
        """
        SELECT base_url, api_token
        FROM paperless_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return "", ""
    return str(row["base_url"] or ""), str(row["api_token"] or "")


def _paperless_is_configured(base_url: str, token: str) -> bool:
    return base_url != "" and token != ""


def _check_paperless_reachability(base_url: str, token: str) -> tuple[bool, str]:
    if base_url == "" or token == "":
        return False, "Paperless ist nicht konfiguriert."

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/document_types/?page_size=1",
        headers={
            "Accept": "application/json",
            "Authorization": f"Token {token}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if 200 <= response.status < 400:
                return True, "Paperless Server erreichbar."
            return False, f"Paperless antwortet mit HTTP {response.status}."
    except urllib.error.HTTPError as error:
        return False, f"Paperless antwortet mit HTTP {error.code}."
    except (urllib.error.URLError, TimeoutError, socket_timeout) as error:
        return False, f"Paperless nicht erreichbar: {error}."


def get_paperless_status(connection: sqlite3.Connection) -> dict:
    base_url, token = _latest_paperless_credentials(connection)
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    if base_url == "" or token == "":
        return {
            "configured": False,
            "reachable": False,
            "message": "Paperless ist nicht konfiguriert.",
            "checked_at": timestamp,
        }

    reachable, message = _check_paperless_reachability(base_url, token)
    return {
        "configured": True,
        "reachable": reachable,
        "message": message,
        "checked_at": timestamp,
    }


SUPPORTED_OBJECT_TYPES = {"property", "building", "unit", "room"}


def _lookup_object_target(
    connection: sqlite3.Connection,
    object_type: str,
    object_id: int,
) -> sqlite3.Row | None:
    if object_type == "property":
        return connection.execute(
            """
            SELECT id, id AS property_id, name AS object_name
            FROM properties
            WHERE id = ?
            """,
            (object_id,),
        ).fetchone()
    if object_type == "building":
        return connection.execute(
            """
            SELECT id, property_id, name AS object_name
            FROM buildings
            WHERE id = ?
            """,
            (object_id,),
        ).fetchone()
    if object_type == "unit":
        return connection.execute(
            """
            SELECT u.id, b.property_id, u.label AS object_name
            FROM units u
            LEFT JOIN buildings b ON b.id = u.building_id
            WHERE u.id = ?
            """,
            (object_id,),
        ).fetchone()
    if object_type == "room":
        return connection.execute(
            """
            SELECT r.id, b.property_id, r.label AS object_name
            FROM rooms r
            JOIN units u ON u.id = r.unit_id
            LEFT JOIN buildings b ON b.id = u.building_id
            WHERE r.id = ?
            """,
            (object_id,),
        ).fetchone()
    raise ValueError("object_type must be property, building, unit or room")


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
    target_row = _lookup_object_target(connection, object_type, object_id)
    if target_row is None:
        raise ValueError("target object not found")
    return object_type, object_id, target_row["property_id"]


def _normalize_meter_target(
    connection: sqlite3.Connection,
    payload: dict,
) -> tuple[str, int, int | None]:
    object_type = _require_payload_value(payload, "object_type")
    if object_type not in SUPPORTED_OBJECT_TYPES:
        raise ValueError("object_type must be property, building, unit or room")
    object_id = _parse_int(payload.get("object_id"), "object_id")
    target_row = _lookup_object_target(connection, object_type, object_id)
    if target_row is None:
        raise ValueError("target object not found")
    return object_type, object_id, target_row["property_id"]


def _lookup_meter(connection: sqlite3.Connection, meter_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, property_id, object_type, object_id, label, unit, is_archived
        FROM meters
        WHERE id = ?
        """,
        (meter_id,),
    ).fetchone()


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
    meter_row = _lookup_meter(connection, normalized_meter_id)
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
        _parse_decimal(conversion_factor_value, "conversion_factor")
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
        return _decimal_to_string(_parse_decimal(raw_value, "consumption_value"))

    if meter_id is not None:
        return None

    if raw_value in (None, ""):
        raise ValueError("consumption_value is required when meter_id is not provided")
    return _decimal_to_string(_parse_decimal(raw_value, "consumption_value"))


def _load_meter_reading_points(
    connection: sqlite3.Connection,
    meter_id: int,
) -> list[tuple[date, Decimal]]:
    rows = connection.execute(
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


def _meter_consumption_for_period(
    connection: sqlite3.Connection,
    meter_id: int,
    period_start: str,
    period_end: str,
) -> Decimal | None:
    reading_points = _load_meter_reading_points(connection, meter_id)
    return meter_consumption_for_period(reading_points, period_start, period_end)


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
            meter_row = _lookup_meter(connection, int(meter_id))
            meter_unit = str(meter_row["unit"]) if meter_row is not None else None
        raw_quantity = _meter_consumption_for_period(connection, int(meter_id), period_start, period_end)
    else:
        raw_quantity = (
            Decimal(str(expense_payload["consumption_value"]))
            if expense_payload.get("consumption_value") not in (None, "")
            else None
        )
        expense_start = expense_payload.get("period_start")
        expense_end = expense_payload.get("period_end")
        if raw_quantity is not None and expense_start and expense_end:
            overlap = overlap_period(
                str(expense_start), str(expense_end), period_start, period_end
            )
            if overlap is None:
                return meter_unit, None
            overlap_start, overlap_end = overlap
            total_days = Decimal(
                (parse_date(str(expense_end)) - parse_date(str(expense_start))).days + 1
            )
            overlap_days = Decimal(
                (parse_date(overlap_end) - parse_date(overlap_start)).days + 1
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
    if expense_payload["charge_type"] == "consumption":
        if effective_consumption_value is None:
            return meter_unit, None
        total_amount = quantize_money(
            Decimal(str(expense_payload["amount"])) * effective_consumption_value
        )
        return meter_unit, f"{total_amount:.2f}"

    charge_type = str(expense_payload["charge_type"])
    expense_start = str(expense_payload.get("period_start") or period_start)
    expense_end = str(expense_payload.get("period_end") or period_end)
    overlap = overlap_period(expense_start, expense_end, period_start, period_end)
    if overlap is None:
        return meter_unit, "0.00"

    overlap_start, overlap_end = overlap
    if charge_type == "one_time" and expense_start != expense_end:
        total_days = Decimal((parse_date(expense_end) - parse_date(expense_start)).days + 1)
        overlap_days = Decimal((parse_date(overlap_end) - parse_date(overlap_start)).days + 1)
        return meter_unit, f"{quantize_money(Decimal(str(expense_payload['amount'])) * overlap_days / total_days):.2f}"
    total_amount = day_accurate_recurring_amount(
        Decimal(str(expense_payload["amount"])),
        charge_type,
        parse_date(overlap_start),
        parse_date(overlap_end),
        parse_date(expense_start),
    )
    return meter_unit, f"{total_amount:.2f}"


def _latest_meter_reading_date(connection: sqlite3.Connection, meter_id: int) -> str | None:
    row = connection.execute(
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
        latest_reading_date = _latest_meter_reading_date(connection, meter_id)
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


MAX_EXPENSE_DOCUMENT_SIZE = 15 * 1024 * 1024


def _expense_exists(connection: sqlite3.Connection, expense_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, is_archived
        FROM expense_items
        WHERE id = ?
        """,
        (expense_id,),
    ).fetchone()


def _tenant_exists(connection: sqlite3.Connection, tenant_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id
        FROM tenants
        WHERE id = ?
        """,
        (tenant_id,),
    ).fetchone()


def _lease_exists(connection: sqlite3.Connection, lease_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id
        FROM leases
        WHERE id = ?
        """,
        (lease_id,),
    ).fetchone()


def _linked_document_config(resource_type: str) -> dict[str, str]:
    if resource_type == "tenant":
        return {
            "table": "tenant_documents",
            "resource_field": "tenant_id",
            "resource_type": "tenant",
        }
    if resource_type == "lease":
        return {
            "table": "lease_documents",
            "resource_field": "lease_id",
            "resource_type": "lease",
        }
    raise ValueError(f"unsupported document resource: {resource_type}")


def _require_linked_document_owner(
    connection: sqlite3.Connection,
    resource_type: str,
    resource_id: int,
) -> None:
    if resource_type == "tenant":
        if _tenant_exists(connection, resource_id) is None:
            raise ValueError("tenant not found")
        return
    if resource_type == "lease":
        if _lease_exists(connection, resource_id) is None:
            raise ValueError("lease not found")
        return
    raise ValueError(f"unsupported document resource: {resource_type}")


def _extract_paperless_identifiers(payload: object) -> tuple[str | None, str | None]:
    document_id: str | None = None
    task_id: str | None = None

    if isinstance(payload, int):
        document_id = str(payload)
    elif isinstance(payload, str):
        trimmed = payload.strip()
        if trimmed:
            if trimmed.isdigit():
                document_id = trimmed
            else:
                task_id = trimmed
    elif isinstance(payload, dict):
        for key in ("related_document", "document_id", "paperless_id"):
            candidate = payload.get(key)
            if isinstance(candidate, int):
                document_id = str(candidate)
                break
            if isinstance(candidate, str) and candidate.strip().isdigit():
                document_id = candidate.strip()
                break
        for key in ("task_id", "task", "uuid"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                task_id = candidate.strip()
                break
        if document_id is None:
            candidate_id = payload.get("id")
            if isinstance(candidate_id, int):
                document_id = str(candidate_id)
            elif isinstance(candidate_id, str) and candidate_id.strip().isdigit():
                document_id = candidate_id.strip()
        result_payload = payload.get("result")
        if document_id is None and isinstance(result_payload, dict):
            result_candidate = result_payload.get("document_id") or result_payload.get("related_document")
            if isinstance(result_candidate, int):
                document_id = str(result_candidate)
            elif isinstance(result_candidate, str) and result_candidate.strip().isdigit():
                document_id = result_candidate.strip()
    return document_id, task_id


def _build_paperless_document_url(base_url: str, document_id: str | None) -> str | None:
    if not document_id:
        return None
    return base_url.rstrip("/") + "/documents/" + document_id + "/details/"


def _filename_from_content_disposition(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    for segment in str(content_disposition).split(";")[1:]:
        normalized_segment = segment.strip()
        if normalized_segment.lower().startswith("filename="):
            filename = normalized_segment.split("=", 1)[1].strip().strip('"')
            return filename or None
    return None


def _normalize_paperless_document_id(raw_value: object, field_name: str) -> str:
    normalized = str(raw_value or "").strip()
    if normalized == "":
        raise ValueError(f"{field_name} is required")
    if not normalized.isdigit():
        raise ValueError(f"{field_name} must be an integer string")
    return normalized


def _upload_document_to_paperless(
    base_url: str,
    token: str,
    filename: str,
    content_type: str,
    content_blob: bytes,
) -> dict:
    if not _paperless_is_configured(base_url, token):
        raise ValueError("Paperless configuration is required for file uploads")

    sanitized_filename = filename.replace('"', "_")
    boundary = "----easyprent-" + uuid.uuid4().hex
    multipart_body = [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="document"; filename="{sanitized_filename}"\r\n'.encode(
            "utf-8"
        ),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        content_blob,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/documents/post_document/",
        data=b"".join(multipart_body),
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw_body = response.read().decode("utf-8").strip()
            if raw_body == "":
                parsed_payload: object = {}
            else:
                try:
                    parsed_payload = json.loads(raw_body)
                except ValueError:
                    parsed_payload = raw_body
        document_id, task_id = _extract_paperless_identifiers(parsed_payload)
        return {
            "upload_status": "paperless_uploaded" if document_id else "paperless_queued",
            "paperless_document_id": document_id,
            "paperless_task_id": task_id,
            "paperless_reference_url": _build_paperless_document_url(base_url, document_id),
            "upload_error": None,
        }
    except Exception as error:  # pragma: no cover - network behavior depends on runtime
        return {
            "upload_status": "paperless_error",
            "paperless_document_id": None,
            "paperless_task_id": None,
            "paperless_reference_url": None,
            "upload_error": str(error),
        }


def _download_document_from_paperless(
    base_url: str,
    token: str,
    paperless_document_id: str,
    fallback_filename: str,
) -> dict:
    if base_url == "" or token == "":
        raise ValueError("paperless settings are not configured")

    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/documents/" + paperless_document_id + "/download/",
        headers={
            "Accept": "*/*",
            "Authorization": f"Token {token}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            content_blob = response.read()
            content_type = str(
                response.headers.get("Content-Type") or "application/octet-stream"
            )
            filename = _filename_from_content_disposition(
                response.headers.get("Content-Disposition")
            ) or fallback_filename
    except urllib.error.HTTPError as error:
        raise ValueError(f"paperless document fetch failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, socket_timeout) as error:
        raise ValueError(f"paperless document fetch failed: {error}") from error

    if len(content_blob) == 0:
        raise ValueError("paperless document is empty")

    return {
        "filename": filename,
        "content_type": content_type,
        "content_blob": content_blob,
    }


def _normalize_linked_documents_payload(payload: dict, base_url: str) -> list[dict]:
    documents = payload.get("documents")
    if not isinstance(documents, list) or len(documents) == 0:
        raise ValueError("documents must be a non-empty array")
    normalized_documents: list[dict] = []
    for index, document_payload in enumerate(documents):
        if not isinstance(document_payload, dict):
            raise ValueError(f"documents[{index}] must be an object")
        paperless_document_id = str(document_payload.get("paperless_document_id") or "").strip()
        if paperless_document_id != "":
            if base_url == "":
                raise ValueError("paperless_document_id requires configured Paperless settings")
            normalized_paperless_document_id = _normalize_paperless_document_id(
                paperless_document_id,
                f"documents[{index}].paperless_document_id",
            )
            filename = str(document_payload.get("filename") or "").strip()
            normalized_documents.append(
                {
                    "filename": filename or f"paperless-document-{normalized_paperless_document_id}",
                    "content_type": str(
                        document_payload.get("content_type") or "application/octet-stream"
                    ).strip(),
                    "content_blob": b"",
                    "skip_paperless_upload": True,
                    "paperless_document_id": normalized_paperless_document_id,
                    "paperless_task_id": None,
                    "paperless_reference_url": _build_paperless_document_url(
                        base_url,
                        normalized_paperless_document_id,
                    ),
                    "upload_status": "paperless_linked",
                    "upload_error": None,
                }
            )
            continue
        filename = str(document_payload.get("filename") or "").strip()
        if filename == "":
            raise ValueError(f"documents[{index}].filename is required")
        if base_url == "":
            raise ValueError("Paperless configuration is required for file uploads")
        content_type = str(document_payload.get("content_type") or "application/octet-stream").strip()
        content_base64 = str(document_payload.get("content_base64") or "").strip()
        if content_base64 == "":
            raise ValueError(f"documents[{index}].content_base64 is required")
        try:
            content_blob = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError(f"documents[{index}].content_base64 must be valid base64") from error
        if len(content_blob) == 0:
            raise ValueError(f"documents[{index}] is empty")
        if len(content_blob) > MAX_EXPENSE_DOCUMENT_SIZE:
            raise ValueError(
                f"documents[{index}] exceeds max size of {MAX_EXPENSE_DOCUMENT_SIZE} bytes"
            )
        normalized_documents.append(
            {
                "filename": filename,
                "content_type": content_type,
                "content_blob": content_blob,
                "skip_paperless_upload": False,
            }
        )
    return normalized_documents


def _normalize_expense_documents_payload(payload: dict, base_url: str) -> list[dict]:
    return _normalize_linked_documents_payload(payload, base_url)


def _linked_document_rows(
    connection: sqlite3.Connection,
    resource_type: str,
    resource_id: int,
    document_ids: list[int] | None = None,
) -> list[dict]:
    config = _linked_document_config(resource_type)
    if document_ids:
        placeholders = ",".join(["?"] * len(document_ids))
        rows = connection.execute(
            f"""
            SELECT
                id,
                {config['resource_field']} AS resource_id,
                filename,
                content_type,
                content_size,
                paperless_document_id,
                paperless_task_id,
                paperless_reference_url,
                upload_status,
                upload_error,
                created_at
            FROM {config['table']}
            WHERE {config['resource_field']} = ? AND id IN ({placeholders})
            ORDER BY id
            """,
            [resource_id, *document_ids],
        ).fetchall()
    else:
        rows = connection.execute(
            f"""
            SELECT
                id,
                {config['resource_field']} AS resource_id,
                filename,
                content_type,
                content_size,
                paperless_document_id,
                paperless_task_id,
                paperless_reference_url,
                upload_status,
                upload_error,
                created_at
            FROM {config['table']}
            WHERE {config['resource_field']} = ?
            ORDER BY id
            """,
            (resource_id,),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "resource_type": config["resource_type"],
            "resource_id": int(row["resource_id"]),
            "filename": str(row["filename"]),
            "content_type": str(row["content_type"]),
            "content_size": int(row["content_size"]),
            "paperless_document_id": row["paperless_document_id"],
            "paperless_task_id": row["paperless_task_id"],
            "paperless_reference_url": row["paperless_reference_url"],
            "upload_status": str(row["upload_status"]),
            "upload_error": row["upload_error"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _expense_document_rows(
    connection: sqlite3.Connection,
    expense_id: int,
    document_ids: list[int] | None = None,
) -> list[dict]:
    if document_ids:
        placeholders = ",".join(["?"] * len(document_ids))
        rows = connection.execute(
            f"""
            SELECT
                id,
                expense_id,
                filename,
                content_type,
                content_size,
                paperless_document_id,
                paperless_task_id,
                paperless_reference_url,
                upload_status,
                upload_error,
                created_at
            FROM expense_documents
            WHERE expense_id = ? AND id IN ({placeholders})
            ORDER BY id
            """,
            [expense_id, *document_ids],
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT
                id,
                expense_id,
                filename,
                content_type,
                content_size,
                paperless_document_id,
                paperless_task_id,
                paperless_reference_url,
                upload_status,
                upload_error,
                created_at
            FROM expense_documents
            WHERE expense_id = ?
            ORDER BY id
            """,
            (expense_id,),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "expense_id": int(row["expense_id"]),
            "filename": str(row["filename"]),
            "content_type": str(row["content_type"]),
            "content_size": int(row["content_size"]),
            "paperless_document_id": row["paperless_document_id"],
            "paperless_task_id": row["paperless_task_id"],
            "paperless_reference_url": row["paperless_reference_url"],
            "upload_status": str(row["upload_status"]),
            "upload_error": row["upload_error"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_expense_documents(connection: sqlite3.Connection, expense_id: int) -> dict:
    if _expense_exists(connection, expense_id) is None:
        raise ValueError("expense not found")
    return {
        "expense_id": expense_id,
        "documents": _expense_document_rows(connection, expense_id),
    }


def upload_expense_documents(connection: sqlite3.Connection, expense_id: int, payload: dict) -> dict:
    expense_row = _expense_exists(connection, expense_id)
    if expense_row is None:
        raise ValueError("expense not found")
    if int(expense_row["is_archived"] or 0):
        raise ValueError("archived expenses cannot be edited")

    base_url, token = _latest_paperless_credentials(connection)
    normalized_documents = _normalize_expense_documents_payload(payload, base_url)
    created_document_ids: list[int] = []
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()

    for document in normalized_documents:
        if document["skip_paperless_upload"]:
            paperless_result = {
                "upload_status": document["upload_status"],
                "paperless_document_id": document["paperless_document_id"],
                "paperless_task_id": document["paperless_task_id"],
                "paperless_reference_url": document["paperless_reference_url"],
                "upload_error": document["upload_error"],
            }
        else:
            paperless_result = _upload_document_to_paperless(
                base_url,
                token,
                document["filename"],
                document["content_type"],
                document["content_blob"],
            )
            if (
                paperless_result["paperless_document_id"] in (None, "")
                and paperless_result["paperless_task_id"] in (None, "")
            ):
                raise ValueError(
                    "document upload to Paperless failed: "
                    + str(paperless_result["upload_error"] or "unknown error")
                )
        cursor = connection.execute(
            """
            INSERT INTO expense_documents (
                expense_id,
                filename,
                content_type,
                content_size,
                content_blob,
                paperless_document_id,
                paperless_task_id,
                paperless_reference_url,
                upload_status,
                upload_error,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense_id,
                document["filename"],
                document["content_type"],
                len(document["content_blob"]),
                sqlite3.Binary(b""),
                paperless_result["paperless_document_id"],
                paperless_result["paperless_task_id"],
                paperless_result["paperless_reference_url"],
                paperless_result["upload_status"],
                paperless_result["upload_error"],
                timestamp,
            ),
        )
        created_document_ids.append(int(cursor.lastrowid))
    connection.commit()

    return {
        "expense_id": expense_id,
        "documents": _expense_document_rows(connection, expense_id, created_document_ids),
    }


def delete_expense_document(
    connection: sqlite3.Connection,
    expense_id: int,
    document_id: int,
) -> dict:
    expense_row = _expense_exists(connection, expense_id)
    if expense_row is None:
        raise ValueError("expense not found")
    if int(expense_row["is_archived"] or 0):
        raise ValueError("archived expenses cannot be edited")

    document_row = connection.execute(
        """
        SELECT id
        FROM expense_documents
        WHERE id = ? AND expense_id = ?
        """,
        (document_id, expense_id),
    ).fetchone()
    if document_row is None:
        raise ValueError("expense document not found")

    connection.execute(
        "DELETE FROM expense_documents WHERE id = ? AND expense_id = ?",
        (document_id, expense_id),
    )
    connection.commit()
    return {
        "expense_id": expense_id,
        "document_id": document_id,
        "deleted": True,
    }


def download_expense_document(
    connection: sqlite3.Connection,
    expense_id: int,
    document_id: int,
) -> dict:
    row = connection.execute(
        """
        SELECT filename, content_type, content_blob, paperless_document_id
        FROM expense_documents
        WHERE id = ? AND expense_id = ?
        """,
        (document_id, expense_id),
    ).fetchone()
    if row is None:
        raise ValueError("expense document not found")
    content_blob = bytes(row["content_blob"])
    if len(content_blob) == 0:
        if row["paperless_document_id"] not in (None, ""):
            base_url, token = _latest_paperless_credentials(connection)
            return _download_document_from_paperless(
                base_url,
                token,
                str(row["paperless_document_id"]),
                str(row["filename"]),
            )
        raise ValueError("expense document has no downloadable content")
    return {
        "filename": str(row["filename"]),
        "content_type": str(row["content_type"] or "application/octet-stream"),
        "content_blob": content_blob,
    }


def _linked_documents_list_response(
    connection: sqlite3.Connection,
    resource_type: str,
    resource_id: int,
) -> dict:
    _require_linked_document_owner(connection, resource_type, resource_id)
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "documents": _linked_document_rows(connection, resource_type, resource_id),
    }


def _upload_linked_documents(
    connection: sqlite3.Connection,
    resource_type: str,
    resource_id: int,
    payload: dict,
) -> dict:
    _require_linked_document_owner(connection, resource_type, resource_id)
    config = _linked_document_config(resource_type)
    base_url, token = _latest_paperless_credentials(connection)
    normalized_documents = _normalize_linked_documents_payload(payload, base_url)
    created_document_ids: list[int] = []
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()

    for document in normalized_documents:
        if document["skip_paperless_upload"]:
            paperless_result = {
                "upload_status": document["upload_status"],
                "paperless_document_id": document["paperless_document_id"],
                "paperless_task_id": document["paperless_task_id"],
                "paperless_reference_url": document["paperless_reference_url"],
                "upload_error": document["upload_error"],
            }
        else:
            paperless_result = _upload_document_to_paperless(
                base_url,
                token,
                document["filename"],
                document["content_type"],
                document["content_blob"],
            )
            if (
                paperless_result["paperless_document_id"] in (None, "")
                and paperless_result["paperless_task_id"] in (None, "")
            ):
                raise ValueError(
                    "document upload to Paperless failed: "
                    + str(paperless_result["upload_error"] or "unknown error")
                )
        cursor = connection.execute(
            f"""
            INSERT INTO {config['table']} (
                {config['resource_field']},
                filename,
                content_type,
                content_size,
                content_blob,
                paperless_document_id,
                paperless_task_id,
                paperless_reference_url,
                upload_status,
                upload_error,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resource_id,
                document["filename"],
                document["content_type"],
                len(document["content_blob"]),
                sqlite3.Binary(b""),
                paperless_result["paperless_document_id"],
                paperless_result["paperless_task_id"],
                paperless_result["paperless_reference_url"],
                paperless_result["upload_status"],
                paperless_result["upload_error"],
                timestamp,
            ),
        )
        created_document_ids.append(int(cursor.lastrowid))
    connection.commit()

    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "documents": _linked_document_rows(connection, resource_type, resource_id, created_document_ids),
    }


def _delete_linked_document(
    connection: sqlite3.Connection,
    resource_type: str,
    resource_id: int,
    document_id: int,
) -> dict:
    _require_linked_document_owner(connection, resource_type, resource_id)
    config = _linked_document_config(resource_type)
    row = connection.execute(
        f"""
        SELECT id
        FROM {config['table']}
        WHERE id = ? AND {config['resource_field']} = ?
        """,
        (document_id, resource_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"{resource_type} document not found")

    connection.execute(
        f"DELETE FROM {config['table']} WHERE id = ? AND {config['resource_field']} = ?",
        (document_id, resource_id),
    )
    connection.commit()
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "document_id": document_id,
        "deleted": True,
    }


def _download_linked_document(
    connection: sqlite3.Connection,
    resource_type: str,
    resource_id: int,
    document_id: int,
) -> dict:
    _require_linked_document_owner(connection, resource_type, resource_id)
    config = _linked_document_config(resource_type)
    row = connection.execute(
        f"""
        SELECT filename, content_type, content_blob, paperless_document_id
        FROM {config['table']}
        WHERE id = ? AND {config['resource_field']} = ?
        """,
        (document_id, resource_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"{resource_type} document not found")
    content_blob = bytes(row["content_blob"])
    if len(content_blob) == 0:
        if row["paperless_document_id"] not in (None, ""):
            base_url, token = _latest_paperless_credentials(connection)
            return _download_document_from_paperless(
                base_url,
                token,
                str(row["paperless_document_id"]),
                str(row["filename"]),
            )
        raise ValueError(f"{resource_type} document has no downloadable content")
    return {
        "filename": str(row["filename"]),
        "content_type": str(row["content_type"] or "application/octet-stream"),
        "content_blob": content_blob,
    }


def list_tenant_documents(connection: sqlite3.Connection, tenant_id: int) -> dict:
    return _linked_documents_list_response(connection, "tenant", tenant_id)


def upload_tenant_documents(connection: sqlite3.Connection, tenant_id: int, payload: dict) -> dict:
    return _upload_linked_documents(connection, "tenant", tenant_id, payload)


def delete_tenant_document(connection: sqlite3.Connection, tenant_id: int, document_id: int) -> dict:
    return _delete_linked_document(connection, "tenant", tenant_id, document_id)


def download_tenant_document(connection: sqlite3.Connection, tenant_id: int, document_id: int) -> dict:
    return _download_linked_document(connection, "tenant", tenant_id, document_id)


def list_lease_documents(connection: sqlite3.Connection, lease_id: int) -> dict:
    return _linked_documents_list_response(connection, "lease", lease_id)


def upload_lease_documents(connection: sqlite3.Connection, lease_id: int, payload: dict) -> dict:
    return _upload_linked_documents(connection, "lease", lease_id, payload)


def delete_lease_document(connection: sqlite3.Connection, lease_id: int, document_id: int) -> dict:
    return _delete_linked_document(connection, "lease", lease_id, document_id)


def download_lease_document(connection: sqlite3.Connection, lease_id: int, document_id: int) -> dict:
    return _download_linked_document(connection, "lease", lease_id, document_id)


def _expense_dependency_query(object_type: str) -> str:
    return (
        "SELECT COUNT(*) FROM expense_items "
        f"WHERE object_type = '{object_type}' AND object_id = ?"
    )


def _meter_dependency_query(object_type: str) -> str:
    return "SELECT COUNT(*) FROM meters " f"WHERE object_type = '{object_type}' AND object_id = ?"


def _expense_meter_dependency_query() -> str:
    return "SELECT COUNT(*) FROM expense_items WHERE meter_id = ?"


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
    "meters": {
        "table": "meters",
        "label": "meter",
        "dependencies": [
            {"table": "meter_readings", "foreign_key": "meter_id", "label": "meter_readings"},
            {"query": _expense_meter_dependency_query(), "label": "expenses"},
        ],
    },
    "expenses": {
        "table": "expense_items",
        "label": "expense",
        "dependencies": [
            {"table": "expense_documents", "foreign_key": "expense_id", "label": "expense_documents"},
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


def list_overview(connection: sqlite3.Connection) -> dict:
    properties = _row_dicts(
        connection.execute(
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
            LEFT JOIN expense_items e ON e.property_id = p.id
            GROUP BY p.id, o.name
            ORDER BY p.id
            """
        ).fetchall()
    )
    buildings = _row_dicts(
        connection.execute(
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
    units = _row_dicts(
        connection.execute(
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
    rooms = _row_dicts(
        connection.execute(
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
        room["area_sqm"] = _normalize_optional_decimal_string(room.get("area_sqm"), "area_sqm")
    tenants = _row_dicts(
        connection.execute(
            """
            SELECT id, full_name, email, phone,
                   alternate_street, alternate_postal_code, alternate_city
            FROM tenants
            ORDER BY id
            """
        ).fetchall()
    )
    leases = _row_dicts(
        connection.execute(
            """
            SELECT
                l.*,
                u.label AS unit_label,
                r.label AS room_label,
                t.full_name AS tenant_name,
                CASE
                    WHEN l.room_id IS NOT NULL THEN 'room'
                    ELSE 'unit'
                END AS rental_object_type,
                CASE
                    WHEN l.room_id IS NOT NULL THEN r.label || ' (' || u.label || ')'
                    ELSE u.label
                END AS rental_object_label
            FROM leases l
            JOIN units u ON u.id = l.unit_id
            LEFT JOIN rooms r ON r.id = l.room_id
            JOIN tenants t ON t.id = l.tenant_id
            ORDER BY l.id
            """
        ).fetchall()
    )
    expenses = _row_dicts(
        connection.execute(
            """
            SELECT
                e.id,
                e.object_type,
                e.object_id,
                e.expense_category,
                e.beneficiary_name,
                e.label,
                e.amount,
                e.allocation_method,
                e.charge_type,
                e.recurrence,
                e.interval_name,
                e.meter_id,
                e.consumption_unit,
                e.consumption_value,
                e.conversion_factor,
                e.booking_date,
                e.period_start,
                e.period_end,
                e.is_archived,
                e.archived_at,
                m.label AS meter_label,
                m.unit AS meter_unit,
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
    )
    for expense in expenses:
        expense["is_open_ended"] = expense["period_end"] == OPEN_ENDED_PERIOD_END
        if expense["is_open_ended"]:
            expense["effective_consumption_value"] = None
            expense["total_amount"] = None
            expense["period_end"] = None
            continue
        meter_unit, total_amount = _total_amount_for_expense_period(
            connection,
            expense,
            expense["period_start"],
            expense["period_end"],
        )
        _, effective_consumption_value = _effective_consumption_quantity(
            connection,
            expense,
            expense["period_start"],
            expense["period_end"],
        )
        expense["meter_unit"] = meter_unit
        expense["effective_consumption_value"] = _decimal_to_string(effective_consumption_value)
        expense["total_amount"] = total_amount

    expense_categories = _row_dicts(
        connection.execute(
            """
            SELECT
                expense_category,
                beneficiary_name,
                COUNT(*) AS expense_count
            FROM expense_items
            GROUP BY expense_category, beneficiary_name
            ORDER BY expense_category, beneficiary_name
            """
        ).fetchall()
    )
    meters = _row_dicts(
        connection.execute(
            """
            SELECT
                m.*,
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
            LEFT JOIN properties p ON p.id = m.property_id
            LEFT JOIN properties p_target
                ON m.object_type = 'property' AND p_target.id = m.object_id
            LEFT JOIN buildings b_target
                ON m.object_type = 'building' AND b_target.id = m.object_id
            LEFT JOIN units u_target
                ON m.object_type = 'unit' AND u_target.id = m.object_id
            LEFT JOIN rooms r_target
                ON m.object_type = 'room' AND r_target.id = m.object_id
            ORDER BY m.id
            """
        ).fetchall()
    )
    meter_readings = _row_dicts(
        connection.execute(
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
            LEFT JOIN properties p ON p.id = m.property_id
            LEFT JOIN properties p_target
                ON m.object_type = 'property' AND p_target.id = m.object_id
            LEFT JOIN buildings b_target
                ON m.object_type = 'building' AND b_target.id = m.object_id
            LEFT JOIN units u_target
                ON m.object_type = 'unit' AND u_target.id = m.object_id
            LEFT JOIN rooms r_target
                ON m.object_type = 'room' AND r_target.id = m.object_id
            ORDER BY mr.meter_id, mr.reading_date, mr.id
            """
        ).fetchall()
    )
    depreciation_assets = _row_dicts(
        connection.execute("SELECT * FROM depreciation_assets ORDER BY id").fetchall()
    )
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


def create_property(connection: sqlite3.Connection, payload: dict) -> dict:
    cursor = connection.execute(
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
    connection.commit()
    return {"id": cursor.lastrowid, **payload}


def create_building(connection: sqlite3.Connection, payload: dict) -> dict:
    cursor = connection.execute(
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
    connection.commit()
    return {"id": cursor.lastrowid, **payload}


def _unit_address(connection: sqlite3.Connection, payload: dict) -> tuple[str, str, str]:
    building_id = payload.get("building_id")
    if building_id is None:
        return payload["street"], payload["city"], payload["postal_code"]

    building = connection.execute(
        "SELECT street, city, postal_code FROM buildings WHERE id = ?",
        (building_id,),
    ).fetchone()
    if building is None:
        raise ValueError("building not found")
    return building["street"], building["city"], building["postal_code"]


def create_unit(connection: sqlite3.Connection, payload: dict) -> dict:
    street, city, postal_code = _unit_address(connection, payload)
    cursor = connection.execute(
        """
        INSERT INTO units (building_id, label, area_sqm, room_count, street, city, postal_code)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("building_id"),
            payload["label"],
            str(Decimal(str(payload["area_sqm"]))),
            payload["room_count"],
            street,
            city,
            postal_code,
        ),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        **payload,
        "street": street,
        "city": city,
        "postal_code": postal_code,
    }


def create_room(connection: sqlite3.Connection, payload: dict) -> dict:
    unit_id = _parse_int(payload.get("unit_id"), "unit_id")
    label = _require_payload_value(payload, "label")
    area_sqm = _normalize_optional_decimal_string(payload.get("area_sqm"), "area_sqm")

    unit_row = connection.execute(
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

    cursor = connection.execute(
        "INSERT INTO rooms (unit_id, label, area_sqm) VALUES (?, ?, ?)",
        (unit_id, label, area_sqm),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        "unit_id": unit_id,
        "label": label,
        "area_sqm": area_sqm,
    }


def create_meter(connection: sqlite3.Connection, payload: dict) -> dict:
    object_type, object_id, property_id = _normalize_meter_target(connection, payload)
    label = _require_payload_value(payload, "label")
    unit = _require_payload_value(payload, "unit")
    cursor = connection.execute(
        """
        INSERT INTO meters (property_id, object_type, object_id, label, meter_type, unit, serial_number)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            property_id,
            object_type,
            object_id,
            label,
            payload.get("meter_type"),
            unit,
            payload.get("serial_number"),
        ),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        **payload,
        "object_type": object_type,
        "object_id": object_id,
        "property_id": property_id,
        "label": label,
        "unit": unit,
    }


def update_meter(connection: sqlite3.Connection, meter_id: int, payload: dict) -> dict:
    row = connection.execute(
        """
        SELECT id, property_id, object_type, object_id, label, meter_type, unit,
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

    object_type, object_id, property_id = _normalize_meter_target(connection, payload)
    label = _require_payload_value(payload, "label")
    unit = _require_payload_value(payload, "unit")
    target_changed = object_type != row["object_type"] or object_id != row["object_id"]
    unit_changed = unit != row["unit"]
    if target_changed or unit_changed:
        reading_count = connection.execute(
            "SELECT COUNT(*) FROM meter_readings WHERE meter_id = ?", (meter_id,)
        ).fetchone()[0]
        expense_count = connection.execute(
            "SELECT COUNT(*) FROM expense_items WHERE meter_id = ?", (meter_id,)
        ).fetchone()[0]
        if reading_count or expense_count:
            raise ValueError(
                "object assignment or unit cannot be changed while meter has readings or dependent expenses"
            )

    connection.execute(
        """
        UPDATE meters
        SET property_id = ?, object_type = ?, object_id = ?, label = ?,
            meter_type = ?, unit = ?, serial_number = ?
        WHERE id = ?
        """,
        (
            property_id,
            object_type,
            object_id,
            label,
            payload.get("meter_type"),
            unit,
            payload.get("serial_number"),
            meter_id,
        ),
    )
    connection.commit()
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


def create_meter_reading(connection: sqlite3.Connection, payload: dict) -> dict:
    meter_id = _parse_int(payload.get("meter_id"), "meter_id")
    meter_row = _lookup_meter(connection, meter_id)
    if meter_row is None:
        raise ValueError("meter_id not found")
    if meter_row["is_archived"]:
        raise ValueError("meter_id must reference an active meter")

    reading_date = _require_payload_value(payload, "reading_date")
    parse_date(reading_date)
    reading_value = _parse_decimal(payload.get("reading_value"), "reading_value")
    existing_row = connection.execute(
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

    previous_row = connection.execute(
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

    next_row = connection.execute(
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

    cursor = connection.execute(
        """
        INSERT INTO meter_readings (meter_id, reading_date, reading_value)
        VALUES (?, ?, ?)
        """,
        (meter_id, reading_date, str(reading_value)),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        "meter_id": meter_id,
        "reading_date": reading_date,
        "reading_value": str(reading_value),
    }


def delete_meter_reading(connection: sqlite3.Connection, reading_id: int) -> dict:
    row = connection.execute(
        "SELECT id FROM meter_readings WHERE id = ?",
        (reading_id,),
    ).fetchone()
    if row is None:
        raise ValueError("meter reading not found")

    connection.execute("DELETE FROM meter_readings WHERE id = ?", (reading_id,))
    connection.commit()
    return {"resource": "meter_readings", "id": reading_id, "deleted": True}


def archive_object(connection: sqlite3.Connection, resource_name: str, object_id: int) -> dict:
    config = _get_lifecycle_config(resource_name)
    row = connection.execute(
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
    connection.execute(
        f"UPDATE {config['table']} SET is_archived = 1, archived_at = ? WHERE id = ?",
        (archived_at, object_id),
    )
    connection.commit()
    return {
        "resource": resource_name,
        "id": object_id,
        "is_archived": 1,
        "archived_at": archived_at,
    }


def restore_object(connection: sqlite3.Connection, resource_name: str, object_id: int) -> dict:
    config = _get_lifecycle_config(resource_name)
    row = connection.execute(
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

    connection.execute(
        f"UPDATE {config['table']} SET is_archived = 0, archived_at = NULL WHERE id = ?",
        (object_id,),
    )
    connection.commit()
    return {
        "resource": resource_name,
        "id": object_id,
        "is_archived": 0,
        "archived_at": None,
    }


def delete_object(connection: sqlite3.Connection, resource_name: str, object_id: int) -> dict:
    config = _get_lifecycle_config(resource_name)
    row = connection.execute(
        f"SELECT id, is_archived FROM {config['table']} WHERE id = ?",
        (object_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{config['label']} not found")
    if not row["is_archived"]:
        raise ValueError(f"{config['label']} must be archived before deletion")

    dependency_counts: list[str] = []
    for dependency in config["dependencies"]:
        dependency_count = _count_lifecycle_dependency(connection, dependency, object_id)
        if dependency_count:
            dependency_counts.append(f"{dependency['label']}:{dependency_count}")

    if dependency_counts:
        raise ValueError(
            f"dependencies prevent deletion of {config['label']}: " + ", ".join(dependency_counts)
        )

    connection.execute(f"DELETE FROM {config['table']} WHERE id = ?", (object_id,))
    connection.commit()
    return {"resource": resource_name, "id": object_id, "deleted": True}


def create_tenant(connection: sqlite3.Connection, payload: dict) -> dict:
    cursor = connection.execute(
        """
        INSERT INTO tenants (
            full_name, email, phone, alternate_street, alternate_postal_code, alternate_city
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload["full_name"],
            payload.get("email"),
            payload.get("phone"),
            payload.get("alternate_street"),
            payload.get("alternate_postal_code"),
            payload.get("alternate_city"),
        ),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        "full_name": payload["full_name"],
        "email": payload.get("email"),
        "phone": payload.get("phone"),
        "alternate_street": payload.get("alternate_street"),
        "alternate_postal_code": payload.get("alternate_postal_code"),
        "alternate_city": payload.get("alternate_city"),
    }


def _normalize_lease_payload(
    connection: sqlite3.Connection,
    payload: dict,
    lease_id: int | None = None,
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id in (None, ""):
        raise ValueError("lease requires tenant_id")
    tenant_row = connection.execute(
        "SELECT id FROM tenants WHERE id = ?",
        (int(tenant_id),),
    ).fetchone()
    if tenant_row is None:
        raise ValueError("lease requires existing tenant_id")

    raw_unit_id = payload.get("unit_id")
    raw_room_id = payload.get("room_id")
    unit_id = None if raw_unit_id in (None, "") else int(raw_unit_id)
    room_id = None if raw_room_id in (None, "") else int(raw_room_id)

    if unit_id is None and room_id is None:
        raise ValueError("lease requires unit_id or room_id")

    if room_id is not None:
        room_row = connection.execute(
            """
            SELECT id, unit_id, COALESCE(is_archived, 0) AS is_archived
            FROM rooms
            WHERE id = ?
            """,
            (room_id,),
        ).fetchone()
        if room_row is None:
            raise ValueError("lease requires existing room_id")
        if int(room_row["is_archived"] or 0):
            raise ValueError("archived room cannot be assigned to lease")
        derived_unit_id = int(room_row["unit_id"])
        if unit_id is not None and unit_id != derived_unit_id:
            raise ValueError("room_id must belong to unit_id")
        unit_id = derived_unit_id

    if unit_id is None:
        raise ValueError("lease requires unit_id or room_id")

    unit_row = connection.execute(
        """
        SELECT id, COALESCE(is_archived, 0) AS is_archived
        FROM units
        WHERE id = ?
        """,
        (unit_id,),
    ).fetchone()
    if unit_row is None:
        raise ValueError("lease requires existing unit_id")
    if int(unit_row["is_archived"] or 0):
        raise ValueError("archived unit cannot be assigned to lease")

    start_date = str(payload["start_date"])
    parse_date(start_date)
    end_date = payload.get("end_date")
    if end_date not in (None, ""):
        parse_date(str(end_date))
        if str(end_date) < start_date:
            raise ValueError("end_date must be after or equal to start_date")

    occupant_count = int(payload["occupant_count"])
    if occupant_count < 1:
        raise ValueError("occupant_count must be at least 1")

    gnucash_account_guid = str(payload.get("gnucash_nk_account_guid") or "").strip() or None
    gnucash_account_name = str(payload.get("gnucash_nk_account_name") or "").strip() or None
    if gnucash_account_guid is not None:
        existing_lease = connection.execute(
            "SELECT id FROM leases WHERE gnucash_nk_account_guid = ?",
            (gnucash_account_guid,),
        ).fetchone()
        if existing_lease is not None and int(existing_lease["id"]) != lease_id:
            raise ValueError("a GnuCash NK account can only be assigned to one lease")

    return {
        "unit_id": unit_id,
        "room_id": room_id,
        "tenant_id": int(tenant_id),
        "rent_cold": str(Decimal(str(payload["rent_cold"]))),
        "additional_charges_advance": str(Decimal(str(payload["additional_charges_advance"]))),
        "occupant_count": occupant_count,
        "start_date": start_date,
        "end_date": end_date if end_date not in ("",) else None,
        "status": payload.get("status", "active"),
        "gnucash_nk_account_guid": gnucash_account_guid,
        "gnucash_nk_account_name": gnucash_account_name,
    }


def create_lease(connection: sqlite3.Connection, payload: dict) -> dict:
    normalized_payload = _normalize_lease_payload(connection, payload)
    cursor = connection.execute(
        """
        INSERT INTO leases (
            unit_id, room_id, tenant_id, rent_cold, additional_charges_advance,
            occupant_count, start_date, end_date, status,
            gnucash_nk_account_guid, gnucash_nk_account_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_payload["unit_id"],
            normalized_payload["room_id"],
            normalized_payload["tenant_id"],
            normalized_payload["rent_cold"],
            normalized_payload["additional_charges_advance"],
            normalized_payload["occupant_count"],
            normalized_payload["start_date"],
            normalized_payload["end_date"],
            normalized_payload["status"],
            normalized_payload["gnucash_nk_account_guid"],
            normalized_payload["gnucash_nk_account_name"],
        ),
    )
    connection.commit()
    return {"id": cursor.lastrowid, **normalized_payload}


def update_property(connection: sqlite3.Connection, property_id: int, payload: dict) -> dict:
    row = connection.execute(
        "SELECT id, is_archived FROM properties WHERE id = ?",
        (property_id,),
    ).fetchone()
    if row is None:
        raise ValueError("property not found")
    if row["is_archived"]:
        raise ValueError("archived property cannot be edited")

    connection.execute(
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
    connection.commit()
    return {"id": property_id, **payload}


def update_building(connection: sqlite3.Connection, building_id: int, payload: dict) -> dict:
    row = connection.execute(
        "SELECT id, is_archived FROM buildings WHERE id = ?",
        (building_id,),
    ).fetchone()
    if row is None:
        raise ValueError("building not found")
    if row["is_archived"]:
        raise ValueError("archived building cannot be edited")

    connection.execute(
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
    connection.commit()
    return {"id": building_id, **payload}


def update_unit(connection: sqlite3.Connection, unit_id: int, payload: dict) -> dict:
    row = connection.execute(
        "SELECT id, is_archived FROM units WHERE id = ?",
        (unit_id,),
    ).fetchone()
    if row is None:
        raise ValueError("unit not found")
    if row["is_archived"]:
        raise ValueError("archived unit cannot be edited")

    requested_room_count = int(payload["room_count"])
    room_count_row = connection.execute(
        """
        SELECT COUNT(*) AS actual_room_count
        FROM rooms
        WHERE unit_id = ?
        """,
        (unit_id,),
    ).fetchone()
    if room_count_row is not None and room_count_row["actual_room_count"] > requested_room_count:
        raise ValueError("room_count cannot be lower than existing rooms")

    street, city, postal_code = _unit_address(connection, payload)
    connection.execute(
        """
        UPDATE units
        SET building_id = ?, label = ?, area_sqm = ?, room_count = ?, street = ?, city = ?, postal_code = ?
        WHERE id = ?
        """,
        (
            payload.get("building_id"),
            payload["label"],
            str(Decimal(str(payload["area_sqm"]))),
            requested_room_count,
            street,
            city,
            postal_code,
            unit_id,
        ),
    )
    connection.commit()
    return {
        "id": unit_id,
        **payload,
        "street": street,
        "city": city,
        "postal_code": postal_code,
    }


def update_room(connection: sqlite3.Connection, room_id: int, payload: dict) -> dict:
    row = connection.execute(
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
    unit_row = connection.execute(
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

    connection.execute(
        "UPDATE rooms SET unit_id = ?, label = ?, area_sqm = ? WHERE id = ?",
        (unit_id, label, area_sqm, room_id),
    )
    connection.commit()
    return {
        "id": room_id,
        "unit_id": unit_id,
        "label": label,
        "area_sqm": area_sqm,
    }


def update_tenant(connection: sqlite3.Connection, tenant_id: int, payload: dict) -> dict:
    row = _tenant_exists(connection, tenant_id)
    if row is None:
        raise ValueError("tenant not found")

    connection.execute(
        """
        UPDATE tenants
        SET full_name = ?, email = ?, phone = ?, alternate_street = ?, alternate_postal_code = ?,
            alternate_city = ?
        WHERE id = ?
        """,
        (
            payload["full_name"],
            payload.get("email"),
            payload.get("phone"),
            payload.get("alternate_street"),
            payload.get("alternate_postal_code"),
            payload.get("alternate_city"),
            tenant_id,
        ),
    )
    connection.commit()
    return {
        "id": tenant_id,
        "full_name": payload["full_name"],
        "email": payload.get("email"),
        "phone": payload.get("phone"),
        "alternate_street": payload.get("alternate_street"),
        "alternate_postal_code": payload.get("alternate_postal_code"),
        "alternate_city": payload.get("alternate_city"),
    }


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
    connection_settings = _gnucash_connection_settings(connection)
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
    connection.commit()
    return {"imported": imported, "existing": existing, "accounts": len(accounts)}


def delete_tenant(connection: sqlite3.Connection, tenant_id: int) -> dict:
    row = _tenant_exists(connection, tenant_id)
    if row is None:
        raise ValueError("tenant not found")

    lease_count_row = connection.execute(
        "SELECT COUNT(*) AS lease_count FROM leases WHERE tenant_id = ?",
        (tenant_id,),
    ).fetchone()
    if lease_count_row is not None and int(lease_count_row["lease_count"] or 0) > 0:
        raise ValueError("tenant cannot be deleted while leases exist")

    payment_count_row = connection.execute(
        "SELECT COUNT(*) AS payment_count FROM gnucash_payments WHERE tenant_id = ?", (tenant_id,)
    ).fetchone()
    if payment_count_row is not None and int(payment_count_row["payment_count"] or 0) > 0:
        raise ValueError("tenant cannot be deleted while GnuCash payments exist")

    connection.execute("DELETE FROM tenant_documents WHERE tenant_id = ?", (tenant_id,))
    connection.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
    connection.commit()
    return {"resource": "tenants", "id": tenant_id, "deleted": True}


def delete_lease(connection: sqlite3.Connection, lease_id: int) -> dict:
    row = _lease_exists(connection, lease_id)
    if row is None:
        raise ValueError("lease not found")

    payment_count_row = connection.execute(
        "SELECT COUNT(*) AS payment_count FROM gnucash_payments WHERE lease_id = ?", (lease_id,)
    ).fetchone()
    if payment_count_row is not None and int(payment_count_row["payment_count"] or 0) > 0:
        raise ValueError("lease cannot be deleted while GnuCash payments exist")

    connection.execute("DELETE FROM lease_documents WHERE lease_id = ?", (lease_id,))
    connection.execute("DELETE FROM leases WHERE id = ?", (lease_id,))
    connection.commit()
    return {"resource": "leases", "id": lease_id, "deleted": True}


def update_lease(connection: sqlite3.Connection, lease_id: int, payload: dict) -> dict:
    row = _lease_exists(connection, lease_id)
    if row is None:
        raise ValueError("lease not found")

    normalized_payload = _normalize_lease_payload(connection, payload, lease_id)

    connection.execute(
        """
        UPDATE leases
        SET unit_id = ?,
            room_id = ?,
            tenant_id = ?,
            rent_cold = ?,
            additional_charges_advance = ?,
            occupant_count = ?,
            start_date = ?,
            end_date = ?,
            status = ?,
            gnucash_nk_account_guid = ?,
            gnucash_nk_account_name = ?
        WHERE id = ?
        """,
        (
            normalized_payload["unit_id"],
            normalized_payload["room_id"],
            normalized_payload["tenant_id"],
            normalized_payload["rent_cold"],
            normalized_payload["additional_charges_advance"],
            normalized_payload["occupant_count"],
            normalized_payload["start_date"],
            normalized_payload["end_date"],
            normalized_payload["status"],
            normalized_payload["gnucash_nk_account_guid"],
            normalized_payload["gnucash_nk_account_name"],
            lease_id,
        ),
    )
    connection.commit()
    return {
        "id": lease_id,
        **normalized_payload,
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
    connection.commit()
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
    connection.commit()
    return _expense_response_payload(connection, expense_id, normalized_payload)


def create_depreciation_asset(connection: sqlite3.Connection, payload: dict) -> dict:
    cursor = connection.execute(
        """
        INSERT INTO depreciation_assets (
            property_id, asset_name, acquisition_cost, building_share_percent,
            useful_life_years, placed_in_service, method
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["property_id"],
            payload["asset_name"],
            str(Decimal(str(payload["acquisition_cost"]))),
            str(Decimal(str(payload["building_share_percent"]))),
            payload["useful_life_years"],
            payload["placed_in_service"],
            payload.get("method", "linear"),
        ),
    )
    connection.commit()
    return {"id": cursor.lastrowid, **payload}


def _allocation_basis_for_lease(lease_row: sqlite3.Row, method: str) -> Decimal:
    if method == "area":
        return Decimal(str(lease_row["area_sqm"]))
    if method == "occupants":
        return Decimal(str(lease_row["occupant_count"]))
    return Decimal("1")


def _exact_expense_shares_for_period(
    connection: sqlite3.Connection,
    expense_row: sqlite3.Row,
    eligible_leases: list[sqlite3.Row],
    period_start: str,
    period_end: str,
) -> dict[int, Decimal]:
    """Allocate exact cost-curve segments without counting sequential leases twice."""
    shares = {lease_row["id"]: Decimal("0") for lease_row in eligible_leases}
    coverage_start = max(parse_date(expense_row["period_start"]), parse_date(period_start))
    coverage_end = min(parse_date(expense_row["period_end"]), parse_date(period_end))
    if coverage_start > coverage_end:
        return shares

    boundaries = {coverage_start, coverage_end + timedelta(days=1)}
    for lease_row in eligible_leases:
        lease_start = max(parse_date(lease_row["start_date"]), coverage_start)
        lease_end = min(
            parse_date(lease_row["end_date"])
            if lease_row["end_date"]
            else coverage_end,
            coverage_end,
        )
        if lease_start <= lease_end:
            boundaries.add(lease_start)
            boundaries.add(lease_end + timedelta(days=1))

    sorted_boundaries = sorted(boundaries)
    for segment_start, next_segment_start in zip(
        sorted_boundaries, sorted_boundaries[1:]
    ):
        segment_end = next_segment_start - timedelta(days=1)
        active_leases = [
            lease_row
            for lease_row in eligible_leases
            if parse_date(lease_row["start_date"]) <= segment_start
            and (
                parse_date(lease_row["end_date"])
                if lease_row["end_date"]
                else coverage_end
            )
            >= segment_end
        ]
        if not active_leases:
            continue
        _, segment_amount_text = _total_amount_for_expense_period(
            connection,
            dict(expense_row),
            segment_start.isoformat(),
            segment_end.isoformat(),
        )
        segment_amount = Decimal(segment_amount_text or "0")
        basis_values = {
            lease_row["id"]: _allocation_basis_for_lease(
                lease_row, expense_row["allocation_method"]
            )
            for lease_row in active_leases
        }
        basis_total = sum(basis_values.values(), start=Decimal("0"))
        if basis_total <= 0:
            continue
        for lease_row in active_leases:
            shares[lease_row["id"]] += (
                segment_amount * basis_values[lease_row["id"]] / basis_total
            )
    return {lease_id: quantize_money(share) for lease_id, share in shares.items()}


def settlement_for_period(
    connection: sqlite3.Connection,
    property_id: int | None,
    period_start: str,
    period_end: str,
    unit_id: int | None = None,
    payment_split_guids: set[str] | None = None,
) -> dict:
    target_where = "b.property_id = ?" if unit_id is None else "u.id = ?"
    target_value = property_id if unit_id is None else unit_id
    lease_rows = connection.execute(
        """
        SELECT
               l.id,
               l.unit_id,
               l.room_id,
               l.tenant_id,
               t.full_name AS tenant_name,
               CASE
                   WHEN l.room_id IS NOT NULL THEN r.label || ' (' || u.label || ')'
                   ELSE u.label
               END AS unit_label,
               u.area_sqm, u.building_id,
               l.occupant_count, l.additional_charges_advance, l.start_date, l.end_date
        FROM leases l
        JOIN tenants t ON t.id = l.tenant_id
        JOIN units u ON u.id = l.unit_id
        LEFT JOIN rooms r ON r.id = l.room_id
        LEFT JOIN buildings b ON b.id = u.building_id
        WHERE """ + target_where + """
        ORDER BY l.id
        """,
        (target_value,),
    ).fetchall()

    expense_rows = connection.execute(
        """
        SELECT id, object_type, object_id, expense_category, label, amount,
               allocation_method,
               charge_type, recurrence, interval_name,
               meter_id, consumption_unit, consumption_value, conversion_factor,
               booking_date, period_start, period_end,
               CASE
                   WHEN object_type = 'room'
                   THEN (SELECT unit_id FROM rooms WHERE rooms.id = expense_items.object_id)
                   ELSE NULL
               END AS target_room_unit_id
        FROM expense_items
        WHERE (
              property_id = ?
              OR (
                  ? IS NOT NULL
                  AND (
                      (object_type = 'unit' AND object_id = ?)
                      OR (
                          object_type = 'room'
                          AND EXISTS (
                              SELECT 1 FROM rooms target_room
                              WHERE target_room.id = expense_items.object_id
                                AND target_room.unit_id = ?
                          )
                      )
                      OR (
                          object_type = 'building'
                          AND object_id = (SELECT building_id FROM units WHERE id = ?)
                      )
                  )
              )
          )
          AND COALESCE(is_archived, 0) = 0
          AND period_end >= ?
          AND period_start <= ?
        ORDER BY id
        """,
        (
            property_id,
            unit_id,
            unit_id,
            unit_id,
            unit_id,
            period_start,
            period_end,
        ),
    ).fetchall()

    leases = [
        SettlementLease(
            lease_id=row["id"],
            tenant_name=row["tenant_name"],
            unit_label=row["unit_label"],
            unit_area_sqm=Decimal(str(row["area_sqm"])),
            occupant_count=row["occupant_count"],
            additional_charges_advance=Decimal(str(row["additional_charges_advance"])),
            lease_start=parse_date(row["start_date"]),
            lease_end=parse_date(row["end_date"]) if row["end_date"] else None,
        )
        for row in lease_rows
    ]
    expenses: list[SettlementExpense] = []
    eligible_lease_ids_by_expense: dict[int, tuple[int, ...]] = {}
    for row in expense_rows:
        if row["object_type"] == "building":
            eligible_lease_ids = tuple(
                lease_row["id"]
                for lease_row in lease_rows
                if lease_row["building_id"] == row["object_id"]
            )
        elif row["object_type"] == "unit":
            eligible_lease_ids = tuple(
                lease_row["id"]
                for lease_row in lease_rows
                if lease_row["unit_id"] == row["object_id"]
            )
        elif row["object_type"] == "room":
            eligible_lease_ids = tuple(
                lease_row["id"]
                for lease_row in lease_rows
                if lease_row["room_id"] == row["object_id"]
                or (
                    lease_row["room_id"] is None
                    and lease_row["unit_id"] == row["target_room_unit_id"]
                )
            )
        else:
            eligible_lease_ids = tuple(lease_row["id"] for lease_row in lease_rows)
        eligible_lease_ids_by_expense[row["id"]] = eligible_lease_ids
        overlap = overlap_period(
            row["period_start"], row["period_end"], period_start, period_end
        )
        overlap_start, overlap_end = overlap or (row["period_start"], row["period_end"])
        _, effective_consumption_value = _effective_consumption_quantity(
            connection,
            {
                "charge_type": row["charge_type"],
                "meter_id": row["meter_id"],
                "consumption_unit": row["consumption_unit"],
                "consumption_value": row["consumption_value"],
                "conversion_factor": row["conversion_factor"],
                "period_start": row["period_start"],
                "period_end": row["period_end"],
            },
            overlap_start,
            overlap_end,
        )
        expenses.append(
            SettlementExpense(
                source_id=row["id"],
                label=row["label"],
                amount=Decimal(str(row["amount"])),
                allocation_method=row["allocation_method"],
                charge_type=row["charge_type"],
                recurrence=row["recurrence"],
                interval_name=row["interval_name"],
                expense_start=parse_date(row["period_start"]),
                expense_end=parse_date(row["period_end"]),
                consumption_unit=row["consumption_unit"],
                consumption_value=effective_consumption_value,
                eligible_lease_ids=eligible_lease_ids,
            )
        )

    result = calculate_settlement(
        leases=leases,
        expenses=expenses,
        period_start=parse_date(period_start),
        period_end=parse_date(period_end),
    )
    expense_by_id = {row["id"]: row for row in expense_rows}
    lease_by_id = {row["id"]: row for row in lease_rows}
    exact_shares = {
        (expense_row["id"], lease_id): share
        for expense_row in expense_rows
        for lease_id, share in _exact_expense_shares_for_period(
            connection,
            expense_row,
            [
                lease_by_id[eligible_lease_id]
                for eligible_lease_id in eligible_lease_ids_by_expense[expense_row["id"]]
            ],
            period_start,
            period_end,
        ).items()
    }
    adjusted_total_costs = Decimal("0")
    for lease_result in result["results"]:
        lease_row = lease_by_id[lease_result["lease_id"]]
        lease_start = max(parse_date(lease_row["start_date"]), parse_date(period_start))
        lease_end = min(
            parse_date(lease_row["end_date"])
            if lease_row["end_date"]
            else parse_date(period_end),
            parse_date(period_end),
        )
        for line_item in lease_result["line_items"]:
            row = expense_by_id[line_item["source_id"]]
            line_item["expense_category"] = row["expense_category"] or row["label"]
            tenant_expense_overlap = overlap_period(
                row["period_start"],
                row["period_end"],
                lease_start.isoformat(),
                lease_end.isoformat(),
            )
            tenant_consumption = None
            if tenant_expense_overlap is not None:
                tenant_period_start, tenant_period_end = tenant_expense_overlap
                _, tenant_consumption = _effective_consumption_quantity(
                    connection,
                    dict(row),
                    tenant_period_start,
                    tenant_period_end,
                )
            tenant_share = exact_shares[(line_item["source_id"], lease_result["lease_id"])]
            line_item["share"] = f"{tenant_share:.2f}"
            line_item["tenant_consumption_value"] = _decimal_to_string(tenant_consumption)
            adjusted_total_costs += tenant_share
        lease_result["allocated_costs"] = (
            f"{sum((Decimal(item['share']) for item in lease_result['line_items']), start=Decimal('0')):.2f}"
        )
    payment_filter = ""
    payment_params: list[object] = [period_start, period_end]
    if payment_split_guids is not None:
        if not payment_split_guids:
            payment_filter = " AND 1 = 0"
        else:
            payment_filter = " AND gp.split_guid IN (" + ", ".join(
                "?" for _ in payment_split_guids
            ) + ")"
            payment_params.extend(sorted(payment_split_guids))
    payment_rows = connection.execute(
        """
        SELECT gp.lease_id, gp.amount
        FROM gnucash_payments gp
        JOIN leases l ON l.id = gp.lease_id
        WHERE gp.booking_date >= ? AND gp.booking_date <= ?
          AND gp.booking_date >= l.start_date
          AND (l.end_date IS NULL OR gp.booking_date <= l.end_date)
        """ + payment_filter,
        payment_params,
    ).fetchall()
    total_advances = Decimal("0")
    for lease_result in result["results"]:
        raw_signed_advances = sum(
            (
                Decimal(str(payment["amount"]))
                for payment in payment_rows
                if int(payment["lease_id"]) == int(lease_result["lease_id"])
            ),
            start=Decimal("0"),
        )
        advances_paid = quantize_money(-raw_signed_advances)
        balance = quantize_money(
            Decimal(lease_result["allocated_costs"]) - advances_paid
        )
        lease_result["advances_paid"] = f"{advances_paid:.2f}"
        lease_result["balance"] = f"{balance:.2f}"
        total_advances += advances_paid
    total_costs = quantize_money(adjusted_total_costs)
    result["totals"] = {
        "costs": f"{total_costs:.2f}",
        "advances": f"{quantize_money(total_advances):.2f}",
        "balance": f"{quantize_money(total_costs - total_advances):.2f}",
    }
    result["property_id"] = property_id
    result["unit_id"] = unit_id
    return result


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
    settlement = settlement_for_period(
        connection,
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
        const_in_run = _payment_is_in_settlement_run(payment, lease, run)
        if assignments.get(str(payment["split_guid"])) == "considered":
            if not const_in_run:
                item["warning"] = "Außerhalb berücksichtigtem Zeitraum"
            groups["considered_payments"].append(item)
        elif not const_in_run:
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
        _gnucash_connection_settings(connection), set(accounts), date(1900, 1, 1), date(2100, 12, 31)
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
    connection.commit()
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
    connection.commit()
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
    connection.commit()
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
        connection.commit()
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


def _format_settlement_money(value: str) -> str:
    return f"{Decimal(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def settlement_document_for_period(
    connection: sqlite3.Connection,
    property_id: int,
    lease_id: int,
    period_start: str,
    period_end: str,
) -> str:
    """Render a printable settlement document from the calculated source data.

    The line items are deliberately taken from the settlement result, so newly
    created expense categories and their allocation methods need no document
    template changes.
    """
    settlement = settlement_for_period(connection, property_id, period_start, period_end)
    result = next((item for item in settlement["results"] if item["lease_id"] == lease_id), None)
    if result is None:
        raise ValueError("lease is not part of the selected settlement period")

    details = connection.execute(
        """
        SELECT p.name AS property_name, p.street AS property_street,
               p.postal_code AS property_postal_code, p.city AS property_city,
               o.name AS organization_name, t.full_name AS tenant_name,
               u.label AS unit_label, u.street AS unit_street,
               u.postal_code AS unit_postal_code, u.city AS unit_city,
               r.label AS room_label
        FROM leases l
        JOIN tenants t ON t.id = l.tenant_id
        JOIN units u ON u.id = l.unit_id
        LEFT JOIN rooms r ON r.id = l.room_id
        JOIN buildings b ON b.id = u.building_id
        JOIN properties p ON p.id = b.property_id
        JOIN organizations o ON o.id = p.organization_id
        WHERE l.id = ? AND p.id = ?
        """,
        (lease_id, property_id),
    ).fetchone()
    if details is None:
        raise ValueError("lease not found for property")

    def esc(value: object) -> str:
        return html.escape(str(value or ""))

    allocation_labels = {
        "area": "Wohnfläche",
        "unit_count": "Einheiten",
        "occupants": "Personen",
    }
    line_rows = "".join(
        "<tr>"
        f"<td>{esc(item['label'])}</td>"
        f"<td>{esc(allocation_labels.get(item['allocation_method'], item['allocation_method']))}</td>"
        f"<td class=\"amount\">{_format_settlement_money(item['share'])}</td>"
        "</tr>"
        for item in result["line_items"]
    )
    rental_object = details["room_label"] or details["unit_label"]
    today = date.today().strftime("%d.%m.%Y")
    return f"""<!doctype html>
<html lang=\"de\"><head><meta charset=\"utf-8\"><title>Nebenkostenabrechnung {esc(details['tenant_name'])} {esc(period_start[:4])}</title>
<style>
@page {{ size: A4; margin: 20mm; }}
body {{ font: 11pt Arial, sans-serif; color: #111; max-width: 170mm; margin: 0 auto; }}
header {{ display: flex; justify-content: space-between; margin-bottom: 28mm; }}
.muted {{ color: #555; }} .recipient {{ margin-bottom: 22mm; }}
table {{ border-collapse: collapse; width: 100%; margin: 14px 0; }}
th, td {{ border-bottom: 1px solid #bbb; padding: 8px 5px; text-align: left; }}
th {{ border-top: 1px solid #555; }} .amount {{ text-align: right; white-space: nowrap; }}
.total td {{ border-top: 2px solid #222; font-weight: bold; }}
.notice {{ margin-top: 22px; }}
@media print {{ .no-print {{ display: none; }} }}
</style></head><body onload="window.print()">
<button class=\"no-print\" onclick=\"window.print()\">Drucken / als PDF speichern</button>
<header><div><strong>{esc(details['organization_name'])}</strong><br>{esc(details['property_street'])}<br>{esc(details['property_postal_code'])} {esc(details['property_city'])}</div>
<div class=\"muted\">Erstellt am: {today}</div></header>
<div class=\"recipient\"><strong>{esc(details['tenant_name'])}</strong><br>{esc(rental_object)}<br>{esc(details['unit_street'])}<br>{esc(details['unit_postal_code'])} {esc(details['unit_city'])}</div>
<h1>Nebenkostenabrechnung</h1>
<p>Abrechnungszeitraum: <strong>{esc(result['billing_period_start'])} bis {esc(result['billing_period_end'])}</strong><br>Mietobjekt: {esc(rental_object)} · {esc(details['property_name'])}</p>
<table><thead><tr><th>Kostenart</th><th>Verteilerschlüssel</th><th class=\"amount\">Ihr Anteil</th></tr></thead>
<tbody>{line_rows}</tbody>
<tfoot><tr class=\"total\"><td colspan=\"2\">Umlagefähige Kosten</td><td class=\"amount\">{_format_settlement_money(result['allocated_costs'])}</td></tr></tfoot></table>
</body></html>"""


def settlement_pdf_for_period(
    connection: sqlite3.Connection,
    property_id: int | None,
    lease_id: int,
    period_start: str,
    period_end: str,
    unit_id: int | None = None,
) -> tuple[bytes, str]:
    """Create a downloadable PDF; each row comes from the stored cost item key."""
    settlement = settlement_for_period(connection, property_id, period_start, period_end, unit_id)
    result = next((item for item in settlement["results"] if item["lease_id"] == lease_id), None)
    if result is None:
        raise ValueError("lease is not part of the selected settlement period")
    details = connection.execute(
        """
        SELECT p.name AS property_name, p.street, p.postal_code, p.city,
               o.name AS organization_name, t.full_name AS tenant_name,
               t.alternate_street, t.alternate_postal_code, t.alternate_city,
               u.label AS unit_label, u.street AS unit_street, u.postal_code AS unit_postal_code, u.city AS unit_city, r.label AS room_label
        FROM leases l JOIN tenants t ON t.id = l.tenant_id
        JOIN units u ON u.id = l.unit_id LEFT JOIN rooms r ON r.id = l.room_id
        LEFT JOIN buildings b ON b.id = u.building_id LEFT JOIN properties p ON p.id = b.property_id
        LEFT JOIN organizations o ON o.id = p.organization_id
        WHERE l.id = ? AND (p.id = ? OR (? IS NOT NULL AND u.id = ?))
        """,
        (lease_id, property_id, unit_id, unit_id),
    ).fetchone()
    if details is None:
        raise ValueError("lease not found for property")

    labels = {"area": "Wohnfläche", "unit_count": "Einheiten", "occupants": "Personen"}
    has_alternate_address = all(
        details[field] for field in ("alternate_street", "alternate_postal_code", "alternate_city")
    )
    recipient_street = details["alternate_street"] if has_alternate_address else details["unit_street"]
    recipient_city_line = (
        f"{details['alternate_postal_code']} {details['alternate_city']}"
        if has_alternate_address
        else f"{details['unit_postal_code']} {details['unit_city']}"
    )
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(html.escape(str(details["organization_name"])), styles["Normal"]),
        Paragraph(html.escape(f"{details['street']}, {details['postal_code']} {details['city']}"), styles["Normal"]),
        Spacer(1, 15 * mm),
        Paragraph(html.escape(str(details["tenant_name"])), styles["Normal"]),
        Paragraph(html.escape(str(recipient_street)), styles["Normal"]),
        Paragraph(html.escape(recipient_city_line), styles["Normal"]),
        Paragraph(html.escape(f"Mietobjekt: {details['room_label'] or details['unit_label']}"), styles["Normal"]),
        Spacer(1, 10 * mm),
        Paragraph("Nebenkostenabrechnung", styles["Title"]),
        Paragraph(
            f"Abrechnungszeitraum: {result['billing_period_start']} "
            f"bis {result['billing_period_end']}",
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]
    rows = [["Kostenart", "Schlüssel", "Jahreskosten", "Mietzeitraum", "Ihr Anteil"]]
    for item in result["line_items"]:
        rows.append([
            item["label"],
            labels.get(item["allocation_method"], item["allocation_method"])
            + f" ({item['basis_value']} / {item['basis_total']})",
            _format_settlement_money(item["period_amount"]),
            _format_settlement_money(item.get("tenant_period_amount", item["period_amount"])),
            _format_settlement_money(item["share"]),
        ])
    rows.append(
        [
            "",
            "Umlagefähige Kosten",
            "",
            "",
            _format_settlement_money(result["allocated_costs"]),
        ]
    )
    table = Table(rows, colWidths=[42 * mm, 41 * mm, 29 * mm, 29 * mm, 28 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf2")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    document.build(story)
    safe_tenant = "".join(char if char.isalnum() else "-" for char in str(details["tenant_name"]))
    return stream.getvalue(), f"Nebenkostenabrechnung-{safe_tenant}-{period_start[:4]}.pdf"


def settlement_ods_for_period(
    connection: sqlite3.Connection,
    property_id: int | None,
    lease_id: int,
    period_start: str,
    period_end: str,
    unit_id: int | None = None,
    payment_split_guids: set[str] | None = None,
) -> tuple[bytes, str]:
    """Fill and return the repository's editable ODS master template."""
    settlement = settlement_for_period(
        connection, property_id, period_start, period_end, unit_id, payment_split_guids
    )
    result = next((item for item in settlement["results"] if item["lease_id"] == lease_id), None)
    if result is None:
        raise ValueError("lease is not part of the selected settlement period")
    details = connection.execute(
        """
        SELECT t.alternate_street, t.alternate_postal_code, t.alternate_city,
               u.label AS unit_label, u.street AS unit_street,
               u.postal_code AS unit_postal_code, u.city AS unit_city,
               r.label AS room_label,
               b.street AS building_street, b.postal_code AS building_postal_code,
               b.city AS building_city,
               p.street AS property_street, p.postal_code AS property_postal_code,
               p.city AS property_city, o.name AS organization_name
        FROM leases l
        JOIN tenants t ON t.id = l.tenant_id
        JOIN units u ON u.id = l.unit_id
        LEFT JOIN rooms r ON r.id = l.room_id
        LEFT JOIN buildings b ON b.id = u.building_id
        LEFT JOIN properties p ON p.id = b.property_id
        LEFT JOIN organizations o ON o.id = p.organization_id
        WHERE l.id = ?
          AND (? IS NULL OR p.id = ?)
          AND (? IS NULL OR u.id = ?)
        """,
        (lease_id, property_id, property_id, unit_id, unit_id),
    ).fetchone()
    if details is None:
        raise ValueError("lease not found for selected settlement object")

    unit_street = (
        details["unit_street"]
        or details["building_street"]
        or details["property_street"]
        or ""
    )
    unit_postal_code = (
        details["unit_postal_code"]
        or details["building_postal_code"]
        or details["property_postal_code"]
        or ""
    )
    unit_city = (
        details["unit_city"]
        or details["building_city"]
        or details["property_city"]
        or ""
    )
    has_alternate = details is not None and all(
        details[field] for field in ("alternate_street", "alternate_postal_code", "alternate_city")
    )
    street = str(details["alternate_street"] if has_alternate else unit_street)
    postal_code = str(details["alternate_postal_code"] if has_alternate else unit_postal_code)
    city = str(details["alternate_city"] if has_alternate else unit_city)
    city_line = " ".join(part for part in (postal_code, city) if part)
    period_display = (
        f"{parse_date(result['billing_period_start']).strftime('%d.%m.%Y')} – "
        f"{parse_date(result['billing_period_end']).strftime('%d.%m.%Y')}"
    )
    payment_filter = ""
    payment_params: list[object] = [lease_id, period_start, period_end]
    if payment_split_guids is not None:
        if not payment_split_guids:
            payment_filter = " AND 1 = 0"
        else:
            payment_filter = " AND gp.split_guid IN (" + ", ".join(
                "?" for _ in payment_split_guids
            ) + ")"
            payment_params.extend(sorted(payment_split_guids))
    advance_payments = [
        {
            "booking_date": parse_date(row["booking_date"]).strftime("%d.%m.%Y"),
            "description": str(row["description"] or ""),
            # GnuCash stores incoming payments on the tenant account as credits.
            "amount": f"{-Decimal(str(row['amount'])):.2f}",
        }
        for row in connection.execute(
            """
            SELECT gp.booking_date, gp.description, gp.amount
            FROM gnucash_payments gp
            JOIN leases l ON l.id = gp.lease_id
            WHERE gp.lease_id = ?
              AND gp.booking_date >= ? AND gp.booking_date <= ?
              AND gp.booking_date >= l.start_date
              AND (l.end_date IS NULL OR gp.booking_date <= l.end_date)
            """ + payment_filter + """
            ORDER BY gp.booking_date, gp.split_guid
            """,
            payment_params,
        ).fetchall()
    ]
    document_bytes = render_settlement_template(
        sender_name=os.environ.get(
            "EASYPRENT_SENDER_NAME", str(details["organization_name"] or "")
        ),
        sender_street=os.environ.get("EASYPRENT_SENDER_STREET", ""),
        sender_city_line=os.environ.get("EASYPRENT_SENDER_CITY", ""),
        tenant_name=result["tenant_name"],
        tenant_street=street,
        tenant_city_line=city_line,
        object_lines=[
            str(result["unit_label"]),
            unit_street,
            " ".join(part for part in (str(unit_postal_code), str(unit_city)) if part),
        ],
        created_on=date.today().strftime("%d.%m.%Y"),
        period_label=period_display,
        line_items=result["line_items"],
        allocated_costs=result["allocated_costs"],
        advances_paid=result["advances_paid"],
        balance=result["balance"],
        advance_payments=advance_payments,
    )
    safe_tenant = "".join(char if char.isalnum() else "-" for char in result["tenant_name"])
    return document_bytes, f"Nebenkostenabrechnung-{safe_tenant}-{period_start[:4]}.ods"


def settlement_run_ods(
    connection: sqlite3.Connection, settlement_id: str, lease_id: int
) -> tuple[bytes, str]:
    run = connection.execute("SELECT * FROM settlement_runs WHERE id = ?", (settlement_id,)).fetchone()
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
    return settlement_ods_for_period(
        connection, run["property_id"], lease_id, run["period_start"], run["period_end"],
        run["unit_id"], considered_split_guids,
    )


def depreciation_schedule_for_year(connection: sqlite3.Connection, year: int) -> dict:
    assets = _row_dicts(connection.execute("SELECT * FROM depreciation_assets ORDER BY id").fetchall())
    return calculate_depreciation_schedule(assets, year)
