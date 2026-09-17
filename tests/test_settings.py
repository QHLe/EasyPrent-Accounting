from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from easyprent_accounting.db import get_connection, initialize_database
from easyprent_accounting.schema_v1 import apply_schema_v1
from easyprent_accounting.settings import (
    export_application_data,
    import_application_data,
)
from tests.legacy_fixture import create_legacy_fixture
from tests.support import in_memory_database


def _version_one_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    apply_schema_v1(connection)
    connection.execute(
        "INSERT INTO organizations (id, name, organization_type) VALUES (1, 'Test', 'owner')"
    )
    connection.execute(
        """
        INSERT INTO properties (
            id, organization_id, name, street, city, postal_code
        ) VALUES (1, 1, 'Haus', 'Testweg 1', 'Berlin', '10115')
        """
    )
    connection.execute(
        """
        INSERT INTO meters (
            id, object_type, object_id, label, meter_type, unit
        ) VALUES (1, 'property', 1, 'Strom', 'electricity', 'kWh')
        """
    )
    connection.execute(
        """
        INSERT INTO expense_items (
            id, object_type, object_id, expense_category, beneficiary_name,
            label, amount, allocation_method, charge_type, conversion_factor,
            period_start, period_end
        ) VALUES (
            1, 'property', 1, 'energy', 'Versorger', 'Strom', 120,
            'area', 'monthly', 1, '2025-01-01', '2025-12-31'
        )
        """
    )
    connection.commit()
    return connection


class ApplicationExportContractTests(unittest.TestCase):
    def test_export_uses_one_snapshot_when_another_connection_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "application.sqlite"
            initialize_database(path)
            reader = get_connection(path)
            writer = get_connection(path)
            try:
                reader.execute("PRAGMA journal_mode = WAL")
                writer.execute(
                    "INSERT INTO organizations (id, name, organization_type) "
                    "VALUES (1, 'Original', 'owner')"
                )
                writer.commit()
                wrote_during_export = False

                def write_before_users(sql: str) -> None:
                    nonlocal wrote_during_export
                    if wrote_during_export or not sql.startswith("SELECT * FROM users"):
                        return
                    wrote_during_export = True
                    writer.execute(
                        "INSERT INTO organizations (id, name, organization_type) "
                        "VALUES (2, 'Concurrent', 'owner')"
                    )
                    writer.execute(
                        "INSERT INTO users (id, full_name, email) "
                        "VALUES (2, 'Concurrent', 'concurrent@example.invalid')"
                    )
                    writer.execute(
                        "INSERT INTO memberships (organization_id, user_id, role) "
                        "VALUES (2, 2, 'manager')"
                    )
                    writer.commit()

                reader.set_trace_callback(write_before_users)
                exported = export_application_data(reader)
                self.assertTrue(wrote_during_export)
                self.assertEqual(
                    [row["id"] for row in exported["tables"]["organizations"]], [1]
                )
                self.assertEqual(exported["tables"]["users"], [])
                self.assertEqual(exported["tables"]["memberships"], [])
                self.assertFalse(reader.in_transaction)
            finally:
                reader.close()
                writer.close()

    def test_legacy_tenant_account_is_preserved_on_v2_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite"
            create_legacy_fixture(path)
            connection = get_connection(path)
            try:
                exported = export_application_data(connection)
                tenant = next(
                    row for row in exported["tables"]["tenants"] if row["id"] == 10
                )
                lease = next(
                    row for row in exported["tables"]["leases"] if row["id"] == 10
                )
                self.assertNotIn("gnucash_nk_account_guid", tenant)
                self.assertEqual(lease["gnucash_nk_account_guid"], "nk-legacy-10")
                payment = next(
                    row
                    for row in exported["tables"]["gnucash_payments"]
                    if row["split_guid"] == "split-synthetic-10"
                )
                self.assertEqual(payment["lease_id"], 10)

                import_application_data(connection, exported)
                restored = connection.execute(
                    "SELECT gnucash_nk_account_guid FROM leases WHERE id = 10"
                ).fetchone()[0]
                self.assertEqual(restored, "nk-legacy-10")
                self.assertEqual(
                    connection.execute(
                        "SELECT lease_id FROM gnucash_payments "
                        "WHERE split_guid = 'split-synthetic-10'"
                    ).fetchone()[0],
                    10,
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(), []
                )
            finally:
                connection.close()

    def test_version_two_has_the_same_row_shape_on_legacy_and_v1_schemas(self) -> None:
        legacy = in_memory_database()
        version_one = _version_one_database()
        try:
            legacy.execute(
                """
                INSERT INTO meters (
                    property_id, object_type, object_id, label, meter_type, unit
                ) VALUES (1, 'property', 1, 'Strom', 'electricity', 'kWh')
                """
            )
            legacy.commit()

            legacy_export = export_application_data(legacy)
            version_one_export = export_application_data(version_one)

            self.assertEqual(legacy_export["format_version"], 2)
            self.assertEqual(version_one_export["format_version"], 2)
            expected_columns = {
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
            }
            for table_name, columns in expected_columns.items():
                with self.subTest(table=table_name):
                    legacy_columns = tuple(
                        legacy_export["tables"][table_name][0]
                    )
                    version_one_columns = tuple(
                        version_one_export["tables"][table_name][0]
                    )
                    self.assertEqual(legacy_columns, columns)
                    self.assertEqual(version_one_columns, legacy_columns)
        finally:
            legacy.close()
            version_one.close()

    def test_version_two_round_trips_through_schema_v1(self) -> None:
        connection = _version_one_database()
        try:
            payload = export_application_data(connection)

            result = import_application_data(connection, payload)

            self.assertEqual(result["format_version"], 2)
            self.assertEqual(
                connection.execute("SELECT label FROM expense_items").fetchone()[0],
                "Strom",
            )
        finally:
            connection.close()

    def test_legacy_round_trip_derives_columns_removed_from_v1(self) -> None:
        connection = in_memory_database()
        try:
            payload = export_application_data(connection)

            import_application_data(connection, payload)

            monthly_expense = connection.execute(
                """
                SELECT property_id, recurrence, interval_name
                FROM expense_items
                WHERE charge_type = 'monthly'
                """
            ).fetchone()
            self.assertEqual(dict(monthly_expense), {
                "property_id": 1,
                "recurrence": "recurring",
                "interval_name": "monthly",
            })
        finally:
            connection.close()


class ApplicationImportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.payload = export_application_data(self.connection)
        self.original_organizations = [
            tuple(row)
            for row in self.connection.execute(
                "SELECT id, name, organization_type FROM organizations ORDER BY id"
            )
        ]

    def tearDown(self) -> None:
        self.connection.close()

    def assert_database_is_unchanged(self) -> None:
        organizations = [
            tuple(row)
            for row in self.connection.execute(
                "SELECT id, name, organization_type FROM organizations ORDER BY id"
            )
        ]
        self.assertEqual(organizations, self.original_organizations)
        self.assertFalse(self.connection.in_transaction)

    def test_requires_an_explicit_format_version_before_mutating_data(self) -> None:
        payload = deepcopy(self.payload)
        del payload["format_version"]

        with self.assertRaisesRegex(ValueError, "format_version is required"):
            import_application_data(self.connection, payload)

        self.assert_database_is_unchanged()

    def test_rejects_an_incomplete_table_set_before_mutating_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "tables has invalid entries"):
            import_application_data(
                self.connection,
                {"format_version": 2, "tables": {}},
            )

        self.assert_database_is_unchanged()

    def test_rejects_an_incomplete_row_before_mutating_data(self) -> None:
        payload = deepcopy(self.payload)
        del payload["tables"]["organizations"][0]["name"]

        with self.assertRaisesRegex(
            ValueError,
            r"tables\.organizations\[0\] has invalid columns: missing name",
        ):
            import_application_data(self.connection, payload)

        self.assert_database_is_unchanged()

    def test_version_two_rejects_a_payment_without_lease_before_mutating_data(self) -> None:
        payload = deepcopy(self.payload)
        payload["tables"]["gnucash_payments"].append({
            "id": 99,
            "split_guid": "unassigned-split",
            "transaction_guid": "unassigned-transaction",
            "tenant_id": 1,
            "lease_id": None,
            "account_guid": "unassigned-account",
            "account_name": None,
            "booking_date": "2025-01-01",
            "amount": 10,
            "description": "Unassigned payment",
            "imported_at": "2025-01-02T00:00:00+00:00",
        })
        payload["row_count"] += 1

        with self.assertRaisesRegex(ValueError, "lease_id is required"):
            import_application_data(self.connection, payload)

        self.assert_database_is_unchanged()

    def test_rejects_non_linear_depreciation_without_mutating_data(self) -> None:
        payload = deepcopy(self.payload)
        payload["tables"]["depreciation_assets"][0]["method"] = "declining"
        original_assets = [
            tuple(row)
            for row in self.connection.execute(
                "SELECT id, asset_name, method FROM depreciation_assets ORDER BY id"
            )
        ]

        with self.assertRaisesRegex(
            ValueError, r"tables\.depreciation_assets\[0\]\.method must be linear"
        ):
            import_application_data(self.connection, payload)

        self.assert_database_is_unchanged()
        self.assertEqual(
            [
                tuple(row)
                for row in self.connection.execute(
                    "SELECT id, asset_name, method FROM depreciation_assets ORDER BY id"
                )
            ],
            original_assets,
        )

    def test_rejects_active_caller_transaction_without_rolling_it_back(self) -> None:
        self.connection.execute(
            "UPDATE organizations SET name = 'Pending' WHERE id = 1"
        )
        with self.assertRaisesRegex(ValueError, "active transaction"):
            import_application_data(self.connection, self.payload)

        self.assertTrue(self.connection.in_transaction)
        self.assertEqual(
            self.connection.execute(
                "SELECT name FROM organizations WHERE id = 1"
            ).fetchone()[0],
            "Pending",
        )
        self.connection.rollback()

    def test_accepts_original_seventeen_table_format_one_backup(self) -> None:
        original_tables = (
            "organizations", "users", "memberships", "properties", "buildings",
            "units", "rooms", "meters", "meter_readings", "tenants", "leases",
            "expense_items", "application_settings", "expense_documents",
            "tenant_documents", "lease_documents", "depreciation_assets",
        )
        payload = {
            "format_version": 1,
            "table_count": 17,
            "row_count": 1,
            "tables": {name: [] for name in original_tables},
        }
        payload["tables"]["organizations"] = [
            {"id": 7, "name": "Altbestand", "organization_type": "owner"}
        ]

        result = import_application_data(self.connection, payload)

        self.assertEqual(result["format_version"], 1)
        self.assertEqual(
            self.connection.execute(
                "SELECT id, name FROM organizations"
            ).fetchall()[0]["name"],
            "Altbestand",
        )

    def test_rejects_unmappable_legacy_account_before_mutating_data(self) -> None:
        payload = deepcopy(self.payload)
        payload["format_version"] = 1
        payload["tables"]["tenants"][0][
            "gnucash_nk_account_guid"
        ] = "orphan-account"
        payload["tables"]["tenants"][0][
            "gnucash_nk_account_name"
        ] = "Orphan"
        payload["tables"]["leases"] = []
        payload["row_count"] = sum(len(rows) for rows in payload["tables"].values())
        for row in payload["tables"]["meters"]:
            row["property_id"] = None
        for row in payload["tables"]["expense_items"]:
            row.update(property_id=None, recurrence="one_time", interval_name=None)

        with self.assertRaisesRegex(ValueError, "cannot be mapped"):
            import_application_data(self.connection, payload)

        self.assert_database_is_unchanged()


if __name__ == "__main__":
    unittest.main()
