"""Settlement document downloads through the public HTTP routes."""

from __future__ import annotations

from io import BytesIO
import unittest
from zipfile import ZipFile

from easyprent_accounting.settlement_runs import create_or_open_settlement_run
from tests.support import asgi_test_client, temporary_database


class SettlementDocumentHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def test_period_pdf_is_a_named_attachment(self) -> None:
        response = self.client.get(
            "/api/v1/settlements/document.pdf",
            params={
                "property_id": 1,
                "lease_id": 1,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn("Nebenkostenabrechnung-Anna-Schulz-2025.pdf", response.headers["content-disposition"])

    def test_period_ods_contains_the_selected_lease_and_period(self) -> None:
        response = self.client.get(
            "/api/v1/settlements/document.ods",
            params={
                "property_id": 1,
                "lease_id": 1,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.oasis.opendocument.spreadsheet",
        )
        self.assertIn("Nebenkostenabrechnung-Anna-Schulz-2025.ods", response.headers["content-disposition"])
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertIsNone(archive.testzip())
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Anna Schulz", content)
        self.assertIn("01.01.2025 – 31.12.2025", content)

    def test_run_ods_uses_the_saved_run_period(self) -> None:
        connection = self.database.connect(rows=True)
        try:
            with connection:
                run, _ = create_or_open_settlement_run(
                    connection, {"property_id": 1, "year": 2025}
                )
        finally:
            connection.close()

        response = self.client.get(
            f"/api/v1/settlement-runs/{run['id']}/leases/1/document.ods"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.oasis.opendocument.spreadsheet",
        )
        self.assertIn("attachment", response.headers["content-disposition"])
        with ZipFile(BytesIO(response.content)) as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Anna Schulz", content)
        self.assertIn("01.01.2025 – 31.12.2025", content)

    def test_document_routes_validate_ids_dates_and_missing_runs(self) -> None:
        malformed: tuple[tuple[str, dict[str, str | int]], ...] = (
            ("/api/v1/settlements/document.pdf", {"property_id": "no", "lease_id": 1,
                "period_start": "2025-01-01", "period_end": "2025-12-31"}),
            ("/api/v1/settlements/document.ods", {"property_id": 1, "lease_id": 0,
                "period_start": "2025-01-01", "period_end": "2025-12-31"}),
            ("/api/v1/settlements/document.pdf", {"property_id": 1, "lease_id": 1,
                "period_start": "not-a-date", "period_end": "2025-12-31"}),
            ("/api/v1/settlement-runs/unknown/leases/0/document.ods", {}),
        )
        for path, params in malformed:
            with self.subTest(path=path, params=params):
                response = self.client.get(path, params=params)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "invalid_request")

        missing = self.client.get(
            "/api/v1/settlement-runs/unknown/leases/1/document.ods"
        )
        self.assertEqual(missing.status_code, 422, missing.text)
        self.assertEqual(missing.json()["error"]["code"], "invalid_value")

    def test_period_documents_require_one_settlement_target(self) -> None:
        for extension in ("pdf", "ods"):
            with self.subTest(extension=extension):
                response = self.client.get(
                    f"/api/v1/settlements/document.{extension}",
                    params={
                        "property_id": 1,
                        "unit_id": 1,
                        "lease_id": 1,
                        "period_start": "2025-01-01",
                        "period_end": "2025-12-31",
                    },
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "invalid_value")
                self.assertIn("exactly one property or standalone unit", response.json()["error"]["reason"])


if __name__ == "__main__":
    unittest.main()
