from __future__ import annotations

import unittest

from easyprent_accounting.settlement_runs import create_or_open_settlement_run
from tests.support import in_memory_database


class SettlementRunTransactionTests(unittest.TestCase):
    def test_run_creation_uses_the_callers_transaction(self) -> None:
        connection = in_memory_database()
        self.addCleanup(connection.close)

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with connection:
                create_or_open_settlement_run(
                    connection, {"property_id": 1, "year": 2025}
                )
                raise RuntimeError("rollback")

        count = connection.execute("SELECT COUNT(*) FROM settlement_runs").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
