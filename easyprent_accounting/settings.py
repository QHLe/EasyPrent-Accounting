from __future__ import annotations

import base64
import binascii
import sqlite3
from datetime import UTC, date, datetime
from typing import Any, TypedDict

from .integrations.gnucash import GnuCashAccount, GnuCashReader, PiecashGnuCashReader
from .legacy_mapping import resolved_payment_leases


class ApplicationExport(TypedDict):
    format_version: int
    exported_at: str
    table_count: int
    row_count: int
    tables: dict[str, list[dict[str, Any]]]


APPLICATION_EXPORT_FORMAT_VERSION = 2

# Version 2 is a logical data contract. Its columns are deliberately listed here
# rather than discovered from SQLite so the same version has the same shape on
# both the Legacy database and schema v1.
APPLICATION_EXPORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "organizations": ("id", "name", "organization_type"),
    "users": ("id", "full_name", "email"),
    "memberships": ("id", "organization_id", "user_id", "role"),
    "properties": (
        "id",
        "organization_id",
        "name",
        "street",
        "city",
        "postal_code",
        "is_archived",
        "archived_at",
    ),
    "buildings": (
        "id",
        "property_id",
        "name",
        "year_built",
        "street",
        "city",
        "postal_code",
        "is_archived",
        "archived_at",
    ),
    "units": (
        "id",
        "building_id",
        "label",
        "area_sqm",
        "mea_percent",
        "room_count",
        "street",
        "city",
        "postal_code",
        "is_archived",
        "archived_at",
    ),
    "rooms": (
        "id",
        "unit_id",
        "label",
        "area_sqm",
        "area_share_percent",
        "is_archived",
        "archived_at",
    ),
    "meters": (
        "id",
        "object_type",
        "object_id",
        "label",
        "meter_type",
        "unit",
        "serial_number",
        "is_archived",
        "archived_at",
    ),
    "meter_readings": ("id", "meter_id", "reading_date", "reading_value"),
    "tenants": (
        "id",
        "full_name",
        "email",
        "phone",
        "alternate_street",
        "alternate_postal_code",
        "alternate_city",
    ),
    "leases": (
        "id",
        "unit_id",
        "room_id",
        "tenant_id",
        "rent_cold",
        "additional_charges_advance",
        "occupant_count",
        "start_date",
        "end_date",
        "status",
        "gnucash_nk_account_guid",
        "gnucash_nk_account_name",
    ),
    "expense_items": (
        "id",
        "object_type",
        "object_id",
        "expense_category",
        "beneficiary_name",
        "label",
        "amount",
        "allocation_method",
        "charge_type",
        "meter_id",
        "consumption_unit",
        "consumption_value",
        "conversion_factor",
        "booking_date",
        "period_start",
        "period_end",
        "is_archived",
        "archived_at",
    ),
    "application_settings": (
        "id",
        "show_delete_actions",
        "sender_name",
        "sender_street",
        "sender_city",
        "created_at",
        "updated_at",
    ),
    "gnucash_payments": (
        "id",
        "split_guid",
        "transaction_guid",
        "tenant_id",
        "lease_id",
        "account_guid",
        "account_name",
        "booking_date",
        "amount",
        "description",
        "imported_at",
    ),
    "settlement_runs": (
        "id",
        "property_id",
        "unit_id",
        "period_start",
        "period_end",
        "status",
        "created_at",
        "updated_at",
    ),
    "settlement_payment_assignments": (
        "id",
        "settlement_id",
        "split_guid",
        "lease_id",
        "status",
        "reason",
        "assigned_amount",
        "created_at",
        "updated_at",
    ),
    "expense_documents": (
        "id",
        "expense_id",
        "filename",
        "content_type",
        "content_size",
        "content_blob",
        "paperless_document_id",
        "paperless_task_id",
        "paperless_reference_url",
        "upload_status",
        "upload_error",
        "created_at",
    ),
    "tenant_documents": (
        "id",
        "tenant_id",
        "filename",
        "content_type",
        "content_size",
        "content_blob",
        "paperless_document_id",
        "paperless_task_id",
        "paperless_reference_url",
        "upload_status",
        "upload_error",
        "created_at",
    ),
    "lease_documents": (
        "id",
        "lease_id",
        "filename",
        "content_type",
        "content_size",
        "content_blob",
        "paperless_document_id",
        "paperless_task_id",
        "paperless_reference_url",
        "upload_status",
        "upload_error",
        "created_at",
    ),
    "depreciation_assets": (
        "id",
        "property_id",
        "asset_name",
        "acquisition_cost",
        "building_share_percent",
        "useful_life_years",
        "placed_in_service",
        "method",
    ),
}

APP_DATA_EXPORT_TABLES = tuple(APPLICATION_EXPORT_COLUMNS)

DOCUMENT_EXPORT_TABLES = {
    "expense_documents",
    "tenant_documents",
    "lease_documents",
}

LEGACY_TENANT_ACCOUNT_COLUMNS = {
    "gnucash_nk_account_guid",
    "gnucash_nk_account_name",
}

LEGACY_STORAGE_COLUMNS: dict[str, tuple[str, ...]] = {
    "meters": ("property_id",),
    "expense_items": ("property_id", "recurrence", "interval_name"),
}

# Format 1 was emitted before payments and settlement runs joined the backup.
# Later schema additions still used version 1, so those tables and their added
# columns are accepted when present but are not required by the original contract.
FORMAT_V1_REQUIRED_TABLES = tuple(
    table_name
    for table_name in APP_DATA_EXPORT_TABLES
    if table_name
    not in {
        "gnucash_payments",
        "settlement_runs",
        "settlement_payment_assignments",
    }
)

FORMAT_V1_REQUIRED_COLUMNS: dict[str, set[str]] = {
    table_name: set(columns)
    for table_name, columns in APPLICATION_EXPORT_COLUMNS.items()
}
FORMAT_V1_REQUIRED_COLUMNS["units"].remove("mea_percent")
FORMAT_V1_REQUIRED_COLUMNS["rooms"].remove("area_share_percent")
FORMAT_V1_REQUIRED_COLUMNS["tenants"] = {"id", "full_name", "email", "phone"}
FORMAT_V1_REQUIRED_COLUMNS["leases"].difference_update(
    LEGACY_TENANT_ACCOUNT_COLUMNS
)
FORMAT_V1_REQUIRED_COLUMNS["application_settings"].difference_update(
    {"sender_name", "sender_street", "sender_city"}
)
FORMAT_V1_REQUIRED_COLUMNS["meters"].add("property_id")
FORMAT_V1_REQUIRED_COLUMNS["expense_items"].update(
    LEGACY_STORAGE_COLUMNS["expense_items"]
)
FORMAT_V1_REQUIRED_COLUMNS["gnucash_payments"].remove("lease_id")

FORMAT_V1_ALLOWED_COLUMNS: dict[str, set[str]] = {
    table_name: set(columns)
    for table_name, columns in APPLICATION_EXPORT_COLUMNS.items()
}
for table_name, columns in LEGACY_STORAGE_COLUMNS.items():
    FORMAT_V1_ALLOWED_COLUMNS[table_name].update(columns)
FORMAT_V1_ALLOWED_COLUMNS["tenants"].update(LEGACY_TENANT_ACCOUNT_COLUMNS)

FORMAT_V1_COLUMN_DEFAULTS: dict[str, dict[str, object]] = {
    "units": {"mea_percent": None},
    "rooms": {"area_share_percent": None},
    "tenants": {
        "alternate_street": None,
        "alternate_postal_code": None,
        "alternate_city": None,
    },
    "leases": {
        "gnucash_nk_account_guid": None,
        "gnucash_nk_account_name": None,
    },
    "application_settings": {
        "sender_name": "",
        "sender_street": "",
        "sender_city": "",
    },
    "gnucash_payments": {"lease_id": None},
}

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
        SELECT show_delete_actions, sender_name, sender_street, sender_city, updated_at
        FROM application_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {
            "show_delete_actions": True,
            "sender_name": "",
            "sender_street": "",
            "sender_city": "",
            "updated_at": None,
        }

    return {
        "show_delete_actions": bool(int(row["show_delete_actions"] or 0)),
        "sender_name": str(row["sender_name"] or ""),
        "sender_street": str(row["sender_street"] or ""),
        "sender_city": str(row["sender_city"] or ""),
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


def get_gnucash_connection_settings(connection: sqlite3.Connection) -> dict:
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
        get_gnucash_connection_settings(connection)
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
        SELECT id, sender_name, sender_street, sender_city
        FROM application_settings
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    def text_value(field: str) -> str:
        value = payload.get(field)
        if value is None:
            return str(existing_row[field] or "") if existing_row is not None else ""
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text")
        return value.strip()

    sender_name = text_value("sender_name")
    sender_street = text_value("sender_street")
    sender_city = text_value("sender_city")
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    if existing_row is None:
        connection.execute(
            """
            INSERT INTO application_settings (
                show_delete_actions, sender_name, sender_street, sender_city, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1 if show_delete_actions else 0, sender_name, sender_street, sender_city, timestamp, timestamp),
        )
    else:
        connection.execute(
            """
            UPDATE application_settings
            SET show_delete_actions = ?, sender_name = ?, sender_street = ?, sender_city = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                1 if show_delete_actions else 0,
                sender_name,
                sender_street,
                sender_city,
                timestamp,
                int(existing_row["id"]),
            ),
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
        str(row[1])
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


def _export_application_table_rows(
    connection: sqlite3.Connection, table_name: str
) -> list[dict[str, Any]]:
    columns = APPLICATION_EXPORT_COLUMNS[table_name]
    missing_columns = set(columns) - set(_table_column_names(connection, table_name))
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"database table {table_name} is incompatible with export format "
            f"{APPLICATION_EXPORT_FORMAT_VERSION}: missing {missing}"
        )

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


def export_application_data(connection: sqlite3.Connection) -> ApplicationExport:
    owns_transaction = not connection.in_transaction
    if owns_transaction:
        connection.execute("BEGIN")
    try:
        exported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        tables: dict[str, list[dict]] = {}
        total_rows = 0

        for table_name in APP_DATA_EXPORT_TABLES:
            exported_rows = _export_application_table_rows(connection, table_name)
            tables[table_name] = exported_rows
            total_rows += len(exported_rows)

        _fold_legacy_tenant_accounts_into_leases(connection, tables)
        _assign_export_payment_leases(connection, tables)

        return {
            "format_version": APPLICATION_EXPORT_FORMAT_VERSION,
            "exported_at": exported_at,
            "table_count": len(APP_DATA_EXPORT_TABLES),
            "row_count": total_rows,
            "tables": tables,
        }
    finally:
        if owns_transaction:
            connection.rollback()


def _fold_legacy_tenant_accounts_into_leases(
    connection: sqlite3.Connection,
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    """Preserve old tenant-side GnuCash links in the canonical lease rows."""
    if not LEGACY_TENANT_ACCOUNT_COLUMNS.issubset(
        _table_column_names(connection, "tenants")
    ):
        return

    tenants_by_id = {tenant["id"]: tenant for tenant in tables["tenants"]}
    for tenant_id, account_guid, account_name in connection.execute(
        """
        SELECT id, gnucash_nk_account_guid, gnucash_nk_account_name
        FROM tenants
        """
    ):
        tenant = tenants_by_id[tenant_id]
        tenant["gnucash_nk_account_guid"] = account_guid
        tenant["gnucash_nk_account_name"] = account_name

    try:
        _migrate_legacy_import_gnucash_accounts(tables)
    finally:
        for tenant in tables["tenants"]:
            tenant.pop("gnucash_nk_account_guid", None)
            tenant.pop("gnucash_nk_account_name", None)


def _assign_export_payment_leases(
    connection: sqlite3.Connection,
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    """Give every exported payment an unambiguous lease before restoring it."""
    if not tables["gnucash_payments"]:
        return
    accounts = {
        int(lease["id"]): (
            lease["gnucash_nk_account_guid"],
            lease["gnucash_nk_account_name"],
        )
        for lease in tables["leases"]
    }
    payment_leases = resolved_payment_leases(connection, accounts)
    for payment in tables["gnucash_payments"]:
        payment["lease_id"] = payment_leases[int(payment["id"])]


def _format_import_columns(
    table_name: str, format_version: int
) -> tuple[set[str], set[str]]:
    if format_version == 1:
        return (
            FORMAT_V1_REQUIRED_COLUMNS[table_name],
            FORMAT_V1_ALLOWED_COLUMNS[table_name],
        )
    columns = set(APPLICATION_EXPORT_COLUMNS[table_name])
    return columns, columns


def _invalid_columns_message(
    table_name: str,
    row_index: int,
    missing: set[str],
    unexpected: set[object],
) -> str:
    details: list[str] = []
    if missing:
        details.append(f"missing {', '.join(sorted(missing))}")
    if unexpected:
        names = ", ".join(sorted((str(name) for name in unexpected)))
        details.append(f"unexpected {names}")
    return f"tables.{table_name}[{row_index}] has invalid columns: {'; '.join(details)}"


def _validate_import_payload(
    payload: object,
) -> tuple[int, dict[str, list[dict[str, Any]]]]:
    if not isinstance(payload, dict):
        raise ValueError("application import payload must be an object")
    if "format_version" not in payload:
        raise ValueError("format_version is required")

    raw_format_version = payload["format_version"]
    if isinstance(raw_format_version, bool) or not isinstance(raw_format_version, int):
        raise ValueError("format_version must be an integer")
    format_version = raw_format_version
    if format_version not in (1, APPLICATION_EXPORT_FORMAT_VERSION):
        raise ValueError("unsupported import format_version")

    tables_payload = payload.get("tables")
    if not isinstance(tables_payload, dict):
        raise ValueError("tables is required")

    supplied_tables = set(tables_payload)
    allowed_tables = set(APP_DATA_EXPORT_TABLES)
    required_tables = (
        set(FORMAT_V1_REQUIRED_TABLES)
        if format_version == 1
        else allowed_tables
    )
    missing_tables = required_tables - supplied_tables
    unexpected_tables = supplied_tables - allowed_tables
    if missing_tables or unexpected_tables:
        details: list[str] = []
        if missing_tables:
            details.append(f"missing {', '.join(sorted(missing_tables))}")
        if unexpected_tables:
            names = ", ".join(sorted((str(name) for name in unexpected_tables)))
            details.append(f"unexpected {names}")
        raise ValueError(f"tables has invalid entries: {'; '.join(details)}")

    validated_tables: dict[str, list[dict[str, Any]]] = {}
    for table_name in APP_DATA_EXPORT_TABLES:
        table_rows = tables_payload.get(table_name, [])
        if not isinstance(table_rows, list):
            raise ValueError(f"tables.{table_name} must be a list")

        required_columns, allowed_columns = _format_import_columns(
            table_name, format_version
        )
        validated_rows: list[dict[str, Any]] = []
        for row_index, row in enumerate(table_rows):
            if not isinstance(row, dict):
                raise ValueError(f"tables.{table_name}[{row_index}] must be an object")
            supplied_columns = set(row)
            missing_columns = required_columns - supplied_columns
            unexpected_columns = supplied_columns - allowed_columns
            if missing_columns or unexpected_columns:
                raise ValueError(
                    _invalid_columns_message(
                        table_name,
                        row_index,
                        missing_columns,
                        unexpected_columns,
                    )
                )

            validated_row: dict[str, Any] = {}
            for column_name, encoded_value in row.items():
                value = _decode_application_import_value(encoded_value)
                if isinstance(value, (dict, list)):
                    raise ValueError(
                        f"tables.{table_name}[{row_index}].{column_name} "
                        "has an unsupported value"
                    )
                validated_row[str(column_name)] = value
            if (
                format_version == APPLICATION_EXPORT_FORMAT_VERSION
                and table_name == "gnucash_payments"
                and not validated_row["lease_id"]
            ):
                raise ValueError(
                    f"tables.gnucash_payments[{row_index}].lease_id is required"
                )
            if (
                table_name == "depreciation_assets"
                and validated_row.get("method") != "linear"
            ):
                raise ValueError(
                    f"tables.depreciation_assets[{row_index}].method must be linear"
                )
            validated_rows.append(validated_row)
        validated_tables[table_name] = validated_rows

    expected_row_count = sum(len(rows) for rows in validated_tables.values())
    if "table_count" in payload and payload["table_count"] != len(supplied_tables):
        raise ValueError("table_count does not match tables")
    if "row_count" in payload and payload["row_count"] != expected_row_count:
        raise ValueError("row_count does not match tables")
    return format_version, validated_tables


def _normalize_import_tables(
    format_version: int,
    tables_payload: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    if format_version == APPLICATION_EXPORT_FORMAT_VERSION:
        return tables_payload

    normalized_tables: dict[str, list[dict[str, Any]]] = {}
    for table_name, columns in APPLICATION_EXPORT_COLUMNS.items():
        defaults = FORMAT_V1_COLUMN_DEFAULTS.get(table_name, {})
        normalized_rows: list[dict[str, Any]] = []
        for row in tables_payload[table_name]:
            normalized_row: dict[str, Any] = {}
            for column_name in columns:
                if column_name in row:
                    normalized_row[column_name] = row[column_name]
                else:
                    normalized_row[column_name] = defaults[column_name]
            normalized_rows.append(normalized_row)
        normalized_tables[table_name] = normalized_rows
    return normalized_tables


def _target_insert_columns(
    connection: sqlite3.Connection,
) -> dict[str, tuple[str, ...]]:
    insert_columns: dict[str, tuple[str, ...]] = {}
    for table_name, export_columns in APPLICATION_EXPORT_COLUMNS.items():
        physical_columns = set(_table_column_names(connection, table_name))
        missing_columns = set(export_columns) - physical_columns
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"database table {table_name} is incompatible with import format "
                f"{APPLICATION_EXPORT_FORMAT_VERSION}: missing {missing}"
            )
        legacy_columns = tuple(
            column_name
            for column_name in LEGACY_STORAGE_COLUMNS.get(table_name, ())
            if column_name in physical_columns
        )
        insert_columns[table_name] = (*export_columns, *legacy_columns)
    return insert_columns


def _legacy_property_id(
    connection: sqlite3.Connection, object_type: object, object_id: object
) -> object:
    if object_type == "property":
        return object_id
    queries = {
        "building": "SELECT property_id FROM buildings WHERE id = ?",
        "unit": (
            "SELECT b.property_id FROM units u "
            "LEFT JOIN buildings b ON b.id = u.building_id WHERE u.id = ?"
        ),
        "room": (
            "SELECT b.property_id FROM rooms r "
            "JOIN units u ON u.id = r.unit_id "
            "LEFT JOIN buildings b ON b.id = u.building_id WHERE r.id = ?"
        ),
    }
    query = queries.get(str(object_type))
    if query is None:
        return None
    row = connection.execute(query, (object_id,)).fetchone()
    return None if row is None else row[0]


def _legacy_storage_value(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    row: dict[str, Any],
) -> object:
    if column_name == "property_id":
        return _legacy_property_id(
            connection, row.get("object_type"), row.get("object_id")
        )
    if column_name == "recurrence":
        if row.get("charge_type") in {"monthly", "quarterly", "yearly"}:
            return "recurring"
        return "one_time"
    if column_name == "interval_name":
        charge_type = row.get("charge_type")
        return charge_type if charge_type in {"monthly", "quarterly", "yearly"} else None
    raise ValueError(f"unsupported Legacy storage column {table_name}.{column_name}")


def _account_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _migrate_legacy_import_gnucash_accounts(
    tables_payload: dict[str, list[dict[str, Any]]],
) -> int:
    tenant_rows = tables_payload["tenants"]
    lease_rows = tables_payload["leases"]
    payment_rows = tables_payload["gnucash_payments"]

    leases_by_tenant: dict[object, list[dict[str, Any]]] = {}
    leases_by_id: dict[object, dict[str, Any]] = {}
    account_owners: dict[str, dict[str, Any]] = {}
    for lease in lease_rows:
        leases_by_tenant.setdefault(lease.get("tenant_id"), []).append(lease)
        leases_by_id[lease.get("id")] = lease
        lease_guid = _account_text(lease.get("gnucash_nk_account_guid"))
        if lease_guid is None:
            continue
        if lease_guid in account_owners:
            raise ValueError("legacy GnuCash account is linked to multiple leases")
        account_owners[lease_guid] = lease

    migrated = 0
    for tenant in tenant_rows:
        account_guid = _account_text(tenant.get("gnucash_nk_account_guid"))
        account_name = _account_text(tenant.get("gnucash_nk_account_name"))
        if account_guid is None:
            if account_name is not None:
                raise ValueError("legacy tenant GnuCash account name has no GUID")
            continue

        candidates = leases_by_tenant.get(tenant.get("id"), [])
        if not candidates:
            raise ValueError(
                "legacy tenant GnuCash account cannot be mapped to a lease"
            )

        existing_owner = account_owners.get(account_guid)
        if existing_owner is not None and existing_owner not in candidates:
            raise ValueError("legacy tenant GnuCash account conflicts with a lease")

        matching_leases = [
            lease
            for lease in candidates
            if _account_text(lease.get("gnucash_nk_account_guid")) == account_guid
        ]
        if len(matching_leases) > 1:
            raise ValueError("legacy tenant GnuCash account is ambiguous")

        if matching_leases:
            target_lease = matching_leases[0]
        else:
            payment_lease_ids = {
                payment.get("lease_id")
                for payment in payment_rows
                if payment.get("tenant_id") == tenant.get("id")
                and _account_text(payment.get("account_guid")) == account_guid
                and payment.get("lease_id") is not None
            }
            if any(
                lease_id not in leases_by_id
                or leases_by_id[lease_id] not in candidates
                for lease_id in payment_lease_ids
            ):
                raise ValueError(
                    "legacy tenant GnuCash account conflicts with a payment lease"
                )
            if len(payment_lease_ids) > 1:
                raise ValueError("legacy tenant GnuCash account is ambiguous")
            if payment_lease_ids:
                target_lease = leases_by_id[next(iter(payment_lease_ids))]
            else:
                available_leases = [
                    lease
                    for lease in candidates
                    if _account_text(lease.get("gnucash_nk_account_guid")) is None
                ]
                if len(available_leases) > 1:
                    raise ValueError("legacy tenant GnuCash account is ambiguous")
                if not available_leases:
                    raise ValueError(
                        "legacy tenant GnuCash account conflicts with a lease"
                    )
                target_lease = available_leases[0]

        existing_guid = _account_text(target_lease.get("gnucash_nk_account_guid"))
        existing_name = _account_text(target_lease.get("gnucash_nk_account_name"))
        if existing_guid not in (None, account_guid):
            raise ValueError("legacy tenant GnuCash account conflicts with a lease")
        if account_name is not None and existing_name not in (None, account_name):
            raise ValueError(
                "legacy tenant GnuCash account name conflicts with a lease"
            )

        target_lease["gnucash_nk_account_guid"] = account_guid
        target_lease["gnucash_nk_account_name"] = account_name or existing_name
        tenant["gnucash_nk_account_guid"] = None
        tenant["gnucash_nk_account_name"] = None
        account_owners[account_guid] = target_lease
        migrated += 1
    return migrated


def import_application_data(connection: sqlite3.Connection, payload: object) -> dict:
    if connection.in_transaction:
        raise ValueError("application import requires a connection without an active transaction")

    format_version, tables_payload = _validate_import_payload(payload)
    insert_columns = _target_insert_columns(connection)

    migrated_legacy_gnucash_accounts = 0
    if format_version == 1:
        migrated_legacy_gnucash_accounts = _migrate_legacy_import_gnucash_accounts(
            tables_payload
        )
    tables_payload = _normalize_import_tables(format_version, tables_payload)

    total_rows = 0
    skipped_legacy_gnucash_payments = 0
    transaction_started = False
    try:
        connection.execute("BEGIN")
        transaction_started = True
        for table_name in reversed(APP_DATA_EXPORT_TABLES):
            connection.execute(f"DELETE FROM {table_name}")

        for table_name in APP_DATA_EXPORT_TABLES:
            table_rows = tables_payload[table_name]
            columns = insert_columns[table_name]
            insert_sql = (
                f"INSERT INTO {table_name} ({', '.join(columns)}) "
                f"VALUES ({', '.join(['?'] * len(columns))})"
            )
            export_column_count = len(APPLICATION_EXPORT_COLUMNS[table_name])
            for row in table_rows:
                if (
                    format_version == 1
                    and table_name == "gnucash_payments"
                    and not row.get("lease_id")
                ):
                    # Exports from before contract assignment cannot be allocated
                    # safely. They can be re-imported from GnuCash on demand.
                    skipped_legacy_gnucash_payments += 1
                    continue
                values = [row.get(column_name) for column_name in columns[:export_column_count]]
                values.extend(
                    _legacy_storage_value(connection, table_name, column_name, row)
                    for column_name in columns[export_column_count:]
                )
                connection.execute(insert_sql, values)
                total_rows += 1
        connection.commit()
    except ValueError:
        if transaction_started:
            connection.rollback()
        raise
    except sqlite3.DatabaseError as error:
        if transaction_started:
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


def _row_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


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
