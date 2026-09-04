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
    create_or_open_settlement_run,
    delete_lease,
    get_settlement_run_overview,
    import_gnucash_payments_for_period,
    refresh_settlement_run_payments,
    set_settlement_payment_considered,
    settlement_for_period,
    update_gnucash_settings,
    update_lease,
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

        lease = self.connection.execute("SELECT * FROM leases ORDER BY id LIMIT 1").fetchone()
        assert lease is not None
        self.tenant_id = int(lease["tenant_id"])
        self.property_id = int(
            self.connection.execute("SELECT id FROM properties ORDER BY id LIMIT 1").fetchone()["id"]
        )
        update_lease(
            self.connection,
            int(lease["id"]),
            {
                "unit_id": lease["unit_id"],
                "room_id": lease["room_id"],
                "tenant_id": lease["tenant_id"],
                "rent_cold": lease["rent_cold"],
                "additional_charges_advance": lease["additional_charges_advance"],
                "occupant_count": lease["occupant_count"],
                "start_date": lease["start_date"],
                "end_date": lease["end_date"],
                "status": lease["status"],
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

    def test_links_the_gnucash_nk_account_to_the_lease(self) -> None:
        lease = self.connection.execute("SELECT * FROM leases WHERE id = 1").fetchone()
        assert lease is not None

        updated = update_lease(
            self.connection,
            1,
            {
                "unit_id": lease["unit_id"],
                "room_id": lease["room_id"],
                "tenant_id": lease["tenant_id"],
                "rent_cold": lease["rent_cold"],
                "additional_charges_advance": lease["additional_charges_advance"],
                "occupant_count": lease["occupant_count"],
                "start_date": lease["start_date"],
                "end_date": lease["end_date"],
                "status": lease["status"],
                "gnucash_nk_account_guid": "nk-lease-1",
                "gnucash_nk_account_name": "Mietvertrag 1:Nebenkosten",
            },
        )

        self.assertEqual(updated["gnucash_nk_account_guid"], "nk-lease-1")
        stored = self.connection.execute(
            "SELECT gnucash_nk_account_guid FROM leases WHERE id = 1"
        ).fetchone()
        self.assertEqual(stored["gnucash_nk_account_guid"], "nk-lease-1")

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
        self.assertEqual(tenant_result["advances_paid"], "75.00")
        self.assertEqual(
            tenant_result["balance"],
            f"{Decimal(tenant_result['allocated_costs']) - Decimal('75.00'):.2f}",
        )
        self.assertEqual(settlement["totals"]["advances"], "75.00")
        self.assertEqual(
            settlement["totals"]["balance"],
            f"{Decimal(settlement['totals']['costs']) - Decimal('75.00'):.2f}",
        )

    def test_ignores_payment_before_lease_start(self) -> None:
        lease = self.connection.execute("SELECT * FROM leases WHERE id = 1").fetchone()
        assert lease is not None
        update_lease(
            self.connection,
            1,
            {
                "unit_id": lease["unit_id"],
                "room_id": lease["room_id"],
                "tenant_id": lease["tenant_id"],
                "rent_cold": lease["rent_cold"],
                "additional_charges_advance": lease["additional_charges_advance"],
                "occupant_count": lease["occupant_count"],
                "start_date": "2025-02-01",
                "end_date": lease["end_date"],
                "status": lease["status"],
                "gnucash_nk_account_guid": "nk-tenant-1",
                "gnucash_nk_account_name": "Mieter 1:Nebenkosten",
            },
        )
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="split-before-lease-start",
                    transaction_guid="transaction-before-lease-start",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 31),
                    amount=Decimal("-75.00"),
                    description="Vorauszahlung vor Mietbeginn",
                )
            ]
        )

        imported = import_gnucash_payments_for_period(
            self.connection,
            self.property_id,
            "2025-01-01",
            "2025-12-31",
            reader=reader,
        )

        self.assertEqual(imported["imported"], 0)
        self.assertEqual(imported["existing"], 0)
        self.assertEqual(
            reader.requests,
            [({"nk-tenant-1"}, date(2025, 1, 1), date(2025, 12, 31))],
        )
        stored = self.connection.execute(
            "SELECT lease_id FROM gnucash_payments WHERE split_guid = ?",
            ("split-before-lease-start",),
        ).fetchone()
        self.assertIsNone(stored)

        self.connection.execute(
            """
            INSERT INTO gnucash_payments (
                split_guid, transaction_guid, tenant_id, lease_id, account_guid, account_name,
                booking_date, amount, description, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "previously-imported-before-lease-start",
                "transaction-before-lease-start",
                self.tenant_id,
                1,
                "nk-tenant-1",
                "Mieter 1:Nebenkosten",
                "2025-01-31",
                "-75.00",
                "Vorauszahlung vor Mietbeginn",
                "2025-02-01T00:00:00+00:00",
            ),
        )
        self.connection.commit()

        settlement = settlement_for_period(
            self.connection, self.property_id, "2025-01-01", "2025-12-31"
        )
        tenant_result = next(result for result in settlement["results"] if result["lease_id"] == 1)
        self.assertEqual(tenant_result["advances_paid"], "0.00")

    def test_settlement_run_loads_all_account_payments_and_excludes_outside_ones(self) -> None:
        settlement_run, _ = create_or_open_settlement_run(
            self.connection, {"property_id": self.property_id, "year": 2025}
        )
        reader = FakeGnuCashReader(
            [
                GnuCashPayment(
                    split_guid="run-inside",
                    transaction_guid="run-inside-transaction",
                    account_guid="nk-tenant-1",
                    booking_date=date(2025, 1, 5),
                    amount=Decimal("-75.00"),
                    description="Vorauszahlung Januar",
                ),
                GnuCashPayment(
                    split_guid="run-before",
                    transaction_guid="run-before-transaction",
                    account_guid="nk-tenant-1",
                    booking_date=date(2024, 12, 31),
                    amount=Decimal("-75.00"),
                    description="Vorauszahlung davor",
                ),
            ]
        )

        refreshed = refresh_settlement_run_payments(
            self.connection, settlement_run["id"], reader=reader
        )
        overview = get_settlement_run_overview(self.connection, settlement_run["id"])

        self.assertEqual(refreshed["imported"], 2)
        self.assertEqual(len(overview["open_payments"]), 1)
        self.assertEqual(overview["open_payments"][0]["split_guid"], "run-inside")
        self.assertEqual(len(overview["outside_payments"]), 1)
        self.assertEqual(overview["outside_payments"][0]["split_guid"], "run-before")

        considered = set_settlement_payment_considered(
            self.connection, settlement_run["id"], "run-inside", True
        )
        self.assertEqual(len(considered["considered_payments"]), 1)
        self.assertEqual(considered["settlement"]["totals"]["advances"], "75.00")

    def test_positive_reversal_reduces_paid_advances_and_increases_balance(self) -> None:
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
        self.assertEqual(tenant_result["advances_paid"], "-20.00")
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

    def test_rejects_assigning_the_same_nk_account_to_multiple_leases(self) -> None:
        lease = self.connection.execute("SELECT * FROM leases WHERE id = 2").fetchone()
        assert lease is not None
        with self.assertRaisesRegex(ValueError, "only be assigned to one lease"):
            update_lease(
                self.connection,
                2,
                {
                    "unit_id": lease["unit_id"],
                    "room_id": lease["room_id"],
                    "tenant_id": lease["tenant_id"],
                    "rent_cold": lease["rent_cold"],
                    "additional_charges_advance": lease["additional_charges_advance"],
                    "occupant_count": lease["occupant_count"],
                    "start_date": lease["start_date"],
                    "end_date": lease["end_date"],
                    "status": lease["status"],
                    "gnucash_nk_account_guid": "nk-tenant-1",
                    "gnucash_nk_account_name": "Mieter 1:Nebenkosten",
                },
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
