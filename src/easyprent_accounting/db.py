from __future__ import annotations

import os
import sqlite3
from decimal import Decimal


SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    organization_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS properties (
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

CREATE TABLE IF NOT EXISTS buildings (
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

CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER,
    label TEXT NOT NULL,
    area_sqm NUMERIC NOT NULL,
    room_count INTEGER NOT NULL,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (building_id) REFERENCES buildings(id)
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    area_sqm NUMERIC,
    area_share_percent NUMERIC,
    is_archived INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(id)
);

CREATE TABLE IF NOT EXISTS meters (
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

CREATE TABLE IF NOT EXISTS meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id INTEGER NOT NULL,
    reading_date TEXT NOT NULL,
    reading_value NUMERIC NOT NULL,
    FOREIGN KEY (meter_id) REFERENCES meters(id)
);

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    alternate_street TEXT,
    alternate_postal_code TEXT,
    alternate_city TEXT
);

CREATE TABLE IF NOT EXISTS leases (
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

CREATE TABLE IF NOT EXISTS expense_items (
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

CREATE TABLE IF NOT EXISTS paperless_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_url TEXT NOT NULL,
    api_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_delete_actions INTEGER NOT NULL DEFAULT 1,
    sender_name TEXT NOT NULL DEFAULT '',
    sender_street TEXT NOT NULL DEFAULT '',
    sender_city TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gnucash_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    database_name TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    sslmode TEXT NOT NULL DEFAULT 'require',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gnucash_payments (
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

CREATE TABLE IF NOT EXISTS settlement_runs (
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

CREATE TABLE IF NOT EXISTS settlement_payment_assignments (
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_assignments_considered_split
ON settlement_payment_assignments(split_guid)
WHERE status = 'considered';

CREATE TABLE IF NOT EXISTS expense_documents (
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

CREATE TABLE IF NOT EXISTS tenant_documents (
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

CREATE TABLE IF NOT EXISTS lease_documents (
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

CREATE TABLE IF NOT EXISTS depreciation_assets (
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
"""


def default_db_path() -> str:
    return os.environ.get(
        "EASYPRENT_DB_PATH",
        os.path.join(os.getcwd(), "easyprent_accounting.db"),
    )


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(default_db_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    connection = get_connection()
    try:
        connection.executescript(SCHEMA)
        ensure_schema_updates(connection)
        connection.commit()
    finally:
        connection.close()


def ensure_schema_updates(connection: sqlite3.Connection) -> None:
    _ensure_buildings_table_supports_standalone(connection)
    _ensure_units_table_supports_standalone(connection)
    _ensure_rooms_table_exists(connection)
    _ensure_rooms_have_area_sqm(connection)
    _ensure_rooms_have_area_share_percent(connection)
    _ensure_leases_support_room_targets(connection)
    _ensure_buildings_have_addresses(connection)
    _ensure_units_have_addresses(connection)
    _ensure_object_archive_columns(connection)
    _ensure_expense_item_legacy_columns(connection)
    _ensure_expense_items_support_object_targets(connection)
    _ensure_expense_items_support_categories(connection)
    _ensure_expense_items_support_conversion_factor(connection)
    _ensure_paperless_settings_table(connection)
    _ensure_application_settings_table(connection)
    _ensure_expense_documents_table(connection)
    _ensure_tenant_documents_table(connection)
    _ensure_lease_documents_table(connection)
    _ensure_tenant_alternate_address_columns(connection)
    _ensure_gnucash_settings_table(connection)
    _ensure_gnucash_payments_table(connection)
    _ensure_settlement_payment_assignment_tables(connection)
    _ensure_lease_gnucash_account_columns(connection)


def _ensure_tenant_alternate_address_columns(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(tenants)").fetchall()}
    for column in ("alternate_street", "alternate_postal_code", "alternate_city"):
        if column not in columns:
            connection.execute(f"ALTER TABLE tenants ADD COLUMN {column} TEXT")


def _ensure_gnucash_settings_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS gnucash_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            database_name TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            sslmode TEXT NOT NULL DEFAULT 'require',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _ensure_gnucash_payments_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS gnucash_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            split_guid TEXT NOT NULL UNIQUE,
            transaction_guid TEXT NOT NULL,
            tenant_id INTEGER NOT NULL,
            lease_id INTEGER,
            account_guid TEXT NOT NULL,
            account_name TEXT,
            booking_date TEXT NOT NULL,
            amount NUMERIC NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
        """
    )
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(gnucash_payments)").fetchall()}
    if "lease_id" not in columns:
        connection.execute("ALTER TABLE gnucash_payments ADD COLUMN lease_id INTEGER")


def _ensure_settlement_payment_assignment_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS settlement_runs (
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

        CREATE TABLE IF NOT EXISTS settlement_payment_assignments (
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

        CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_assignments_considered_split
        ON settlement_payment_assignments(split_guid)
        WHERE status = 'considered';
        """
    )


def _ensure_lease_gnucash_account_columns(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(leases)").fetchall()}
    for column in ("gnucash_nk_account_guid", "gnucash_nk_account_name"):
        if column not in columns:
            connection.execute(f"ALTER TABLE leases ADD COLUMN {column} TEXT")

    tenant_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(tenants)").fetchall()
    }
    if {"gnucash_nk_account_guid", "gnucash_nk_account_name"} <= tenant_columns:
        legacy_links = connection.execute(
            """
            SELECT id, gnucash_nk_account_guid, gnucash_nk_account_name
            FROM tenants
            WHERE COALESCE(gnucash_nk_account_guid, '') != ''
            """
        ).fetchall()
        for tenant in legacy_links:
            linked_lease = connection.execute(
                "SELECT id FROM leases WHERE gnucash_nk_account_guid = ?",
                (tenant["gnucash_nk_account_guid"],),
            ).fetchone()
            if linked_lease is None:
                linked_lease = connection.execute(
                    """
                    SELECT l.id
                    FROM leases l
                    WHERE l.tenant_id = ?
                      AND COALESCE(l.gnucash_nk_account_guid, '') = ''
                    ORDER BY
                        EXISTS (
                            SELECT 1 FROM gnucash_payments gp WHERE gp.lease_id = l.id
                        ) DESC,
                        l.start_date DESC,
                        l.id DESC
                    LIMIT 1
                    """,
                    (tenant["id"],),
                ).fetchone()
                if linked_lease is not None:
                    connection.execute(
                        """
                        UPDATE leases
                        SET gnucash_nk_account_guid = ?, gnucash_nk_account_name = ?
                        WHERE id = ?
                        """,
                        (
                            tenant["gnucash_nk_account_guid"],
                            tenant["gnucash_nk_account_name"],
                            linked_lease["id"],
                        ),
                    )
            if linked_lease is not None:
                connection.execute(
                    """
                    UPDATE tenants
                    SET gnucash_nk_account_guid = NULL, gnucash_nk_account_name = NULL
                    WHERE id = ?
                    """,
                    (tenant["id"],),
                )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_leases_gnucash_nk_account_guid
        ON leases(gnucash_nk_account_guid)
        WHERE gnucash_nk_account_guid IS NOT NULL AND gnucash_nk_account_guid != ''
        """
    )


def _ensure_expense_item_legacy_columns(connection: sqlite3.Connection) -> None:
    expense_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(expense_items)").fetchall()
    }
    if "charge_type" not in expense_columns:
        connection.execute(
            "ALTER TABLE expense_items ADD COLUMN charge_type TEXT NOT NULL DEFAULT 'one_time'"
        )
    if "consumption_unit" not in expense_columns:
        connection.execute("ALTER TABLE expense_items ADD COLUMN consumption_unit TEXT")
    if "consumption_value" not in expense_columns:
        connection.execute("ALTER TABLE expense_items ADD COLUMN consumption_value NUMERIC")
    if "recurrence" not in expense_columns:
        connection.execute(
            "ALTER TABLE expense_items ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'one_time'"
        )
    if "interval_name" not in expense_columns:
        connection.execute("ALTER TABLE expense_items ADD COLUMN interval_name TEXT")
    if "meter_id" not in expense_columns:
        connection.execute("ALTER TABLE expense_items ADD COLUMN meter_id INTEGER")
    if "conversion_factor" not in expense_columns:
        connection.execute(
            "ALTER TABLE expense_items ADD COLUMN conversion_factor NUMERIC NOT NULL DEFAULT 1"
        )


def _ensure_leases_support_room_targets(connection: sqlite3.Connection) -> None:
    lease_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(leases)").fetchall()
    }
    if "room_id" not in lease_columns:
        connection.execute("ALTER TABLE leases ADD COLUMN room_id INTEGER")


def _ensure_expense_items_support_categories(connection: sqlite3.Connection) -> None:
    expense_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(expense_items)").fetchall()
    }
    if "expense_category" not in expense_columns:
        connection.execute(
            "ALTER TABLE expense_items ADD COLUMN expense_category TEXT NOT NULL DEFAULT ''"
        )
    if "beneficiary_name" not in expense_columns:
        connection.execute(
            "ALTER TABLE expense_items ADD COLUMN beneficiary_name TEXT NOT NULL DEFAULT 'Nicht gepflegt'"
        )
    connection.execute(
        """
        UPDATE expense_items
        SET expense_category = label
        WHERE COALESCE(expense_category, '') = ''
        """
    )
    connection.execute(
        """
        UPDATE expense_items
        SET beneficiary_name = 'Nicht gepflegt'
        WHERE COALESCE(beneficiary_name, '') = ''
        """
    )


def _ensure_expense_items_support_conversion_factor(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE expense_items
        SET conversion_factor = 1
        WHERE conversion_factor IS NULL
        """
    )


def _ensure_expense_items_support_object_targets(connection: sqlite3.Connection) -> None:
    expense_columns = {
        row["name"]: row for row in connection.execute("PRAGMA table_info(expense_items)").fetchall()
    }
    if {"object_type", "object_id", "booking_date"}.issubset(expense_columns):
        return

    connection.executescript(
        """
        ALTER TABLE expense_items RENAME TO expense_items_legacy;
        CREATE TABLE expense_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            object_type TEXT NOT NULL DEFAULT 'property',
            object_id INTEGER NOT NULL,
            expense_category TEXT NOT NULL DEFAULT '',
            beneficiary_name TEXT NOT NULL DEFAULT 'Nicht gepflegt',
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
        INSERT INTO expense_items (
            id, property_id, object_type, object_id, label, amount, allocation_method,
            charge_type, recurrence, interval_name, meter_id, consumption_unit, consumption_value,
            conversion_factor, booking_date, period_start, period_end, is_archived, archived_at
        )
        SELECT
            id,
            property_id,
            'property',
            property_id,
            label,
            amount,
            allocation_method,
            COALESCE(charge_type, 'one_time'),
            COALESCE(
                recurrence,
                CASE
                    WHEN COALESCE(charge_type, 'one_time') IN ('monthly', 'yearly') THEN 'recurring'
                    ELSE 'one_time'
                END
            ),
            interval_name,
            NULL,
            consumption_unit,
            consumption_value,
            1,
            CASE
                WHEN COALESCE(charge_type, 'one_time') = 'one_time' THEN period_start
                ELSE NULL
            END,
            period_start,
            period_end,
            COALESCE(is_archived, 0),
            archived_at
        FROM expense_items_legacy;
        DROP TABLE expense_items_legacy;
        """
    )


def _ensure_buildings_table_supports_standalone(connection: sqlite3.Connection) -> None:
    building_columns = {
        row["name"]: row for row in connection.execute("PRAGMA table_info(buildings)").fetchall()
    }
    property_column = building_columns.get("property_id")
    if not property_column or property_column["notnull"] == 0:
        return

    connection.executescript(
        """
        ALTER TABLE buildings RENAME TO buildings_legacy;
        CREATE TABLE buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            name TEXT NOT NULL,
            year_built INTEGER,
            street TEXT,
            city TEXT,
            postal_code TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            FOREIGN KEY (property_id) REFERENCES properties(id)
        );
        INSERT INTO buildings (id, property_id, name, year_built)
        SELECT id, property_id, name, year_built
        FROM buildings_legacy;
        DROP TABLE buildings_legacy;
        """
    )


def _ensure_units_table_supports_standalone(connection: sqlite3.Connection) -> None:
    unit_columns = {
        row["name"]: row for row in connection.execute("PRAGMA table_info(units)").fetchall()
    }
    building_column = unit_columns.get("building_id")
    if not building_column or building_column["notnull"] == 0:
        return

    connection.executescript(
        """
        ALTER TABLE units RENAME TO units_legacy;
        CREATE TABLE units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER,
            label TEXT NOT NULL,
            area_sqm NUMERIC NOT NULL,
            room_count INTEGER NOT NULL,
            street TEXT,
            city TEXT,
            postal_code TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings(id)
        );
        INSERT INTO units (id, building_id, label, area_sqm, room_count)
        SELECT id, building_id, label, area_sqm, room_count
        FROM units_legacy;
        DROP TABLE units_legacy;
        """
    )


def _ensure_rooms_table_exists(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "rooms" in existing_tables:
        return

    connection.execute(
        """
        CREATE TABLE rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            area_sqm NUMERIC,
            area_share_percent NUMERIC,
            is_archived INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            FOREIGN KEY (unit_id) REFERENCES units(id)
        )
        """
    )


def _ensure_rooms_have_area_sqm(connection: sqlite3.Connection) -> None:
    room_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()
    }
    if "area_sqm" not in room_columns:
        connection.execute("ALTER TABLE rooms ADD COLUMN area_sqm NUMERIC")


def _ensure_rooms_have_area_share_percent(connection: sqlite3.Connection) -> None:
    room_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()
    }
    if "area_share_percent" not in room_columns:
        connection.execute("ALTER TABLE rooms ADD COLUMN area_share_percent NUMERIC")


def _ensure_paperless_settings_table(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "paperless_settings" in existing_tables:
        return

    connection.execute(
        """
        CREATE TABLE paperless_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_url TEXT NOT NULL,
            api_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _ensure_expense_documents_table(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "expense_documents" in existing_tables:
        return

    connection.execute(
        """
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
        )
        """
    )


def _ensure_tenant_documents_table(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "tenant_documents" in existing_tables:
        return

    connection.execute(
        """
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
        )
        """
    )


def _ensure_lease_documents_table(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "lease_documents" in existing_tables:
        return

    connection.execute(
        """
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
        )
        """
    )


def _ensure_application_settings_table(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "application_settings" not in existing_tables:
        connection.execute(
            """
            CREATE TABLE application_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_delete_actions INTEGER NOT NULL DEFAULT 1,
                sender_name TEXT NOT NULL DEFAULT '',
                sender_street TEXT NOT NULL DEFAULT '',
                sender_city TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        return

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(application_settings)").fetchall()
    }
    for column in ("sender_name", "sender_street", "sender_city"):
        if column not in columns:
            connection.execute(
                f"ALTER TABLE application_settings ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
            )


def _ensure_buildings_have_addresses(connection: sqlite3.Connection) -> None:
    building_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(buildings)").fetchall()
    }
    if "street" not in building_columns:
        connection.execute("ALTER TABLE buildings ADD COLUMN street TEXT")
    if "city" not in building_columns:
        connection.execute("ALTER TABLE buildings ADD COLUMN city TEXT")
    if "postal_code" not in building_columns:
        connection.execute("ALTER TABLE buildings ADD COLUMN postal_code TEXT")

    connection.execute(
        """
        UPDATE buildings
        SET street = COALESCE(street, (SELECT street FROM properties WHERE id = buildings.property_id)),
            city = COALESCE(city, (SELECT city FROM properties WHERE id = buildings.property_id)),
            postal_code = COALESCE(postal_code, (SELECT postal_code FROM properties WHERE id = buildings.property_id))
        WHERE street IS NULL OR city IS NULL OR postal_code IS NULL
        """
    )


def _ensure_units_have_addresses(connection: sqlite3.Connection) -> None:
    unit_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(units)").fetchall()
    }
    if "street" not in unit_columns:
        connection.execute("ALTER TABLE units ADD COLUMN street TEXT")
    if "city" not in unit_columns:
        connection.execute("ALTER TABLE units ADD COLUMN city TEXT")
    if "postal_code" not in unit_columns:
        connection.execute("ALTER TABLE units ADD COLUMN postal_code TEXT")

    connection.execute(
        """
        UPDATE units
        SET street = COALESCE(
                street,
                (SELECT b.street FROM buildings b WHERE b.id = units.building_id),
                (
                    SELECT p.street
                    FROM buildings b
                    JOIN properties p ON p.id = b.property_id
                    WHERE b.id = units.building_id
                )
            ),
            city = COALESCE(
                city,
                (SELECT b.city FROM buildings b WHERE b.id = units.building_id),
                (
                    SELECT p.city
                    FROM buildings b
                    JOIN properties p ON p.id = b.property_id
                    WHERE b.id = units.building_id
                )
            ),
            postal_code = COALESCE(
                postal_code,
                (SELECT b.postal_code FROM buildings b WHERE b.id = units.building_id),
                (
                    SELECT p.postal_code
                    FROM buildings b
                    JOIN properties p ON p.id = b.property_id
                    WHERE b.id = units.building_id
                )
            )
        WHERE street IS NULL OR city IS NULL OR postal_code IS NULL
        """
    )


def _ensure_object_archive_columns(connection: sqlite3.Connection) -> None:
    for table_name in ("properties", "buildings", "units", "rooms", "meters", "expense_items"):
        columns = {
            row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if "is_archived" not in columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0"
            )
        if "archived_at" not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN archived_at TEXT")


def seed_demo_data(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
        ("EasyPrent Demo Verwaltung", "property_management"),
    )
    organization_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    connection.execute(
        "INSERT INTO users (full_name, email) VALUES (?, ?)",
        ("Maria Becker", "maria@example.com"),
    )
    user_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO memberships (organization_id, user_id, role) VALUES (?, ?, ?)",
        (organization_id, user_id, "manager"),
    )

    connection.execute(
        """
        INSERT INTO properties (organization_id, name, street, city, postal_code)
        VALUES (?, ?, ?, ?, ?)
        """,
        (organization_id, "Wohnpark Lindenhof", "Lindenweg 12", "Berlin", "10439"),
    )
    property_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    connection.execute(
        """
        INSERT INTO buildings (property_id, name, year_built, street, city, postal_code)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (property_id, "Haus A", 1998, "Lindenweg 12", "Berlin", "10439"),
    )
    building_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    units = [
        ("A-01", Decimal("74.5"), 3, "Lindenweg 12", "Berlin", "10439"),
        ("A-02", Decimal("61.0"), 2, "Lindenweg 12", "Berlin", "10439"),
        ("A-03", Decimal("83.0"), 4, "Lindenweg 12", "Berlin", "10439"),
    ]
    unit_ids = []
    for label, area_sqm, room_count, street, city, postal_code in units:
        connection.execute(
            """
            INSERT INTO units (building_id, label, area_sqm, room_count, street, city, postal_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (building_id, label, str(area_sqm), room_count, street, city, postal_code),
        )
        unit_ids.append(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    tenants = [
        ("Anna Schulz", "anna@example.com", "030-111111"),
        ("Tim Wagner", "tim@example.com", "030-222222"),
    ]
    tenant_ids = []
    for tenant in tenants:
        connection.execute(
            "INSERT INTO tenants (full_name, email, phone) VALUES (?, ?, ?)",
            tenant,
        )
        tenant_ids.append(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    leases = [
        (unit_ids[0], tenant_ids[0], "1200.00", "230.00", 2, "2025-01-01", None, "active"),
        (unit_ids[1], tenant_ids[1], "980.00", "190.00", 1, "2025-04-01", None, "active"),
    ]
    connection.executemany(
        """
        INSERT INTO leases (
            unit_id, tenant_id, rent_cold, additional_charges_advance, occupant_count,
            start_date, end_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        leases,
    )

    expenses = [
        (
            property_id,
            "property",
            property_id,
            "Heizung",
            "Stadtwerke Berlin",
            "Heizung",
            "4200.00",
            "area",
            "one_time",
            "one_time",
            None,
            None,
            None,
            None,
            "1",
            "2025-12-31",
            "2025-12-31",
            "2025-12-31",
        ),
        (
            property_id,
            "property",
            property_id,
            "Wasser",
            "Berliner Wasserbetriebe",
            "Wasser",
            "1600.00",
            "occupants",
            "consumption",
            "one_time",
            None,
            None,
            "m3",
            "210.0",
            "1",
            None,
            "2025-01-01",
            "2025-12-31",
        ),
        (
            property_id,
            "property",
            property_id,
            "Hausreinigung",
            "Firma Sauber GmbH",
            "Treppenhausreinigung",
            "75.00",
            "unit_count",
            "monthly",
            "recurring",
            "monthly",
            None,
            None,
            None,
            "1",
            None,
            "2025-01-01",
            "2025-12-31",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO expense_items (
            property_id, object_type, object_id, expense_category, beneficiary_name, label, amount,
            allocation_method, charge_type, recurrence, interval_name, meter_id, consumption_unit,
            consumption_value, conversion_factor, booking_date, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        expenses,
    )

    assets = [
        (property_id, "Gebäudekörper Haus A", "720000.00", "82.0", 40, "2025-01-01", "linear"),
        (property_id, "Dachanierung 2025", "68000.00", "100.0", 20, "2025-07-01", "linear"),
    ]
    connection.executemany(
        """
        INSERT INTO depreciation_assets (
            property_id, asset_name, acquisition_cost, building_share_percent,
            useful_life_years, placed_in_service, method
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        assets,
    )
