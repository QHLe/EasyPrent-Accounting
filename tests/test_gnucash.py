from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from src.easyprent_accounting.db import SCHEMA, seed_demo_data
from src.easyprent_accounting.integrations.gnucash import GnuCashPayment, PiecashGnuCashReader
from src.easyprent_accounting.services import (
    delete_lease,
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
                "bank_account_guid": "bank-main",
                "bank_account_name": "Bank:Giro",
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
                    amount=Decimal("-75.00"),
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
        self.assertEqual(tenant_result["advances_paid"], "-75.00")
        self.assertEqual(
            tenant_result["balance"],
            f"{Decimal(tenant_result['allocated_costs']) - Decimal('75.00'):.2f}",
        )

    def test_keeps_positive_reversals_signed_and_increases_the_balance(self) -> None:
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="split-refund",
                    transaction_guid="transaction-refund",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 5),
                    amount=Decimal("20.00"),
                    description="Rückzahlung",
                )
            ]
        )

        import_gnucash_payments_for_period(
            self.connection, self.property_id, "2025-01-01", "2025-12-31", reader=reader
        )
        settlement = settlement_for_period(
            self.connection, self.property_id, "2025-01-01", "2025-12-31"
        )

        tenant_result = next(result for result in settlement["results"] if result["lease_id"] == 1)
        self.assertEqual(tenant_result["advances_paid"], "20.00")
        self.assertEqual(
            tenant_result["balance"],
            f"{Decimal(tenant_result['allocated_costs']) + Decimal('20.00'):.2f}",
        )

    def test_import_uses_the_tenant_nk_account_without_a_bank_account(self) -> None:
        update_gnucash_settings(
            self.connection,
            {
                "host": "gnucash.internal",
                "port": 5432,
                "database": "gnucash",
                "username": "easyprent_reader",
                "password": "",
                "sslmode": "require",
            },
        )
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="split-no-bank-link",
                    transaction_guid="transaction-no-bank-link",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 5),
                    amount=Decimal("-75.00"),
                    description="Nebenkostenvorauszahlung",
                )
            ]
        )

        result = import_gnucash_payments_for_period(
            self.connection, self.property_id, "2025-01-01", "2025-12-31", reader=reader
        )

        self.assertEqual(result["imported"], 1)

    def test_rejects_payment_when_multiple_leases_are_active(self) -> None:
        lease = self.connection.execute("SELECT * FROM leases WHERE id = 1").fetchone()
        assert lease is not None
        self.connection.execute(
            """
            INSERT INTO leases (
                unit_id, room_id, tenant_id, rent_cold, additional_charges_advance,
                occupant_count, start_date, end_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lease["unit_id"], lease["room_id"], lease["tenant_id"], lease["rent_cold"],
                lease["additional_charges_advance"], lease["occupant_count"],
                "2025-01-01", "2025-12-31", lease["status"],
            ),
        )
        self.connection.commit()
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="split-ambiguous",
                    transaction_guid="transaction-ambiguous",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 5),
                    amount=Decimal("75.00"),
                    description="Nebenkostenvorauszahlung",
                )
            ]
        )

        with self.assertRaisesRegex(ValueError, "exactly one active lease"):
            import_gnucash_payments_for_period(
                self.connection, self.property_id, "2025-01-01", "2025-12-31", reader=reader
            )

    def test_rejects_deleting_a_lease_with_imported_payments(self) -> None:
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="split-protected-lease",
                    transaction_guid="transaction-protected-lease",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 5),
                    amount=Decimal("75.00"),
                    description="Nebenkostenvorauszahlung",
                )
            ]
        )
        import_gnucash_payments_for_period(
            self.connection, self.property_id, "2025-01-01", "2025-12-31", reader=reader
        )

        with self.assertRaisesRegex(ValueError, "GnuCash payments exist"):
            delete_lease(self.connection, 1)


class PiecashGnuCashReaderTests(unittest.TestCase):
    def test_connection_error_never_contains_the_password_or_uri(self) -> None:
        fake_piecash = SimpleNamespace(
            open_book=mock.Mock(side_effect=RuntimeError(
                "Database 'postgresql+psycopg2://postgres:secret-password@db/book' does not exist"
            ))
        )
        reader = PiecashGnuCashReader()

        with mock.patch.dict(sys.modules, {"piecash": fake_piecash}):
            with self.assertRaisesRegex(ValueError, "GnuCash connection failed") as context:
                reader.list_accounts(
                    {
                        "host": "db",
                        "port": 5432,
                        "database": "book",
                        "username": "postgres",
                        "password": "secret-password",
                        "sslmode": "require",
                    }
                )

        self.assertNotIn("secret-password", str(context.exception))
        self.assertNotIn("postgresql+psycopg2://", str(context.exception))
        self.assertIsNone(context.exception.__cause__)

    def test_preserves_the_sign_of_a_nk_account_split(self) -> None:
        transaction = SimpleNamespace(
            guid="transaction-refund",
            post_date=date(2025, 1, 5),
            description="Rückzahlung",
        )
        split = SimpleNamespace(guid="split-refund", value=Decimal("-20.00"), transaction=transaction)
        account = SimpleNamespace(
            guid="nk-tenant-1",
            parent=SimpleNamespace(guid="tenant-1"),
            splits=[split],
        )
        book = SimpleNamespace(accounts=[account], close=lambda: None)
        reader = PiecashGnuCashReader()
        reader._open_book = lambda settings: book  # type: ignore[method-assign]

        payments = reader.list_payments({}, {"nk-tenant-1"}, date(2025, 1, 1), date(2025, 1, 31))

        self.assertEqual(payments[0].amount, Decimal("-20.00"))
