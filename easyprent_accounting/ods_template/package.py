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
import easyprent_accounting.ods_template.markers as markers
import easyprent_accounting.ods_template.rendering as rendering

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

def _packaged_template_bytes() -> bytes:
    packaged_template = resources.files("easyprent_accounting").joinpath("templates", _TEMPLATE_FILENAME)
    if not packaged_template.is_file():
        raise ValueError("packaged settlement template is missing")
    return packaged_template.read_bytes()

def _read_template_bytes(template_path: Path | None) -> bytes:
    if template_path is not None:
        if not template_path.is_file():
            raise ValueError(f"configured settlement template does not exist: {template_path}")
        return template_path.read_bytes()

    return _packaged_template_bytes()

def _serialize_content(root: ET.Element) -> bytes:
    content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if b"xmlns:of=" not in content:
        content = content.replace(
            b"<office:document-content ",
            f'<office:document-content xmlns:of="{OF_NS}" '.encode("ascii"),
            1,
        )
    return content

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

