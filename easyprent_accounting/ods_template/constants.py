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
__all__ = ["TABLE_NS", "TEXT_NS", "OFFICE_NS", "STYLE_NS", "NUMBER_NS", "FO_NS", "CALCEXT_NS", "OF_NS", "MANIFEST_NS", "CONFIG_NS", "META_NS", "DC_NS", "NS", "_CELL_TAGS", "_TEMPLATE_FILENAME", "_POSITION_MARKERS", "_ALLOCATION_MARKERS"]
