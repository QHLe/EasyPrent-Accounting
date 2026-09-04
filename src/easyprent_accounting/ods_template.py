from __future__ import annotations

from copy import copy, deepcopy
from decimal import Decimal, ROUND_HALF_UP
from importlib import resources
from io import BytesIO
import os
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo
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


def _format_decimal(value: Decimal | str) -> str:
    decimal_value = Decimal(str(value))
    if decimal_value.as_tuple().exponent < -3:
        decimal_value = decimal_value.quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
    sign = "-" if decimal_value < 0 else ""
    raw = format(abs(decimal_value), "f")
    integer, separator, fraction = raw.partition(".")
    grouped = f"{int(integer or '0'):,}".replace(",", ".")
    fraction = fraction.rstrip("0")
    return f"{sign}{grouped}{',' + fraction if separator and fraction else ''}"


def _format_money(value: Decimal | str) -> str:
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"))
    raw = f"{decimal_value:,.2f}"
    return raw.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


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


def _apply_object_row_style(root: ET.Element, row: ET.Element) -> None:
    style_name = "roEasyObject"
    automatic_styles = root.find("office:automatic-styles", NS)
    if automatic_styles is None:
        return
    if not any(
        style.get(f"{{{STYLE_NS}}}name") == style_name
        for style in automatic_styles.findall("style:style", NS)
    ):
        object_row_style = ET.SubElement(
            automatic_styles,
            f"{{{STYLE_NS}}}style",
            {
                f"{{{STYLE_NS}}}name": style_name,
                f"{{{STYLE_NS}}}family": "table-row",
            },
        )
        ET.SubElement(
            object_row_style,
            f"{{{STYLE_NS}}}table-row-properties",
            {
                f"{{{STYLE_NS}}}row-height": "0.8in",
                f"{{{STYLE_NS}}}use-optimal-row-height": "false",
                f"{{{FO_NS}}}break-before": "auto",
            },
        )
    row.set(f"{{{TABLE_NS}}}style-name", style_name)


def _apply_advance_payment_page_break(root: ET.Element, row: ET.Element) -> None:
    """Start the advance-payment section on its own printed page."""
    style_name = "roEasyAdvancePayments"
    automatic_styles = root.find("office:automatic-styles", NS)
    if automatic_styles is None:
        return
    styles_by_name = {
        style.get(f"{{{STYLE_NS}}}name", ""): style
        for style in automatic_styles.findall("style:style", NS)
    }
    payment_row_style = styles_by_name.get(style_name)
    if payment_row_style is None:
        original_style = styles_by_name.get(
            row.get(f"{{{TABLE_NS}}}style-name", "")
        )
        if original_style is not None:
            payment_row_style = deepcopy(original_style)
            payment_row_style.set(f"{{{STYLE_NS}}}name", style_name)
            payment_row_style.attrib.pop(
                f"{{{STYLE_NS}}}parent-style-name", None
            )
            automatic_styles.append(payment_row_style)
        else:
            payment_row_style = ET.SubElement(
                automatic_styles,
                f"{{{STYLE_NS}}}style",
                {
                    f"{{{STYLE_NS}}}name": style_name,
                    f"{{{STYLE_NS}}}family": "table-row",
                },
            )
    row_properties = payment_row_style.find("style:table-row-properties", NS)
    if row_properties is None:
        row_properties = ET.SubElement(
            payment_row_style, f"{{{STYLE_NS}}}table-row-properties"
        )
    row_properties.attrib.pop(f"{{{STYLE_NS}}}row-height", None)
    row_properties.set(f"{{{STYLE_NS}}}use-optimal-row-height", "true")
    row_properties.set(f"{{{FO_NS}}}break-before", "page")
    row.set(f"{{{TABLE_NS}}}style-name", style_name)


def _apply_optimal_row_heights(root: ET.Element) -> None:
    """Remove fixed heights and enable content-based height on every row style."""
    automatic_styles = root.find("office:automatic-styles", NS)
    if automatic_styles is None:
        return
    for row_style in automatic_styles.findall("style:style", NS):
        if row_style.get(f"{{{STYLE_NS}}}family") != "table-row":
            continue
        row_properties = row_style.find("style:table-row-properties", NS)
        if row_properties is None:
            row_properties = ET.SubElement(
                row_style, f"{{{STYLE_NS}}}table-row-properties"
            )
        row_properties.attrib.pop(f"{{{STYLE_NS}}}row-height", None)
        row_properties.set(f"{{{STYLE_NS}}}use-optimal-row-height", "true")


def _apply_subposition_styles(
    root: ET.Element,
    row: ET.Element,
    *,
    label_column: int,
    value_columns: tuple[int, ...],
) -> None:
    automatic_styles = root.find("office:automatic-styles", NS)
    if automatic_styles is None:
        return
    styles_by_name = {
        style.get(f"{{{STYLE_NS}}}name", ""): style
        for style in automatic_styles.findall("style:style", NS)
    }
    cells = _cells(row)
    for column in (label_column, *value_columns):
        cell = cells[column - 1]
        original_name = cell.get(f"{{{TABLE_NS}}}style-name", "Default")
        style_kind = "Label" if column == label_column else "Value"
        safe_original_name = re.sub(r"[^A-Za-z0-9_]", "_", original_name)
        derived_name = f"ceEasySub{style_kind}_{safe_original_name}"
        if derived_name not in styles_by_name:
            original_style = styles_by_name.get(original_name)
            if original_style is not None:
                derived_style = deepcopy(original_style)
                derived_style.set(f"{{{STYLE_NS}}}name", derived_name)
            else:
                derived_style = ET.Element(
                    f"{{{STYLE_NS}}}style",
                    {
                        f"{{{STYLE_NS}}}name": derived_name,
                        f"{{{STYLE_NS}}}family": "table-cell",
                        f"{{{STYLE_NS}}}parent-style-name": "Default",
                    },
                )
            text_properties = derived_style.find("style:text-properties", NS)
            if text_properties is None:
                text_properties = ET.SubElement(
                    derived_style, f"{{{STYLE_NS}}}text-properties"
                )
            text_properties.set(f"{{{FO_NS}}}font-weight", "normal")
            text_properties.set(f"{{{STYLE_NS}}}font-weight-asian", "normal")
            text_properties.set(f"{{{STYLE_NS}}}font-weight-complex", "normal")
            if column == label_column:
                paragraph_properties = derived_style.find(
                    "style:paragraph-properties", NS
                )
                if paragraph_properties is None:
                    paragraph_properties = ET.SubElement(
                        derived_style, f"{{{STYLE_NS}}}paragraph-properties"
                    )
                paragraph_properties.set(f"{{{FO_NS}}}margin-left", "0.12in")
            automatic_styles.append(derived_style)
            styles_by_name[derived_name] = derived_style
        cell.set(f"{{{TABLE_NS}}}style-name", derived_name)


def _group_line_items(line_items: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, tuple[str, list[dict]]] = {}
    for item in line_items:
        label = str(item.get("label") or "").strip()
        category = str(item.get("expense_category") or label).strip() or label
        group_key = category.casefold()
        if group_key not in groups:
            groups[group_key] = (category, [])
        groups[group_key][1].append(item)
    return list(groups.values())


def _has_subpositions(category: str, items: list[dict]) -> bool:
    if len(items) > 1:
        return True
    return bool(items) and str(items[0].get("label") or "").strip().casefold() != (
        category.strip().casefold()
    )


def _position_prototype_from_cost(
    root: ET.Element, cost_prototype: ET.Element
) -> ET.Element:
    position_prototype = deepcopy(cost_prototype)
    label_column = _find_marker_in_row(position_prototype, "{{KOSTENART}}")
    annual_column = _find_marker_in_row(position_prototype, "{{JAHRESKOSTEN}}")
    share_column = _find_marker_in_row(position_prototype, "{{MIETERANTEIL}}")
    consumption_column = _find_marker_in_row(position_prototype, "{{VERBRAUCH}}")
    _set_cell(position_prototype, label_column, "{{POSITION}}")
    _set_cell(
        position_prototype, annual_column, "{{POSITION_JAHRESKOSTEN}}"
    )
    _set_cell(
        position_prototype, share_column, "{{POSITION_MIETERANTEIL}}"
    )
    _set_cell(position_prototype, consumption_column, "{{POSITION_VERBRAUCH}}")
    _apply_subposition_styles(
        root,
        position_prototype,
        label_column=label_column,
        value_columns=(annual_column, share_column),
    )
    return position_prototype


def _sum_formula_for_rows(column_name: str, row_numbers: list[int]) -> str | None:
    if not row_numbers:
        return None
    if row_numbers == list(range(row_numbers[0], row_numbers[-1] + 1)):
        return (
            f"of:=SUM([.{column_name}{row_numbers[0]}:"
            f".{column_name}{row_numbers[-1]}])"
        )
    references = ";".join(
        f"[.{column_name}{row_number}]" for row_number in row_numbers
    )
    return f"of:=SUM({references})"


def _row_number(sheet: ET.Element, target: ET.Element) -> int:
    return sheet.findall("table:table-row", NS).index(target) + 1


def _read_template_bytes(template_path: Path | None) -> bytes:
    if template_path is not None:
        return template_path.read_bytes()

    configured_path = os.environ.get("EASYPRENT_SETTLEMENT_TEMPLATE")
    if configured_path:
        path = Path(configured_path).expanduser()
        if not path.is_file():
            raise ValueError(f"configured settlement template does not exist: {path}")
        return path.read_bytes()

    checkout_template = Path(__file__).parents[2] / "templates" / _TEMPLATE_FILENAME
    if checkout_template.is_file():
        return checkout_template.read_bytes()

    packaged_template = resources.files(__package__).joinpath("templates").joinpath(_TEMPLATE_FILENAME)
    if not packaged_template.is_file():
        raise ValueError("packaged settlement template is missing")
    return packaged_template.read_bytes()


def _archive_entries(document: bytes) -> list[tuple[ZipInfo, bytes]]:
    with ZipFile(BytesIO(document)) as archive:
        return [(copy(entry), archive.read(entry.filename)) for entry in archive.infolist()]


def _without_thumbnail_entries(
    entries: list[tuple[ZipInfo, bytes]], replacements: dict[str, bytes]
) -> tuple[list[tuple[ZipInfo, bytes]], dict[str, bytes]]:
    """Remove stale ODS previews and their package-manifest references."""
    filtered_entries = [
        (entry, data)
        for entry, data in entries
        if not entry.filename.startswith("Thumbnails/")
    ]
    manifest_name = "META-INF/manifest.xml"
    manifest_data = replacements.get(
        manifest_name,
        next(
            (data for entry, data in filtered_entries if entry.filename == manifest_name),
            None,
        ),
    )
    if manifest_data is None:
        return filtered_entries, replacements

    manifest_root = ET.fromstring(manifest_data)
    full_path_attribute = f"{{{MANIFEST_NS}}}full-path"
    for file_entry in list(manifest_root.findall(f"{{{MANIFEST_NS}}}file-entry")):
        if (file_entry.get(full_path_attribute) or "").startswith("Thumbnails/"):
            manifest_root.remove(file_entry)
    updated_replacements = dict(replacements)
    updated_replacements[manifest_name] = ET.tostring(
        manifest_root, encoding="utf-8", xml_declaration=True
    )
    return filtered_entries, updated_replacements


def _write_archive(entries: list[tuple[ZipInfo, bytes]], replacements: dict[str, bytes]) -> bytes:
    entries, replacements = _without_thumbnail_entries(entries, replacements)
    output = BytesIO()
    ordered_entries = sorted(entries, key=lambda item: item[0].filename != "mimetype")
    with ZipFile(output, "w") as target:
        for entry, data in ordered_entries:
            entry.compress_type = ZIP_STORED if entry.filename == "mimetype" else ZIP_DEFLATED
            target.writestr(entry, replacements.get(entry.filename, data))
    return output.getvalue()


def _column_name(column: int) -> str:
    if column < 1:
        raise ValueError("spreadsheet column must be positive")
    result = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _sheet_name_for_period(period_label: str) -> str:
    years: list[str] = []
    for year in re.findall(r"(?<!\d)\d{4}(?!\d)", period_label):
        if year not in years:
            years.append(year)
    if not years:
        return "Abrechnung"
    if len(years) == 1:
        return years[0]
    return f"{years[0]}-{years[-1]}"


def _sanitize_settings(
    document: bytes, sheet_name: str, old_sheet_name: str | None = None
) -> bytes:
    root = ET.fromstring(document)
    name_attribute = f"{{{CONFIG_NS}}}name"
    for parent in root.iter():
        for child in list(parent):
            if child.tag != f"{{{CONFIG_NS}}}config-item":
                continue
            if (child.get(name_attribute) or "").startswith("Printer"):
                parent.remove(child)

    for named_map in root.findall(f".//{{{CONFIG_NS}}}config-item-map-named"):
        if named_map.get(name_attribute) not in {"Tables", "ScriptConfiguration"}:
            continue
        for entry in list(named_map):
            if entry.tag != f"{{{CONFIG_NS}}}config-item-map-entry":
                continue
            entry_name = entry.get(name_attribute, "")
            if old_sheet_name and entry_name == old_sheet_name:
                entry_name = sheet_name
                entry.set(name_attribute, sheet_name)
            if entry_name != sheet_name:
                named_map.remove(entry)

    for item in root.findall(f".//{{{CONFIG_NS}}}config-item"):
        if item.get(name_attribute) == "ActiveTable":
            item.text = sheet_name
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _sanitize_metadata(document: bytes) -> bytes:
    root = ET.fromstring(document)
    office_meta = root.find(f".//{{{OFFICE_NS}}}meta")
    if office_meta is None:
        return document
    private_tags = {
        f"{{{META_NS}}}initial-creator",
        f"{{{META_NS}}}printed-by",
        f"{{{DC_NS}}}creator",
    }
    for child in list(office_meta):
        if child.tag in private_tags:
            office_meta.remove(child)
    statistic = office_meta.find(f"{{{META_NS}}}document-statistic")
    if statistic is not None:
        statistic.set(f"{{{META_NS}}}table-count", "1")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _sanitize_package_files(
    entries: list[tuple[ZipInfo, bytes]],
    replacements: dict[str, bytes],
    *,
    sheet_name: str,
    old_sheet_name: str | None = None,
) -> dict[str, bytes]:
    updated = dict(replacements)
    entry_data = {entry.filename: data for entry, data in entries}
    meta = updated.get("meta.xml", entry_data.get("meta.xml"))
    if meta is not None:
        updated["meta.xml"] = _sanitize_metadata(meta)
    settings = updated.get("settings.xml", entry_data.get("settings.xml"))
    if settings is not None:
        updated["settings.xml"] = _sanitize_settings(
            settings, sheet_name, old_sheet_name
        )
    return updated


def _serialize_content(root: ET.Element) -> bytes:
    content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if b"xmlns:of=" not in content:
        content = content.replace(
            b"<office:document-content ",
            f'<office:document-content xmlns:of="{OF_NS}" '.encode("ascii"),
            1,
        )
    return content


def _find_row_containing(rows: list[ET.Element], text: str) -> ET.Element:
    for row in rows:
        if text in "\n".join(_cell_text(cell) for cell in _cells(row)):
            return row
    raise ValueError(f"source template is missing row containing {text!r}")


def _finish_prepared_template(
    entries: list[tuple[ZipInfo, bytes]], root: ET.Element
) -> bytes:
    styles = next((data for entry, data in entries if entry.filename == "styles.xml"), None)
    styles_root = ET.fromstring(styles) if styles is not None else None
    currency_style_names: set[str] = set()
    if styles_root is not None:
        for currency_style in styles_root.findall(".//number:currency-style", NS):
            style_name = currency_style.get(f"{{{STYLE_NS}}}name", "")
            if style_name:
                currency_style_names.add(style_name)
            currency_style.set(f"{{{NUMBER_NS}}}language", "de")
            currency_style.set(f"{{{NUMBER_NS}}}country", "DE")
    for style in root.findall(".//style:style", NS):
        if style.get(f"{{{STYLE_NS}}}data-style-name") not in currency_style_names:
            continue
        paragraph_properties = style.find("style:paragraph-properties", NS)
        if paragraph_properties is None:
            paragraph_properties = ET.SubElement(style, f"{{{STYLE_NS}}}paragraph-properties")
        paragraph_properties.set(f"{{{FO_NS}}}text-align", "start")

    replacements = {
        "content.xml": _serialize_content(root),
    }
    if styles_root is not None:
        replacements["styles.xml"] = ET.tostring(
            styles_root, encoding="utf-8", xml_declaration=True
        )
    sheet = root.find(".//table:table", NS)
    if sheet is None:
        raise ValueError("source template has no spreadsheet table")
    replacements = _sanitize_package_files(
        entries,
        replacements,
        sheet_name=sheet.get(f"{{{TABLE_NS}}}name", "Abrechnung"),
    )
    return _write_archive(entries, replacements)


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


def render_settlement_template(
    template_path: Path | None = None,
    *,
    sender_name: str = "",
    sender_street: str = "",
    sender_city_line: str = "",
    tenant_name: str,
    tenant_street: str,
    tenant_city_line: str,
    object_lines: list[str],
    created_on: str,
    period_label: str,
    line_items: list[dict],
    allocated_costs: str,
    advances_paid: str | None,
    balance: str | None,
    advance_payments: list[dict] | None = None,
) -> bytes:
    """Fill the editable master ODS while retaining its styles and merged cells."""
    entries = _archive_entries(_read_template_bytes(template_path))
    content = next((data for entry, data in entries if entry.filename == "content.xml"), None)
    if content is None:
        raise ValueError("settlement template has no content.xml")
    root = ET.fromstring(content)
    spreadsheet = root.find(".//office:spreadsheet", NS)
    if spreadsheet is None:
        raise ValueError("settlement template has no spreadsheet")
    sheets = spreadsheet.findall("table:table", NS)
    if not sheets:
        raise ValueError("settlement template has no spreadsheet table")
    sheet = sheets[0]
    for extra_sheet in sheets[1:]:
        spreadsheet.remove(extra_sheet)
    old_sheet_name = sheet.get(f"{{{TABLE_NS}}}name", "")
    new_sheet_name = _sheet_name_for_period(period_label)
    sheet.set(f"{{{TABLE_NS}}}name", new_sheet_name)
    _expand_repeated_rows(sheet)
    for row in sheet.findall("table:table-row", NS):
        _expand_repeated_cells(row)

    scalar_values: dict[str, tuple[str | list[str], Decimal | None, bool]] = {
        "{{ABSENDER_NAME}}": (sender_name, None, False),
        "{{ABSENDER_STRASSE}}": (sender_street, None, False),
        "{{ABSENDER_PLZ_ORT}}": (sender_city_line, None, False),
        "{{ERSTELLDATUM}}": (created_on, None, False),
        "{{MIETER_NAME}}": (tenant_name, None, False),
        "{{MIETER_STRASSE}}": (tenant_street, None, False),
        "{{MIETER_PLZ_ORT}}": (tenant_city_line, None, False),
        "{{ABRECHNUNGSZEITRAUM}}": (["Nebenkostenabrechnung", period_label], None, False),
        "{{OBJEKT}}": (object_lines, None, False),
    }
    for marker, (text, number, is_currency) in scalar_values.items():
        row, column = _find_marker(sheet, marker)
        _set_cell(row, column, text, number=number, currency=is_currency)
        if marker == "{{OBJEKT}}":
            _apply_object_row_style(root, row)

    cost_row, _ = _find_marker(sheet, "{{KOSTENART}}")
    total_row, annual_total_column = _find_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
    _, tenant_total_column = _find_marker(sheet, "{{SUMME_MIETERANTEIL}}")
    rows = sheet.findall("table:table-row", NS)
    cost_index = rows.index(cost_row)
    cost_child_index = list(sheet).index(cost_row)
    total_index = rows.index(total_row)
    prototype = deepcopy(cost_row)
    annual_cost_column = _find_marker_in_row(prototype, "{{JAHRESKOSTEN}}")
    tenant_share_column = _find_marker_in_row(prototype, "{{MIETERANTEIL}}")
    cost_label_column = _find_marker_in_row(prototype, "{{KOSTENART}}")
    consumption_column = _find_marker_in_row(prototype, "{{VERBRAUCH}}")
    position_row = _find_position_prototype_row(sheet, cost_row, total_row)
    if position_row is None:
        position_prototype = _position_prototype_from_cost(root, prototype)
    else:
        position_prototype = deepcopy(position_row)
    position_label_column = _find_marker_in_row(position_prototype, "{{POSITION}}")
    position_annual_column = _find_marker_in_row(
        position_prototype, "{{POSITION_JAHRESKOSTEN}}"
    )
    position_share_column = _find_marker_in_row(
        position_prototype, "{{POSITION_MIETERANTEIL}}"
    )
    position_consumption_column = _find_marker_in_row(
        position_prototype, "{{POSITION_VERBRAUCH}}"
    )
    for obsolete_row in rows[cost_index:total_index]:
        sheet.remove(obsolete_row)

    annual_total = sum(
        (Decimal(str(item["period_amount"])) for item in line_items),
        start=Decimal("0"),
    )
    cost_start_row = cost_index + 1
    inserted_row_count = 0
    top_level_row_numbers: list[int] = []
    annual_cost_column_name = _column_name(annual_cost_column)
    tenant_share_column_name = _column_name(tenant_share_column)
    position_annual_column_name = _column_name(position_annual_column)
    position_share_column_name = _column_name(position_share_column)

    def insert_item_row(item: dict, *, subposition: bool = False) -> None:
        nonlocal inserted_row_count
        row = deepcopy(position_prototype if subposition else prototype)
        label = str(item["label"])
        row_label_column = (
            position_label_column if subposition else cost_label_column
        )
        row_annual_column = (
            position_annual_column if subposition else annual_cost_column
        )
        row_share_column = (
            position_share_column if subposition else tenant_share_column
        )
        row_consumption_column = (
            position_consumption_column if subposition else consumption_column
        )
        _set_cell(row, row_label_column, label)
        annual_amount = Decimal(str(item["period_amount"]))
        _set_cell(
            row,
            row_annual_column,
            _format_money(annual_amount),
            number=annual_amount,
            currency=True,
        )
        tenant_share = Decimal(str(item["share"]))
        _set_cell(
            row,
            row_share_column,
            _format_money(tenant_share),
            number=tenant_share,
            currency=True,
        )
        consumption_value = item.get("tenant_consumption_value")
        if consumption_value is None:
            consumption_value = item.get("consumption_value")
        usage = ""
        if consumption_value is not None:
            usage = f"{_format_decimal(consumption_value)} {item.get('consumption_unit') or ''}".strip()
        _set_cell(row, row_consumption_column, usage)
        sheet.insert(cost_child_index + inserted_row_count, row)
        inserted_row_count += 1

    for category, category_items in _group_line_items(line_items):
        top_level_row_number = cost_start_row + inserted_row_count
        top_level_row_numbers.append(top_level_row_number)
        if not _has_subpositions(category, category_items):
            insert_item_row(category_items[0])
            continue

        category_row = deepcopy(prototype)
        category_annual_amount = sum(
            (Decimal(str(item["period_amount"])) for item in category_items),
            start=Decimal("0"),
        )
        category_tenant_share = sum(
            (Decimal(str(item["share"])) for item in category_items),
            start=Decimal("0"),
        )
        subposition_start_row = top_level_row_number + 1
        subposition_end_row = top_level_row_number + len(category_items)
        _set_cell(category_row, cost_label_column, category)
        _set_cell(
            category_row,
            annual_cost_column,
            _format_money(category_annual_amount),
            number=category_annual_amount,
            currency=True,
            formula=(
                f"of:=SUM([.{position_annual_column_name}{subposition_start_row}:"
                f".{position_annual_column_name}{subposition_end_row}])"
            ),
        )
        _set_cell(
            category_row,
            tenant_share_column,
            _format_money(category_tenant_share),
            number=category_tenant_share,
            currency=True,
            formula=(
                f"of:=SUM([.{position_share_column_name}{subposition_start_row}:"
                f".{position_share_column_name}{subposition_end_row}])"
            ),
        )
        _set_cell(category_row, consumption_column, "")
        sheet.insert(cost_child_index + inserted_row_count, category_row)
        inserted_row_count += 1
        for item in category_items:
            insert_item_row(item, subposition=True)

    total_row, annual_total_column = _find_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
    _, tenant_total_column = _find_marker(sheet, "{{SUMME_MIETERANTEIL}}")
    annual_formula = _sum_formula_for_rows(
        annual_cost_column_name, top_level_row_numbers
    )
    share_formula = _sum_formula_for_rows(
        tenant_share_column_name, top_level_row_numbers
    )
    _set_cell(
        total_row,
        annual_total_column,
        _format_money(annual_total),
        number=annual_total,
        currency=True,
        formula=annual_formula,
    )
    _set_cell(
        total_row,
        tenant_total_column,
        _format_money(allocated_costs),
        number=Decimal(allocated_costs),
        currency=True,
        formula=share_formula,
    )

    payment_period_row, payment_period_column = _find_marker(
        sheet, "{{VORAUSZAHLUNG_ZEITRAUM}}"
    )
    payment_title = _find_row_containing(
        sheet.findall("table:table-row", NS), "Geleistete Vorauszahlungen"
    )
    _apply_advance_payment_page_break(root, payment_title)
    payment_row, payment_column = _find_marker(sheet, "{{VORAUSZAHLUNGEN}}")
    advance_row, advance_column = _find_marker(sheet, "{{VORAUSZAHLUNGEN_SUMME}}")
    balance_label_row, balance_label_column = _find_marker(sheet, "{{SALDO_BEZEICHNUNG}}")
    balance_amount_row, balance_amount_column = _find_marker(sheet, "{{SALDO_BETRAG}}")
    notice_row, notice_column = _find_marker(sheet, "{{ERGEBNIS_TEXT}}")

    if advances_paid is None or balance is None:
        # The lease stores an agreed monthly advance, but that is not proof of
        # actual payments. Keep this section in every export as editable ODS
        # structure for the later payment-recording feature, without deriving
        # or calculating any values from the lease today.
        for row, column in (
            (payment_period_row, payment_period_column),
            (payment_row, payment_column),
            (advance_row, advance_column),
            (balance_label_row, balance_label_column),
            (balance_amount_row, balance_amount_column),
            (notice_row, notice_column),
        ):
            _set_cell(row, column, "")
    else:
        rendered_payment_rows: list[ET.Element] = []
        if advance_payments:
            payment_prototype = deepcopy(payment_row)
            payment_insert_index = list(sheet).index(payment_row)
            sheet.remove(payment_row)
            for offset, payment in enumerate(advance_payments):
                rendered_row = deepcopy(payment_prototype)
                booking_date = str(payment.get("booking_date") or "")
                _set_cell(
                    rendered_row,
                    payment_period_column,
                    booking_date or "Vorauszahlung",
                )
                amount = Decimal(str(payment["amount"]))
                _set_cell(
                    rendered_row,
                    payment_column,
                    _format_money(amount),
                    number=amount,
                    currency=True,
                )
                sheet.insert(payment_insert_index + offset, rendered_row)
                rendered_payment_rows.append(rendered_row)
        else:
            _set_cell(payment_period_row, payment_period_column, period_label)
            _set_cell(
                payment_row,
                payment_column,
                _format_money(advances_paid),
                number=Decimal(advances_paid),
                currency=True,
            )
            rendered_payment_rows.append(payment_row)

        first_payment_row_number = _row_number(sheet, rendered_payment_rows[0])
        last_payment_row_number = _row_number(sheet, rendered_payment_rows[-1])
        payment_column_name = _column_name(payment_column)
        _set_cell(
            advance_row,
            advance_column,
            _format_money(advances_paid),
            number=Decimal(advances_paid),
            currency=True,
            formula=(
                f"of:=SUM([.{payment_column_name}{first_payment_row_number}:"
                f".{payment_column_name}{last_payment_row_number}])"
            ),
        )

        balance_value = Decimal(balance)
        balance_label = "Nachzahlung" if balance_value > 0 else "Guthaben" if balance_value < 0 else "Saldo"
        total_row_number = _row_number(sheet, total_row)
        advance_row_number = _row_number(sheet, advance_row)
        tenant_total_column_name = _column_name(tenant_total_column)
        advance_column_name = _column_name(advance_column)
        difference = (
            f"[.{tenant_total_column_name}{total_row_number}]-"
            f"[.{advance_column_name}{advance_row_number}]"
        )
        _set_cell(
            balance_label_row,
            balance_label_column,
            balance_label,
            formula=(
                f'of:=IF({difference}>0;"Nachzahlung";IF({difference}<0;"Guthaben";"Saldo"))'
            ),
        )
        _set_cell(
            balance_amount_row,
            balance_amount_column,
            _format_money(abs(balance_value)),
            number=abs(balance_value),
            currency=True,
            formula=f"of:=ABS({difference})",
        )
        notice = (
            "Bitte überweisen Sie die ausgewiesene Nachzahlung."
            if balance_value > 0
            else "Ihr ausgewiesenes Guthaben wird Ihnen erstattet."
            if balance_value < 0
            else "Die Abrechnung ist ausgeglichen."
        )
        _set_cell(
            notice_row,
            notice_column,
            notice,
            formula=(
                f'of:=IF({difference}>0;"Bitte überweisen Sie die ausgewiesene Nachzahlung.";'
                f'IF({difference}<0;"Ihr ausgewiesenes Guthaben wird Ihnen erstattet.";'
                '"Die Abrechnung ist ausgeglichen."))'
            ),
        )

    # A user may enter long labels or edit fields after the export. Keep all
    # table-row styles content-based; explicit fixed heights otherwise take
    # precedence in LibreOffice even when optimal height is also enabled.
    _apply_optimal_row_heights(root)

    replacements = _sanitize_package_files(
        entries,
        {"content.xml": _serialize_content(root)},
        sheet_name=new_sheet_name,
        old_sheet_name=old_sheet_name,
    )
    return _write_archive(entries, replacements)
