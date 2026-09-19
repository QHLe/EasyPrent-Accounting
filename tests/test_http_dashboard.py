"""Dashboard HTTP use cases."""

from __future__ import annotations

import unittest

from tests.support import asgi_test_client, temporary_database


class DashboardHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def test_dashboard_summary(self) -> None:
        response = self.client.get("/api/v1/dashboard/summary")
        self.assertEqual(response.status_code, 200, response.text)
        
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("properties", data["summary"])
        self.assertIn("roles", data)
        self.assertTrue(len(data["roles"]) > 0)


if __name__ == "__main__":
    unittest.main()

