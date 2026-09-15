"""Fingerprint of the one unversioned schema accepted by the one-time migrator.

The fingerprint covers schema objects, column metadata, foreign keys, and SQLite's
user_version. It contains no application rows or secrets. Unknown fingerprints must
be rejected before any backup or target creation begins.
"""

from __future__ import annotations

from hashlib import sha256
import json
import sqlite3


SOURCE_TABLES = (
    "application_settings",
    "buildings",
    "depreciation_assets",
    "expense_documents",
    "expense_items",
    "gnucash_payments",
    "gnucash_settings",
    "lease_documents",
    "leases",
    "memberships",
    "meter_readings",
    "meters",
    "organizations",
    "paperless_settings",
    "properties",
    "rooms",
    "settlement_payment_assignments",
    "settlement_runs",
    "tenant_documents",
    "tenants",
    "units",
    "users",
)


def _canonical_sql(sql: str) -> str:
    """Collapse formatting outside quoted SQL values without changing their contents."""

    output: list[str] = []
    quote: str | None = None
    position = 0
    while position < len(sql):
        character = sql[position]
        if quote is not None:
            output.append(character)
            if character == quote:
                if position + 1 < len(sql) and sql[position + 1] == quote:
                    output.append(sql[position + 1])
                    position += 1
                else:
                    quote = None
        elif character in ("'", '"', "`"):
            quote = character
            output.append(character)
        elif character == "[":
            quote = "]"
            output.append(character)
        elif character.isspace():
            if output and output[-1] != " ":
                output.append(" ")
        else:
            output.append(character)
        position += 1
    return "".join(output).strip()


def schema_fingerprint(connection: sqlite3.Connection) -> str:
    """Return a deterministic SHA-256 fingerprint of SQLite schema metadata."""

    objects = []
    for kind, name, table_name, sql in connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ):
        entry: dict[str, object] = {
            "type": kind,
            "name": name,
            "table": table_name,
            "sql": _canonical_sql(sql) if sql is not None else None,
        }
        if kind == "table":
            # Names come from sqlite_master but may still require SQL quoting.
            quoted_name = '"' + name.replace('"', '""') + '"'
            entry["columns"] = [
                tuple(row)
                for row in connection.execute(f"PRAGMA table_info({quoted_name})")
            ]
            entry["foreign_keys"] = [
                tuple(row)
                for row in connection.execute(f"PRAGMA foreign_key_list({quoted_name})")
            ]
        objects.append(entry)

    payload = {
        "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
        "objects": objects,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


# Frozen from the known unversioned development schema at refactor start.
# Updated only through an explicit decision to support another historical layout.
SUPPORTED_LEGACY_FINGERPRINTS = frozenset({
    "def730f07d955d8375934fc94c24e004c462774bdc12ee18affd71401a88e312",
})
