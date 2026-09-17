from __future__ import annotations

import json
from .config import get_global_config


from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .asset_registry import AssetRegistry
from .db import get_connection
from .depreciation import Depreciation
from .integrations.paperless import PaperlessAdapter, UrllibPaperlessAdapter
from .linked_documents import LinkedDocuments, get_paperless_status
from .metering import Metering
from .expenses import Expenses
from .openapi import build_openapi_document
from .tenancy import Tenancy
from .settlement_documents import SettlementDocuments
from .settlement_runs import (
    create_or_open_settlement_run,
    consider_all_settlement_payments,
    get_settlement_run_overview,
    find_settlement_run_id,
    import_gnucash_payments_for_period,
    refresh_settlement_run_payments,
    set_settlement_payment_considered,
)
from .settlements import Settlements
from .dashboard import Dashboard
from .services import (
    health_status,
)
from .settings import (
    get_application_settings,
    get_gnucash_settings,
    get_paperless_settings,
    update_application_settings,
    update_paperless_settings,
    update_gnucash_settings,
    export_application_data,
    import_application_data,    list_gnucash_accounts,
)




STATIC_DIR = Path(__file__).with_name("static")
LIFECYCLE_RESOURCES = {"properties", "buildings", "units", "rooms", "meters", "expenses"}
ASSET_RESOURCE_NAMES = {
    "properties": "property",
    "buildings": "building",
    "units": "unit",
    "rooms": "room",
}


def json_response(start_response, status: HTTPStatus, payload: dict | list) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))],
    )
    return [body]


def html_response(start_response, html: str) -> list[bytes]:
    body = html.encode("utf-8")
    start_response(
        "200 OK",
        [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))],
    )
    return [body]


def text_response(start_response, status: HTTPStatus, body: str, content_type: str) -> list[bytes]:
    encoded = body.encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", content_type), ("Content-Length", str(len(encoded)))],
    )
    return [encoded]


def bytes_response(
    start_response,
    status: HTTPStatus,
    body: bytes,
    content_type: str,
    filename: str | None = None,
    disposition: str = "inline",
) -> list[bytes]:
    headers = [("Content-Type", content_type), ("Content-Length", str(len(body)))]
    if filename:
        safe_name = filename.replace('"', "_")
        headers.append(("Content-Disposition", f'{disposition}; filename="{safe_name}"'))
    start_response(f"{status.value} {status.phrase}", headers)
    return [body]


def read_json(environ) -> dict:
    size = int(environ.get("CONTENT_LENGTH") or 0)
    raw = environ["wsgi.input"].read(size).decode("utf-8") if size else "{}"
    return json.loads(raw or "{}")


def read_form(environ) -> dict:
    size = int(environ.get("CONTENT_LENGTH") or 0)
    raw = environ["wsgi.input"].read(size).decode("utf-8") if size else ""
    parsed = parse_qs(raw)
    return {key: values[0] for key, values in parsed.items()}


def _optional_query_int(params: dict[str, list[str]], name: str) -> int | None:
    raw_value = params.get(name, [""])[0].strip()
    if raw_value.lower() in {"", "null", "undefined"}:
        return None
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def redirect_response(start_response, location: str) -> list[bytes]:
    start_response("303 See Other", [("Location", location), ("Content-Length", "0")])
    return [b""]


def static_file_response(start_response, filename: str, content_type: str) -> list[bytes]:
    body = (STATIC_DIR / filename).read_text(encoding="utf-8")
    return text_response(start_response, HTTPStatus.OK, body, content_type)


def parse_object_lifecycle_path(path: str) -> tuple[str, int, str] | None:
    segments = [segment for segment in path.split("/") if segment]
    if (
        len(segments) == 4
        and segments[0] == "api"
        and segments[1] in LIFECYCLE_RESOURCES
        and segments[3] in {"archive", "restore"}
    ):
        try:
            return segments[1], int(segments[2]), segments[3]
        except ValueError:
            return None
    if len(segments) == 3 and segments[0] == "api" and segments[1] in LIFECYCLE_RESOURCES:
        try:
            return segments[1], int(segments[2]), "delete"
        except ValueError:
            return None
    return None


def parse_expense_documents_path(path: str) -> tuple[str, int, int | None] | None:
    segments = [segment for segment in path.split("/") if segment]
    if (
        len(segments) == 4
        and segments[0] == "api"
        and segments[1] == "expenses"
        and segments[2].isdigit()
        and segments[3] == "documents"
    ):
        return "collection", int(segments[2]), None
    if (
        len(segments) == 5
        and segments[0] == "api"
        and segments[1] == "expenses"
        and segments[2].isdigit()
        and segments[3] == "documents"
        and segments[4].isdigit()
    ):
        return "item", int(segments[2]), int(segments[4])
    if (
        len(segments) == 6
        and segments[0] == "api"
        and segments[1] == "expenses"
        and segments[2].isdigit()
        and segments[3] == "documents"
        and segments[4].isdigit()
        and segments[5] == "download"
    ):
        return "download", int(segments[2]), int(segments[4])
    return None


def parse_resource_documents_path(
    path: str,
    resource_segment: str,
) -> tuple[str, int, int | None] | None:
    segments = [segment for segment in path.split("/") if segment]
    if (
        len(segments) == 4
        and segments[0] == "api"
        and segments[1] == resource_segment
        and segments[2].isdigit()
        and segments[3] == "documents"
    ):
        return "collection", int(segments[2]), None
    if (
        len(segments) == 5
        and segments[0] == "api"
        and segments[1] == resource_segment
        and segments[2].isdigit()
        and segments[3] == "documents"
        and segments[4].isdigit()
    ):
        return "item", int(segments[2]), int(segments[4])
    if (
        len(segments) == 6
        and segments[0] == "api"
        and segments[1] == resource_segment
        and segments[2].isdigit()
        and segments[3] == "documents"
        and segments[4].isdigit()
        and segments[5] == "download"
    ):
        return "download", int(segments[2]), int(segments[4])
    return None


def render_app_shell() -> str:
    return """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EasyPrent Accounting</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <div class="shell-links">
    <a href="/openapi.json">OpenAPI JSON</a>
  </div>
  <div id="root"></div>
  <noscript>Die Oberfläche benötigt JavaScript, um die React-Anwendung auszuführen.</noscript>
  <script>
    window.__EASYPRENT_BOOTSTRAP__ = {
      settlementPeriodStart: "2025-01-01",
      settlementPeriodEnd: "2025-12-31",
      depreciationYear: 2025,
      openApiUrl: "/openapi.json"
    };
  </script>
  <script src="/static/vendor/react.production.min.js"></script>
  <script src="/static/vendor/react-dom.production.min.js"></script>
  <script src="/static/vendor/echarts.min.js"></script>
  <script src="/static/app_helpers.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>"""


def application(
    environ, start_response, paperless_adapter: PaperlessAdapter | None = None
):
    method = environ["REQUEST_METHOD"]
    parsed = urlparse(environ["PATH_INFO"])
    path = parsed.path

    if method == "GET" and path == "/":
        return html_response(start_response, render_app_shell())

    if method == "GET" and path == "/openapi.json":
        return json_response(start_response, HTTPStatus.OK, build_openapi_document())

    if method == "GET" and path == "/api/health":
        return json_response(start_response, HTTPStatus.OK, health_status())

    if method == "GET" and path == "/static/app.js":
        return static_file_response(
            start_response,
            "app.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_main.js":
        return static_file_response(
            start_response,
            "app_main.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_domain.js":
        return static_file_response(
            start_response,
            "app_domain.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_charts.js":
        return static_file_response(
            start_response,
            "app_charts.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_sections.js":
        return static_file_response(
            start_response,
            "app_sections.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_forms.js":
        return static_file_response(
            start_response,
            "app_forms.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_previews.js":
        return static_file_response(
            start_response,
            "app_previews.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app_helpers.js":
        return static_file_response(
            start_response,
            "app_helpers.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/app.css":
        return static_file_response(
            start_response,
            "app.css",
            "text/css; charset=utf-8",
        )

    if method == "GET" and path == "/static/vendor/react.production.min.js":
        return static_file_response(
            start_response,
            "vendor/react.production.min.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/vendor/react-dom.production.min.js":
        return static_file_response(
            start_response,
            "vendor/react-dom.production.min.js",
            "application/javascript; charset=utf-8",
        )

    if method == "GET" and path == "/static/vendor/echarts.min.js":
        return static_file_response(
            start_response,
            "vendor/echarts.min.js",
            "application/javascript; charset=utf-8",
        )

    cfg = get_global_config()
    connection = get_connection(cfg.db_path)
    paperless = paperless_adapter if paperless_adapter is not None else UrllibPaperlessAdapter()
    documents = LinkedDocuments(connection, paperless)
    assets = AssetRegistry(connection)
    metering = Metering(connection)
    expenses = Expenses(connection)
    tenancy = Tenancy(connection)
    try:
        lifecycle_route = parse_object_lifecycle_path(path)
        if lifecycle_route is not None:
            resource_name, object_id, action = lifecycle_route
            try:
                if (method == "POST" and action in {"archive", "restore"}) or (
                    method == "DELETE" and action == "delete"
                ):
                    if resource_name in ASSET_RESOURCE_NAMES:
                        operation = getattr(
                            assets, f"{action}_{ASSET_RESOURCE_NAMES[resource_name]}"
                        )
                        with connection:
                            result = operation(object_id)
                    elif resource_name == "meters":
                        operation = getattr(metering, f"{action}_meter")
                        with connection:
                            result = operation(object_id)
                    else:
                        with connection:
                            result = getattr(expenses, action)(object_id)
                    return json_response(start_response, HTTPStatus.OK, result)
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "GET" and path == "/api/overview":
            overview = Dashboard(connection).summary()
            asset_data = assets.list_assets()
            tenancy_data = tenancy.list_tenancy()
            expense_data = expenses.list_expenses()
            meter_data = metering.list_meters()
            depreciation_assets = Depreciation(connection).list_assets()
            overview["properties"] = asset_data["properties"]
            overview["buildings"] = asset_data["buildings"]
            overview["units"] = asset_data["units"]
            overview["rooms"] = asset_data["rooms"]
            overview["tenants"] = tenancy_data["tenants"]
            overview["leases"] = tenancy_data["leases"]
            overview["expenses"] = expense_data["expenses"]
            overview["expense_categories"] = expense_data["expense_categories"]
            overview["meters"] = meter_data["meters"]
            overview["meter_readings"] = meter_data["meter_readings"]
            overview["depreciation_assets"] = depreciation_assets
            return json_response(start_response, HTTPStatus.OK, overview)

        if method == "GET" and path == "/api/paperless-settings":
            return json_response(start_response, HTTPStatus.OK, get_paperless_settings(connection))

        if method == "GET" and path == "/api/paperless-status":
            return json_response(
                start_response, HTTPStatus.OK, get_paperless_status(connection, paperless)
            )

        if method == "GET" and path == "/api/application-settings":
            return json_response(start_response, HTTPStatus.OK, get_application_settings(connection))

        if method == "GET" and path == "/api/gnucash-settings":
            return json_response(start_response, HTTPStatus.OK, get_gnucash_settings(connection))

        if method == "GET" and path == "/api/gnucash-accounts":
            try:
                return json_response(start_response, HTTPStatus.OK, list_gnucash_accounts(connection))
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "GET" and path == "/api/application-export":
            return json_response(start_response, HTTPStatus.OK, export_application_data(connection))

        if method == "PUT" and path == "/api/paperless-settings":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.OK,
                    update_paperless_settings(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "PUT" and path == "/api/application-settings":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.OK,
                    update_application_settings(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "PUT" and path == "/api/gnucash-settings":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.OK,
                    update_gnucash_settings(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "POST" and path == "/api/application-import":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.OK,
                    import_application_data(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        expense_document_route = parse_expense_documents_path(path)
        if expense_document_route is not None:
            route_type, expense_id, document_id = expense_document_route
            try:
                if method == "GET" and route_type == "collection":
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        documents.list("expense", expense_id),
                    )
                if method == "POST" and route_type == "collection":
                    with connection:
                        result = documents.add("expense", expense_id, read_json(environ))
                    return json_response(start_response, HTTPStatus.CREATED, result)
                if method == "DELETE" and route_type == "item" and document_id is not None:
                    with connection:
                        result = documents.delete("expense", expense_id, document_id)
                    return json_response(start_response, HTTPStatus.OK, result)
                if method == "GET" and route_type == "download" and document_id is not None:
                    document_payload = documents.download("expense", expense_id, document_id)
                    return bytes_response(
                        start_response,
                        HTTPStatus.OK,
                        document_payload["content_blob"],
                        document_payload["content_type"],
                        filename=document_payload["filename"],
                    )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        tenant_document_route = parse_resource_documents_path(path, "tenants")
        if tenant_document_route is not None:
            route_type, tenant_id, document_id = tenant_document_route
            try:
                if method == "GET" and route_type == "collection":
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        documents.list("tenant", tenant_id),
                    )
                if method == "POST" and route_type == "collection":
                    with connection:
                        result = documents.add("tenant", tenant_id, read_json(environ))
                    return json_response(start_response, HTTPStatus.CREATED, result)
                if method == "DELETE" and route_type == "item" and document_id is not None:
                    with connection:
                        result = documents.delete("tenant", tenant_id, document_id)
                    return json_response(start_response, HTTPStatus.OK, result)
                if method == "GET" and route_type == "download" and document_id is not None:
                    document_payload = documents.download("tenant", tenant_id, document_id)
                    return bytes_response(
                        start_response,
                        HTTPStatus.OK,
                        document_payload["content_blob"],
                        document_payload["content_type"],
                        filename=document_payload["filename"],
                    )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        lease_document_route = parse_resource_documents_path(path, "leases")
        if lease_document_route is not None:
            route_type, lease_id, document_id = lease_document_route
            try:
                if method == "GET" and route_type == "collection":
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        documents.list("lease", lease_id),
                    )
                if method == "POST" and route_type == "collection":
                    with connection:
                        result = documents.add("lease", lease_id, read_json(environ))
                    return json_response(start_response, HTTPStatus.CREATED, result)
                if method == "DELETE" and route_type == "item" and document_id is not None:
                    with connection:
                        result = documents.delete("lease", lease_id, document_id)
                    return json_response(start_response, HTTPStatus.OK, result)
                if method == "GET" and route_type == "download" and document_id is not None:
                    document_payload = documents.download("lease", lease_id, document_id)
                    return bytes_response(
                        start_response,
                        HTTPStatus.OK,
                        document_payload["content_blob"],
                        document_payload["content_type"],
                        filename=document_payload["filename"],
                    )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "GET" and path == "/api/settlements":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                unit_id = _optional_query_int(params, "unit_id")
                property_id = _optional_query_int(params, "property_id")
                period_start = params.get("period_start", ["2025-01-01"])[0]
                period_end = params.get("period_end", ["2025-12-31"])[0]
                settlement = Settlements(connection).for_period(
                    property_id, period_start, period_end, unit_id
                )
            except (TypeError, ValueError) as error:
                return json_response(
                    start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)}
                )
            return json_response(start_response, HTTPStatus.OK, settlement)

        if method == "GET" and path == "/api/settlement-runs":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                property_id = _optional_query_int(params, "property_id")
                unit_id = _optional_query_int(params, "unit_id")
                year = int(params.get("year", [""])[0])
                if (property_id is None) == (unit_id is None):
                    raise ValueError("settlement run requires exactly one property or standalone unit")
                settlement_id = find_settlement_run_id(connection, property_id, unit_id, year)
                return json_response(start_response, HTTPStatus.OK, {"id": settlement_id})
            except (TypeError, ValueError) as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "POST" and path == "/api/settlement-runs":
            try:
                with connection:
                    settlement_run, created = create_or_open_settlement_run(
                        connection, read_json(environ)
                    )
                return json_response(
                    start_response,
                    HTTPStatus.CREATED if created else HTTPStatus.OK,
                    settlement_run,
                )
            except (TypeError, ValueError) as error:
                return json_response(
                    start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)}
                )

        if method == "POST" and path.startswith("/api/settlement-runs/"):
            suffix = path.removeprefix("/api/settlement-runs/")
            settlement_id, separator, payment_path = suffix.partition("/payments/")
            try:
                if separator and payment_path == "refresh":
                    with connection:
                        refreshed = refresh_settlement_run_payments(connection, settlement_id)
                        overview = get_settlement_run_overview(connection, settlement_id)
                    return json_response(start_response, HTTPStatus.OK, {"import": refreshed, "overview": overview})
                if separator and payment_path == "consider-all":
                    with connection:
                        overview = consider_all_settlement_payments(connection, settlement_id)
                    return json_response(start_response, HTTPStatus.OK, overview)
                split_guid, action_separator, action = payment_path.rpartition("/")
                if separator and action in {"consider", "unassign"} and split_guid:
                    with connection:
                        overview = set_settlement_payment_considered(
                            connection, settlement_id, split_guid, action == "consider"
                        )
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        overview,
                    )
            except (TypeError, ValueError) as error:
                return json_response(
                    start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)}
                )

        if method == "GET" and path.startswith("/api/settlement-runs/") and "/leases/" in path:
            settlement_id, _, lease_path = path.removeprefix("/api/settlement-runs/").partition("/leases/")
            lease_id_text, _, document_name = lease_path.partition("/")
            if document_name == "document.ods":
                try:
                    document, filename = SettlementDocuments(connection, cfg).ods_for_run(
                        settlement_id, int(lease_id_text)
                    )
                    return bytes_response(
                        start_response, HTTPStatus.OK, document,
                        "application/vnd.oasis.opendocument.spreadsheet", filename, "attachment"
                    )
                except (TypeError, ValueError) as error:
                    return text_response(start_response, HTTPStatus.BAD_REQUEST, str(error), "text/plain; charset=utf-8")

        if method == "GET" and path.startswith("/api/settlement-runs/"):
            settlement_id = path.removeprefix("/api/settlement-runs/")
            if settlement_id and "/" not in settlement_id:
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        get_settlement_run_overview(connection, settlement_id),
                    )
                except ValueError as error:
                    return json_response(
                        start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)}
                    )

        if method == "POST" and path == "/api/settlements/refresh":
            payload = read_json(environ)
            try:
                raw_property_id = payload.get("property_id")
                raw_unit_id = payload.get("unit_id")
                property_id = None if raw_property_id in (None, "") else int(raw_property_id)
                unit_id = None if raw_unit_id in (None, "") else int(raw_unit_id)
                period_start = str(payload.get("period_start") or "")
                period_end = str(payload.get("period_end") or "")
                with connection:
                    imported = import_gnucash_payments_for_period(
                        connection, property_id, period_start, period_end, unit_id
                    )
                settlement = Settlements(connection).for_period(
                    property_id, period_start, period_end, unit_id
                )
                return json_response(
                    start_response,
                    HTTPStatus.OK,
                    {"import": imported, "settlement": settlement},
                )
            except (TypeError, ValueError) as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "GET" and path == "/api/settlements/document.pdf":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                unit_id = _optional_query_int(params, "unit_id")
                property_id = _optional_query_int(params, "property_id")
                lease_id = int(params.get("lease_id", [""])[0])
                period_start = params.get("period_start", [""])[0]
                period_end = params.get("period_end", [""])[0]
                document, filename = SettlementDocuments(connection).pdf_for_period(
                    property_id, lease_id, period_start, period_end, unit_id
                )
                return bytes_response(
                    start_response, HTTPStatus.OK, document, "application/pdf", filename, "attachment"
                )
            except (TypeError, ValueError) as error:
                return text_response(start_response, HTTPStatus.BAD_REQUEST, str(error), "text/plain; charset=utf-8")

        if method == "GET" and path == "/api/settlements/document.ods":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                unit_id = _optional_query_int(params, "unit_id")
                property_id = _optional_query_int(params, "property_id")
                lease_id = int(params.get("lease_id", [""])[0])
                period_start = params.get("period_start", [""])[0]
                period_end = params.get("period_end", [""])[0]
                document, filename = SettlementDocuments(connection, cfg).ods_for_period(
                    property_id, lease_id, period_start, period_end, unit_id
                )
                return bytes_response(start_response, HTTPStatus.OK, document, "application/vnd.oasis.opendocument.spreadsheet", filename, "attachment")
            except (TypeError, ValueError) as error:
                return text_response(start_response, HTTPStatus.BAD_REQUEST, str(error), "text/plain; charset=utf-8")

        if method == "GET" and path == "/api/depreciation-schedule":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                year = int(params.get("year", ["2025"])[0])
                schedule = Depreciation(connection).schedule_for_year(year)
                return json_response(start_response, HTTPStatus.OK, schedule)
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "POST" and path == "/expenses/new":
            payload = read_form(environ)
            if payload.get("property_id") and not payload.get("object_type"):
                payload["object_type"] = "property"
                payload["object_id"] = payload["property_id"]
            if payload.get("recurrence") == "one_time" and not payload.get("booking_date"):
                payload["booking_date"] = payload.get("period_start") or payload.get("period_end")
            try:
                with connection:
                    expenses.create(payload)
                return redirect_response(start_response, "/?tab=costs&created=1")
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "POST" and path == "/api/properties":
            with connection:
                result = assets.create_property(read_json(environ))
            return json_response(start_response, HTTPStatus.CREATED, result)
        if method == "PUT" and path.startswith("/api/properties/"):
            property_id = path.removeprefix("/api/properties/")
            if property_id.isdigit():
                try:
                    with connection:
                        result = assets.update_property(int(property_id), read_json(environ))
                    return json_response(start_response, HTTPStatus.OK, result)
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/buildings":
            with connection:
                result = assets.create_building(read_json(environ))
            return json_response(start_response, HTTPStatus.CREATED, result)
        if method == "PUT" and path.startswith("/api/buildings/"):
            building_id = path.removeprefix("/api/buildings/")
            if building_id.isdigit():
                try:
                    with connection:
                        result = assets.update_building(int(building_id), read_json(environ))
                    return json_response(start_response, HTTPStatus.OK, result)
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/units":
            with connection:
                result = assets.create_unit(read_json(environ))
            return json_response(start_response, HTTPStatus.CREATED, result)
        if method == "PUT" and path.startswith("/api/units/"):
            unit_id = path.removeprefix("/api/units/")
            if unit_id.isdigit():
                try:
                    with connection:
                        result = assets.update_unit(int(unit_id), read_json(environ))
                    return json_response(start_response, HTTPStatus.OK, result)
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/rooms":
            try:
                with connection:
                    result = assets.create_room(read_json(environ))
                return json_response(start_response, HTTPStatus.CREATED, result)
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "PUT" and path.startswith("/api/rooms/"):
            room_id = path.removeprefix("/api/rooms/")
            if room_id.isdigit():
                try:
                    with connection:
                        result = assets.update_room(int(room_id), read_json(environ))
                    return json_response(start_response, HTTPStatus.OK, result)
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/meters":
            try:
                with connection:
                    result = metering.create_meter(read_json(environ))
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    result,
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "PUT" and path.startswith("/api/meters/"):
            meter_id = path.removeprefix("/api/meters/")
            if meter_id.isdigit():
                try:
                    with connection:
                        result = metering.update_meter(int(meter_id), read_json(environ))
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        result,
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/meter-readings":
            try:
                with connection:
                    result = metering.create_reading(read_json(environ))
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    result,
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "DELETE" and path.startswith("/api/meter-readings/"):
            reading_id = path.removeprefix("/api/meter-readings/")
            if reading_id.isdigit():
                try:
                    with connection:
                        result = metering.delete_reading(int(reading_id))
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        result,
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/tenants":
            try:
                with connection:
                    result = tenancy.create_tenant(read_json(environ))
                return json_response(start_response, HTTPStatus.CREATED, result)
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if path.startswith("/api/tenants/"):
            tenant_id = path.removeprefix("/api/tenants/")
            if tenant_id.isdigit():
                try:
                    if method == "PUT":
                        with connection:
                            result = tenancy.update_tenant(int(tenant_id), read_json(environ))
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            result,
                        )
                    if method == "DELETE":
                        with connection:
                            result = tenancy.delete_tenant(int(tenant_id))
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            result,
                        )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/leases":
            try:
                with connection:
                    result = tenancy.create_lease(read_json(environ))
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    result,
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if path.startswith("/api/leases/"):
            lease_id = path.removeprefix("/api/leases/")
            if lease_id.isdigit():
                try:
                    if method == "PUT":
                        with connection:
                            result = tenancy.update_lease(int(lease_id), read_json(environ))
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            result,
                        )
                    if method == "DELETE":
                        with connection:
                            result = tenancy.delete_lease(int(lease_id))
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            result,
                        )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/expenses":
            try:
                with connection:
                    result = expenses.create(read_json(environ))
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    result,
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "PUT" and path.startswith("/api/expenses/"):
            expense_id = path.removeprefix("/api/expenses/")
            if expense_id.isdigit():
                try:
                    with connection:
                        result = expenses.update(int(expense_id), read_json(environ))
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        result,
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/depreciation-assets":
            try:
                with connection:
                    result = Depreciation(connection).create_asset(read_json(environ))
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    result,
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
    finally:
        connection.close()

    return json_response(start_response, HTTPStatus.NOT_FOUND, {"error": "Route not found"})
