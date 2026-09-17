from __future__ import annotations

from copy import deepcopy
import xml.etree.ElementTree as ET

from .cells import (
    FO_NS, NS, STYLE_NS, TABLE_NS, _ALLOCATION_MARKERS,
    _cell_text, _cells, _expand_repeated_cells, _expand_repeated_rows,
    _find_marker, _find_marker_in_row, _find_optional_marker_in_row,
    _find_position_prototype_row, _find_row_containing, _set_cell,
)
from .package import _archive_entries, _finish_prepared_template
from .rendering import _position_prototype_from_cost

def _prepare_allocation_markers(sheet: ET.Element) -> None:
    """Add dynamic markers to the optional allocation-key section."""
    rows = sheet.findall("table:table-row", NS)
    header_row = next(
        (
            row
            for row in rows
            if "Nr." in {_cell_text(cell).strip() for cell in _cells(row)}
            and any(
                "Umlageschlüssel" in _cell_text(cell)
                for cell in _cells(row)
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
            if any("Jahreskosten" in _cell_text(cell) for cell in _cells(row))
        ),
        None,
    )
    if cost_header_row is None:
        raise ValueError("source template has no cost header after allocation keys")

    existing_allocation_markers = [
        marker
        for marker in _ALLOCATION_MARKERS
        if any(
            _cell_text(cell).strip() == marker
            for row in rows
            for cell in _cells(row)
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
                and not any(_cell_text(cell).strip() for cell in _cells(row))
            ),
            None,
        )
        if prototype is None:
            raise ValueError("source template has no allocation-key prototype row")
        for marker, column in zip(_ALLOCATION_MARKERS, (1, 2, 4, 5, 7, 8)):
            _set_cell(prototype, column, marker)

    cost_row, _ = _find_marker(sheet, "{{KOSTENART}}")
    total_row, _ = _find_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
    position_row = _find_position_prototype_row(sheet, cost_row, total_row)
    if position_row is None:
        raise ValueError("source template has no position prototype")
    allocation_reference_column = next(
        (
            column
            for column, cell in enumerate(_cells(cost_header_row), start=1)
            if "Umlage" in _cell_text(cell)
        ),
        None,
    )
    if allocation_reference_column is None:
        raise ValueError("source template cost header has no allocation-key column")
    if _find_optional_marker_in_row(cost_row, "{{UMLAGE_REF}}") is None:
        _set_cell(cost_row, allocation_reference_column, "{{UMLAGE_REF}}")
    if _find_optional_marker_in_row(position_row, "{{POSITION_UMLAGE_REF}}") is None:
        _set_cell(
            position_row,
            allocation_reference_column,
            "{{POSITION_UMLAGE_REF}}",
        )


def prepare_settlement_template_bytes(document: bytes) -> bytes:
    """Convert the styled source ODS into the marker-based master template."""
    entries = _archive_entries(document)
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
    _expand_repeated_rows(sheet)
    rows = sheet.findall("table:table-row", NS)
    for row in rows:
        _expand_repeated_cells(row)
    has_cost_marker = any(
        _cell_text(cell).strip() == "{{KOSTENART}}"
        for row in rows
        for cell in _cells(row)
    )
    if has_cost_marker:
        cost_row, _ = _find_marker(sheet, "{{KOSTENART}}")
        total_row, _ = _find_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
        position_row = _find_position_prototype_row(
            sheet, cost_row, total_row
        )
        if position_row is None:
            position_prototype = _position_prototype_from_cost(root, cost_row)
            sheet.insert(list(sheet).index(cost_row) + 1, position_prototype)
        _prepare_allocation_markers(sheet)
        return _finish_prepared_template(entries, root)

    created_row = _find_row_containing(rows, "erstellt am:")
    created_index = rows.index(created_row)
    if created_index < 3:
        raise ValueError("source template has no sender block before creation date")
    _set_cell(rows[created_index - 3], 7, "{{ABSENDER_NAME}}")
    _set_cell(rows[created_index - 2], 7, "{{ABSENDER_STRASSE}}")
    _set_cell(rows[created_index - 1], 7, "{{ABSENDER_PLZ_ORT}}")
    _set_cell(created_row, 7, "{{ERSTELLDATUM}}")

    title_row = _find_row_containing(rows, "Nebenkostenabrechnung")
    title_index = rows.index(title_row)
    if title_index < 4:
        raise ValueError("source template has no recipient block before title")
    _set_cell(rows[title_index - 4], 1, "{{MIETER_NAME}}")
    _set_cell(rows[title_index - 3], 1, "{{MIETER_STRASSE}}")
    _set_cell(rows[title_index - 2], 1, "{{MIETER_PLZ_ORT}}")
    _set_cell(title_row, 1, "{{ABRECHNUNGSZEITRAUM}}")

    object_row = _find_row_containing(rows, "Objekt")
    _set_cell(object_row, 7, "{{OBJEKT}}")

    header_row = _find_row_containing(rows, "Jahreskosten")
    total_row = _find_row_containing(rows, "Total")
    header_index = rows.index(header_row)
    total_index = rows.index(total_row)
    populated_rows = [row for row in rows[header_index + 1 : total_index] if any(
        _cell_text(cell).strip() for cell in _cells(row)
    )]
    if not populated_rows:
        raise ValueError("source template has no prototype cost row")
    prototype = deepcopy(populated_rows[0])
    first_cost_index = rows.index(populated_rows[0])
    first_cost_child_index = list(sheet).index(populated_rows[0])
    for obsolete_row in rows[first_cost_index:total_index]:
        sheet.remove(obsolete_row)
    _set_cell(prototype, 1, "{{KOSTENART}}")
    _set_cell(prototype, 3, "{{JAHRESKOSTEN}}")
    _set_cell(prototype, 5, "{{MIETERANTEIL}}")
    _set_cell(prototype, 7, "{{VERBRAUCH}}")
    consumption_cell = _cells(prototype)[6]
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
    position_prototype = _position_prototype_from_cost(root, prototype)
    sheet.insert(first_cost_child_index + 1, position_prototype)
    _set_cell(total_row, 3, "{{SUMME_JAHRESKOSTEN}}")
    _set_cell(total_row, 5, "{{SUMME_MIETERANTEIL}}")
    _prepare_allocation_markers(sheet)

    rows = sheet.findall("table:table-row", NS)
    payment_header = _find_row_containing(rows, "Betrag")
    sum_row = _find_row_containing(rows, "Summe")
    payment_header_index = rows.index(payment_header)
    sum_index = rows.index(sum_row)
    payment_rows = [row for row in rows[payment_header_index + 1 : sum_index] if any(
        _cell_text(cell).strip() for cell in _cells(row)
    )]
    if not payment_rows:
        raise ValueError("source template has no advance payment row")
    payment_row = payment_rows[0]
    _set_cell(payment_row, 1, "{{VORAUSZAHLUNG_ZEITRAUM}}")
    _set_cell(payment_row, 4, "{{VORAUSZAHLUNGEN}}")
    _set_cell(sum_row, 4, "{{VORAUSZAHLUNGEN_SUMME}}")

    balance_candidates = [row for row in rows[sum_index + 1 :] if any(
        marker in "\n".join(_cell_text(cell) for cell in _cells(row))
        for marker in ("Guthaben", "Nachzahlung", "Saldo")
    )]
    if not balance_candidates:
        raise ValueError("source template has no balance row")
    balance_row = balance_candidates[0]
    balance_index = rows.index(balance_row)
    _set_cell(balance_row, 3, "{{SALDO_BEZEICHNUNG}}")
    _set_cell(balance_row, 4, "{{SALDO_BETRAG}}")
    notice_rows = [row for row in rows[balance_index + 1 :] if any(
        _cell_text(cell).strip() for cell in _cells(row)
    )]
    if not notice_rows:
        raise ValueError("source template has no result notice row")
    _set_cell(notice_rows[0], 1, "{{ERGEBNIS_TEXT}}")

    return _finish_prepared_template(entries, root)


