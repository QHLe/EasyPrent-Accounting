from __future__ import annotations

import unittest

from tests.support import temporary_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initialize_database_creates_an_empty_database(self) -> None:
        with temporary_database() as database:
            connection = database.connect()
            try:
                organization_count = connection.execute(
                    "SELECT COUNT(*) FROM organizations"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(organization_count, 0)

    def test_initialize_database_prepares_settlement_payment_assignment_storage(self) -> None:
        with temporary_database() as database:
            connection = database.connect()
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                assignment_columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(settlement_payment_assignments)"
                    ).fetchall()
                }
            finally:
                connection.close()

        self.assertIn("settlement_runs", tables)
        self.assertIn("settlement_payment_assignments", tables)
        self.assertTrue(
            {
                "settlement_id",
                "split_guid",
                "lease_id",
                "status",
                "reason",
                "assigned_amount",
            }
            <= assignment_columns
        )

    def test_initialize_database_adds_area_share_percent_to_existing_rooms(self) -> None:
        with temporary_database(initialized=False) as database:
            connection = database.connect()
            try:
                connection.execute(
                    "CREATE TABLE rooms (id INTEGER PRIMARY KEY, unit_id INTEGER, label TEXT, area_sqm NUMERIC)"
                )
                connection.commit()
            finally:
                connection.close()

            database.initialize()
            connection = database.connect()
            try:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()
                }
            finally:
                connection.close()

        self.assertIn("area_share_percent", columns)

    def test_migrates_legacy_tenant_gnucash_account_to_lease(self) -> None:
        with temporary_database(initialized=False) as database:
            connection = database.connect()
            connection.executescript(
                """
                CREATE TABLE tenants (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    gnucash_nk_account_guid TEXT,
                    gnucash_nk_account_name TEXT
                );
                CREATE TABLE leases (
                    id INTEGER PRIMARY KEY,
                    unit_id INTEGER NOT NULL,
                    tenant_id INTEGER NOT NULL,
                    rent_cold NUMERIC NOT NULL,
                    additional_charges_advance NUMERIC NOT NULL,
                    occupant_count INTEGER NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT NOT NULL
                );
                INSERT INTO tenants (
                    id, full_name, gnucash_nk_account_guid, gnucash_nk_account_name
                ) VALUES (1, 'Testmieter', 'legacy-nk-account', 'Alt:Nebenkosten');
                INSERT INTO leases (
                    id, unit_id, tenant_id, rent_cold, additional_charges_advance,
                    occupant_count, start_date, end_date, status
                ) VALUES (1, 1, 1, 1000, 200, 1, '2025-01-01', NULL, 'active');
                """
            )
            connection.commit()
            connection.close()

            database.initialize()
            connection = database.connect(rows=True)
            try:
                lease = connection.execute(
                    "SELECT gnucash_nk_account_guid, gnucash_nk_account_name FROM leases WHERE id = 1"
                ).fetchone()
                tenant = connection.execute(
                    "SELECT gnucash_nk_account_guid, gnucash_nk_account_name FROM tenants WHERE id = 1"
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(lease["gnucash_nk_account_guid"], "legacy-nk-account")
        self.assertEqual(lease["gnucash_nk_account_name"], "Alt:Nebenkosten")
        self.assertIsNone(tenant["gnucash_nk_account_guid"])
        self.assertIsNone(tenant["gnucash_nk_account_name"])
