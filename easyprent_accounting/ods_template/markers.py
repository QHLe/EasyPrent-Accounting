from __future__ import annotations

from copy import copy, deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from importlib import resources
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo
import xml.etree.ElementTree as ET

from .constants import *
import easyprent_accounting.ods_template.package as package
import easyprent_accounting.ods_template.rendering as rendering

def _find_marker(sheet: ET.Element, marker: str) -> tuple[ET.Element, int]:
    for row in sheet.findall("table:table-row", NS):
        for column, cell in enumerate(rendering._cells(row), start=1):
            if rendering._cell_text(cell).strip() == marker:
                return row, column
    raise ValueError(f"settlement template is missing marker {marker}")

def _find_marker_in_row(row: ET.Element, marker: str) -> int:
    for column, cell in enumerate(rendering._cells(row), start=1):
        if rendering._cell_text(cell).strip() == marker:
            return column
    raise ValueError(f"settlement template cost row is missing marker {marker}")

def _find_optional_marker_in_row(row: ET.Element, marker: str) -> int | None:
    for column, cell in enumerate(rendering._cells(row), start=1):
        if rendering._cell_text(cell).strip() == marker:
            return column
    return None

def _prepare_allocation_markers(sheet: ET.Element) -> None:
    """Add dynamic markers to the optional allocation-key section."""
    rows = sheet.findall("table:table-row", NS)
    header_row = next(
        (
            row
            for row in rows
            if "Nr." in {rendering._cell_text(cell).strip() for cell in rendering._cells(row)}
            and any(
                "Umlageschlüssel" in rendering._cell_text(cell)
                for cell in rendering._cells(row)
            )
        ),
        None,
    )
    if header_row is None:
        return

    cost_header_row = next(
        (
            row
            for row in rows[rows.index(header_row) + 1 :]
            if any("Jahreskosten" in rendering._cell_text(cell) for cell in rendering._cells(row))
        ),
        None,
    )
    if cost_header_row is None:
        raise ValueError("source template has no cost header after allocation keys")

    existing_allocation_markers = [
        marker
        for marker in _ALLOCATION_MARKERS
        if any(
            rendering._cell_text(cell).strip() == marker
            for row in rows
            for cell in rendering._cells(row)
        )
    ]
    if existing_allocation_markers and len(existing_allocation_markers) != len(
        _ALLOCATION_MARKERS
    ):
        raise ValueError("settlement template has an incomplete allocation prototype")

    if not existing_allocation_markers:
        candidates = rows[rows.index(header_row) + 1 : rows.index(cost_header_row)]
        header_style = header_row.get(f"{{{TABLE_NS}}}style-name")
        prototype = next(
            (
                row
                for row in candidates
                if row.get(f"{{{TABLE_NS}}}style-name") == header_style
                and not any(rendering._cell_text(cell).strip() for cell in rendering._cells(row))
            ),
            None,
        )
        if prototype is None:
            raise ValueError("source template has no allocation-key prototype row")
        for marker, column in zip(_ALLOCATION_MARKERS, (1, 2, 4, 5, 7, 8)):
            rendering._set_cell(prototype, column, marker)

    cost_row, _ = _find_marker(sheet, "{{KOSTENART}}")
    total_row, _ = _find_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
    position_row = _find_position_prototype_row(sheet, cost_row, total_row)
    if position_row is None:
        raise ValueError("source template has no position prototype")
    allocation_reference_column = next(
        (
            column
            for column, cell in enumerate(rendering._cells(cost_header_row), start=1)
            if "Umlage" in rendering._cell_text(cell)
        ),
        None,
    )
    if allocation_reference_column is None:
        raise ValueError("source template cost header has no allocation-key column")
    if _find_optional_marker_in_row(cost_row, "{{UMLAGE_REF}}") is None:
        rendering._set_cell(cost_row, allocation_reference_column, "{{UMLAGE_REF}}")
    if _find_optional_marker_in_row(position_row, "{{POSITION_UMLAGE_REF}}") is None:
        rendering._set_cell(
            position_row,
            allocation_reference_column,
            "{{POSITION_UMLAGE_REF}}",
        )

def _find_position_prototype_row(
    sheet: ET.Element,
    cost_row: ET.Element,
    total_row: ET.Element,
) -> ET.Element | None:
    rows = sheet.findall("table:table-row", NS)
    locations: dict[str, list[tuple[ET.Element, int]]] = {
        marker: [
            (row, column)
            for row in rows
            for column, cell in enumerate(rendering._cells(row), start=1)
            if rendering._cell_text(cell).strip() == marker
        ]
        for marker in _POSITION_MARKERS
    }
    if not any(locations.values()):
        return None

    for marker, marker_locations in locations.items():
        if len(marker_locations) != 1:
            raise ValueError(
                "settlement template position prototype must contain "
                f"{marker} exactly once"
            )

    position_row = locations["{{POSITION}}"][0][0]
    if any(
        marker_locations[0][0] is not position_row
        for marker_locations in locations.values()
    ):
        raise ValueError(
            "settlement template position markers must be in the same row"
        )

    cost_index = rows.index(cost_row)
    position_index = rows.index(position_row)
    total_index = rows.index(total_row)
    if not cost_index < position_index < total_index:
        raise ValueError(
            "settlement template position prototype must be between "
            "{{KOSTENART}} and the total row"
        )
    return position_row

def _find_row_containing(rows: list[ET.Element], text: str) -> ET.Element:
    for row in rows:
        if text in "\n".join(rendering._cell_text(cell) for cell in rendering._cells(row)):
            return row
    raise ValueError(f"source template is missing row containing {text!r}")

def prepare_settlement_template_bytes(document: bytes) -> bytes:
    """Convert the styled source ODS into the marker-based master template."""
    entries = package._archive_entries(document)
    content = next((data for entry, data in entries if entry.filename == "content.xml"), None)
    if content is None:
        raise ValueError("source template has no content.xml")
    root = ET.fromstring(content)
    spreadsheet = root.find(".//office:spreadsheet", NS)
    if spreadsheet is None:
        raise ValueError("source template has no spreadsheet")
    sheets = spreadsheet.findall("table:table", NS)
    if not sheets:
        raise ValueError("source template has no spreadsheet table")
    sheet = sheets[0]
    for extra_sheet in sheets[1:]:
        spreadsheet.remove(extra_sheet)
    rendering._expand_repeated_rows(sheet)
    rows = sheet.findall("table:table-row", NS)
    for row in rows:
        rendering._expand_repeated_cells(row)
    has_cost_marker = any(
        rendering._cell_text(cell).strip() == "{{KOSTENART}}"
        for row in rows
        for cell in rendering._cells(row)
    )
    if has_cost_marker:
        cost_row, _ = _find_marker(sheet, "{{KOSTENART}}")
        total_row, _ = _find_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
        position_row = _find_position_prototype_row(
            sheet, cost_row, total_row
        )
        if position_row is None:
            position_prototype = rendering._position_prototype_from_cost(root, cost_row)
            sheet.insert(list(sheet).index(cost_row) + 1, position_prototype)
        _prepare_allocation_markers(sheet)
        return package._finish_prepared_template(entries, root)

    created_row = _find_row_containing(rows, "erstellt am:")
    created_index = rows.index(created_row)
    if created_index < 3:
        raise ValueError("source template has no sender block before creation date")
    rendering._set_cell(rows[created_index - 3], 7, "{{ABSENDER_NAME}}")
    rendering._set_cell(rows[created_index - 2], 7, "{{ABSENDER_STRASSE}}")
    rendering._set_cell(rows[created_index - 1], 7, "{{ABSENDER_PLZ_ORT}}")
    rendering._set_cell(created_row, 7, "{{ERSTELLDATUM}}")

    title_row = _find_row_containing(rows, "Nebenkostenabrechnung")
    title_index = rows.index(title_row)
    if title_index < 4:
        raise ValueError("source template has no recipient block before title")
    rendering._set_cell(rows[title_index - 4], 1, "{{MIETER_NAME}}")
    rendering._set_cell(rows[title_index - 3], 1, "{{MIETER_STRASSE}}")
    rendering._set_cell(rows[title_index - 2], 1, "{{MIETER_PLZ_ORT}}")
    rendering._set_cell(title_row, 1, "{{ABRECHNUNGSZEITRAUM}}")

    object_row = _find_row_containing(rows, "Objekt")
    rendering._set_cell(object_row, 7, "{{OBJEKT}}")

    header_row = _find_row_containing(rows, "Jahreskosten")
    total_row = _find_row_containing(rows, "Total")
    header_index = rows.index(header_row)
    total_index = rows.index(total_row)
    populated_rows = [row for row in rows[header_index + 1 : total_index] if any(
        rendering._cell_text(cell).strip() for cell in rendering._cells(row)
    )]
    if not populated_rows:
        raise ValueError("source template has no prototype cost row")
    prototype = deepcopy(populated_rows[0])
    first_cost_index = rows.index(populated_rows[0])
    first_cost_child_index = list(sheet).index(populated_rows[0])
    for obsolete_row in rows[first_cost_index:total_index]:
        sheet.remove(obsolete_row)
    rendering._set_cell(prototype, 1, "{{KOSTENART}}")
    rendering._set_cell(prototype, 3, "{{JAHRESKOSTEN}}")
    rendering._set_cell(prototype, 5, "{{MIETERANTEIL}}")
    rendering._set_cell(prototype, 7, "{{VERBRAUCH}}")
    consumption_cell = rendering._cells(prototype)[6]
    consumption_cell.set(f"{{{TABLE_NS}}}style-name", "ceEasyConsumption")
    automatic_styles = root.find("office:automatic-styles", NS)
    if automatic_styles is not None and not any(
        style.get(f"{{{STYLE_NS}}}name") == "ceEasyConsumption"
        for style in automatic_styles.findall("style:style", NS)
    ):
        consumption_style = ET.SubElement(
            automatic_styles,
            f"{{{STYLE_NS}}}style",
            {
                f"{{{STYLE_NS}}}name": "ceEasyConsumption",
                f"{{{STYLE_NS}}}family": "table-cell",
                f"{{{STYLE_NS}}}parent-style-name": "Default",
            },
        )
        ET.SubElement(
            consumption_style,
            f"{{{STYLE_NS}}}table-cell-properties",
            {
                f"{{{FO_NS}}}padding-left": "0.04in",
                f"{{{FO_NS}}}padding-right": "0.04in",
                f"{{{STYLE_NS}}}vertical-align": "middle",
            },
        )
        ET.SubElement(
            consumption_style,
            f"{{{STYLE_NS}}}paragraph-properties",
            {f"{{{FO_NS}}}text-align": "center"},
        )
    sheet.insert(first_cost_child_index, prototype)
    position_prototype = rendering._position_prototype_from_cost(root, prototype)
    sheet.insert(first_cost_child_index + 1, position_prototype)
    rendering._set_cell(total_row, 3, "{{SUMME_JAHRESKOSTEN}}")
    rendering._set_cell(total_row, 5, "{{SUMME_MIETERANTEIL}}")
    _prepare_allocation_markers(sheet)

    rows = sheet.findall("table:table-row", NS)
    payment_header = _find_row_containing(rows, "Betrag")
    sum_row = _find_row_containing(rows, "Summe")
    payment_header_index = rows.index(payment_header)
    sum_index = rows.index(sum_row)
    payment_rows = [row for row in rows[payment_header_index + 1 : sum_index] if any(
        rendering._cell_text(cell).strip() for cell in rendering._cells(row)
    )]
    if not payment_rows:
        raise ValueError("source template has no advance payment row")
    payment_row = payment_rows[0]
    rendering._set_cell(payment_row, 1, "{{VORAUSZAHLUNG_ZEITRAUM}}")
    rendering._set_cell(payment_row, 4, "{{VORAUSZAHLUNGEN}}")
    rendering._set_cell(sum_row, 4, "{{VORAUSZAHLUNGEN_SUMME}}")

    balance_candidates = [row for row in rows[sum_index + 1 :] if any(
        marker in "\n".join(rendering._cell_text(cell) for cell in rendering._cells(row))
        for marker in ("Guthaben", "Nachzahlung", "Saldo")
    )]
    if not balance_candidates:
        raise ValueError("source template has no balance row")
    balance_row = balance_candidates[0]
    balance_index = rows.index(balance_row)
    rendering._set_cell(balance_row, 3, "{{SALDO_BEZEICHNUNG}}")
    rendering._set_cell(balance_row, 4, "{{SALDO_BETRAG}}")
    notice_rows = [row for row in rows[balance_index + 1 :] if any(
        rendering._cell_text(cell).strip() for cell in rendering._cells(row)
    )]
    if not notice_rows:
        raise ValueError("source template has no result notice row")
    rendering._set_cell(notice_rows[0], 1, "{{ERGEBNIS_TEXT}}")

    return package._finish_prepared_template(entries, root)

