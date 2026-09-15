-- Schema-only snapshot of the known unversioned development layout.
-- No user rows or values are copied.

CREATE TABLE application_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_delete_actions INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
, sender_name TEXT NOT NULL DEFAULT '', sender_street TEXT NOT NULL DEFAULT '', sender_city TEXT NOT NULL DEFAULT '');

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

CREATE TABLE expense_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    object_type TEXT NOT NULL DEFAULT 'property',
    object_id INTEGER NOT NULL,
    expense_category TEXT NOT NULL,
    beneficiary_name TEXT NOT NULL,
    label TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    allocation_method TEXT NOT NULL,
    charge_type TEXT NOT NULL DEFAULT 'one_time',
    recurrence TEXT NOT NULL DEFAULT 'one_time',
    interval_name TEXT,
    meter_id INTEGER,
    consumption_unit TEXT,
    consumption_value NUMERIC,
    conversion_factor NUMERIC NOT NULL DEFAULT 1,
    booking_date TEXT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE gnucash_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    split_guid TEXT NOT NULL UNIQUE,
    transaction_guid TEXT NOT NULL,
    tenant_id INTEGER NOT NULL,
    account_guid TEXT NOT NULL,
    account_name TEXT,
    booking_date TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL, lease_id INTEGER,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE gnucash_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    database_name TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    sslmode TEXT NOT NULL DEFAULT 'require',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
, bank_account_guid TEXT, bank_account_name TEXT);

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
    status TEXT NOT NULL, gnucash_nk_account_guid TEXT, gnucash_nk_account_name TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id INTEGER NOT NULL,
    reading_date TEXT NOT NULL,
    reading_value NUMERIC NOT NULL,
    FOREIGN KEY (meter_id) REFERENCES meters(id)
);

CREATE TABLE meters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    object_type TEXT NOT NULL,
    object_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    meter_type TEXT,
    unit TEXT NOT NULL,
    serial_number TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    organization_type TEXT NOT NULL
);

CREATE TABLE paperless_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_url TEXT NOT NULL,
    api_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    area_sqm NUMERIC,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT, area_share_percent NUMERIC,
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

CREATE TABLE tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT
, alternate_street TEXT, alternate_postal_code TEXT, alternate_city TEXT, gnucash_nk_account_guid TEXT, gnucash_nk_account_name TEXT);

CREATE TABLE units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER,
    label TEXT NOT NULL,
    area_sqm NUMERIC NOT NULL,
    room_count INTEGER NOT NULL,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT, mea_percent NUMERIC,
    FOREIGN KEY (building_id) REFERENCES buildings(id)
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE UNIQUE INDEX idx_leases_gnucash_nk_account_guid
        ON leases(gnucash_nk_account_guid)
        WHERE gnucash_nk_account_guid IS NOT NULL AND gnucash_nk_account_guid != '';

CREATE UNIQUE INDEX idx_settlement_assignments_considered_split
ON settlement_payment_assignments(split_guid)
WHERE status = 'considered';

CREATE UNIQUE INDEX idx_tenants_gnucash_nk_account_guid
        ON tenants(gnucash_nk_account_guid)
        WHERE gnucash_nk_account_guid IS NOT NULL AND gnucash_nk_account_guid != '';
