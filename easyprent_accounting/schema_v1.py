"""Schema version 1 for the new modular-monolith persistence boundary.

This DDL is separate from db.py's current Legacy application entry. The regular
migration runner calls apply_schema_v1 inside its own transaction.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol


class SchemaExecutor(Protocol):
    """The one SQL operation needed by version-one DDL callbacks."""

    def execute(self, sql: str) -> sqlite3.Cursor: ...

SCHEMA_V1 = """
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    organization_type TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);

CREATE TABLE buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    name TEXT NOT NULL,
    year_built INTEGER,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER,
    label TEXT NOT NULL,
    area_sqm NUMERIC NOT NULL,
    mea_percent NUMERIC,
    room_count INTEGER NOT NULL,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (building_id) REFERENCES buildings(id)
);

CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    area_sqm NUMERIC,
    area_share_percent NUMERIC,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(id)
);

CREATE TABLE meters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT NOT NULL,
    object_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    meter_type TEXT,
    unit TEXT NOT NULL,
    serial_number TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT
);

CREATE TABLE meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id INTEGER NOT NULL,
    reading_date TEXT NOT NULL,
    reading_value NUMERIC NOT NULL,
    FOREIGN KEY (meter_id) REFERENCES meters(id)
);

CREATE TABLE tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    alternate_street TEXT,
    alternate_postal_code TEXT,
    alternate_city TEXT
);

CREATE TABLE leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    room_id INTEGER,
    tenant_id INTEGER NOT NULL,
    rent_cold NUMERIC NOT NULL,
    additional_charges_advance NUMERIC NOT NULL,
    occupant_count INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    status TEXT NOT NULL,
    gnucash_nk_account_guid TEXT,
    gnucash_nk_account_name TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE expense_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_type TEXT NOT NULL DEFAULT 'property',
    object_id INTEGER NOT NULL,
    expense_category TEXT NOT NULL,
    beneficiary_name TEXT NOT NULL,
    label TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    allocation_method TEXT NOT NULL,
    charge_type TEXT NOT NULL DEFAULT 'one_time',
    meter_id INTEGER,
    consumption_unit TEXT,
    consumption_value NUMERIC,
    conversion_factor NUMERIC NOT NULL DEFAULT 1,
    booking_date TEXT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (meter_id) REFERENCES meters(id)
);

CREATE TABLE paperless_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_url TEXT NOT NULL,
    api_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE application_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_delete_actions INTEGER NOT NULL DEFAULT 1,
    sender_name TEXT NOT NULL DEFAULT '',
    sender_street TEXT NOT NULL DEFAULT '',
    sender_city TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE gnucash_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    database_name TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    sslmode TEXT NOT NULL DEFAULT 'require',
    bank_account_guid TEXT,
    bank_account_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE gnucash_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    split_guid TEXT NOT NULL UNIQUE,
    transaction_guid TEXT NOT NULL,
    tenant_id INTEGER NOT NULL,
    lease_id INTEGER NOT NULL,
    account_guid TEXT NOT NULL,
    account_name TEXT,
    booking_date TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (lease_id) REFERENCES leases(id)
);

CREATE TABLE settlement_runs (
    id TEXT PRIMARY KEY,
    property_id INTEGER,
    unit_id INTEGER,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (status IN ('draft', 'finalized', 'cancelled')),
    CHECK (property_id IS NOT NULL OR unit_id IS NOT NULL),
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (unit_id) REFERENCES units(id)
);

CREATE TABLE settlement_payment_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id TEXT NOT NULL,
    split_guid TEXT NOT NULL,
    lease_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    assigned_amount NUMERIC,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (status IN ('considered', 'excluded')),
    UNIQUE (settlement_id, split_guid),
    FOREIGN KEY (settlement_id) REFERENCES settlement_runs(id),
    FOREIGN KEY (split_guid) REFERENCES gnucash_payments(split_guid),
    FOREIGN KEY (lease_id) REFERENCES leases(id)
);

CREATE UNIQUE INDEX idx_settlement_assignments_considered_split
ON settlement_payment_assignments(split_guid)
WHERE status = 'considered';

CREATE TABLE expense_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_size INTEGER NOT NULL,
    content_blob BLOB NOT NULL,
    paperless_document_id TEXT,
    paperless_task_id TEXT,
    paperless_reference_url TEXT,
    upload_status TEXT NOT NULL DEFAULT 'local',
    upload_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_items(id)
);

CREATE TABLE tenant_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_size INTEGER NOT NULL,
    content_blob BLOB NOT NULL,
    paperless_document_id TEXT,
    paperless_task_id TEXT,
    paperless_reference_url TEXT,
    upload_status TEXT NOT NULL DEFAULT 'local',
    upload_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE lease_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_size INTEGER NOT NULL,
    content_blob BLOB NOT NULL,
    paperless_document_id TEXT,
    paperless_task_id TEXT,
    paperless_reference_url TEXT,
    upload_status TEXT NOT NULL DEFAULT 'local',
    upload_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (lease_id) REFERENCES leases(id)
);

CREATE TABLE depreciation_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    asset_name TEXT NOT NULL,
    acquisition_cost NUMERIC NOT NULL,
    building_share_percent NUMERIC NOT NULL,
    useful_life_years INTEGER NOT NULL,
    placed_in_service TEXT NOT NULL,
    method TEXT NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE UNIQUE INDEX idx_leases_gnucash_nk_account_guid
ON leases(gnucash_nk_account_guid)
WHERE gnucash_nk_account_guid IS NOT NULL AND gnucash_nk_account_guid != '';
"""

TABLES: tuple[str, ...] = (
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
    "paperless_settings",
    "application_settings",
    "gnucash_settings",
    "gnucash_payments",
    "settlement_runs",
    "settlement_payment_assignments",
    "expense_documents",
    "tenant_documents",
    "lease_documents",
    "depreciation_assets",
)

APPLICATION_TABLES: tuple[str, ...] = (
    'application_settings',
    'buildings',
    'depreciation_assets',
    'expense_documents',
    'expense_items',
    'gnucash_payments',
    'gnucash_settings',
    'lease_documents',
    'leases',
    'memberships',
    'meter_readings',
    'meters',
    'organizations',
    'paperless_settings',
    'properties',
    'rooms',
    'settlement_payment_assignments',
    'settlement_runs',
    'tenant_documents',
    'tenants',
    'units',
    'users',
)

EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    'application_settings': (
        'id', 'show_delete_actions', 'sender_name', 'sender_street', 'sender_city',
        'created_at', 'updated_at',
    ),
    'buildings': (
        'id', 'property_id', 'name', 'year_built', 'street', 'city', 'postal_code',
        'is_archived', 'archived_at',
    ),
    'depreciation_assets': (
        'id', 'property_id', 'asset_name', 'acquisition_cost',
        'building_share_percent', 'useful_life_years', 'placed_in_service', 'method',
    ),
    'expense_documents': (
        'id', 'expense_id', 'filename', 'content_type', 'content_size', 'content_blob',
        'paperless_document_id', 'paperless_task_id', 'paperless_reference_url',
        'upload_status', 'upload_error', 'created_at',
    ),
    'expense_items': (
        'id', 'object_type', 'object_id', 'expense_category', 'beneficiary_name',
        'label', 'amount', 'allocation_method', 'charge_type', 'meter_id',
        'consumption_unit', 'consumption_value', 'conversion_factor', 'booking_date',
        'period_start', 'period_end', 'is_archived', 'archived_at',
    ),
    'gnucash_payments': (
        'id', 'split_guid', 'transaction_guid', 'tenant_id', 'lease_id',
        'account_guid', 'account_name', 'booking_date', 'amount', 'description',
        'imported_at',
    ),
    'gnucash_settings': (
        'id', 'host', 'port', 'database_name', 'username', 'password', 'sslmode',
        'bank_account_guid', 'bank_account_name', 'created_at', 'updated_at',
    ),
    'lease_documents': (
        'id', 'lease_id', 'filename', 'content_type', 'content_size', 'content_blob',
        'paperless_document_id', 'paperless_task_id', 'paperless_reference_url',
        'upload_status', 'upload_error', 'created_at',
    ),
    'leases': (
        'id', 'unit_id', 'room_id', 'tenant_id', 'rent_cold',
        'additional_charges_advance', 'occupant_count', 'start_date', 'end_date',
        'status', 'gnucash_nk_account_guid', 'gnucash_nk_account_name',
    ),
    'memberships': (
        'id', 'organization_id', 'user_id', 'role',
    ),
    'meter_readings': (
        'id', 'meter_id', 'reading_date', 'reading_value',
    ),
    'meters': (
        'id', 'object_type', 'object_id', 'label', 'meter_type', 'unit',
        'serial_number', 'is_archived', 'archived_at',
    ),
    'organizations': (
        'id', 'name', 'organization_type',
    ),
    'paperless_settings': (
        'id', 'base_url', 'api_token', 'created_at', 'updated_at',
    ),
    'properties': (
        'id', 'organization_id', 'name', 'street', 'city', 'postal_code',
        'is_archived', 'archived_at',
    ),
    'rooms': (
        'id', 'unit_id', 'label', 'area_sqm', 'area_share_percent', 'is_archived',
        'archived_at',
    ),
    'settlement_payment_assignments': (
        'id', 'settlement_id', 'split_guid', 'lease_id', 'status', 'reason',
        'assigned_amount', 'created_at', 'updated_at',
    ),
    'settlement_runs': (
        'id', 'property_id', 'unit_id', 'period_start', 'period_end', 'status',
        'created_at', 'updated_at',
    ),
    'tenant_documents': (
        'id', 'tenant_id', 'filename', 'content_type', 'content_size', 'content_blob',
        'paperless_document_id', 'paperless_task_id', 'paperless_reference_url',
        'upload_status', 'upload_error', 'created_at',
    ),
    'tenants': (
        'id', 'full_name', 'email', 'phone', 'alternate_street',
        'alternate_postal_code', 'alternate_city',
    ),
    'units': (
        'id', 'building_id', 'label', 'area_sqm', 'mea_percent', 'room_count',
        'street', 'city', 'postal_code', 'is_archived', 'archived_at',
    ),
    'users': (
        'id', 'full_name', 'email',
    ),
}

# Frozen from a pristine version-one database created by the transactional runner,
# including its schema_migrations ledger. Row values and applied timestamps are absent.
EXPECTED_SCHEMA_FINGERPRINT = "22ba01d2bc93dbd5a749760779e872330ab1111a5f1a61bea682d6b1320aad7d"


def apply_schema_v1(connection: SchemaExecutor) -> None:
    """Create all version-one application tables without committing the caller's transaction."""

    statement = ""
    for line in SCHEMA_V1.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError("Incomplete version-one schema statement")
