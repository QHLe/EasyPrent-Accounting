from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from easyprent_accounting.legacy_schema import (
    SUPPORTED_LEGACY_FINGERPRINTS,
    schema_fingerprint,
)
from easyprent_accounting.schema_v1 import (
    EXPECTED_SCHEMA_FINGERPRINT,
    apply_schema_v1,
)
from easyprent_accounting.schema_runner import Migration, run_migrations
from tests.legacy_fixture import create_legacy_fixture


class FrozenLegacySchemaTests(unittest.TestCase):
    def test_fingerprint_handles_quoted_sqlite_object_names(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute('CREATE TABLE "odd name" (id INTEGER PRIMARY KEY)')
            self.assertEqual(len(schema_fingerprint(connection)), 64)
        finally:
            connection.close()

    def test_fingerprint_preserves_whitespace_inside_sql_string_literals(self) -> None:
        first = sqlite3.connect(":memory:")
        second = sqlite3.connect(":memory:")
        try:
            first.execute("CREATE TABLE sample (value TEXT CHECK (value != 'a  b'))")
            second.execute("CREATE TABLE sample (value TEXT CHECK (value != 'a b'))")
            self.assertNotEqual(schema_fingerprint(first), schema_fingerprint(second))
        finally:
            first.close()
            second.close()

    def test_synthetic_legacy_database_matches_supported_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            create_legacy_fixture(path)
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                fingerprint = schema_fingerprint(connection)
            finally:
                connection.close()

        self.assertIn(fingerprint, SUPPORTED_LEGACY_FINGERPRINTS)


class VersionOneSchemaTests(unittest.TestCase):
    def test_runner_created_version_one_schema_matches_frozen_fingerprint(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            run_migrations(connection, [Migration(1, "initial", apply_schema_v1)])
            self.assertEqual(schema_fingerprint(connection), EXPECTED_SCHEMA_FINGERPRINT)
        finally:
            connection.close()

    def test_schema_creation_is_transactional_and_excludes_legacy_columns(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            apply_schema_v1(connection)
            self.assertTrue(connection.in_transaction)

            tenant_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(tenants)")
            }
            expense_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(expense_items)")
            }
            payment_columns = {
                row[1]: row for row in connection.execute("PRAGMA table_info(gnucash_payments)")
            }
            self.assertNotIn("gnucash_nk_account_guid", tenant_columns)
            self.assertNotIn("recurrence", expense_columns)
            self.assertNotIn("interval_name", expense_columns)
            self.assertEqual(payment_columns["lease_id"][3], 1)

            connection.rollback()
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tenants'"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()
