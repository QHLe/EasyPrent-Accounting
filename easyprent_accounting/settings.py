from __future__ import annotations

import sqlite3
import base64
import binascii
from datetime import datetime, date, UTC
from typing import Any

from typing import TypedDict

class ApplicationExport(TypedDict):
    format_version: int
    exported_at: str
    table_count: int
    row_count: int
    tables: dict[str, list[dict[str, Any]]]



from .integrations.gnucash import PiecashGnuCashReader, GnuCashAccount, GnuCashReader

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

APPLICATION_EXPORT_FORMAT_VERSION = 2

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


def export_application_data(connection: sqlite3.Connection) -> ApplicationExport:
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



DOCUMENT_EXPORT_TABLES = {
    "expense_documents",
    "tenant_documents",
    "lease_documents",
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

