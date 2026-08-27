from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import get_connection
from .openapi import build_openapi_document
from .services import (
    archive_object,
    create_building,
    create_depreciation_asset,
    create_expense,
    create_lease,
    create_meter,
    create_meter_reading,
    create_property,
    delete_lease_document,
    delete_lease,
    delete_tenant_document,
    get_paperless_status,
    get_application_settings,
    create_room,
    create_tenant,
    create_unit,
    download_lease_document,
    delete_expense_document,
    delete_meter_reading,
    delete_object,
    download_tenant_document,
    delete_tenant,
    depreciation_schedule_for_year,
    download_expense_document,
    export_application_data,
    get_paperless_settings,
    list_lease_documents,
    list_overview,
    list_expense_documents,
    list_tenant_documents,
    import_application_data,
    restore_object,
    settlement_for_period,
    health_status,
    upload_lease_documents,
    upload_expense_documents,
    upload_tenant_documents,
    update_application_settings,
    update_building,
    update_paperless_settings,
    update_property,
    update_room,
    update_tenant,
    update_lease,
    update_unit,
    update_expense,
)


STATIC_DIR = Path(__file__).with_name("static")
LIFECYCLE_RESOURCES = {"properties", "buildings", "units", "rooms", "meters", "expenses"}


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


def application(environ, start_response):
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

    connection = get_connection()
    try:
        lifecycle_route = parse_object_lifecycle_path(path)
        if lifecycle_route is not None:
            resource_name, object_id, action = lifecycle_route
            try:
                if method == "POST" and action == "archive":
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        archive_object(connection, resource_name, object_id),
                    )
                if method == "POST" and action == "restore":
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        restore_object(connection, resource_name, object_id),
                    )
                if method == "DELETE" and action == "delete":
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        delete_object(connection, resource_name, object_id),
                    )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "GET" and path == "/api/overview":
            return json_response(start_response, HTTPStatus.OK, list_overview(connection))

        if method == "GET" and path == "/api/paperless-settings":
            return json_response(start_response, HTTPStatus.OK, get_paperless_settings(connection))

        if method == "GET" and path == "/api/paperless-status":
            return json_response(start_response, HTTPStatus.OK, get_paperless_status(connection))

        if method == "GET" and path == "/api/application-settings":
            return json_response(start_response, HTTPStatus.OK, get_application_settings(connection))

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
                        list_expense_documents(connection, expense_id),
                    )
                if method == "POST" and route_type == "collection":
                    return json_response(
                        start_response,
                        HTTPStatus.CREATED,
                        upload_expense_documents(connection, expense_id, read_json(environ)),
                    )
                if method == "DELETE" and route_type == "item" and document_id is not None:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        delete_expense_document(connection, expense_id, document_id),
                    )
                if method == "GET" and route_type == "download" and document_id is not None:
                    document_payload = download_expense_document(connection, expense_id, document_id)
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
                        list_tenant_documents(connection, tenant_id),
                    )
                if method == "POST" and route_type == "collection":
                    return json_response(
                        start_response,
                        HTTPStatus.CREATED,
                        upload_tenant_documents(connection, tenant_id, read_json(environ)),
                    )
                if method == "DELETE" and route_type == "item" and document_id is not None:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        delete_tenant_document(connection, tenant_id, document_id),
                    )
                if method == "GET" and route_type == "download" and document_id is not None:
                    document_payload = download_tenant_document(connection, tenant_id, document_id)
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
                        list_lease_documents(connection, lease_id),
                    )
                if method == "POST" and route_type == "collection":
                    return json_response(
                        start_response,
                        HTTPStatus.CREATED,
                        upload_lease_documents(connection, lease_id, read_json(environ)),
                    )
                if method == "DELETE" and route_type == "item" and document_id is not None:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        delete_lease_document(connection, lease_id, document_id),
                    )
                if method == "GET" and route_type == "download" and document_id is not None:
                    document_payload = download_lease_document(connection, lease_id, document_id)
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
            property_id = int(params.get("property_id", ["1"])[0])
            period_start = params.get("period_start", ["2025-01-01"])[0]
            period_end = params.get("period_end", ["2025-12-31"])[0]
            return json_response(
                start_response,
                HTTPStatus.OK,
                settlement_for_period(connection, property_id, period_start, period_end),
            )

        if method == "GET" and path == "/api/depreciation-schedule":
            params = parse_qs(environ.get("QUERY_STRING", ""))
            year = int(params.get("year", ["2025"])[0])
            return json_response(
                start_response,
                HTTPStatus.OK,
                depreciation_schedule_for_year(connection, year),
            )

        if method == "POST" and path == "/expenses/new":
            payload = read_form(environ)
            if payload.get("property_id") and not payload.get("object_type"):
                payload["object_type"] = "property"
                payload["object_id"] = payload["property_id"]
            if payload.get("recurrence") == "one_time" and not payload.get("booking_date"):
                payload["booking_date"] = payload.get("period_start") or payload.get("period_end")
            try:
                create_expense(connection, payload)
                return redirect_response(start_response, "/?tab=costs&created=1")
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})

        if method == "POST" and path == "/api/properties":
            return json_response(start_response, HTTPStatus.CREATED, create_property(connection, read_json(environ)))
        if method == "PUT" and path.startswith("/api/properties/"):
            property_id = path.removeprefix("/api/properties/")
            if property_id.isdigit():
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        update_property(connection, int(property_id), read_json(environ)),
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/buildings":
            return json_response(start_response, HTTPStatus.CREATED, create_building(connection, read_json(environ)))
        if method == "PUT" and path.startswith("/api/buildings/"):
            building_id = path.removeprefix("/api/buildings/")
            if building_id.isdigit():
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        update_building(connection, int(building_id), read_json(environ)),
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/units":
            return json_response(start_response, HTTPStatus.CREATED, create_unit(connection, read_json(environ)))
        if method == "PUT" and path.startswith("/api/units/"):
            unit_id = path.removeprefix("/api/units/")
            if unit_id.isdigit():
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        update_unit(connection, int(unit_id), read_json(environ)),
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/rooms":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    create_room(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "PUT" and path.startswith("/api/rooms/"):
            room_id = path.removeprefix("/api/rooms/")
            if room_id.isdigit():
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        update_room(connection, int(room_id), read_json(environ)),
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/meters":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    create_meter(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/meter-readings":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    create_meter_reading(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "DELETE" and path.startswith("/api/meter-readings/"):
            reading_id = path.removeprefix("/api/meter-readings/")
            if reading_id.isdigit():
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        delete_meter_reading(connection, int(reading_id)),
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/tenants":
            return json_response(start_response, HTTPStatus.CREATED, create_tenant(connection, read_json(environ)))
        if path.startswith("/api/tenants/"):
            tenant_id = path.removeprefix("/api/tenants/")
            if tenant_id.isdigit():
                try:
                    if method == "PUT":
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            update_tenant(connection, int(tenant_id), read_json(environ)),
                        )
                    if method == "DELETE":
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            delete_tenant(connection, int(tenant_id)),
                        )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/leases":
            return json_response(start_response, HTTPStatus.CREATED, create_lease(connection, read_json(environ)))
        if path.startswith("/api/leases/"):
            lease_id = path.removeprefix("/api/leases/")
            if lease_id.isdigit():
                try:
                    if method == "PUT":
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            update_lease(connection, int(lease_id), read_json(environ)),
                        )
                    if method == "DELETE":
                        return json_response(
                            start_response,
                            HTTPStatus.OK,
                            delete_lease(connection, int(lease_id)),
                        )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/expenses":
            try:
                return json_response(
                    start_response,
                    HTTPStatus.CREATED,
                    create_expense(connection, read_json(environ)),
                )
            except ValueError as error:
                return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "PUT" and path.startswith("/api/expenses/"):
            expense_id = path.removeprefix("/api/expenses/")
            if expense_id.isdigit():
                try:
                    return json_response(
                        start_response,
                        HTTPStatus.OK,
                        update_expense(connection, int(expense_id), read_json(environ)),
                    )
                except ValueError as error:
                    return json_response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        if method == "POST" and path == "/api/depreciation-assets":
            return json_response(
                start_response,
                HTTPStatus.CREATED,
                create_depreciation_asset(connection, read_json(environ)),
            )
    finally:
        connection.close()

    return json_response(start_response, HTTPStatus.NOT_FOUND, {"error": "Route not found"})
