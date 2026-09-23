"""Critical journeys through the bundled frontend and production ASGI server."""

from __future__ import annotations

import json
import os
import sqlite3
import unittest
from unittest import mock

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ImportError:
    HAVE_PLAYWRIGHT = False

from easyprent_accounting.asset_registry import AssetRegistry
from easyprent_accounting.migration import migrate_database
from tests.legacy_fixture import create_legacy_fixture
from tests.support import running_server, temporary_database


@unittest.skipUnless(HAVE_PLAYWRIGHT, "playwright is required for browser smoke tests")
class BrowserSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(initialized=False))
        create_legacy_fixture(self.database.path)
        migrate_database(self.database.path, cutover=True)
        with self.database.connect(rows=True) as connection:
            AssetRegistry(connection).restore_unit(30)
            connection.commit()
        self.enterContext(mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(self.database.path)}))
        self.server = self.enterContext(running_server("127.0.0.1", 0))
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def _open_page(self, playwright):
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        page.set_default_timeout(5000)
        response = page.goto(self.origin)
        self.assertIsNotNone(response)
        self.assertEqual(response.status, 200)
        page.get_by_role("navigation", name="Hauptnavigation").wait_for()
        return page

    def test_offline_start_navigation_and_clean_console(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                errors: list[str] = []
                external_requests: list[str] = []
                page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: external_requests.append(request.url) if not request.url.startswith(self.origin) else None)
                response = page.goto(self.origin)
                self.assertIsNotNone(response)
                self.assertEqual(response.status, 200)
                for label in (
                    "Übersicht", "Objektverwaltung", "Kostenverwaltung", "Zählerverwaltung",
                    "Mieterverwaltung", "Abrechnungen", "Abschreibungen", "Einstellungen",
                ):
                    link = page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name=label)
                    link.click()
                    self.assertEqual(link.get_attribute("aria-current"), "page")
                    page.locator(".shell-content h2").first.wait_for()
                self.assertEqual(external_requests, [])
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_property_expense_entry_and_clear_transport_error(self) -> None:
        with sync_playwright() as playwright:
            page = self._open_page(playwright)
            page.get_by_role("link", name="Objektverwaltung").click()
            page.locator(".asset-registry-view > div select").first.select_option("property")
            form = page.locator(".asset-registry-view .inline-edit form")
            form.wait_for()
            self.assertNotEqual(form.locator("select#property-organization").input_value(), "")
            inputs = form.locator("input")
            inputs.nth(0).fill("Browser Anlage")
            inputs.nth(1).fill("Prüfweg 8")
            inputs.nth(2).fill("10000")
            inputs.nth(3).fill("Teststadt")
            form.get_by_role("button", name="Speichern").click()
            page.get_by_text("Browser Anlage").wait_for()

            page.get_by_role("link", name="Kostenverwaltung").click()
            page.get_by_role("button", name="Kosten erfassen").click()
            form = page.locator(".shell-content form")
            form.get_by_label("Zielobjekt").select_option(label="Anlage: Browser Anlage")
            form.get_by_label("Kostenart").fill("Browser Kostenart")
            form.get_by_label("Bezeichnung").fill("Browser Kosten")
            form.get_by_label("Empfänger").fill("Testversorger")
            form.get_by_label("Wert (EUR)").fill("25")
            form.get_by_label("Verteilerschlüssel").select_option("unit_count")
            form.get_by_label("Buchungsdatum").fill("2025-06-01")
            form.get_by_role("button", name="Speichern").click()
            page.get_by_label("Jahr").fill("2025")
            page.get_by_text("Browser Kosten", exact=True).wait_for()
            with sqlite3.connect(self.database.path) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM expense_items WHERE label = ?", ("Browser Kosten",)
                    ).fetchone()[0], 1,
                )

            def invalid_expense(route):
                if route.request.method == "POST":
                    route.fulfill(
                        status=422,
                        content_type="application/json",
                        body=json.dumps({"error": {"code": "invalid_value", "reason": "Der Kostenbetrag ist ungültig."}}),
                    )
                else:
                    route.continue_()

            page.route("**/api/v1/expenses", invalid_expense)
            page.get_by_role("button", name="Kosten erfassen").click()
            form = page.locator(".shell-content form")
            form.get_by_label("Zielobjekt").select_option(label="Anlage: Browser Anlage")
            form.get_by_label("Kostenart").fill("Fehlerfall")
            form.get_by_label("Wert (EUR)").fill("25")
            form.get_by_label("Buchungsdatum").fill("2025-06-01")
            form.get_by_role("button", name="Speichern").click()
            page.get_by_role("alert").get_by_text("Der Kostenbetrag ist ungültig.").wait_for()

    def test_backup_import_and_settlement_preview(self) -> None:
        with sync_playwright() as playwright:
            page = self._open_page(playwright)
            page.get_by_role("link", name="Einstellungen").click()
            with page.expect_download() as download_info:
                page.get_by_role("button", name="Daten exportieren").click()
            download = download_info.value
            self.assertTrue(download.suggested_filename.startswith("easyprent-export-"))
            page.locator("#import-file-upload").set_input_files(download.path())
            page.get_by_text("Import erfolgreich", exact=False).wait_for()

            page.get_by_role("link", name="Abrechnungen").click()
            form = page.locator(".shell-content form")
            form.get_by_label("Objekt").select_option(label="Wohnung: Freistehende Wohnung")
            form.get_by_label("Von").fill("2025-01-01")
            form.get_by_label("Bis").fill("2025-12-31")
            form.get_by_role("button", name="Berechnen").click()
            page.get_by_text("Kosten 92.30 €", exact=False).wait_for()
            page.get_by_text("Fixture Mieter Drei").first.wait_for()


if __name__ == "__main__":
    unittest.main()
