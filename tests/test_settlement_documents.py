from __future__ import annotations

import unittest

from easyprent_accounting.settlement_documents import SettlementDocuments
from tests.support import in_memory_database


class SettlementDocumentModelTests(unittest.TestCase):
    def test_model_contains_the_data_shared_by_pdf_and_ods(self) -> None:
        connection = in_memory_database()
        self.addCleanup(connection.close)

        document = SettlementDocuments(connection).model_for_period(
            property_id=1,
            lease_id=1,
            period_start="2025-01-01",
            period_end="2025-12-31",
        )

        self.assertEqual(document.tenant_name, "Anna Schulz")
        self.assertEqual(document.object_label, "A-01")
        self.assertEqual(document.billing_period_start, "2025-01-01")
        self.assertEqual(document.billing_period_end, "2025-12-31")
        self.assertEqual(document.allocated_costs, "254488.17")
        self.assertEqual([item.label for item in document.line_items], [
            "Heizung", "Wasser", "Treppenhausreinigung",
        ])


if __name__ == "__main__":
    unittest.main()
