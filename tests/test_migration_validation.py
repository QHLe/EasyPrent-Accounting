from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from easyprent_accounting.migration_validation import (
    MigrationValidationError,
    validate_migration,
)
from easyprent_accounting.legacy_mapping import map_legacy_data
from easyprent_accounting.schema_runner import Migration, run_migrations
from easyprent_accounting.schema_v1 import apply_schema_v1
from tests.legacy_fixture import create_legacy_fixture


class MigrationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source_path = Path(directory.name) / "legacy.db"
        create_legacy_fixture(source_path)
        self.source = sqlite3.connect(source_path)
        self.target = sqlite3.connect(Path(directory.name) / "target.db")
        self.addCleanup(self.source.close)
        self.addCleanup(self.target.close)
        self.source.execute("PRAGMA foreign_keys = ON")
        self.target.execute("PRAGMA foreign_keys = ON")
        run_migrations(self.target, [Migration(1, "schema-v1", apply_schema_v1)])
        map_legacy_data(self.source, self.target)

    def _seed_matching_expense(self) -> None:
        self.source.execute(
            "INSERT INTO expense_items "
            "(id, property_id, object_type, object_id, expense_category, beneficiary_name, "
            "label, amount, allocation_method, period_start, period_end) "
            "VALUES (70, 10, 'property', 10, 'Secret medical detail', 'Vendor', "
            "'Heating', 12.35, 'area', '2025-01-01', '2025-12-31')"
        )
        self.target.execute(
            "INSERT INTO expense_items "
            "(id, object_type, object_id, expense_category, beneficiary_name, "
            "label, amount, allocation_method, period_start, period_end) "
            "VALUES (70, 'property', 10, 'Secret medical detail', 'Vendor', "
            "'Heating', 12.35, 'area', '2025-01-01', '2025-12-31')"
        )
        self.source.commit()
        self.target.commit()

    def test_matching_migration_has_json_report_with_business_totals(self) -> None:
        self._seed_matching_expense()

        report = validate_migration(self.source, self.target)
        serialized = json.dumps(report)

        self.assertTrue(report["success"])
        self.assertEqual(report["schema_version"], {"source": 0, "target": 1, "expected": 1})
        self.assertTrue(report["schema_fingerprint"]["source_supported"])
        self.assertTrue(report["schema_fingerprint"]["target_match"])
        self.assertEqual(report["table_counts"]["expense_items"],
                         {"source": 7, "target": 7, "match": True})
        self.assertEqual(report["integrity_check"], {"source": ["ok"], "target": ["ok"]})
        expense_total = next(
            group for group in report["monetary_totals"]
            if group["family"] == "expenses" and group["year"] == "2025"
            and group["object_type"] == "property"
        )
        self.assertEqual((expense_total["year"], expense_total["source"],
                          expense_total["target"]), ("2025", "12.35", "12.35"))
        self.assertNotIn("Secret medical detail", serialized)

    def test_same_row_count_with_changed_money_fails_and_keeps_report(self) -> None:
        self._seed_matching_expense()
        self.target.execute("UPDATE expense_items SET amount = 12.36 WHERE id = 70")
        self.target.commit()

        with self.assertRaises(MigrationValidationError) as caught:
            validate_migration(self.source, self.target)

        report = caught.exception.report
        self.assertFalse(report["success"])
        self.assertEqual(report["table_counts"]["expense_items"]["match"], True)
        self.assertFalse(report["checksums"]["expense_items"]["match"])
        self.assertTrue(any(error["code"] == "monetary_total" for error in report["errors"]))
        json.dumps(report)

    def test_invalid_foreign_key_is_recorded_in_failed_report(self) -> None:
        self.target.execute("PRAGMA foreign_keys = OFF")
        self.target.execute("UPDATE expense_documents SET expense_id = 999 WHERE id = 10")
        self.target.commit()

        with self.assertRaises(MigrationValidationError) as caught:
            validate_migration(self.source, self.target)

        report = caught.exception.report
        self.assertEqual(report["foreign_key_check"]["target"][0]["table"],
                         "expense_documents")
        self.assertTrue(any(error["code"] == "foreign_key" for error in report["errors"]))
        self.assertNotIn("private.pdf", json.dumps(report))

    def test_changed_document_bytes_fail_checksum_without_exposing_contents(self) -> None:
        self.target.execute(
            "UPDATE expense_documents SET content_blob = ?, content_size = ? WHERE id = 10",
            (b"changed secret!", len(b"changed secret!")),
        )
        self.target.commit()

        with self.assertRaises(MigrationValidationError) as caught:
            validate_migration(self.source, self.target)

        report = caught.exception.report
        self.assertFalse(report["checksums"]["expense_documents"]["match"])
        serialized = json.dumps(report)
        self.assertNotIn("synthetic-password", serialized)
        self.assertNotIn("changed secret", serialized)
        self.assertNotIn("expense-local.pdf", serialized)

    def test_damaged_target_columns_fail_despite_version_ledger(self) -> None:
        self.target.execute("ALTER TABLE tenants DROP COLUMN alternate_city")
        self.target.commit()

        with self.assertRaises(MigrationValidationError) as caught:
            validate_migration(self.source, self.target)

        self.assertTrue(any(error["code"] == "target_columns"
                            for error in caught.exception.report["errors"]))

    def test_changed_payment_link_fails_even_when_money_and_counts_match(self) -> None:
        # Lease 20 belongs to the same tenant but the frozen source explicitly
        # links payment 20 to lease 30.
        self.target.execute("UPDATE gnucash_payments SET lease_id = 20 WHERE id = 20")
        self.target.commit()

        with self.assertRaises(MigrationValidationError) as caught:
            validate_migration(self.source, self.target)

        report = caught.exception.report
        self.assertTrue(report["checksums"]["gnucash_payments"]["match"])
        self.assertEqual(report["link_checks"]["errors"],
                         [{"code": "payment_lease_link", "payment_id": 20}])

    def test_unplanned_target_index_fails_schema_fingerprint(self) -> None:
        self.target.execute("CREATE INDEX unplanned_tenant_name ON tenants(full_name)")
        self.target.commit()

        with self.assertRaises(MigrationValidationError) as caught:
            validate_migration(self.source, self.target)

        report = caught.exception.report
        self.assertFalse(report["schema_fingerprint"]["target_match"])
        self.assertTrue(any(error["code"] == "target_schema_fingerprint"
                            for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
