"""Semantic tests for generated PDF settlement documents.

Uses only the Python standard library (base64 + zlib) to decompress text streams
from ReportLab-generated PDFs without any external dependencies like pypdf.
"""
from __future__ import annotations

import base64
import re
import unittest
import zlib

from easyprent_accounting.services import settlement_pdf_for_period
from tests.support import temporary_database


def _extract_pdf_stream_text(data: bytes) -> str:
    """Decompress and extract text from all PDF streams.

    ReportLab compresses text streams with [ /ASCII85Decode /FlateDecode ].
    We decompress every stream using standard library modules.
    """
    chunks: list[str] = []
    stream_re = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
    for match in stream_re.finditer(data):
        raw_stream = match.group(1).strip()
        if raw_stream.endswith(b"~>"):
            try:
                raw_stream = base64.a85decode(raw_stream, adobe=True)
            except Exception:
                pass
        try:
            decompressed = zlib.decompress(raw_stream)
        except Exception:
            decompressed = raw_stream

        chunks.append(decompressed.decode("latin-1", errors="ignore"))

    return "\n".join(chunks)


class PdfDocumentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.connection = self.database.connect(rows=True)

    def test_pdf_is_valid_and_contains_settlement_content(self) -> None:
        document_bytes, filename = settlement_pdf_for_period(
            self.connection,
            property_id=1,
            lease_id=1,
            period_start="2025-01-01",
            period_end="2025-12-31",
        )

        # 1. Structure validation (avoid full binary snapshots)
        self.assertTrue(document_bytes.startswith(b"%PDF-1."), "Output is not a valid PDF")
        self.assertTrue(filename.endswith(".pdf"), f"Filename should end with .pdf: {filename}")
        self.assertGreater(len(document_bytes), 500, "PDF is suspiciously small")

        text = _extract_pdf_stream_text(document_bytes)

        # 2. Concrete addresses
        self.assertIn("Lindenweg 12", text, "Property/tenant street address missing from PDF")
        self.assertIn("10439 Berlin", text, "Postal code and city missing from PDF")

        # 3. Sender and tenant details
        self.assertIn("EasyPrent Demo Verwaltung", text, "Sender organization name missing")
        self.assertIn("Anna Schulz", text, "Tenant name missing from PDF")
        self.assertIn("Mietobjekt: A-01", text, "Unit label missing from PDF")

        # 4. Billing period
        self.assertIn("2025-01-01 bis 2025-12-31", text, "Concrete billing period missing from PDF")

        # 5. Cost categories and formulas / allocation keys
        self.assertIn("Heizung", text, "Cost category 'Heizung' missing")
        self.assertIn("Wasser", text, "Cost category 'Wasser' missing")
        self.assertIn("Treppenhausreinigung", text, "Cost category 'Treppenhausreinigung' missing")
        self.assertIn("Miteigentumsanteile", text, "Allocation key MEA missing")
        self.assertIn("34.0961 / 62.0137", text, "MEA share fraction missing")

        # 6. Concrete sums and totals
        self.assertIn("4.200,00", text, "Heating cost amount missing")
        self.assertIn("336.000,00", text, "Water cost amount missing")
        self.assertIn("900,00", text, "Stair cleaning cost amount missing")
        self.assertIn("254.488,17", text, "Total apportionable costs (Umlagefähige Kosten) missing")


if __name__ == "__main__":
    unittest.main()
