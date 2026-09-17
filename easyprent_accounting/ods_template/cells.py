from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import xml.etree.ElementTree as ET


TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
STYLE_NS = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
NUMBER_NS = "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"
FO_NS = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
CALCEXT_NS = "urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0"
OF_NS = "urn:oasis:names:tc:opendocument:xmlns:of:1.2"
MANIFEST_NS = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
CONFIG_NS = "urn:oasis:names:tc:opendocument:xmlns:config:1.0"
META_NS = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
DC_NS = "http://purl.org/dc/elements/1.1/"
NS = {
    "table": TABLE_NS,
    "text": TEXT_NS,
    "office": OFFICE_NS,
    "style": STYLE_NS,
    "number": NUMBER_NS,
}
for prefix, uri in {
    **NS,
    "fo": FO_NS,
    "calcext": CALCEXT_NS,
    "manifest": MANIFEST_NS,
    "config": CONFIG_NS,
    "meta": META_NS,
    "dc": DC_NS,
}.items():
    ET.register_namespace(prefix, uri)


_CELL_TAGS = {
    f"{{{TABLE_NS}}}table-cell",
    f"{{{TABLE_NS}}}covered-table-cell",
}
_TEMPLATE_FILENAME = "utility_settlement.ods"
_POSITION_MARKERS = (
    "{{POSITION}}",
    "{{POSITION_JAHRESKOSTEN}}",
    "{{POSITION_MIETERANTEIL}}",
    "{{POSITION_VERBRAUCH}}",
)
_ALLOCATION_MARKERS = (
    "{{UMLAGE_NR}}",
    "{{UMLAGE_ART}}",
    "{{UMLAGE_ZEITRAUM}}",
    "{{UMLAGE_TAGE}}",
    "{{UMLAGE_GESAMT}}",
    "{{UMLAGE_ANTEIL}}",
)


def _cells(row: ET.Element) -> list[ET.Element]:
    return [cell for cell in row if cell.tag in _CELL_TAGS]


def _expand_repeated_cells(row: ET.Element) -> None:
    repeated_attribute = f"{{{TABLE_NS}}}number-columns-repeated"
    for cell in list(row):
        if cell.tag not in _CELL_TAGS:
            continue
        repeated = int(cell.attrib.pop(repeated_attribute, "1"))
        if repeated <= 1:
            continue
        if repeated > 1000 and not _cell_text(cell).strip():
            # LibreOffice stores the unused tail of each row as thousands of
            # repeated blank cells. A single representative is sufficient and
            # avoids expanding a small template into millions of XML nodes.
            continue
        position = list(row).index(cell)
        for offset in range(1, repeated):
            row.insert(position + offset, deepcopy(cell))


def _expand_repeated_rows(sheet: ET.Element) -> None:
    repeated_attribute = f"{{{TABLE_NS}}}number-rows-repeated"
    rows = [
        row for row in list(sheet) if row.tag == f"{{{TABLE_NS}}}table-row"
    ]
    for row_index, row in enumerate(rows):
        repeated = int(row.attrib.pop(repeated_attribute, "1"))
        if repeated <= 1:
            continue
        if repeated > 1000:
            row_has_text = any(_cell_text(cell).strip() for cell in _cells(row))
            later_rows_have_text = any(
                _cell_text(cell).strip()
                for later_row in rows[row_index + 1 :]
                for cell in _cells(later_row)
            )
            if row_has_text or later_rows_have_text:
                raise ValueError("settlement template contains too many repeated rows")
            # LibreOffice commonly stores the unused tail of a sheet as one
            # repeated blank row. One representative row is sufficient here.
            continue
        position = list(sheet).index(row)
        for offset in range(1, repeated):
            sheet.insert(position + offset, deepcopy(row))


def _cell_text(cell: ET.Element) -> str:
    return "\n".join("".join(paragraph.itertext()) for paragraph in cell.findall("text:p", NS))


def _clear_dynamic_cell_data(cell: ET.Element) -> None:
    for child in list(cell):
        if child.tag == f"{{{TEXT_NS}}}p":
            cell.remove(child)
    for attribute in (
        "value",
        "value-type",
        "date-value",
        "formula",
        "string-value",
        "currency",
        "boolean-value",
        "time-value",
    ):
        cell.attrib.pop(f"{{{OFFICE_NS}}}{attribute}", None)
    cell.attrib.pop(f"{{{TABLE_NS}}}formula", None)
    cell.attrib.pop(f"{{{CALCEXT_NS}}}value-type", None)


def _set_cell(
    row: ET.Element,
    column: int,
    text: str | list[str],
    *,
    number: Decimal | str | None = None,
    currency: bool = False,
    formula: str | None = None,
) -> None:
    cells = _cells(row)
    if column < 1 or column > len(cells):
        raise ValueError(f"template row has no column {column}")
    cell = cells[column - 1]
    if cell.tag == f"{{{TABLE_NS}}}covered-table-cell":
        raise ValueError(f"template marker points to covered column {column}")
    _clear_dynamic_cell_data(cell)

    paragraphs = text if isinstance(text, list) else [text]
    if number is not None:
        decimal_value = Decimal(str(number))
        cell.set(f"{{{OFFICE_NS}}}value", format(decimal_value, "f"))
        if currency:
            cell.set(f"{{{OFFICE_NS}}}value-type", "currency")
            cell.set(f"{{{OFFICE_NS}}}currency", "EUR")
            cell.set(f"{{{CALCEXT_NS}}}value-type", "currency")
        else:
            cell.set(f"{{{OFFICE_NS}}}value-type", "float")
            cell.set(f"{{{CALCEXT_NS}}}value-type", "float")
    else:
        cell.set(f"{{{OFFICE_NS}}}value-type", "string")
        cell.set(f"{{{CALCEXT_NS}}}value-type", "string")
    if formula:
        cell.set(f"{{{TABLE_NS}}}formula", formula)
    for paragraph_text in paragraphs or [""]:
        paragraph = ET.SubElement(cell, f"{{{TEXT_NS}}}p")
        paragraph.text = paragraph_text


def _find_marker(sheet: ET.Element, marker: str) -> tuple[ET.Element, int]:
    for row in sheet.findall("table:table-row", NS):
        for column, cell in enumerate(_cells(row), start=1):
            if _cell_text(cell).strip() == marker:
                return row, column
    raise ValueError(f"settlement template is missing marker {marker}")


def _find_marker_in_row(row: ET.Element, marker: str) -> int:
    for column, cell in enumerate(_cells(row), start=1):
        if _cell_text(cell).strip() == marker:
            return column
    raise ValueError(f"settlement template cost row is missing marker {marker}")


def _find_optional_marker_in_row(row: ET.Element, marker: str) -> int | None:
    for column, cell in enumerate(_cells(row), start=1):
        if _cell_text(cell).strip() == marker:
            return column
    return None


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
            for column, cell in enumerate(_cells(row), start=1)
            if _cell_text(cell).strip() == marker
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
        if text in "\n".join(_cell_text(cell) for cell in _cells(row)):
            return row
    raise ValueError(f"source template is missing row containing {text!r}")


