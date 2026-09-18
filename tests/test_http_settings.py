"""Settings and backup routes over the real settings module."""

from __future__ import annotations

import unittest
from datetime import date

from easyprent_accounting.integrations.gnucash import GnuCashAccount
from easyprent_accounting.integrations.gnucash import GnuCashPayment
from tests.support import asgi_test_client, temporary_database


class FakeGnuCashReader:
    def list_accounts(self, settings: dict) -> list[GnuCashAccount]:
        return [GnuCashAccount("account-1", "Advance", "Tenant:Advance", None)]

    def list_payments(
        self, settings: dict, account_guids: set[str], period_start: date, period_end: date
    ) -> list[GnuCashPayment]:
        return []


class SettingsHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database, gnucash_reader=FakeGnuCashReader())

    def test_application_and_external_settings_are_masked_and_persisted(self) -> None:
        application = self.client.put("/api/v1/settings/application", json={
            "show_delete_actions": False,
            "sender_name": "House Management", "sender_street": "Main 1",
            "sender_city": "Berlin",
        })
        self.assertEqual(application.status_code, 200, application.text)
        self.assertFalse(self.client.get("/api/v1/settings/application").json()["show_delete_actions"])

        paperless = self.client.put("/api/v1/settings/paperless", json={
            "base_url": "https://paperless.example.test", "api_token": "secret-token",
        })
        self.assertEqual(paperless.status_code, 200, paperless.text)
        self.assertTrue(paperless.json()["token_present"])
        self.assertNotIn("secret-token", paperless.text)

        gnucash = self.client.put("/api/v1/settings/gnucash", json={
            "host": "localhost", "port": 5432, "database": "book",
            "username": "reader", "password": "secret-password", "sslmode": "require",
        })
        self.assertEqual(gnucash.status_code, 200, gnucash.text)
        self.assertTrue(gnucash.json()["password_present"])
        self.assertNotIn("secret-password", gnucash.text)
        accounts = self.client.get("/api/v1/settings/gnucash/accounts")
        self.assertEqual(accounts.status_code, 200, accounts.text)
        self.assertEqual(accounts.json()[0]["guid"], "account-1")

    def test_export_and_import_restore_versioned_application_data(self) -> None:
        exported = self.client.get("/api/v1/settings/export")
        self.assertEqual(exported.status_code, 200, exported.text)
        payload = exported.json()
        self.assertEqual(payload["format_version"], 2)
        self.assertIn("tenants", payload["tables"])
        self.assertNotIn("paperless_settings", payload["tables"])
        created = self.client.post("/api/v1/tenants", json={"full_name": "Temporary Tenant"})
        self.assertEqual(created.status_code, 201, created.text)
        imported = self.client.post("/api/v1/settings/import", json=payload)
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["row_count"], payload["row_count"])
        names = [tenant["full_name"] for tenant in self.client.get("/api/v1/tenancy").json()["tenants"]]
        self.assertNotIn("Temporary Tenant", names)

    def test_invalid_import_rolls_back_without_erasing_data(self) -> None:
        original = self.client.get("/api/v1/tenancy").json()["tenants"]
        imported = self.client.post("/api/v1/settings/import", json={
            "format_version": 2, "tables": {},
        })
        self.assertEqual(imported.status_code, 422)
        self.assertEqual(imported.json()["error"]["code"], "invalid_value")
        self.assertEqual(self.client.get("/api/v1/tenancy").json()["tenants"], original)


if __name__ == "__main__":
    unittest.main()
