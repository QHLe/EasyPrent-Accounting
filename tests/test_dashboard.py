"""Dashboard read-model: aggregate summary for the UI landing page."""

from __future__ import annotations

import unittest

from easyprent_accounting.dashboard import Dashboard
from tests.support import in_memory_database


class DashboardSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.dashboard = Dashboard(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_summary_returns_entity_counts_from_seeded_data(self) -> None:
        result = self.dashboard.summary()

        self.assertEqual(result["properties"], 1)
        self.assertEqual(result["buildings"], 1)
        self.assertEqual(result["units"], 3)
        self.assertEqual(result["rooms"], 0)
        self.assertEqual(result["meters"], 0)
        self.assertEqual(result["tenants"], 2)
        self.assertEqual(result["leases"], 2)
        self.assertEqual(result["expenses"], 3)
        self.assertEqual(result["depreciation_assets"], 2)

    def test_summary_includes_user_roles(self) -> None:
        result = self.dashboard.summary()

        self.assertIn("roles", result)
        roles = result["roles"]
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]["full_name"], "Maria Becker")
        self.assertEqual(roles[0]["role"], "manager")
        self.assertEqual(roles[0]["organization_name"], "EasyPrent Demo Verwaltung")

    def test_summary_does_not_include_full_entity_lists(self) -> None:
        """The dashboard summary returns counts, not the domain entity arrays."""
        result = self.dashboard.summary()

        for key in ("properties", "buildings", "units", "rooms",
                     "meters", "tenants", "leases", "expenses",
                     "depreciation_assets"):
            self.assertIsInstance(
                result[key], int,
                f"'{key}' should be an integer count, not a list",
            )

    def test_summary_on_empty_database(self) -> None:
        connection = in_memory_database(seeded=False)
        try:
            result = Dashboard(connection).summary()

            self.assertEqual(result["properties"], 0)
            self.assertEqual(result["buildings"], 0)
            self.assertEqual(result["units"], 0)
            self.assertEqual(result["tenants"], 0)
            self.assertEqual(result["expenses"], 0)
            self.assertEqual(result["roles"], [])
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
