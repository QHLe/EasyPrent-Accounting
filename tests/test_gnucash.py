from __future__ import annotations

import sqlite3
import unittest
from datetime import date
from decimal import Decimal

from src.easyprent_accounting.db import SCHEMA, seed_demo_data
from src.easyprent_accounting.integrations.gnucash import GnuCashPayment
from src.easyprent_accounting.services import (
    import_gnucash_payments_for_period,
    settlement_for_period,
    update_gnucash_settings,
    update_tenant,
)


class FakeGnuCashReader:
    def __init__(self, payments: list[GnuCashPayment]) -> None:
        self.payments = payments
        self.requests: list[tuple[set[str], date, date]] = []

    def list_payments(
        self,
        settings: dict,
        account_guids: set[str],
        period_start: date,
        period_end: date,
    ) -> list[GnuCashPayment]:
        self.requests.append((account_guids, period_start, period_end))
        return [
            payment
            for payment in self.payments
            if payment.account_guid in account_guids
            and period_start <= payment.booking_date <= period_end
        ]


class GnuCashPaymentImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        seed_demo_data(self.connection)

        tenant = self.connection.execute("SELECT * FROM tenants ORDER BY id LIMIT 1").fetchone()
        assert tenant is not None
        self.tenant_id = int(tenant["id"])
        self.property_id = int(
            self.connection.execute("SELECT id FROM properties ORDER BY id LIMIT 1").fetchone()["id"]
        )
        update_tenant(
            self.connection,
            self.tenant_id,
            {
                "full_name": tenant["full_name"],
                "email": tenant["email"],
                "phone": tenant["phone"],
                "alternate_street": tenant["alternate_street"],
                "alternate_postal_code": tenant["alternate_postal_code"],
                "alternate_city": tenant["alternate_city"],
                "gnucash_nk_account_guid": "nk-tenant-1",
                "gnucash_nk_account_name": "Mieter 1:Nebenkosten",
            },
        )
        update_gnucash_settings(
            self.connection,
            {
                "host": "gnucash.internal",
                "port": 5432,
                "database": "gnucash",
                "username": "easyprent_reader",
                "password": "not-exported",
                "sslmode": "require",
            },
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_imports_each_matching_split_once_and_uses_booking_month_for_settlement(self) -> None:
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="split-jan-payment",
                    transaction_guid="transaction-jan-payment",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 5),
                    amount=Decimal("75.00"),
                    description="Nebenkostenvorauszahlung Januar",
                )
            ]
        )

        first_import = import_gnucash_payments_for_period(
            self.connection,
            self.property_id,
            "2025-01-01",
            "2025-12-31",
            reader=reader,
        )
        repeated_import = import_gnucash_payments_for_period(
            self.connection,
            self.property_id,
            "2025-01-01",
            "2025-12-31",
            reader=reader,
        )
        settlement = settlement_for_period(
            self.connection,
            self.property_id,
            "2025-01-01",
            "2025-12-31",
        )
        tenant_result = next(
            result for result in settlement["results"] if result["lease_id"] == 1
        )

        self.assertEqual(first_import["imported"], 1)
        self.assertEqual(first_import["existing"], 0)
        self.assertEqual(repeated_import["imported"], 0)
        self.assertEqual(repeated_import["existing"], 1)
        self.assertEqual(reader.requests[0][0], {"nk-tenant-1"})
        self.assertEqual(tenant_result["advances_paid"], "75.00")
        self.assertEqual(
            tenant_result["balance"],
            f"{Decimal(tenant_result['allocated_costs']) - Decimal('75.00'):.2f}",
        )

