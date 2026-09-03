from __future__ import annotations

from copy import copy
from importlib import resources
from io import BytesIO
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from src.easyprent_accounting.ods_template import (
    prepare_settlement_template_bytes,
    render_settlement_template,
)


TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
STYLE_NS = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
MANIFEST_NS = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
CONFIG_NS = "urn:oasis:names:tc:opendocument:xmlns:config:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
FO_NS = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
META_NS = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
DC_NS = "http://purl.org/dc/elements/1.1/"
CELL_TAGS = {
    f"{{{TABLE_NS}}}table-cell",
    f"{{{TABLE_NS}}}covered-table-cell",
}


def _template_bytes() -> bytes:
    return (
        resources.files("src.easyprent_accounting")
        .joinpath("templates")
        .joinpath("utility_settlement.ods")
        .read_bytes()
    )


def _rewrite_archive(
    document: bytes,
    replacements: dict[str, bytes],
    *,
    omit_prefixes: tuple[str, ...] = (),
    additions: dict[str, bytes] | None = None,
) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(document)) as source, ZipFile(output, "w") as target:
        for source_entry in source.infolist():
            if source_entry.filename.startswith(omit_prefixes):
                continue
            entry = copy(source_entry)
            target.writestr(
                entry,
                replacements.get(entry.filename, source.read(source_entry.filename)),
            )
        for filename, data in (additions or {}).items():
            target.writestr(filename, data)
    return output.getvalue()


def _with_stale_thumbnail(document: bytes) -> bytes:
    with ZipFile(BytesIO(document)) as archive:
        manifest = ET.fromstring(archive.read("META-INF/manifest.xml"))
    full_path_attribute = f"{{{MANIFEST_NS}}}full-path"
    for entry in list(manifest.findall(f"{{{MANIFEST_NS}}}file-entry")):
        if (entry.get(full_path_attribute) or "").startswith("Thumbnails/"):
            manifest.remove(entry)
    ET.SubElement(
        manifest,
        f"{{{MANIFEST_NS}}}file-entry",
        {
            full_path_attribute: "Thumbnails/thumbnail.png",
            f"{{{MANIFEST_NS}}}media-type": "image/png",
        },
    )
    return _rewrite_archive(
        document,
        {
            "META-INF/manifest.xml": ET.tostring(
                manifest, encoding="utf-8", xml_declaration=True
            )
        },
        omit_prefixes=("Thumbnails/",),
        additions={"Thumbnails/thumbnail.png": b"stale sample preview"},
    )


def _with_private_metadata(document: bytes) -> bytes:
    with ZipFile(BytesIO(document)) as archive:
        meta = ET.fromstring(archive.read("meta.xml"))
        settings = ET.fromstring(archive.read("settings.xml"))

    office_meta = meta.find(f".//{{{OFFICE_NS}}}meta")
    if office_meta is None:
        raise AssertionError("test document has no office metadata")
    ET.SubElement(office_meta, f"{{{META_NS}}}initial-creator").text = "Private Person"
    ET.SubElement(office_meta, f"{{{DC_NS}}}creator").text = "Private Person"

    name_attribute = f"{{{CONFIG_NS}}}name"
    settings_container = settings.find(f".//{{{CONFIG_NS}}}config-item-set")
    if settings_container is None:
        raise AssertionError("test document has no settings container")
    for name, value_type, value in (
        ("PrinterName", "string", "Private Office Printer"),
        ("PrinterSetup", "base64Binary", "private-printer-setup"),
    ):
        item = ET.SubElement(
            settings_container,
            f"{{{CONFIG_NS}}}config-item",
            {
                name_attribute: name,
                f"{{{CONFIG_NS}}}type": value_type,
            },
        )
        item.text = value
    for named_map in settings.findall(f".//{{{CONFIG_NS}}}config-item-map-named"):
        if named_map.get(name_attribute) in {"Tables", "ScriptConfiguration"}:
            ET.SubElement(
                named_map,
                f"{{{CONFIG_NS}}}config-item-map-entry",
                {name_attribute: "Sheet2"},
            )

    return _rewrite_archive(
        document,
        {
            "meta.xml": ET.tostring(meta, encoding="utf-8", xml_declaration=True),
            "settings.xml": ET.tostring(
                settings, encoding="utf-8", xml_declaration=True
            ),
        },
    )


def _swap_markers(root: ET.Element, first: str, second: str) -> None:
    paragraphs = root.findall(f".//{{{TEXT_NS}}}p")
    first_paragraph = next(p for p in paragraphs if "".join(p.itertext()) == first)
    second_paragraph = next(p for p in paragraphs if "".join(p.itertext()) == second)
    first_paragraph.text, second_paragraph.text = second, first


def _move_marker(root: ET.Element, marker: str, target_column: int) -> None:
    for row in root.findall(f".//{{{TABLE_NS}}}table-row"):
        cells = [cell for cell in row if cell.tag in CELL_TAGS]
        source_cell = next(
            (
                cell
                for cell in cells
                if any(
                    "".join(paragraph.itertext()) == marker
                    for paragraph in cell.findall(f"{{{TEXT_NS}}}p")
                )
            ),
            None,
        )
        if source_cell is None:
            continue
        target_cell = cells[target_column - 1]
        if target_cell.tag != f"{{{TABLE_NS}}}table-cell":
            raise AssertionError("test marker target must be a regular table cell")
        for paragraph in source_cell.findall(f"{{{TEXT_NS}}}p"):
            source_cell.remove(paragraph)
        for paragraph in target_cell.findall(f"{{{TEXT_NS}}}p"):
            target_cell.remove(paragraph)
        paragraph = ET.SubElement(target_cell, f"{{{TEXT_NS}}}p")
        paragraph.text = marker
        return
    raise AssertionError(f"marker not found: {marker}")


def _with_relocated_formula_markers(document: bytes) -> bytes:
    with ZipFile(BytesIO(document)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    _swap_markers(root, "{{JAHRESKOSTEN}}", "{{MIETERANTEIL}}")
    _swap_markers(root, "{{SUMME_JAHRESKOSTEN}}", "{{SUMME_MIETERANTEIL}}")
    _swap_markers(root, "{{VORAUSZAHLUNG_ZEITRAUM}}", "{{VORAUSZAHLUNGEN}}")
    _move_marker(root, "{{VORAUSZAHLUNGEN_SUMME}}", 1)
    return _rewrite_archive(
        document,
        {"content.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True)},
    )


def _with_large_trailing_blank_repeat(document: bytes) -> bytes:
    with ZipFile(BytesIO(document)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    sheet = root.find(f".//{{{TABLE_NS}}}table")
    if sheet is None:
        raise AssertionError("test document has no sheet")
    trailing_row = ET.SubElement(
        sheet,
        f"{{{TABLE_NS}}}table-row",
        {f"{{{TABLE_NS}}}number-rows-repeated": "1048500"},
    )
    ET.SubElement(
        trailing_row,
        f"{{{TABLE_NS}}}table-cell",
        {f"{{{TABLE_NS}}}number-columns-repeated": "7"},
    )
    return _rewrite_archive(
        document,
        {"content.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True)},
    )


def _row_containing_marker(sheet: ET.Element, marker: str) -> ET.Element:
    for row in sheet.findall(f"{{{TABLE_NS}}}table-row"):
        if any(
            "".join(paragraph.itertext()) == marker
            for cell in row
            if cell.tag in CELL_TAGS
            for paragraph in cell.findall(f"{{{TEXT_NS}}}p")
        ):
            return row
    raise AssertionError(f"marker row not found: {marker}")


def _without_position_prototype(document: bytes) -> bytes:
    with ZipFile(BytesIO(document)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    sheet = root.find(f".//{{{TABLE_NS}}}table")
    if sheet is None:
        raise AssertionError("test document has no sheet")
    sheet.remove(_row_containing_marker(sheet, "{{POSITION}}"))
    return _rewrite_archive(
        document,
        {"content.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True)},
    )


def _with_misplaced_position_prototype(document: bytes) -> bytes:
    with ZipFile(BytesIO(document)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    sheet = root.find(f".//{{{TABLE_NS}}}table")
    if sheet is None:
        raise AssertionError("test document has no sheet")
    position_row = _row_containing_marker(sheet, "{{POSITION}}")
    total_row = _row_containing_marker(sheet, "{{SUMME_JAHRESKOSTEN}}")
    sheet.remove(position_row)
    sheet.insert(list(sheet).index(total_row) + 1, position_row)
    return _rewrite_archive(
        document,
        {"content.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True)},
    )


def _render(
    document: bytes,
    period_label: str = "01.01.2026 – 31.12.2026",
    line_items: list[dict] | None = None,
    allocated_costs: str = "300.00",
    advances_paid: str | None = "100.00",
    balance: str | None = "200.00",
) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        template_path = Path(directory) / "template.ods"
        template_path.write_bytes(document)
        return render_settlement_template(
            template_path,
            sender_name="Vermieter",
            sender_street="Absenderweg 1",
            sender_city_line="12345 Musterstadt",
            tenant_name="Testmieter",
            tenant_street="Mieterweg 2",
            tenant_city_line="54321 Beispielstadt",
            object_lines=["WE 1", "Objektstraße 3", "99999 Objektstadt"],
            created_on="01.09.2026",
            period_label=period_label,
            line_items=line_items
            or [
                {
                    "label": "Testkosten",
                    "period_amount": "1200.00",
                    "share": "300.00",
                }
            ],
            allocated_costs=allocated_costs,
            advances_paid=advances_paid,
            balance=balance,
        )


class OdsTemplateTests(unittest.TestCase):
    def assert_has_no_thumbnail(self, document: bytes) -> None:
        with ZipFile(BytesIO(document)) as archive:
            self.assertFalse(
                any(name.startswith("Thumbnails/") for name in archive.namelist())
            )
            manifest = ET.fromstring(archive.read("META-INF/manifest.xml"))
        paths = {
            entry.get(f"{{{MANIFEST_NS}}}full-path")
            for entry in manifest.findall(f"{{{MANIFEST_NS}}}file-entry")
        }
        self.assertFalse(any((path or "").startswith("Thumbnails/") for path in paths))

    def assert_has_no_private_metadata(self, document: bytes) -> None:
        with ZipFile(BytesIO(document)) as archive:
            meta_bytes = archive.read("meta.xml")
            settings_bytes = archive.read("settings.xml")
        meta = ET.fromstring(meta_bytes)
        settings = ET.fromstring(settings_bytes)
        office_meta = meta.find(f".//{{{OFFICE_NS}}}meta")
        self.assertIsNotNone(office_meta)
        self.assertIsNone(office_meta.find(f"{{{META_NS}}}initial-creator"))
        self.assertIsNone(office_meta.find(f"{{{META_NS}}}printed-by"))
        self.assertIsNone(office_meta.find(f"{{{DC_NS}}}creator"))
        statistic = office_meta.find(f"{{{META_NS}}}document-statistic")
        self.assertIsNotNone(statistic)
        self.assertEqual(statistic.get(f"{{{META_NS}}}table-count"), "1")

        name_attribute = f"{{{CONFIG_NS}}}name"
        config_names = {
            item.get(name_attribute, "")
            for item in settings.findall(f".//{{{CONFIG_NS}}}config-item")
        }
        self.assertFalse(any(name.startswith("Printer") for name in config_names))
        sheet_entries = {
            entry.get(name_attribute, "")
            for entry in settings.findall(
                f".//{{{CONFIG_NS}}}config-item-map-entry"
            )
        }
        self.assertNotIn("Sheet2", sheet_entries)
        self.assertNotIn(b"Private Person", meta_bytes)
        self.assertNotIn(b"Private Office Printer", settings_bytes)

    def test_preparation_and_rendering_remove_stale_thumbnail(self) -> None:
        stale_template = _with_private_metadata(
            _with_stale_thumbnail(_template_bytes())
        )

        prepared = prepare_settlement_template_bytes(stale_template)
        rendered = _render(stale_template)

        self.assert_has_no_thumbnail(prepared)
        self.assert_has_no_private_metadata(prepared)
        self.assert_has_no_thumbnail(rendered)
        self.assert_has_no_private_metadata(rendered)

    def test_packaged_master_is_sanitized(self) -> None:
        document = _template_bytes()

        self.assert_has_no_thumbnail(document)
        self.assert_has_no_private_metadata(document)

    def test_preparation_upgrades_legacy_master_with_position_prototype(self) -> None:
        prepared = prepare_settlement_template_bytes(
            _without_position_prototype(_template_bytes())
        )

        with ZipFile(BytesIO(prepared)) as archive:
            content = archive.read("content.xml").decode("utf-8")
        for marker in (
            "{{POSITION}}",
            "{{POSITION_JAHRESKOSTEN}}",
            "{{POSITION_MIETERANTEIL}}",
            "{{POSITION_VERBRAUCH}}",
        ):
            self.assertEqual(content.count(marker), 1)

        rendered = _render(
            prepared,
            line_items=[
                {
                    "expense_category": "Heizung",
                    "label": "Grundkosten",
                    "period_amount": "10.00",
                    "share": "2.00",
                },
                {
                    "expense_category": "Heizung",
                    "label": "Verbrauch",
                    "period_amount": "20.00",
                    "share": "3.00",
                },
            ],
            allocated_costs="5.00",
        )
        with ZipFile(BytesIO(rendered)) as archive:
            rendered_content = archive.read("content.xml").decode("utf-8")
        self.assertIn("<text:p>Grundkosten</text:p>", rendered_content)
        self.assertNotIn("↳", rendered_content)
        self.assertNotIn("{{POSITION", rendered_content)

    def test_render_rejects_position_prototype_outside_cost_block(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be between"):
            _render(_with_misplaced_position_prototype(_template_bytes()))

    def test_render_names_sheet_and_active_table_for_settlement_year(self) -> None:
        document = _render(_template_bytes())

        with ZipFile(BytesIO(document)) as archive:
            content = ET.fromstring(archive.read("content.xml"))
            settings = ET.fromstring(archive.read("settings.xml"))
        sheet = content.find(f".//{{{TABLE_NS}}}table")
        self.assertIsNotNone(sheet)
        self.assertEqual(sheet.get(f"{{{TABLE_NS}}}name"), "2026")
        active_table = next(
            item
            for item in settings.findall(f".//{{{CONFIG_NS}}}config-item")
            if item.get(f"{{{CONFIG_NS}}}name") == "ActiveTable"
        )
        self.assertEqual(active_table.text, "2026")
        self.assert_has_no_private_metadata(document)

    def test_render_keeps_blank_advance_payment_section_for_manual_entry(self) -> None:
        document = _render(
            _template_bytes(),
            advances_paid=None,
            balance=None,
        )

        with ZipFile(BytesIO(document)) as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("Geleistete Vorauszahlungen", content)
        self.assertNotIn("{{", content)
        self.assertNotIn("of:=ABS(", content)
        self.assertNotIn("Nachzahlung", content)
        self.assertNotIn("Guthaben", content)

    def test_render_subtracts_positive_advance_payments_from_costs_for_balance(self) -> None:
        document = _render(
            _template_bytes(),
            allocated_costs="300.00",
            advances_paid="100.00",
            balance="200.00",
        )

        with ZipFile(BytesIO(document)) as archive:
            root = ET.fromstring(archive.read("content.xml"))
            content = archive.read("content.xml").decode("utf-8")
        formulas = {
            cell.get(f"{{{TABLE_NS}}}formula")
            for cell in root.findall(f".//{{{TABLE_NS}}}table-cell")
            if cell.get(f"{{{TABLE_NS}}}formula")
        }

        self.assertIn("100,00 €", content)
        self.assertTrue(
            any(
                formula.startswith("of:=ABS(") and "]-" in formula
                for formula in formulas
            )
        )

    def test_render_left_aligns_all_cost_amounts(self) -> None:
        document = _render(
            _template_bytes(),
            advances_paid=None,
            balance=None,
        )

        with ZipFile(BytesIO(document)) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        styles = {
            style.get(f"{{{STYLE_NS}}}name"): style
            for style in root.findall(f".//{{{STYLE_NS}}}style")
        }
        currency_cells = [
            cell
            for cell in root.findall(f".//{{{TABLE_NS}}}table-cell")
            if cell.get(f"{{{OFFICE_NS}}}value-type") == "currency"
        ]
        self.assertTrue(currency_cells)
        for cell in currency_cells:
            style = styles[cell.get(f"{{{TABLE_NS}}}style-name")]
            paragraph_properties = style.find(
                f"{{{STYLE_NS}}}paragraph-properties"
            )
            self.assertIsNotNone(paragraph_properties)
            self.assertEqual(
                paragraph_properties.get(f"{{{FO_NS}}}text-align"),
                "start",
            )

    def test_formulas_follow_relocated_marker_columns(self) -> None:
        document = _render(_with_relocated_formula_markers(_template_bytes()))

        with ZipFile(BytesIO(document)) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        formulas = {
            cell.get(f"{{{TABLE_NS}}}formula")
            for cell in root.findall(f".//{{{TABLE_NS}}}table-cell")
            if cell.get(f"{{{TABLE_NS}}}formula")
        }
        self.assertTrue(
            any(re.fullmatch(r"of:=SUM\(\[\.E\d+:\.E\d+\]\)", formula) for formula in formulas)
        )
        self.assertTrue(
            any(re.fullmatch(r"of:=SUM\(\[\.C\d+:\.C\d+\]\)", formula) for formula in formulas)
        )
        self.assertTrue(any(re.fullmatch(r"of:=\[\.A\d+\]", formula) for formula in formulas))
        self.assertTrue(
            any(
                re.fullmatch(r"of:=ABS\(\[\.C\d+\]-\[\.A\d+\]\)", formula)
                for formula in formulas
            )
        )

    def test_render_groups_cost_categories_without_double_counting(self) -> None:
        document = _render(
            _template_bytes(),
            line_items=[
                {
                    "expense_category": "Heizung",
                    "label": "Grundkosten",
                    "period_amount": "100.00",
                    "share": "40.00",
                },
                {
                    "expense_category": "heizung",
                    "label": "Verbrauch WE 206",
                    "period_amount": "300.00",
                    "share": "90.00",
                    "tenant_consumption_value": "123.4567",
                    "consumption_unit": "kWh",
                },
                {
                    "expense_category": "Grundsteuer",
                    "label": "Grundsteuer",
                    "period_amount": "200.00",
                    "share": "50.00",
                },
            ],
            allocated_costs="180.00",
        )

        with ZipFile(BytesIO(document)) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        rows = root.findall(f".//{{{TABLE_NS}}}table-row")

        def row_text(row: ET.Element) -> str:
            return " ".join(
                "".join(paragraph.itertext())
                for paragraph in row.findall(f".//{{{TEXT_NS}}}p")
            ).strip()

        cost_rows = [
            row
            for row in rows
            if row_text(row).startswith(
                ("Heizung", "Grundkosten", "Verbrauch WE 206", "Grundsteuer")
            )
        ]
        self.assertEqual(
            [row_text(row).split("  ", 1)[0] for row in cost_rows],
            [
                "Heizung 400,00 € 130,00 €",
                "Grundkosten 100,00 € 40,00 €",
                "Verbrauch WE 206 300,00 € 90,00 € 123,457 kWh",
                "Grundsteuer 200,00 € 50,00 €",
            ],
        )
        heating_row_number = rows.index(cost_rows[0]) + 1
        first_position_row_number = rows.index(cost_rows[1]) + 1
        second_position_row_number = rows.index(cost_rows[2]) + 1
        tax_row_number = rows.index(cost_rows[3]) + 1
        heating_cells = [cell for cell in cost_rows[0] if cell.tag in CELL_TAGS]
        self.assertEqual(
            heating_cells[2].get(f"{{{TABLE_NS}}}formula"),
            f"of:=SUM([.D{first_position_row_number}:.D{second_position_row_number}])",
        )
        self.assertEqual(
            heating_cells[4].get(f"{{{TABLE_NS}}}formula"),
            f"of:=SUM([.F{first_position_row_number}:.F{second_position_row_number}])",
        )
        self.assertEqual(row_text(cost_rows[0]).endswith("130,00 €"), True)
        total_row = next(
            row for row in rows if row_text(row).startswith(("Total", "Summe"))
        )
        total_cells = [cell for cell in total_row if cell.tag in CELL_TAGS]
        self.assertEqual(
            total_cells[2].get(f"{{{TABLE_NS}}}formula"),
            f"of:=SUM([.C{heating_row_number}];[.C{tax_row_number}])",
        )
        self.assertEqual(
            total_cells[4].get(f"{{{TABLE_NS}}}formula"),
            f"of:=SUM([.E{heating_row_number}];[.E{tax_row_number}])",
        )
        self.assertEqual(total_cells[2].get(f"{{{OFFICE_NS}}}value"), "600.00")
        self.assertEqual(total_cells[4].get(f"{{{OFFICE_NS}}}value"), "180.00")

    def test_single_differing_position_gets_category_and_child_row(self) -> None:
        document = _render(
            _template_bytes(),
            line_items=[
                {
                    "expense_category": "Versicherung",
                    "label": "Gebäudeversicherung Police A",
                    "period_amount": "120.00",
                    "share": "30.00",
                }
            ],
            allocated_costs="30.00",
        )

        with ZipFile(BytesIO(document)) as archive:
            content = archive.read("content.xml").decode("utf-8")
        self.assertIn("<text:p>Versicherung</text:p>", content)
        self.assertIn("<text:p>Gebäudeversicherung Police A</text:p>", content)
        self.assertNotIn("↳", content)

    def test_render_collapses_large_trailing_blank_row_repeat(self) -> None:
        document = _render(_with_large_trailing_blank_repeat(_template_bytes()))

        with ZipFile(BytesIO(document)) as archive:
            content = ET.fromstring(archive.read("content.xml"))
        rows = content.findall(f".//{{{TABLE_NS}}}table-row")
        self.assertLess(len(rows), 100)
        self.assertFalse(
            any(
                row.get(f"{{{TABLE_NS}}}number-rows-repeated")
                for row in rows
            )
        )

    def test_render_formats_long_consumption_and_expands_object_row(self) -> None:
        document = _render(
            _template_bytes(),
            line_items=[
                {
                    "label": "Wasser",
                    "period_amount": "12.00",
                    "share": "3.00",
                    "tenant_consumption_value": "0.1180547945205479452054795",
                    "consumption_unit": "m3",
                }
            ],
        )

        with ZipFile(BytesIO(document)) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        text = " ".join(
            "".join(paragraph.itertext())
            for paragraph in root.findall(f".//{{{TEXT_NS}}}p")
        )
        self.assertIn("0,118 m3", text)
        self.assertNotIn("0,118054", text)
        object_row = next(
            row
            for row in root.findall(f".//{{{TABLE_NS}}}table-row")
            if "WE 1"
            in " ".join(
                "".join(paragraph.itertext())
                for paragraph in row.findall(f".//{{{TEXT_NS}}}p")
            )
        )
        self.assertEqual(
            object_row.get(f"{{{TABLE_NS}}}style-name"), "roEasyObject"
        )
        row_properties = next(
            style.find(f"{{{STYLE_NS}}}table-row-properties")
            for style in root.findall(f".//{{{STYLE_NS}}}style")
            if style.get(f"{{{STYLE_NS}}}name") == "roEasyObject"
        )
        self.assertIsNotNone(row_properties)
        self.assertEqual(
            row_properties.get(f"{{{STYLE_NS}}}row-height"), "0.8in"
        )


if __name__ == "__main__":
    unittest.main()
