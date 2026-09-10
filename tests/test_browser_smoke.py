"""Browser smoke tests for offline start, clean console, and main navigation."""
from __future__ import annotations

import os
import sys
import threading
import unittest
from wsgiref.simple_server import make_server



try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ImportError:
    HAVE_PLAYWRIGHT = False

from easyprent_accounting.config import load_config
from easyprent_accounting.web import application
from easyprent_accounting.config import set_global_config
from tests.support import temporary_database


class BrowserSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not HAVE_PLAYWRIGHT:
            raise unittest.SkipTest("playwright is required for browser smoke tests")

    def setUp(self) -> None:
        from tests.support import temporary_database, mocked_global_config
        self.database = self.enterContext(temporary_database(seeded=True))
        self.enterContext(mocked_global_config(load_config({"EASYPRENT_DB_PATH": str(self.database.path)})))

        self.server = make_server("127.0.0.1", 0, application)
        self.port = self.server.server_port
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_offline_start_clean_console_and_navigation(self) -> None:
        """Verify offline start: no external requests, clean console, and clickable main navigation."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            console_errors: list[str] = []
            page_errors: list[str] = []
            all_requests: list[str] = []
            external_requests: list[str] = []

            page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            local_origin = f"http://127.0.0.1:{self.port}"
            def on_request(req):
                all_requests.append(req.url)
                if not req.url.startswith(local_origin):
                    external_requests.append(req.url)

            page.on("request", on_request)

            # 1. Offline Start
            response = page.goto(f"{local_origin}/")
            self.assertIsNotNone(response, "Server did not respond")
            self.assertEqual(response.status, 200)

            # Wait for React app shell to mount
            page.wait_for_selector("button.tab", timeout=5000)

            # 2. Verify no external requests were initiated (strictly offline)
            self.assertGreater(len(all_requests), 0, "Expected local static/API requests to be made")
            self.assertEqual(
                external_requests,
                [],
                f"App is not offline-capable; made external requests: {external_requests}",
            )

            # 3. Verify clean console on initial load
            self.assertEqual(console_errors, [], f"Console errors on load: {console_errors}")
            self.assertEqual(page_errors, [], f"Page crashes on load: {page_errors}")

            # 4. Click through all main navigation tabs
            main_navigation_tabs = [
                "Übersicht",
                "Objektverwaltung",
                "Kostenverwaltung",
                "Mieterverwaltung",
                "Abrechnungen",
                "Einstellungen",
            ]
            for tab_label in main_navigation_tabs:
                tab_btn = page.locator(f'button.tab:has-text("{tab_label}")')
                self.assertTrue(tab_btn.is_visible(), f"Navigation tab '{tab_label}' is not visible")
                tab_btn.click()

                # Verify button received active state
                classes = tab_btn.get_attribute("class") or ""
                self.assertIn("active", classes, f"Tab '{tab_label}' did not become active after click")
                
                # Verify visible behavioral rendering based on seeded data or UI structure
                if tab_label == "Objektverwaltung":
                    page.wait_for_selector('text="Wohnpark Lindenhof"', timeout=2000)
                elif tab_label == "Kostenverwaltung":
                    page.wait_for_selector('text="Gesamtkosten je Kostenart"', timeout=2000)
                    
                    # Verify behavioral chart rendering
                    page.wait_for_selector('.echarts-host', timeout=2000)

                    # Verify behavioral form rendering
                    # Verify behavioral form rendering
                    page.click('text="Kostenposten erzeugen"')
                    page.wait_for_selector('label:has-text("Kostenart")', timeout=2000)
                    
                elif tab_label == "Mieterverwaltung":
                    page.wait_for_selector('text="Tim Wagner"', timeout=2000)

            # 5. Verify console remained error-free throughout full navigation
            self.assertEqual(console_errors, [], f"Console errors during navigation: {console_errors}")
            self.assertEqual(page_errors, [], f"Page errors during navigation: {page_errors}")

            browser.close()


if __name__ == "__main__":
    unittest.main()
