from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from src.easyprent_accounting.db import initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initialize_database_creates_an_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "easyprent_accounting.db")
            original_database_path = os.environ.get("EASYPRENT_DB_PATH")
            os.environ["EASYPRENT_DB_PATH"] = database_path
            try:
                initialize_database()
                connection = sqlite3.connect(database_path)
                try:
                    organization_count = connection.execute(
                        "SELECT COUNT(*) FROM organizations"
                    ).fetchone()[0]
                finally:
                    connection.close()
            finally:
                if original_database_path is None:
                    os.environ.pop("EASYPRENT_DB_PATH", None)
                else:
                    os.environ["EASYPRENT_DB_PATH"] = original_database_path

        self.assertEqual(organization_count, 0)

    def test_migrates_legacy_tenant_gnucash_account_to_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "easyprent_accounting.db")
            connection = sqlite3.connect(database_path)
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

            original_database_path = os.environ.get("EASYPRENT_DB_PATH")
            os.environ["EASYPRENT_DB_PATH"] = database_path
            try:
                initialize_database()
                connection = sqlite3.connect(database_path)
                connection.row_factory = sqlite3.Row
                try:
                    lease = connection.execute(
                        "SELECT gnucash_nk_account_guid, gnucash_nk_account_name FROM leases WHERE id = 1"
                    ).fetchone()
                    tenant = connection.execute(
                        "SELECT gnucash_nk_account_guid, gnucash_nk_account_name FROM tenants WHERE id = 1"
                    ).fetchone()
                finally:
                    connection.close()
            finally:
                if original_database_path is None:
                    os.environ.pop("EASYPRENT_DB_PATH", None)
                else:
                    os.environ["EASYPRENT_DB_PATH"] = original_database_path

        self.assertEqual(lease["gnucash_nk_account_guid"], "legacy-nk-account")
        self.assertEqual(lease["gnucash_nk_account_name"], "Alt:Nebenkosten")
        self.assertIsNone(tenant["gnucash_nk_account_guid"])
        self.assertIsNone(tenant["gnucash_nk_account_name"])
