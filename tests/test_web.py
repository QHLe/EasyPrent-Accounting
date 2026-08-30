from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from io import BytesIO
from unittest import mock

from src.easyprent_accounting.db import initialize_database, seed_demo_data
from src.easyprent_accounting.web import application


class WebApiAndUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.original_db_path = os.environ.get("EASYPRENT_DB_PATH")
        os.environ["EASYPRENT_DB_PATH"] = self.db_path
        initialize_database()
        connection = sqlite3.connect(self.db_path)
        try:
            seed_demo_data(connection)
            connection.commit()
        finally:
            connection.close()

    def tearDown(self) -> None:
        if self.original_db_path is None:
            os.environ.pop("EASYPRENT_DB_PATH", None)
        else:
            os.environ["EASYPRENT_DB_PATH"] = self.original_db_path
        self.temp_dir.cleanup()

    def _call_app(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        query_string: str = "",
        content_type: str = "application/json",
    ):
        status_headers: dict = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = headers

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": content_type,
            "wsgi.input": BytesIO(body),
        }
        response = b"".join(application(environ, start_response))
        return status_headers["status"], dict(status_headers["headers"]), response

    def test_root_serves_react_shell(self) -> None:
        status, _, body = self._call_app("GET", "/")
        content = body.decode("utf-8")
        self.assertTrue(status.startswith("200"))
        self.assertIn('<div id="root"></div>', content)
        self.assertIn('/static/vendor/react.production.min.js', content)
        self.assertIn('/static/vendor/react-dom.production.min.js', content)
        self.assertIn('/static/vendor/echarts.min.js', content)
        self.assertIn('/static/app_helpers.js', content)
        self.assertIn('/static/app.js', content)
        self.assertIn('/static/app.css', content)
        self.assertIn('/openapi.json', content)
        self.assertNotIn("unpkg.com", content)

    def test_static_app_uses_react_and_api_endpoints(self) -> None:
        status, headers, body = self._call_app("GET", "/static/app.js")
        helpers_status, helpers_headers, helpers_body = self._call_app("GET", "/static/app_helpers.js")
        domain_status, domain_headers, domain_body = self._call_app("GET", "/static/app_domain.js")
        charts_status, charts_headers, charts_body = self._call_app("GET", "/static/app_charts.js")
        sections_status, sections_headers, sections_body = self._call_app("GET", "/static/app_sections.js")
        forms_status, forms_headers, forms_body = self._call_app("GET", "/static/app_forms.js")
        previews_status, previews_headers, previews_body = self._call_app("GET", "/static/app_previews.js")
        main_status, main_headers, main_body = self._call_app("GET", "/static/app_main.js")
        self.assertTrue(status.startswith("200"))
        self.assertTrue(helpers_status.startswith("200"))
        self.assertTrue(domain_status.startswith("200"))
        self.assertTrue(charts_status.startswith("200"))
        self.assertTrue(sections_status.startswith("200"))
        self.assertTrue(forms_status.startswith("200"))
        self.assertTrue(previews_status.startswith("200"))
        self.assertTrue(main_status.startswith("200"))
        self.assertEqual(headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(helpers_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(domain_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(charts_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(sections_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(forms_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(previews_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(main_headers["Content-Type"], "application/javascript; charset=utf-8")
        content = (
            helpers_body.decode("utf-8")
            + "\n"
            + domain_body.decode("utf-8")
            + "\n"
            + charts_body.decode("utf-8")
            + "\n"
            + sections_body.decode("utf-8")
            + "\n"
            + forms_body.decode("utf-8")
            + "\n"
            + previews_body.decode("utf-8")
            + "\n"
            + main_body.decode("utf-8")
            + "\n"
            + body.decode("utf-8")
        )
        self.assertIn("EasyPrentFrontendHelpers", content)
        self.assertIn("EasyPrentAppDomain", content)
        self.assertIn("EasyPrentAppCharts", content)
        self.assertIn("EasyPrentAppSections", content)
        self.assertIn("EasyPrentAppForms", content)
        self.assertIn("EasyPrentAppPreviews", content)
        self.assertIn("/static/app_domain.js", content)
        self.assertIn("/static/app_charts.js", content)
        self.assertIn("/static/app_sections.js", content)
        self.assertIn("/static/app_forms.js", content)
        self.assertIn("/static/app_previews.js", content)
        self.assertIn("/static/app_main.js", content)
        self.assertIn("ReactDOM.createRoot", content)
        self.assertIn("/api/overview", content)
        self.assertIn("/api/buildings", content)
        self.assertIn("/api/units", content)
        self.assertIn("/api/rooms", content)
        self.assertIn("/api/meters", content)
        self.assertIn("/api/meter-readings", content)
        self.assertIn("/api/tenants", content)
        self.assertIn("/api/leases", content)
        self.assertIn("/api/expenses", content)
        self.assertIn("/api/health", content)
        self.assertIn("/api/paperless-status", content)
        self.assertIn("/api/paperless-settings", content)
        self.assertIn("/api/application-settings", content)
        self.assertIn("/api/application-export", content)
        self.assertIn("/api/application-import", content)
        self.assertIn("/api/expenses/\" + String(expenseId) + \"/documents", content)
        self.assertIn("Paperless Dokument-ID", content)
        self.assertIn("Dokumenten-ID hinzufügen", content)
        self.assertIn("Dokument öffnen", content)
        self.assertIn("/api/expenses/", content)
        self.assertIn('"/api/meter-readings/" + String(reading.id)', content)
        self.assertIn("Objektverwaltung", content)
        self.assertIn("Kostenverwaltung", content)
        self.assertIn("Kosten-Granularität", content)
        self.assertIn("expenseDevelopmentMonthlySeries", content)
        self.assertIn("Gesamtsumme", content)
        self.assertIn("Mieterverwaltung", content)
        self.assertIn("Objekt erzeugen", content)
        self.assertIn("Kostenposten erzeugen", content)
        self.assertIn("Mieter erzeugen", content)
        self.assertIn("Mietvertrag erzeugen", content)
        self.assertIn("Objektliste filtern", content)
        self.assertIn("Elternobjekt", content)
        self.assertIn("Kindobjekte", content)
        self.assertIn("managementListFilters.objects", content)
        self.assertIn("Mieterliste filtern", content)
        self.assertIn("Mietvertragsliste filtern", content)
        self.assertIn("Übersicht", content)
        self.assertIn("Einstellungen", content)
        self.assertIn("Mieter erfassen", content)
        self.assertIn("Mietvertrag erfassen", content)
        self.assertIn("Zimmer optional", content)
        self.assertIn("Zimmerfläche in m²", content)
        self.assertIn("Mieterliste", content)
        self.assertIn("Mietvertragsliste", content)
        self.assertIn("Identitätsdokumente", content)
        self.assertIn("Vertragsdokumente", content)
        self.assertIn("Paperless URL", content)
        self.assertIn("Paperless Token", content)
        self.assertIn("Löschaktionen anzeigen", content)
        self.assertIn("Daten exportieren", content)
        self.assertIn("Daten importieren", content)
        self.assertIn("Import überschreibt den aktuellen Datenbestand", content)
        self.assertIn("Token (maskiert)", content)
        self.assertIn("Serverstatus", content)
        self.assertIn("Paperless Serverstatus", content)
        self.assertIn("token_masked", content)
        self.assertIn("Kosten erfassen", content)
        self.assertIn("Kosten bearbeiten", content)
        self.assertIn("Kosten archivieren", content)
        self.assertIn("Änderungen speichern", content)
        self.assertIn("buildManagementInlineEditorRow", content)
        self.assertIn("Dokumente auswählen", content)
        self.assertIn("Dokumente hochladen", content)
        self.assertIn("Dokument öffnen", content)
        self.assertIn("Dokument löschen", content)
        self.assertIn("Mieter löschen", content)
        self.assertIn("Mietvertrag löschen", content)
        self.assertIn("Archivierung aufheben", content)
        self.assertNotIn("Vorhandene Kostenart", content)
        self.assertIn("Empfänger", content)
        self.assertIn("Bezeichnung", content)
        self.assertIn('setField("label", event.target.value);', content)
        self.assertIn("value: formState.label", content)
        self.assertIn("Abrechnungsart", content)
        self.assertIn("Turnus", content)
        self.assertIn("Kostenliste filtern", content)
        self.assertIn("expenseListFilters", content)
        self.assertIn("filteredExpenses", content)
        self.assertIn("startExpenseEdit(expense)", content)
        self.assertIn('String(editingExpenseId) === String(expense.id) && !expense.is_archived', content)
        self.assertIn("datalist", content)
        self.assertIn("expense-category-suggestions", content)
        self.assertIn("optgroup", content)
        self.assertIn("Gebäude", content)
        self.assertIn("Wohnungen", content)
        self.assertIn("Zimmer", content)
        self.assertIn("Zähler", content)
        self.assertIn("Zählerstand", content)
        self.assertIn("Zählerstandhistorie", content)
        self.assertIn("Zählerentwicklung", content)
        self.assertIn("Verbrauch im Zeitraum", content)
        self.assertIn("meterConsumptionSummary", content)
        self.assertIn("Zähler anklicken", content)
        self.assertIn("Ansicht", content)
        self.assertIn("Letzte Monate", content)
        self.assertIn("Letzte Jahre", content)
        self.assertIn("Diagrammtyp", content)
        self.assertIn("Kumuliert", content)
        self.assertIn("Säulen", content)
        self.assertIn("Interpolation", content)
        self.assertIn("Linear", content)
        self.assertIn("Quadratisch", content)
        self.assertIn("window.echarts", content)
        self.assertIn("echarts.init", content)
        self.assertIn("tooltip", content)
        self.assertIn("axisPointer", content)
        self.assertNotIn("yAxisIndex: 0", content)
        self.assertIn("scale: true", content)
        self.assertIn(': "dataMin"', content)
        self.assertIn("max: \"dataMax\"", content)
        self.assertIn("type: \"scatter\"", content)
        self.assertIn("actualReadings", content)
        self.assertIn("rangeStartPoint", content)
        self.assertIn("setMeterChartRangeBoundary", content)
        self.assertIn("Kostenentwicklung", content)
        self.assertIn("buildExpenseDevelopmentSeries", content)
        self.assertIn("buildExpenseDevelopmentCompositionSeries", content)
        self.assertIn("calculateMeterConsumptionValue(", content)
        self.assertIn("expense.conversion_factor", content)
        self.assertIn("sortExpensesByEndDateDesc", content)
        self.assertIn("filteredExpenses.slice().sort(sortExpensesByEndDateDesc)", content)
        self.assertIn('stack: "expense-composition"', content)
        self.assertIn("Kosten-Granularität", content)
        self.assertIn("Kosten-Diagrammtyp", content)
        self.assertIn("point-source-recorded", content)
        self.assertIn("point-source-interpolated", content)
        self.assertIn("source_type", content)
        self.assertIn("Zählerstand löschen", content)
        self.assertIn("Gebäude-Straße", content)
        self.assertIn("Wohnungs-Straße", content)
        self.assertIn("Zielobjekt", content)
        self.assertIn("buildObjectTargetValue", content)
        self.assertIn("parseObjectTargetValue", content)
        self.assertIn("Gesamtkosten", content)
        self.assertIn("Von Datum", content)
        self.assertIn("Bis Datum", content)
        self.assertNotIn("Einzeldatum", content)
        self.assertNotIn("Zeitraum optional", content)
        self.assertNotIn("Von Datum optional", content)
        self.assertNotIn("Bis Datum optional", content)
        self.assertIn("Verbrauchseinheit", content)
        self.assertIn("Zähler optional", content)
        self.assertIn("Umrechnungsfaktor", content)
        self.assertIn('formState.charge_type === "consumption" && !formState.meter_id', content)
        self.assertIn("meterOptions: props.meterOptions", content)
        self.assertIn("Gesamtsumme", content)
        self.assertIn("Zeitraum von", content)
        self.assertIn("Zeitraum bis", content)
        self.assertIn("buildDefaultMeterChartRange", content)
        self.assertIn('setMeterChartRange(buildDefaultMeterChartRange(nextReadings))', content)
        self.assertIn('previewTitle = "Objektliste"', content)
        self.assertIn("Objektliste Zähler", content)
        self.assertIn("Alle Anlagen, Gebäude, Wohnungen und Zimmer in gemeinsamer Hierarchie", content)
        self.assertIn("Archivieren", content)
        self.assertIn("Löschen", content)

    def test_static_app_javascript_is_syntax_valid(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is required for JavaScript syntax validation")

        repo_root = os.path.dirname(os.path.dirname(__file__))
        static_dir = os.path.join(repo_root, "src", "easyprent_accounting", "static")
        script_paths = [
            os.path.join(static_dir, "app_domain.js"),
            os.path.join(static_dir, "app_charts.js"),
            os.path.join(static_dir, "app_sections.js"),
            os.path.join(static_dir, "app_forms.js"),
            os.path.join(static_dir, "app_previews.js"),
            os.path.join(static_dir, "app_main.js"),
            os.path.join(static_dir, "app_helpers.js"),
            os.path.join(static_dir, "app.js"),
        ]
        for script_path in script_paths:
            result = subprocess.run(
                ["node", "--check", script_path],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{script_path}: {result.stderr}")

    def test_local_react_vendor_files_are_served(self) -> None:
        react_status, react_headers, react_body = self._call_app("GET", "/static/vendor/react.production.min.js")
        dom_status, dom_headers, dom_body = self._call_app("GET", "/static/vendor/react-dom.production.min.js")
        chart_status, chart_headers, chart_body = self._call_app("GET", "/static/vendor/echarts.min.js")
        self.assertTrue(react_status.startswith("200"))
        self.assertTrue(dom_status.startswith("200"))
        self.assertTrue(chart_status.startswith("200"))
        self.assertEqual(react_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(dom_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertEqual(chart_headers["Content-Type"], "application/javascript; charset=utf-8")
        self.assertGreater(len(react_body), 1000)
        self.assertGreater(len(dom_body), 1000)
        self.assertGreater(len(chart_body), 10000)

    def test_openapi_endpoint_describes_core_api(self) -> None:
        status, headers, body = self._call_app("GET", "/openapi.json")
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("200"))
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(payload["openapi"], "3.1.0")
        self.assertIn("/api/overview", payload["paths"])
        self.assertIn("/api/settlements", payload["paths"])
        self.assertIn("/api/depreciation-schedule", payload["paths"])
        self.assertIn("/api/expenses", payload["paths"])
        self.assertIn("/api/buildings", payload["paths"])
        self.assertIn("/api/units", payload["paths"])
        self.assertIn("/api/rooms", payload["paths"])
        self.assertIn("/api/meters", payload["paths"])
        self.assertIn("/api/meter-readings", payload["paths"])
        self.assertIn("/api/tenants", payload["paths"])
        self.assertIn("/api/leases", payload["paths"])
        self.assertIn("/api/health", payload["paths"])
        self.assertIn("/api/paperless-status", payload["paths"])
        self.assertIn("/api/paperless-settings", payload["paths"])
        self.assertIn("/api/application-settings", payload["paths"])
        self.assertIn("/api/application-export", payload["paths"])
        self.assertIn("/api/application-import", payload["paths"])
        self.assertIn("/api/expenses/{id}", payload["paths"])
        self.assertIn("/api/tenants/{id}", payload["paths"])
        self.assertIn("/api/tenants/{id}/documents", payload["paths"])
        self.assertIn("/api/tenants/{id}/documents/{document_id}", payload["paths"])
        self.assertIn("/api/tenants/{id}/documents/{document_id}/download", payload["paths"])
        self.assertIn("/api/leases/{id}", payload["paths"])
        self.assertIn("/api/leases/{id}/documents", payload["paths"])
        self.assertIn("/api/leases/{id}/documents/{document_id}", payload["paths"])
        self.assertIn("/api/leases/{id}/documents/{document_id}/download", payload["paths"])
        self.assertIn("/api/expenses/{id}/documents", payload["paths"])
        self.assertIn("/api/expenses/{id}/documents/{document_id}", payload["paths"])
        self.assertIn("/api/expenses/{id}/documents/{document_id}/download", payload["paths"])
        self.assertIn("/api/meter-readings/{id}", payload["paths"])
        self.assertIn("/api/rooms/{id}/archive", payload["paths"])
        self.assertIn("/api/rooms/{id}/restore", payload["paths"])
        self.assertIn("/api/expenses/{id}/archive", payload["paths"])
        self.assertIn("/api/expenses/{id}/restore", payload["paths"])
        self.assertIn("/api/meters/{id}/archive", payload["paths"])
        self.assertIn("/api/meters/{id}/restore", payload["paths"])
        self.assertIn("put", payload["paths"]["/api/expenses/{id}"])
        self.assertIn("put", payload["paths"]["/api/properties/{id}"])
        self.assertIn("put", payload["paths"]["/api/buildings/{id}"])
        self.assertIn("put", payload["paths"]["/api/units/{id}"])
        self.assertIn("put", payload["paths"]["/api/rooms/{id}"])
        self.assertIn("put", payload["paths"]["/api/tenants/{id}"])
        self.assertIn("put", payload["paths"]["/api/leases/{id}"])
        self.assertIn("delete", payload["paths"]["/api/tenants/{id}"])
        self.assertIn("delete", payload["paths"]["/api/leases/{id}"])
        self.assertIn("delete", payload["paths"]["/api/expenses/{id}/documents/{document_id}"])
        self.assertIn("object_type", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("object_id", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("booking_date", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("consumption_unit", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("meter_id", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("conversion_factor", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("expense_category", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("area_sqm", payload["components"]["schemas"]["RoomCreateRequest"]["properties"])
        self.assertIn("area_sqm", payload["components"]["schemas"]["RoomResponse"]["properties"])
        self.assertIn("beneficiary_name", payload["components"]["schemas"]["ExpenseCreateRequest"]["properties"])
        self.assertIn("MeterCreateRequest", payload["components"]["schemas"])
        self.assertIn("MeterReadingCreateRequest", payload["components"]["schemas"])
        self.assertIn("meter_readings", payload["components"]["schemas"]["OverviewResponse"]["properties"])
        self.assertIn("tenants", payload["components"]["schemas"]["OverviewResponse"]["properties"])
        self.assertIn("leases", payload["components"]["schemas"]["OverviewResponse"]["properties"])
        self.assertIn("TenantCreateRequest", payload["components"]["schemas"])
        self.assertIn("LeaseCreateRequest", payload["components"]["schemas"])
        self.assertIn("room_id", payload["components"]["schemas"]["LeaseCreateRequest"]["properties"])
        self.assertIn("room_id", payload["components"]["schemas"]["LeaseResponse"]["properties"])
        self.assertIn("expense_categories", payload["components"]["schemas"]["OverviewResponse"]["properties"])
        self.assertIn("total_amount", payload["components"]["schemas"]["ExpenseResponse"]["properties"])
        self.assertIn("effective_consumption_value", payload["components"]["schemas"]["ExpenseResponse"]["properties"])
        self.assertIn("meter_unit", payload["components"]["schemas"]["ExpenseResponse"]["properties"])
        self.assertIn("street", payload["components"]["schemas"]["BuildingCreateRequest"]["properties"])
        self.assertIn("street", payload["components"]["schemas"]["UnitCreateRequest"]["properties"])
        self.assertIn("PaperlessSettingsResponse", payload["components"]["schemas"])
        self.assertIn("PaperlessSettingsUpdateRequest", payload["components"]["schemas"])
        self.assertIn("PaperlessStatusResponse", payload["components"]["schemas"])
        self.assertIn("ApplicationSettingsResponse", payload["components"]["schemas"])
        self.assertIn("ApplicationSettingsUpdateRequest", payload["components"]["schemas"])
        self.assertIn("ApplicationExportResponse", payload["components"]["schemas"])
        self.assertIn("ApplicationImportRequest", payload["components"]["schemas"])
        self.assertIn("ApplicationImportResponse", payload["components"]["schemas"])
        self.assertIn("LinkedDocumentUploadRequest", payload["components"]["schemas"])
        self.assertIn("LinkedDocumentResponse", payload["components"]["schemas"])
        self.assertIn("LinkedDocumentListResponse", payload["components"]["schemas"])
        self.assertIn("LinkedDocumentDeleteResponse", payload["components"]["schemas"])
        self.assertIn("ExpenseDocumentUploadRequest", payload["components"]["schemas"])
        self.assertIn("ExpenseDocumentUploadResponse", payload["components"]["schemas"])
        self.assertIn("ExpenseDocumentListResponse", payload["components"]["schemas"])
        self.assertIn("ExpenseDocumentDeleteResponse", payload["components"]["schemas"])
        self.assertIn(
            "paperless_document_id",
            payload["components"]["schemas"]["ExpenseDocumentUploadEntry"]["properties"],
        )
        self.assertNotIn("label", payload["components"]["schemas"]["ExpenseCreateRequest"]["required"])

    def test_api_health_reports_server_reachable(self) -> None:
        status, _, body = self._call_app("GET", "/api/health")
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("200"))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["reachable"], True)

    def test_api_can_create_tenant_and_lease(self) -> None:
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Test Mieter",
                    "email": "test.mieter@example.org",
                    "phone": "+49 123 4567",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))
        self.assertEqual(tenant_payload["full_name"], "Test Mieter")
        self.assertEqual(tenant_payload["email"], "test.mieter@example.org")

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        self.assertTrue(len(overview_payload["units"]) > 0)
        first_unit_id = overview_payload["units"][0]["id"]

        lease_status, _, lease_body = self._call_app(
            "POST",
            "/api/leases",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "1100.00",
                    "additional_charges_advance": "240.00",
                    "occupant_count": 2,
                    "start_date": "2026-01-01",
                    "end_date": "2026-12-31",
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        lease_payload = json.loads(lease_body.decode("utf-8"))
        self.assertTrue(lease_status.startswith("201"))
        self.assertEqual(lease_payload["unit_id"], first_unit_id)
        self.assertEqual(lease_payload["tenant_id"], tenant_payload["id"])

        overview_after_status, _, overview_after_body = self._call_app("GET", "/api/overview")
        overview_after_payload = json.loads(overview_after_body.decode("utf-8"))
        self.assertTrue(overview_after_status.startswith("200"))
        self.assertTrue(
            any(
                tenant["id"] == tenant_payload["id"]
                for tenant in overview_after_payload["tenants"]
            )
        )
        self.assertTrue(
            any(
                lease["id"] == lease_payload["id"]
                for lease in overview_after_payload["leases"]
            )
        )

    def test_api_can_update_property_tenant_and_lease(self) -> None:
        update_property_status, _, update_property_body = self._call_app(
            "PUT",
            "/api/properties/1",
            json.dumps(
                {
                    "organization_id": 1,
                    "name": "Anlage Alpha Aktualisiert",
                    "street": "Updateweg 10",
                    "city": "Berlin",
                    "postal_code": "10115",
                }
            ).encode("utf-8"),
        )
        update_property_payload = json.loads(update_property_body.decode("utf-8"))
        self.assertTrue(update_property_status.startswith("200"))
        self.assertEqual(update_property_payload["name"], "Anlage Alpha Aktualisiert")

        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Editierbarer Mieter",
                    "email": "edit@example.org",
                    "phone": "111",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        tenant_update_status, _, tenant_update_body = self._call_app(
            "PUT",
            f"/api/tenants/{tenant_payload['id']}",
            json.dumps(
                {
                    "full_name": "Editierter Mieter",
                    "email": "edited@example.org",
                    "phone": "222",
                }
            ).encode("utf-8"),
        )
        tenant_update_payload = json.loads(tenant_update_body.decode("utf-8"))
        self.assertTrue(tenant_update_status.startswith("200"))
        self.assertEqual(tenant_update_payload["full_name"], "Editierter Mieter")
        self.assertEqual(tenant_update_payload["phone"], "222")

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        first_unit_id = overview_payload["units"][0]["id"]

        lease_status, _, lease_body = self._call_app(
            "POST",
            "/api/leases",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "1200.00",
                    "additional_charges_advance": "250.00",
                    "occupant_count": 2,
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        lease_payload = json.loads(lease_body.decode("utf-8"))
        self.assertTrue(lease_status.startswith("201"))

        lease_update_status, _, lease_update_body = self._call_app(
            "PUT",
            f"/api/leases/{lease_payload['id']}",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "1250.00",
                    "additional_charges_advance": "260.00",
                    "occupant_count": 3,
                    "start_date": "2026-01-01",
                    "end_date": "2026-12-31",
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        lease_update_payload = json.loads(lease_update_body.decode("utf-8"))
        self.assertTrue(lease_update_status.startswith("200"))
        self.assertEqual(lease_update_payload["occupant_count"], 3)
        self.assertEqual(lease_update_payload["rent_cold"], "1250.00")

    def test_api_can_create_and_update_room_based_lease(self) -> None:
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Zimmermieter",
                    "email": "room-lease@example.org",
                    "phone": "030-333333",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        first_unit_id = overview_payload["units"][0]["id"]

        room_create_status, _, room_create_body = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "label": "Arbeitszimmer",
                }
            ).encode("utf-8"),
        )
        room_payload = json.loads(room_create_body.decode("utf-8"))
        self.assertTrue(room_create_status.startswith("201"))

        lease_status, _, lease_body = self._call_app(
            "POST",
            "/api/leases",
            json.dumps(
                {
                    "tenant_id": tenant_payload["id"],
                    "room_id": room_payload["id"],
                    "rent_cold": "700.00",
                    "additional_charges_advance": "120.00",
                    "occupant_count": 1,
                    "start_date": "2026-02-01",
                    "end_date": None,
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        lease_payload = json.loads(lease_body.decode("utf-8"))
        self.assertTrue(lease_status.startswith("201"))
        self.assertEqual(lease_payload["room_id"], room_payload["id"])
        self.assertEqual(lease_payload["unit_id"], first_unit_id)

        lease_update_status, _, lease_update_body = self._call_app(
            "PUT",
            f"/api/leases/{lease_payload['id']}",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "750.00",
                    "additional_charges_advance": "130.00",
                    "occupant_count": 1,
                    "start_date": "2026-02-01",
                    "end_date": "2026-12-31",
                    "status": "active",
                    "room_id": room_payload["id"],
                }
            ).encode("utf-8"),
        )
        lease_update_payload = json.loads(lease_update_body.decode("utf-8"))
        self.assertTrue(lease_update_status.startswith("200"))
        self.assertEqual(lease_update_payload["room_id"], room_payload["id"])
        self.assertEqual(lease_update_payload["unit_id"], first_unit_id)

        overview_after_status, _, overview_after_body = self._call_app("GET", "/api/overview")
        overview_after_payload = json.loads(overview_after_body.decode("utf-8"))
        self.assertTrue(overview_after_status.startswith("200"))
        matching_lease = next(
            lease for lease in overview_after_payload["leases"] if lease["id"] == lease_payload["id"]
        )
        self.assertEqual(matching_lease["room_id"], room_payload["id"])
        self.assertEqual(matching_lease["unit_id"], first_unit_id)
        self.assertEqual(matching_lease["room_label"], "Arbeitszimmer")

    def test_api_can_delete_tenant_without_leases(self) -> None:
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Löschbarer Mieter",
                    "email": "delete@example.org",
                    "phone": "030-1",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/tenants/{tenant_payload['id']}",
        )
        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(delete_status.startswith("200"))
        self.assertEqual(delete_payload["resource"], "tenants")
        self.assertEqual(delete_payload["id"], tenant_payload["id"])
        self.assertEqual(delete_payload["deleted"], True)

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        self.assertFalse(
            any(tenant["id"] == tenant_payload["id"] for tenant in overview_payload["tenants"])
        )

    def test_api_rejects_tenant_delete_with_existing_leases(self) -> None:
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Gebundener Mieter",
                    "email": "lease@example.org",
                    "phone": "030-2",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        first_unit_id = overview_payload["units"][0]["id"]

        lease_status, _, _ = self._call_app(
            "POST",
            "/api/leases",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "1300.00",
                    "additional_charges_advance": "260.00",
                    "occupant_count": 2,
                    "start_date": "2026-02-01",
                    "end_date": None,
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(lease_status.startswith("201"))

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/tenants/{tenant_payload['id']}",
        )
        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(delete_status.startswith("400"))
        self.assertIn("lease", delete_payload["error"])

    def test_api_paperless_status_defaults_to_not_configured(self) -> None:
        status, _, body = self._call_app("GET", "/api/paperless-status")
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("200"))
        self.assertEqual(payload["configured"], False)
        self.assertEqual(payload["reachable"], False)
        self.assertIn("nicht konfiguriert", payload["message"].lower())

    def test_api_paperless_settings_can_be_stored_and_token_is_masked(self) -> None:
        initial_status, _, initial_body = self._call_app("GET", "/api/paperless-settings")
        initial_payload = json.loads(initial_body.decode("utf-8"))
        self.assertTrue(initial_status.startswith("200"))
        self.assertEqual(initial_payload["base_url"], "")
        self.assertEqual(initial_payload["token_present"], False)
        self.assertIsNone(initial_payload["token_masked"])

        save_status, _, save_body = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org/",
                    "api_token": "this-is-a-demo-token-1234",
                }
            ).encode("utf-8"),
        )
        save_payload = json.loads(save_body.decode("utf-8"))
        self.assertTrue(save_status.startswith("200"))
        self.assertEqual(save_payload["base_url"], "https://paperless.example.org")
        self.assertEqual(save_payload["token_present"], True)
        self.assertTrue(save_payload["token_masked"].endswith("1234"))
        self.assertNotIn("this-is-a-demo-token-1234", save_payload["token_masked"])

        load_status, _, load_body = self._call_app("GET", "/api/paperless-settings")
        load_payload = json.loads(load_body.decode("utf-8"))
        self.assertTrue(load_status.startswith("200"))
        self.assertEqual(load_payload["base_url"], "https://paperless.example.org")
        self.assertEqual(load_payload["token_present"], True)
        self.assertEqual(load_payload["token_masked"], save_payload["token_masked"])

    def test_api_application_settings_can_be_stored(self) -> None:
        initial_status, _, initial_body = self._call_app("GET", "/api/application-settings")
        initial_payload = json.loads(initial_body.decode("utf-8"))
        self.assertTrue(initial_status.startswith("200"))
        self.assertEqual(initial_payload["show_delete_actions"], True)

        save_status, _, save_body = self._call_app(
            "PUT",
            "/api/application-settings",
            json.dumps({"show_delete_actions": False}).encode("utf-8"),
        )
        save_payload = json.loads(save_body.decode("utf-8"))
        self.assertTrue(save_status.startswith("200"))
        self.assertEqual(save_payload["show_delete_actions"], False)

        load_status, _, load_body = self._call_app("GET", "/api/application-settings")
        load_payload = json.loads(load_body.decode("utf-8"))
        self.assertTrue(load_status.startswith("200"))
        self.assertEqual(load_payload["show_delete_actions"], False)

    def test_api_application_export_and_import_restores_data_but_not_paperless_secrets(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "secret-token-1234",
                }
            ).encode("utf-8"),
        )
        appearance_status, _, _ = self._call_app(
            "PUT",
            "/api/application-settings",
            json.dumps({"show_delete_actions": False}).encode("utf-8"),
        )
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Backup-Mieter",
                    "email": "backup@example.org",
                    "phone": "030-121212",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        document_status, _, document_body = self._call_app(
            "POST",
            f"/api/tenants/{tenant_payload['id']}/documents",
            json.dumps(
                {
                    "documents": [
                        {
                            "paperless_document_id": "7001",
                            "filename": "backup-pass.txt",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        document_payload = json.loads(document_body.decode("utf-8"))
        exported_status, export_headers, export_body = self._call_app("GET", "/api/application-export")
        export_payload = json.loads(export_body.decode("utf-8"))

        self.assertTrue(settings_status.startswith("200"))
        self.assertTrue(appearance_status.startswith("200"))
        self.assertTrue(tenant_status.startswith("201"))
        self.assertTrue(document_status.startswith("201"))
        self.assertEqual(document_payload["documents"][0]["filename"], "backup-pass.txt")
        self.assertTrue(exported_status.startswith("200"))
        self.assertEqual(export_headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(export_payload["format_version"], 1)
        self.assertIn("tables", export_payload)
        self.assertIn("tenants", export_payload["tables"])
        self.assertIn("tenant_documents", export_payload["tables"])
        self.assertIn("application_settings", export_payload["tables"])
        self.assertNotIn("paperless_settings", export_payload["tables"])
        self.assertTrue(
            any(row["full_name"] == "Backup-Mieter" for row in export_payload["tables"]["tenants"])
        )
        exported_tenant_document = next(
            row
            for row in export_payload["tables"]["tenant_documents"]
            if row["filename"] == "backup-pass.txt"
        )
        self.assertEqual(exported_tenant_document["paperless_document_id"], "7001")
        self.assertEqual(exported_tenant_document["content_blob"]["base64"], "")

        transient_status, _, _ = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Transient",
                    "email": "transient@example.org",
                    "phone": "030-343434",
                }
            ).encode("utf-8"),
        )
        changed_settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.changed.example.org",
                    "api_token": "changed-token-9876",
                }
            ).encode("utf-8"),
        )
        toggle_back_status, _, _ = self._call_app(
            "PUT",
            "/api/application-settings",
            json.dumps({"show_delete_actions": True}).encode("utf-8"),
        )
        import_status, _, import_body = self._call_app(
            "POST",
            "/api/application-import",
            json.dumps(export_payload).encode("utf-8"),
        )
        import_payload = json.loads(import_body.decode("utf-8"))

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        application_settings_status, _, application_settings_body = self._call_app(
            "GET",
            "/api/application-settings",
        )
        application_settings_payload = json.loads(application_settings_body.decode("utf-8"))
        paperless_settings_status, _, paperless_settings_body = self._call_app(
            "GET",
            "/api/paperless-settings",
        )
        paperless_settings_payload = json.loads(paperless_settings_body.decode("utf-8"))
        document_list_status, _, document_list_body = self._call_app(
            "GET",
            f"/api/tenants/{tenant_payload['id']}/documents",
        )
        document_list_payload = json.loads(document_list_body.decode("utf-8"))
        restored_document = document_list_payload["documents"][0]
        captured_request: dict[str, str] = {}

        class FakePaperlessResponse:
            def __init__(self) -> None:
                self.status = 200
                self.headers = {
                    "Content-Type": "text/plain",
                    "Content-Disposition": 'attachment; filename="backup-pass.txt"',
                }

            def read(self) -> bytes:
                return b"Backup Dokument aus Paperless"

            def __enter__(self) -> "FakePaperlessResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        def fake_urlopen(request, timeout=0):
            captured_request["url"] = request.full_url
            captured_request["authorization"] = request.get_header("Authorization") or ""
            return FakePaperlessResponse()

        with mock.patch(
            "src.easyprent_accounting.services.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            document_download_status, document_download_headers, document_download_body = self._call_app(
                "GET",
                f"/api/tenants/{tenant_payload['id']}/documents/{restored_document['id']}/download",
                content_type="application/octet-stream",
            )

        self.assertTrue(transient_status.startswith("201"))
        self.assertTrue(changed_settings_status.startswith("200"))
        self.assertTrue(toggle_back_status.startswith("200"))
        self.assertTrue(import_status.startswith("200"))
        self.assertEqual(import_payload["format_version"], 1)
        self.assertGreater(import_payload["row_count"], 0)
        self.assertTrue(overview_status.startswith("200"))
        self.assertTrue(application_settings_status.startswith("200"))
        self.assertTrue(paperless_settings_status.startswith("200"))
        self.assertTrue(document_list_status.startswith("200"))
        self.assertTrue(document_download_status.startswith("200"))
        self.assertEqual(
            sorted(tenant["full_name"] for tenant in overview_payload["tenants"]),
            ["Anna Schulz", "Backup-Mieter", "Tim Wagner"],
        )
        self.assertEqual(application_settings_payload["show_delete_actions"], False)
        self.assertEqual(paperless_settings_payload["base_url"], "https://paperless.changed.example.org")
        self.assertTrue(paperless_settings_payload["token_present"])
        self.assertEqual(restored_document["paperless_document_id"], "7001")
        self.assertEqual(captured_request["url"], "https://paperless.changed.example.org/api/documents/7001/download/")
        self.assertEqual(captured_request["authorization"], "Token changed-token-9876")
        self.assertEqual(document_download_headers["Content-Type"], "text/plain")
        self.assertEqual(
            document_download_headers["Content-Disposition"],
            'inline; filename="backup-pass.txt"',
        )
        self.assertEqual(document_download_body, b"Backup Dokument aus Paperless")

    def test_api_can_delete_lease(self) -> None:
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Vertragsmieter",
                    "email": "lease-delete@example.org",
                    "phone": "040-1",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        first_unit_id = overview_payload["units"][0]["id"]

        lease_status, _, lease_body = self._call_app(
            "POST",
            "/api/leases",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "999.00",
                    "additional_charges_advance": "199.00",
                    "occupant_count": 1,
                    "start_date": "2026-04-01",
                    "end_date": None,
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        lease_payload = json.loads(lease_body.decode("utf-8"))
        self.assertTrue(lease_status.startswith("201"))

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/leases/{lease_payload['id']}",
        )
        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(delete_status.startswith("200"))
        self.assertEqual(delete_payload["resource"], "leases")
        self.assertEqual(delete_payload["id"], lease_payload["id"])
        self.assertEqual(delete_payload["deleted"], True)

        overview_after_status, _, overview_after_body = self._call_app("GET", "/api/overview")
        overview_after_payload = json.loads(overview_after_body.decode("utf-8"))
        self.assertTrue(overview_after_status.startswith("200"))
        self.assertFalse(
            any(lease["id"] == lease_payload["id"] for lease in overview_after_payload["leases"])
        )

    def test_api_tenant_document_upload_requires_paperless_configuration(self) -> None:
        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Dokumenten-Mieter",
                    "email": "tenant-docs@example.org",
                    "phone": "030-999999",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        upload_status, _, upload_body = self._call_app(
            "POST",
            f"/api/tenants/{tenant_payload['id']}/documents",
            json.dumps(
                {
                    "documents": [
                        {
                            "filename": "reisepass.txt",
                            "content_type": "text/plain",
                            "content_base64": base64.b64encode(b"Passdaten").decode("ascii"),
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        upload_payload = json.loads(upload_body.decode("utf-8"))
        self.assertTrue(upload_status.startswith("400"))
        self.assertIn("Paperless", upload_payload["error"])

    def test_api_tenant_documents_can_be_uploaded_to_paperless_listed_downloaded_and_deleted(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "token-12345678",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(settings_status.startswith("200"))

        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Dokumenten-Mieter",
                    "email": "tenant-docs@example.org",
                    "phone": "030-999999",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        class FakeUploadResponse:
            def __init__(self) -> None:
                self.status = 200
                self.headers = {"Content-Type": "application/json"}

            def read(self) -> bytes:
                return b'{"document_id": 7002}'

            def __enter__(self) -> "FakeUploadResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        class FakeDownloadResponse:
            def __init__(self) -> None:
                self.status = 200
                self.headers = {
                    "Content-Type": "text/plain",
                    "Content-Disposition": 'attachment; filename="reisepass.txt"',
                }

            def read(self) -> bytes:
                return b"Passdaten"

            def __enter__(self) -> "FakeDownloadResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        captured_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            captured_urls.append(request.full_url)
            if request.full_url.endswith("/post_document/"):
                return FakeUploadResponse()
            if request.full_url.endswith("/api/documents/7002/download/"):
                return FakeDownloadResponse()
            raise AssertionError(f"unexpected URL {request.full_url}")

        with mock.patch(
            "src.easyprent_accounting.services.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            upload_status, _, upload_body = self._call_app(
                "POST",
                f"/api/tenants/{tenant_payload['id']}/documents",
                json.dumps(
                    {
                        "documents": [
                            {
                                "filename": "reisepass.txt",
                                "content_type": "text/plain",
                                "content_base64": base64.b64encode(b"Passdaten").decode("ascii"),
                            }
                        ]
                    }
                ).encode("utf-8"),
            )
            upload_payload = json.loads(upload_body.decode("utf-8"))
            self.assertTrue(upload_status.startswith("201"))
            self.assertEqual(upload_payload["resource_type"], "tenant")
            self.assertEqual(upload_payload["resource_id"], tenant_payload["id"])
            self.assertEqual(len(upload_payload["documents"]), 1)
            uploaded_document = upload_payload["documents"][0]
            self.assertEqual(uploaded_document["upload_status"], "paperless_uploaded")
            self.assertEqual(uploaded_document["paperless_document_id"], "7002")

            list_status, _, list_body = self._call_app(
                "GET",
                f"/api/tenants/{tenant_payload['id']}/documents",
            )
            list_payload = json.loads(list_body.decode("utf-8"))
            self.assertTrue(list_status.startswith("200"))
            self.assertEqual(list_payload["resource_type"], "tenant")
            self.assertEqual(len(list_payload["documents"]), 1)

            download_status, download_headers, download_body = self._call_app(
                "GET",
                f"/api/tenants/{tenant_payload['id']}/documents/{uploaded_document['id']}/download",
                content_type="application/octet-stream",
            )
        self.assertTrue(download_status.startswith("200"))
        self.assertEqual(download_headers["Content-Type"], "text/plain")
        self.assertEqual(
            download_headers["Content-Disposition"],
            'inline; filename="reisepass.txt"',
        )
        self.assertEqual(download_body, b"Passdaten")
        self.assertIn("https://paperless.example.org/api/documents/post_document/", captured_urls)
        self.assertIn("https://paperless.example.org/api/documents/7002/download/", captured_urls)

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/tenants/{tenant_payload['id']}/documents/{uploaded_document['id']}",
        )
        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(delete_status.startswith("200"))
        self.assertEqual(delete_payload["resource_type"], "tenant")
        self.assertEqual(delete_payload["resource_id"], tenant_payload["id"])
        self.assertEqual(delete_payload["document_id"], uploaded_document["id"])
        self.assertTrue(delete_payload["deleted"])

    def test_api_lease_documents_can_be_linked_by_paperless_document_id(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "token-12345678",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(settings_status.startswith("200"))

        tenant_status, _, tenant_body = self._call_app(
            "POST",
            "/api/tenants",
            json.dumps(
                {
                    "full_name": "Vertragsdokument-Mieter",
                    "email": "lease-docs@example.org",
                    "phone": "040-999999",
                }
            ).encode("utf-8"),
        )
        tenant_payload = json.loads(tenant_body.decode("utf-8"))
        self.assertTrue(tenant_status.startswith("201"))

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        self.assertTrue(overview_status.startswith("200"))
        first_unit_id = overview_payload["units"][0]["id"]

        lease_status, _, lease_body = self._call_app(
            "POST",
            "/api/leases",
            json.dumps(
                {
                    "unit_id": first_unit_id,
                    "tenant_id": tenant_payload["id"],
                    "rent_cold": "888.00",
                    "additional_charges_advance": "188.00",
                    "occupant_count": 1,
                    "start_date": "2026-05-01",
                    "end_date": None,
                    "status": "active",
                }
            ).encode("utf-8"),
        )
        lease_payload = json.loads(lease_body.decode("utf-8"))
        self.assertTrue(lease_status.startswith("201"))

        link_status, _, link_body = self._call_app(
            "POST",
            f"/api/leases/{lease_payload['id']}/documents",
            json.dumps(
                {
                    "documents": [
                        {
                            "paperless_document_id": "9001",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        link_payload = json.loads(link_body.decode("utf-8"))
        self.assertTrue(link_status.startswith("201"))
        self.assertEqual(link_payload["resource_type"], "lease")
        self.assertEqual(link_payload["resource_id"], lease_payload["id"])
        self.assertEqual(len(link_payload["documents"]), 1)
        linked_document = link_payload["documents"][0]
        self.assertEqual(linked_document["paperless_document_id"], "9001")
        self.assertEqual(linked_document["upload_status"], "paperless_linked")
        self.assertEqual(
            linked_document["paperless_reference_url"],
            "https://paperless.example.org/documents/9001/details/",
        )

        list_status, _, list_body = self._call_app(
            "GET",
            f"/api/leases/{lease_payload['id']}/documents",
        )
        list_payload = json.loads(list_body.decode("utf-8"))
        self.assertTrue(list_status.startswith("200"))
        self.assertEqual(list_payload["resource_type"], "lease")
        self.assertEqual(len(list_payload["documents"]), 1)
        self.assertEqual(list_payload["documents"][0]["paperless_document_id"], "9001")

    def test_api_expense_documents_can_be_uploaded_to_paperless_listed_and_downloaded(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "token-12345678",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(settings_status.startswith("200"))

        create_status, _, create_body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Dokumentenkosten",
                    "beneficiary_name": "Test GmbH",
                    "amount": "120.00",
                    "allocation_method": "area",
                    "recurrence": "one_time",
                    "booking_date": "2025-02-01",
                }
            ).encode("utf-8"),
        )
        created_expense = json.loads(create_body.decode("utf-8"))
        self.assertTrue(create_status.startswith("201"))

        class FakeUploadResponse:
            def __init__(self, document_id: int) -> None:
                self.status = 200
                self.headers = {"Content-Type": "application/json"}
                self._document_id = document_id

            def read(self) -> bytes:
                return json.dumps({"document_id": self._document_id}).encode("utf-8")

            def __enter__(self) -> "FakeUploadResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        class FakeDownloadResponse:
            def __init__(self, filename: str, payload: bytes) -> None:
                self.status = 200
                self.headers = {
                    "Content-Type": "text/plain",
                    "Content-Disposition": f'attachment; filename="{filename}"',
                }
                self._payload = payload

            def read(self) -> bytes:
                return self._payload

            def __enter__(self) -> "FakeDownloadResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        upload_ids = iter([7101, 7102])

        def fake_urlopen(request, timeout=0):
            if request.full_url.endswith("/post_document/"):
                return FakeUploadResponse(next(upload_ids))
            if request.full_url.endswith("/api/documents/7101/download/"):
                return FakeDownloadResponse("rechnung-01.txt", b"Rechnung A")
            if request.full_url.endswith("/api/documents/7102/download/"):
                return FakeDownloadResponse("rechnung-02.txt", b"Rechnung B")
            raise AssertionError(f"unexpected URL {request.full_url}")

        with mock.patch(
            "src.easyprent_accounting.services.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            upload_status, _, upload_body = self._call_app(
                "POST",
                f"/api/expenses/{created_expense['id']}/documents",
                json.dumps(
                    {
                        "documents": [
                            {
                                "filename": "rechnung-01.txt",
                                "content_type": "text/plain",
                                "content_base64": base64.b64encode(b"Rechnung A").decode("ascii"),
                            },
                            {
                                "filename": "rechnung-02.txt",
                                "content_type": "text/plain",
                                "content_base64": base64.b64encode(b"Rechnung B").decode("ascii"),
                            },
                        ]
                    }
                ).encode("utf-8"),
            )
            upload_payload = json.loads(upload_body.decode("utf-8"))
            self.assertTrue(upload_status.startswith("201"))
            self.assertEqual(upload_payload["expense_id"], created_expense["id"])
            self.assertEqual(len(upload_payload["documents"]), 2)
            self.assertEqual(upload_payload["documents"][0]["upload_status"], "paperless_uploaded")

            list_status, _, list_body = self._call_app(
                "GET",
                f"/api/expenses/{created_expense['id']}/documents",
            )
            list_payload = json.loads(list_body.decode("utf-8"))
            self.assertTrue(list_status.startswith("200"))
            self.assertEqual(len(list_payload["documents"]), 2)
            first_document = list_payload["documents"][0]
            self.assertEqual(first_document["filename"], "rechnung-01.txt")

            download_status, download_headers, download_body = self._call_app(
                "GET",
                f"/api/expenses/{created_expense['id']}/documents/{first_document['id']}/download",
                content_type="application/octet-stream",
            )
        self.assertTrue(download_status.startswith("200"))
        self.assertEqual(download_headers["Content-Type"], "text/plain")
        self.assertEqual(
            download_headers["Content-Disposition"],
            'inline; filename="rechnung-01.txt"',
        )
        self.assertEqual(download_body, b"Rechnung A")

    def test_api_expense_documents_can_be_deleted(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "token-12345678",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(settings_status.startswith("200"))

        create_status, _, create_body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Löschkosten",
                    "beneficiary_name": "Test GmbH",
                    "amount": "77.00",
                    "allocation_method": "area",
                    "recurrence": "one_time",
                    "booking_date": "2025-02-03",
                }
            ).encode("utf-8"),
        )
        created_expense = json.loads(create_body.decode("utf-8"))
        self.assertTrue(create_status.startswith("201"))

        upload_status, _, upload_body = self._call_app(
            "POST",
            f"/api/expenses/{created_expense['id']}/documents",
            json.dumps(
                {
                    "documents": [
                        {
                            "paperless_document_id": "8111",
                            "filename": "loeschbar.txt",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        self.assertTrue(upload_status.startswith("201"))
        uploaded_document = json.loads(upload_body.decode("utf-8"))["documents"][0]

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/expenses/{created_expense['id']}/documents/{uploaded_document['id']}",
        )
        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(delete_status.startswith("200"))
        self.assertEqual(delete_payload["expense_id"], created_expense["id"])
        self.assertEqual(delete_payload["document_id"], uploaded_document["id"])
        self.assertTrue(delete_payload["deleted"])

        list_status, _, list_body = self._call_app(
            "GET",
            f"/api/expenses/{created_expense['id']}/documents",
        )
        list_payload = json.loads(list_body.decode("utf-8"))
        self.assertTrue(list_status.startswith("200"))
        self.assertEqual(list_payload["documents"], [])

    def test_api_expense_documents_can_be_linked_by_paperless_document_id(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "token-12345678",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(settings_status.startswith("200"))

        create_status, _, create_body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Referenzkosten",
                    "beneficiary_name": "Test GmbH",
                    "amount": "99.00",
                    "allocation_method": "area",
                    "recurrence": "one_time",
                    "booking_date": "2025-02-15",
                }
            ).encode("utf-8"),
        )
        created_expense = json.loads(create_body.decode("utf-8"))
        self.assertTrue(create_status.startswith("201"))

        link_status, _, link_body = self._call_app(
            "POST",
            f"/api/expenses/{created_expense['id']}/documents",
            json.dumps(
                {
                    "documents": [
                        {
                            "paperless_document_id": "4711",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        link_payload = json.loads(link_body.decode("utf-8"))
        self.assertTrue(link_status.startswith("201"))
        self.assertEqual(len(link_payload["documents"]), 1)
        linked_document = link_payload["documents"][0]
        self.assertEqual(linked_document["paperless_document_id"], "4711")
        self.assertEqual(linked_document["upload_status"], "paperless_linked")
        self.assertEqual(
            linked_document["paperless_reference_url"],
            "https://paperless.example.org/documents/4711/details/",
        )
        self.assertEqual(linked_document["content_size"], 0)

        list_status, _, list_body = self._call_app(
            "GET",
            f"/api/expenses/{created_expense['id']}/documents",
        )
        list_payload = json.loads(list_body.decode("utf-8"))
        self.assertTrue(list_status.startswith("200"))
        self.assertEqual(len(list_payload["documents"]), 1)
        self.assertEqual(list_payload["documents"][0]["paperless_document_id"], "4711")

    def test_api_expense_document_open_proxies_paperless_without_direct_user_login(self) -> None:
        settings_status, _, _ = self._call_app(
            "PUT",
            "/api/paperless-settings",
            json.dumps(
                {
                    "base_url": "https://paperless.example.org",
                    "api_token": "token-12345678",
                }
            ).encode("utf-8"),
        )
        self.assertTrue(settings_status.startswith("200"))

        create_status, _, create_body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Proxykosten",
                    "beneficiary_name": "Test GmbH",
                    "amount": "49.00",
                    "allocation_method": "area",
                    "recurrence": "one_time",
                    "booking_date": "2025-03-01",
                }
            ).encode("utf-8"),
        )
        created_expense = json.loads(create_body.decode("utf-8"))
        self.assertTrue(create_status.startswith("201"))

        link_status, _, link_body = self._call_app(
            "POST",
            f"/api/expenses/{created_expense['id']}/documents",
            json.dumps(
                {
                    "documents": [
                        {
                            "paperless_document_id": "4711",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
        self.assertTrue(link_status.startswith("201"))
        linked_document = json.loads(link_body.decode("utf-8"))["documents"][0]

        captured_request: dict[str, str] = {}

        class FakePaperlessResponse:
            def __init__(self) -> None:
                self.status = 200
                self.headers = {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": 'attachment; filename="paperless-4711.pdf"',
                }

            def read(self) -> bytes:
                return b"%PDF-1.4 proxy"

            def __enter__(self) -> "FakePaperlessResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        def fake_urlopen(request, timeout=0):
            captured_request["url"] = request.full_url
            captured_request["authorization"] = request.get_header("Authorization") or ""
            return FakePaperlessResponse()

        with mock.patch(
            "src.easyprent_accounting.services.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            open_status, open_headers, open_body = self._call_app(
                "GET",
                f"/api/expenses/{created_expense['id']}/documents/{linked_document['id']}/download",
                content_type="application/octet-stream",
            )

        self.assertTrue(open_status.startswith("200"))
        self.assertEqual(
            captured_request["url"],
            "https://paperless.example.org/api/documents/4711/download/",
        )
        self.assertEqual(captured_request["authorization"], "Token token-12345678")
        self.assertEqual(open_headers["Content-Type"], "application/pdf")
        self.assertEqual(
            open_headers["Content-Disposition"],
            'inline; filename="paperless-4711.pdf"',
        )
        self.assertEqual(open_body, b"%PDF-1.4 proxy")

    def test_api_expense_creation_returns_created_json(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Versicherung",
                    "beneficiary_name": "Allianz SE",
                    "label": "OpenAPI Testkosten",
                    "amount": "275.00",
                    "allocation_method": "area",
                    "recurrence": "recurring",
                    "interval": "yearly",
                    "period_start": "2025-01-01",
                    "period_end": "2027-12-31",
                }
            ).encode("utf-8"),
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("201"))
        self.assertEqual(payload["label"], "OpenAPI Testkosten")
        self.assertEqual(payload["expense_category"], "Versicherung")
        self.assertEqual(payload["beneficiary_name"], "Allianz SE")
        self.assertEqual(payload["charge_type"], "yearly")
        self.assertEqual(payload["object_type"], "property")
        self.assertEqual(payload["object_id"], 1)

    def test_api_expense_creation_derives_label_from_expense_category(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Versicherung",
                    "beneficiary_name": "Allianz SE",
                    "amount": "275.00",
                    "allocation_method": "area",
                    "recurrence": "one_time",
                    "booking_date": "2025-04-01",
                }
            ).encode("utf-8"),
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("201"))
        self.assertEqual(payload["expense_category"], "Versicherung")
        self.assertEqual(payload["label"], "Versicherung")

    def test_api_expense_creation_supports_unit_target_and_single_date(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Türreparatur",
                    "amount": "190.00",
                    "allocation_method": "unit_count",
                    "recurrence": "one_time",
                    "booking_date": "2025-06-15",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("201"))
        self.assertEqual(payload["object_type"], "unit")
        self.assertEqual(payload["object_id"], 1)
        self.assertEqual(payload["booking_date"], "2025-06-15")

    def test_api_expense_creation_supports_one_time_optional_period(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Sonderumlage",
                    "beneficiary_name": "Dienstleister AG",
                    "amount": "190.00",
                    "allocation_method": "unit_count",
                    "recurrence": "one_time",
                    "period_start": "2025-06-01",
                    "period_end": "2025-06-30",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("201"))
        self.assertEqual(payload["charge_type"], "one_time")
        self.assertEqual(payload["period_start"], "2025-06-01")
        self.assertEqual(payload["period_end"], "2025-06-30")
        self.assertEqual(payload["booking_date"], "2025-06-01")

    def test_api_expense_creation_rejects_one_time_partial_period(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Sonderumlage",
                    "beneficiary_name": "Dienstleister AG",
                    "amount": "190.00",
                    "allocation_method": "unit_count",
                    "recurrence": "one_time",
                    "period_start": "2025-06-01",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("400"))
        self.assertIn("period_start", payload["error"])
        self.assertIn("period_end", payload["error"])

    def test_api_can_update_expense(self) -> None:
        create_status, _, create_body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Türreparatur",
                    "amount": "190.00",
                    "allocation_method": "unit_count",
                    "recurrence": "one_time",
                    "booking_date": "2025-06-15",
                }
            ).encode("utf-8"),
        )
        created = json.loads(create_body.decode("utf-8"))

        update_status, _, update_body = self._call_app(
            "PUT",
            f"/api/expenses/{created['id']}",
            json.dumps(
                {
                    "object_type": "building",
                    "object_id": 1,
                    "label": "Gebäudereinigung",
                    "amount": "75.00",
                    "allocation_method": "area",
                    "recurrence": "recurring",
                    "interval": "monthly",
                    "period_start": "2025-01-01",
                    "period_end": "2025-03-31",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(update_body.decode("utf-8"))
        self.assertTrue(create_status.startswith("201"))
        self.assertTrue(update_status.startswith("200"))
        self.assertEqual(payload["label"], "Gebäudereinigung")
        self.assertEqual(payload["object_type"], "building")
        self.assertEqual(payload["charge_type"], "monthly")

    def test_api_overview_expense_does_not_expose_property_name(self) -> None:
        status, _, body = self._call_app("GET", "/api/overview")

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("200"))
        self.assertTrue(payload["expenses"])
        self.assertNotIn("property_name", payload["expenses"][0])
        self.assertIn("expense_category", payload["expenses"][0])
        self.assertIn("beneficiary_name", payload["expenses"][0])
        self.assertTrue(payload["expense_categories"])
        self.assertIn("expense_category", payload["expense_categories"][0])
        self.assertIn("beneficiary_name", payload["expense_categories"][0])

    def test_api_expense_requires_consumption_unit_for_consumption_costs(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "property",
                    "object_id": 1,
                    "label": "Wasser",
                    "amount": "400.00",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("400"))
        self.assertIn("consumption_unit", payload["error"])
        self.assertIn("meter_id", payload["error"])

    def test_api_can_create_meter_and_meter_reading(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserzähler A-01",
                    "meter_type": "water",
                    "unit": "m3",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))

        reading_status, _, reading_body = self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-03-31",
                    "reading_value": "44.8",
                }
            ).encode("utf-8"),
        )
        reading_payload = json.loads(reading_body.decode("utf-8"))

        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(reading_status.startswith("201"))
        self.assertEqual(meter_payload["unit"], "m3")
        self.assertEqual(reading_payload["meter_id"], meter_payload["id"])
        self.assertEqual(reading_payload["reading_date"], "2025-03-31")

    def test_api_can_update_meter_master_data(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserzähler A-01",
                    "meter_type": "water",
                    "unit": "m3",
                    "serial_number": "ALT-1",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))

        update_status, _, update_body = self._call_app(
            "PUT",
            "/api/meters/" + str(meter_payload["id"]),
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserzähler Bad",
                    "meter_type": "Kaltwasser",
                    "unit": "m3",
                    "serial_number": "NEU-2",
                }
            ).encode("utf-8"),
        )
        update_payload = json.loads(update_body.decode("utf-8"))

        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(update_status.startswith("200"))
        self.assertEqual(update_payload["label"], "Wasserzähler Bad")
        self.assertEqual(update_payload["serial_number"], "NEU-2")

    def test_api_rejects_meter_reading_that_breaks_monotonic_order(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Stromzähler A-01",
                    "meter_type": "power",
                    "unit": "kWh",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))

        first_status, _, _ = self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-03-01",
                    "reading_value": "100",
                }
            ).encode("utf-8"),
        )
        second_status, _, second_body = self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-04-01",
                    "reading_value": "90",
                }
            ).encode("utf-8"),
        )

        second_payload = json.loads(second_body.decode("utf-8"))
        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(first_status.startswith("201"))
        self.assertTrue(second_status.startswith("400"))
        self.assertIn("previous", second_payload["error"])

    def test_api_overview_contains_full_meter_reading_history(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Heizzähler A-01",
                    "meter_type": "heating",
                    "unit": "kWh",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))
        self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-01-15",
                    "reading_value": "10",
                }
            ).encode("utf-8"),
        )
        self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-02-15",
                    "reading_value": "18",
                }
            ).encode("utf-8"),
        )
        status, _, body = self._call_app("GET", "/api/overview")

        payload = json.loads(body.decode("utf-8"))
        meter_readings = payload["meter_readings"]
        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(status.startswith("200"))
        self.assertEqual(len(meter_readings), 2)
        self.assertEqual(meter_readings[0]["reading_date"], "2025-01-15")
        self.assertEqual(meter_readings[1]["reading_date"], "2025-02-15")
        self.assertEqual(meter_readings[1]["meter_label"], "Heizzähler A-01")

    def test_api_can_delete_meter_reading(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserzähler A-02",
                    "meter_type": "water",
                    "unit": "m3",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))
        _, _, first_body = self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-01-31",
                    "reading_value": "11",
                }
            ).encode("utf-8"),
        )
        _, _, second_body = self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-02-28",
                    "reading_value": "19",
                }
            ).encode("utf-8"),
        )
        first_payload = json.loads(first_body.decode("utf-8"))
        second_payload = json.loads(second_body.decode("utf-8"))

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/meter-readings/{second_payload['id']}",
        )
        overview_status, _, overview_body = self._call_app("GET", "/api/overview")

        delete_payload = json.loads(delete_body.decode("utf-8"))
        overview_payload = json.loads(overview_body.decode("utf-8"))
        meter_rows = [meter for meter in overview_payload["meters"] if meter["id"] == meter_payload["id"]]
        reading_rows = [
            reading for reading in overview_payload["meter_readings"] if reading["meter_id"] == meter_payload["id"]
        ]

        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(delete_status.startswith("200"))
        self.assertTrue(overview_status.startswith("200"))
        self.assertEqual(delete_payload["id"], second_payload["id"])
        self.assertEqual(delete_payload["deleted"], True)
        self.assertEqual(len(meter_rows), 1)
        self.assertEqual(meter_rows[0]["latest_reading_date"], first_payload["reading_date"])
        self.assertEqual(str(meter_rows[0]["latest_reading_value"]), first_payload["reading_value"])
        self.assertEqual(len(reading_rows), 1)

    def test_api_rejects_delete_for_unknown_meter_reading(self) -> None:
        delete_status, _, delete_body = self._call_app(
            "DELETE",
            "/api/meter-readings/9999",
        )

        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(delete_status.startswith("400"))
        self.assertIn("not found", delete_payload["error"])

    def test_api_consumption_expense_accepts_meter_without_consumption_unit(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserzähler A-01",
                    "meter_type": "water",
                    "unit": "m3",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))

        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserkosten A-01",
                    "amount": "430.00",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "meter_id": meter_payload["id"],
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(status.startswith("201"))
        self.assertEqual(payload["meter_id"], meter_payload["id"])
        self.assertEqual(payload["consumption_unit"], "m3")
        self.assertEqual(payload["meter_unit"], "m3")
        self.assertIsNone(payload["consumption_value"])

    def test_api_consumption_expense_requires_conversion_factor_for_different_meter_unit(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Gaszähler A-01",
                    "meter_type": "gas",
                    "unit": "m3",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))

        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Gaskosten A-01",
                    "amount": "0.12",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "meter_id": meter_payload["id"],
                    "consumption_unit": "kWh",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(status.startswith("400"))
        self.assertIn("conversion_factor", payload["error"])

    def test_api_consumption_expense_with_conversion_calculates_total_amount(self) -> None:
        meter_status, _, meter_body = self._call_app(
            "POST",
            "/api/meters",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Gaszähler A-01",
                    "meter_type": "gas",
                    "unit": "m3",
                }
            ).encode("utf-8"),
        )
        meter_payload = json.loads(meter_body.decode("utf-8"))
        self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2025-01-01",
                    "reading_value": "100",
                }
            ).encode("utf-8"),
        )
        self._call_app(
            "POST",
            "/api/meter-readings",
            json.dumps(
                {
                    "meter_id": meter_payload["id"],
                    "reading_date": "2026-01-01",
                    "reading_value": "130",
                }
            ).encode("utf-8"),
        )

        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Gaskosten A-01",
                    "amount": "0.12",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "meter_id": meter_payload["id"],
                    "consumption_unit": "kWh",
                    "conversion_factor": "10.5",
                    "consumption_value": "999",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(meter_status.startswith("201"))
        self.assertTrue(status.startswith("201"))
        self.assertEqual(payload["meter_unit"], "m3")
        self.assertEqual(payload["consumption_unit"], "kWh")
        self.assertEqual(payload["effective_consumption_value"], "315")
        self.assertEqual(payload["total_amount"], "37.80")
        self.assertIsNone(payload["consumption_value"])

    def test_api_consumption_expense_rejects_more_than_ten_decimal_amount(self) -> None:
        status, _, body = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Gaspreis zu fein",
                    "amount": "0.12345678901",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "consumption_unit": "kWh",
                    "consumption_value": "12",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                }
            ).encode("utf-8"),
        )

        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(status.startswith("400"))
        self.assertIn("amount", payload["error"])
        self.assertIn("10", payload["error"])

    def test_api_settlement_includes_unit_target_expense(self) -> None:
        create_status, _, _ = self._call_app(
            "POST",
            "/api/expenses",
            json.dumps(
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wohnungswartung",
                    "amount": "110.00",
                    "allocation_method": "unit_count",
                    "recurrence": "one_time",
                    "booking_date": "2025-02-10",
                }
            ).encode("utf-8"),
        )
        settlement_status, _, settlement_body = self._call_app(
            "GET",
            "/api/settlements",
            query_string="property_id=1&period_start=2025-01-01&period_end=2025-12-31",
        )

        payload = json.loads(settlement_body.decode("utf-8"))
        labels = {
            line_item["label"]
            for result in payload["results"]
            for line_item in result["line_items"]
        }
        self.assertTrue(create_status.startswith("201"))
        self.assertTrue(settlement_status.startswith("200"))
        self.assertIn("Wohnungswartung", labels)

    def test_api_can_create_building_unit_and_room(self) -> None:
        building_status, _, building_body = self._call_app(
            "POST",
            "/api/buildings",
            json.dumps(
                {
                    "property_id": 1,
                    "name": "Haus B",
                    "year_built": 2010,
                    "street": "Parkstrasse 1",
                    "city": "Berlin",
                    "postal_code": "10117",
                }
            ).encode("utf-8"),
        )
        building_payload = json.loads(building_body.decode("utf-8"))
        self.assertTrue(building_status.startswith("201"))
        self.assertEqual(building_payload["name"], "Haus B")
        self.assertEqual(building_payload["street"], "Parkstrasse 1")

        unit_status, _, unit_body = self._call_app(
            "POST",
            "/api/units",
            json.dumps(
                {
                    "building_id": building_payload["id"],
                    "label": "B-01",
                    "area_sqm": "71.5",
                    "room_count": 3,
                    "street": "Parkstrasse 1",
                    "city": "Berlin",
                    "postal_code": "10117",
                }
            ).encode("utf-8"),
        )
        unit_payload = json.loads(unit_body.decode("utf-8"))
        self.assertTrue(unit_status.startswith("201"))
        self.assertEqual(unit_payload["label"], "B-01")
        self.assertEqual(unit_payload["street"], "Parkstrasse 1")

        room_status, _, room_body = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": unit_payload["id"],
                    "label": "Wohnzimmer",
                    "area_sqm": "18.5",
                }
            ).encode("utf-8"),
        )
        room_payload = json.loads(room_body.decode("utf-8"))
        self.assertTrue(room_status.startswith("201"))
        self.assertEqual(room_payload["label"], "Wohnzimmer")
        self.assertEqual(room_payload["area_sqm"], "18.5")

        room_update_status, _, room_update_body = self._call_app(
            "PUT",
            f"/api/rooms/{room_payload['id']}",
            json.dumps(
                {
                    "unit_id": unit_payload["id"],
                    "label": "Wohnzimmer Nord",
                    "area_sqm": "19.25",
                }
            ).encode("utf-8"),
        )
        room_update_payload = json.loads(room_update_body.decode("utf-8"))
        self.assertTrue(room_update_status.startswith("200"))
        self.assertEqual(room_update_payload["label"], "Wohnzimmer Nord")
        self.assertEqual(room_update_payload["area_sqm"], "19.25")

        overview_status, _, overview_body = self._call_app("GET", "/api/overview")
        overview_payload = json.loads(overview_body.decode("utf-8"))
        persisted_room = next(
            room for room in overview_payload["rooms"] if room["id"] == room_payload["id"]
        )
        self.assertTrue(overview_status.startswith("200"))
        self.assertEqual(persisted_room["label"], "Wohnzimmer Nord")
        self.assertEqual(persisted_room["area_sqm"], "19.25")

    def test_api_rejects_room_creation_above_unit_room_count(self) -> None:
        first_status, _, _ = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": 2,
                    "label": "Zimmer 1",
                }
            ).encode("utf-8"),
        )
        second_status, _, _ = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": 2,
                    "label": "Zimmer 2",
                }
            ).encode("utf-8"),
        )
        third_status, _, third_body = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": 2,
                    "label": "Zimmer 3",
                }
            ).encode("utf-8"),
        )

        third_payload = json.loads(third_body.decode("utf-8"))
        self.assertTrue(first_status.startswith("201"))
        self.assertTrue(second_status.startswith("201"))
        self.assertTrue(third_status.startswith("400"))
        self.assertIn("room_count", third_payload["error"])

    def test_api_can_archive_and_delete_room(self) -> None:
        room_status, _, room_body = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": 1,
                    "label": "Archivzimmer",
                }
            ).encode("utf-8"),
        )
        room_payload = json.loads(room_body.decode("utf-8"))

        archive_status, _, archive_body = self._call_app(
            "POST",
            f"/api/rooms/{room_payload['id']}/archive",
        )
        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/rooms/{room_payload['id']}",
        )

        archive_payload = json.loads(archive_body.decode("utf-8"))
        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(room_status.startswith("201"))
        self.assertTrue(archive_status.startswith("200"))
        self.assertTrue(delete_status.startswith("200"))
        self.assertEqual(archive_payload["id"], room_payload["id"])
        self.assertEqual(archive_payload["is_archived"], 1)
        self.assertEqual(delete_payload["deleted"], True)

    def test_api_can_restore_archived_room(self) -> None:
        room_status, _, room_body = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": 1,
                    "label": "Rueckholzimmer",
                }
            ).encode("utf-8"),
        )
        room_payload = json.loads(room_body.decode("utf-8"))

        archive_status, _, _ = self._call_app(
            "POST",
            f"/api/rooms/{room_payload['id']}/archive",
        )
        restore_status, _, restore_body = self._call_app(
            "POST",
            f"/api/rooms/{room_payload['id']}/restore",
        )

        restore_payload = json.loads(restore_body.decode("utf-8"))
        self.assertTrue(room_status.startswith("201"))
        self.assertTrue(archive_status.startswith("200"))
        self.assertTrue(restore_status.startswith("200"))
        self.assertEqual(restore_payload["id"], room_payload["id"])
        self.assertEqual(restore_payload["is_archived"], 0)
        self.assertIsNone(restore_payload["archived_at"])

    def test_api_rejects_delete_for_active_room(self) -> None:
        room_status, _, room_body = self._call_app(
            "POST",
            "/api/rooms",
            json.dumps(
                {
                    "unit_id": 1,
                    "label": "Direktloeschung",
                }
            ).encode("utf-8"),
        )
        room_payload = json.loads(room_body.decode("utf-8"))

        delete_status, _, delete_body = self._call_app(
            "DELETE",
            f"/api/rooms/{room_payload['id']}",
        )

        delete_payload = json.loads(delete_body.decode("utf-8"))
        self.assertTrue(room_status.startswith("201"))
        self.assertTrue(delete_status.startswith("400"))
        self.assertIn("archived", delete_payload["error"])


if __name__ == "__main__":
    unittest.main()
