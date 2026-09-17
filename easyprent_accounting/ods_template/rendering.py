from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .cells import (
    CALCEXT_NS, FO_NS, NS, OFFICE_NS, STYLE_NS, TABLE_NS, TEXT_NS,
    _ALLOCATION_MARKERS,
    _cell_text, _cells, _clear_dynamic_cell_data, _expand_repeated_cells,
    _expand_repeated_rows, _find_marker, _find_marker_in_row,
    _find_optional_marker_in_row, _find_position_prototype_row,
    _find_row_containing, _set_cell,
)
from .package import (
    _archive_entries, _read_template_bytes, _sanitize_package_files,
    _serialize_content, _write_archive,
)

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


def _format_allocation_period(value: object) -> str:
    raw = str(value or "")
    try:
        return date.fromisoformat(raw).strftime("%d.%m.%Y")
    except ValueError:
        return raw


def _allocation_method(item: dict) -> str:
    method = str(item.get("allocation_method") or "").strip()
    if not method:
        raise ValueError("settlement line item is missing allocation_method")
    return method


def _render_allocation_keys(
    sheet: ET.Element, line_items: list[dict]
) -> dict[int, list[int]]:
    """Render the optional allocation legend and return references per item."""
    marker_locations = [
        (row, cell)
        for row in sheet.findall("table:table-row", NS)
        for cell in _cells(row)
        if _cell_text(cell).strip() == "{{UMLAGE_NR}}"
    ]
    if not marker_locations:
        return {}

    prototype, _ = _find_marker(sheet, "{{UMLAGE_NR}}")
    columns = {
        marker: _find_marker_in_row(prototype, marker)
        for marker in _ALLOCATION_MARKERS
    }
    insert_index = list(sheet).index(prototype)
    sheet.remove(prototype)
    references_by_item: dict[int, list[int]] = {}
    reference_by_signature: dict[tuple[str, str, str, str, str], int] = {}

    labels = {
        "occupants": "Personen",
        "area": "Flächenanteil",
        "direct": "Direkt",
        "consumption": "Verbrauchsabhängig",
        "unit_count": "Einheiten",
    }
    rendered_rows: list[ET.Element] = []
    for item in line_items:
        kind = _allocation_method(item)
        periods = item.get("allocation_periods") or [{}]
        item_references: list[int] = []
        for period in periods:
            period_start = str(period.get("period_start") or "")
            period_end = str(period.get("period_end") or "")
            total = "" if kind in {"direct", "consumption"} else str(
                period.get("basis_total", item.get("basis_total", ""))
            )
            share = "" if kind in {"direct", "consumption"} else str(
                period.get("basis_value", item.get("basis_value", ""))
            )
            if kind == "area" and total and share:
                total_value = Decimal(total)
                if total_value > 0:
                    share = format(Decimal(share) * Decimal("100") / total_value, "f")
                    total = "100"
            signature = (kind, period_start, period_end, total, share)
            reference = reference_by_signature.get(signature)
            if reference is None:
                reference = len(reference_by_signature) + 1
                reference_by_signature[signature] = reference
                row = deepcopy(prototype)
                period_label = ""
                days_label = ""
                if period_start or period_end:
                    period_label = (
                        f"{_format_allocation_period(period_start)} – "
                        f"{_format_allocation_period(period_end)}"
                    )
                    try:
                        days_label = str(
                            (date.fromisoformat(period_end) - date.fromisoformat(period_start)).days
                            + 1
                        )
                    except ValueError:
                        pass
                if kind == "area":
                    total = f"{_format_decimal(total)} %" if total else ""
                    share = f"{_format_decimal(share)} %" if share else ""
                elif total:
                    total = _format_decimal(total)
                    share = _format_decimal(share)
                values = {
                    "{{UMLAGE_NR}}": str(reference),
                    "{{UMLAGE_ART}}": labels.get(kind, kind),
                    "{{UMLAGE_ZEITRAUM}}": period_label,
                    "{{UMLAGE_TAGE}}": days_label,
                    "{{UMLAGE_GESAMT}}": total,
                    "{{UMLAGE_ANTEIL}}": share,
                }
                for marker, value in values.items():
                    _set_cell(row, columns[marker], value)
                rendered_rows.append(row)
            if reference not in item_references:
                item_references.append(reference)
        references_by_item[id(item)] = item_references

    for offset, row in enumerate(rendered_rows):
        sheet.insert(insert_index + offset, row)
    return references_by_item


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

    allocation_references = _render_allocation_keys(sheet, line_items)

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
    allocation_reference_column = _find_optional_marker_in_row(
        prototype, "{{UMLAGE_REF}}"
    )
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
    position_allocation_reference_column = _find_optional_marker_in_row(
        position_prototype, "{{POSITION_UMLAGE_REF}}"
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
        row_allocation_reference_column = (
            position_allocation_reference_column
            if subposition
            else allocation_reference_column
        )
        if row_allocation_reference_column is not None:
            references = allocation_references.get(id(item), [])
            _set_cell(
                row,
                row_allocation_reference_column,
                ", ".join(str(reference) for reference in references),
            )
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
        if allocation_reference_column is not None:
            _set_cell(category_row, allocation_reference_column, "")
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


