"""Settlement requests and decimal JSON contracts through the ASGI application."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from easyprent_accounting.integrations.gnucash import GnuCashAccount, GnuCashPayment

from tests.support import asgi_test_client, temporary_database


class FakeGnuCashReader:
    def __init__(self) -> None:
        self.payment = GnuCashPayment(
            split_guid="payment-1", transaction_guid="transaction-1",
            account_guid="nk-1", booking_date=date(2025, 1, 5),
            amount=Decimal("-75.05"), description="January advance",
        )

    def list_accounts(self, settings: dict) -> list[GnuCashAccount]:
        return []

    def list_payments(
        self, settings: dict, account_guids: set[str],
        period_start: date, period_end: date,
    ) -> list[GnuCashPayment]:
        if self.payment.account_guid in account_guids and period_start <= self.payment.booking_date <= period_end:
            return [self.payment]
        return []


class SettlementHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def test_period_calculation_returns_exact_decimal_strings(self) -> None:
        response = self.client.get("/api/v1/settlements", params={
            "property_id": 1,
            "period_start": "2025-01-01", "period_end": "2025-12-31",
        })

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/json")
        settlement = response.json()
        self.assertEqual(settlement["totals"], {
            "costs": "341100.00", "advances": "0.00", "balance": "341100.00",
        })
        first = settlement["results"][0]
        self.assertEqual(first["allocated_costs"], "254488.17")
        self.assertEqual(first["line_items"][0]["period_amount"], "4200.00")
        self.assertEqual(first["line_items"][0]["share"], "2309.23")
        self.assertEqual(first["line_items"][0]["allocation_periods"][0]["share"], "2309.23")
        self.assertEqual(first["line_items"][0]["basis_value"], "34.0961")
        self.assertEqual(first["line_items"][1]["consumption_value"], "210")

    def test_run_creation_lookup_and_overview(self) -> None:
        payload = {"property_id": 1, "year": 2025}
        created = self.client.post("/api/v1/settlement-runs", json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        run_id = created.json()["id"]
        self.assertEqual(created.json()["period_start"], "2025-01-01")
        self.assertEqual(created.json()["period_end"], "2025-12-31")

        reopened = self.client.post("/api/v1/settlement-runs", json=payload)
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(reopened.json()["id"], run_id)

        lookup = self.client.get("/api/v1/settlement-runs", params=payload)
        self.assertEqual(lookup.status_code, 200, lookup.text)
        self.assertEqual(lookup.json(), {"id": run_id})

        overview = self.client.get(f"/api/v1/settlement-runs/{run_id}")
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["run"]["id"], run_id)
        self.assertEqual(overview.json()["settlement"]["totals"]["costs"], "341100.00")
        self.assertEqual(overview.json()["missing_account_leases"][0]["tenant_name"], "Anna Schulz")

    def test_refresh_and_payment_assignment_update_settlement(self) -> None:
        connection = self.database.connect()
        try:
            connection.execute(
                "UPDATE leases SET gnucash_nk_account_guid = 'nk-1' WHERE id = 1"
            )
            connection.commit()
        finally:
            connection.close()
        client = asgi_test_client(self.database, gnucash_reader=FakeGnuCashReader())
        settings = client.put("/api/v1/settings/gnucash", json={
            "host": "gnucash.example.test", "port": 5432,
            "database": "book", "username": "reader", "password": "test-only",
            "sslmode": "require",
        })
        self.assertEqual(settings.status_code, 200, settings.text)

        period = {"property_id": 1, "period_start": "2025-01-01", "period_end": "2025-12-31"}
        refreshed_period = client.post("/api/v1/settlements/refresh", json=period)
        self.assertEqual(refreshed_period.status_code, 200, refreshed_period.text)
        self.assertEqual(refreshed_period.json()["import"]["imported"], 1)
        self.assertEqual(refreshed_period.json()["settlement"]["totals"]["advances"], "75.05")

        run = client.post("/api/v1/settlement-runs", json={"property_id": 1, "year": 2025})
        run_id = run.json()["id"]
        refreshed_run = client.post(f"/api/v1/settlement-runs/{run_id}/payments/refresh")
        self.assertEqual(refreshed_run.status_code, 200, refreshed_run.text)
        self.assertEqual(refreshed_run.json()["import"]["existing"], 1)
        self.assertEqual(refreshed_run.json()["overview"]["open_payments"][0]["amount"], "-75.05")
        self.assertEqual(refreshed_run.json()["overview"]["settlement"]["totals"]["advances"], "0.00")

        considered = client.post(f"/api/v1/settlement-runs/{run_id}/payments/payment-1/consider")
        self.assertEqual(considered.status_code, 200, considered.text)
        self.assertEqual(considered.json()["considered_payments"][0]["amount"], "-75.05")
        self.assertEqual(considered.json()["settlement"]["totals"]["advances"], "75.05")

        unassigned = client.post(f"/api/v1/settlement-runs/{run_id}/payments/payment-1/unassign")
        self.assertEqual(unassigned.status_code, 200, unassigned.text)
        self.assertEqual(unassigned.json()["settlement"]["totals"]["advances"], "0.00")

        all_considered = client.post(f"/api/v1/settlement-runs/{run_id}/payments/consider-all")
        self.assertEqual(all_considered.status_code, 200, all_considered.text)
        self.assertEqual(all_considered.json()["settlement"]["totals"]["advances"], "75.05")

    def test_invalid_periods_targets_and_runs_return_an_error_envelope(self) -> None:
        invalid_period = self.client.get("/api/v1/settlements", params={
            "property_id": 1,
            "period_start": "2025-12-31", "period_end": "2025-01-01",
        })
        self.assertEqual(invalid_period.status_code, 422, invalid_period.text)
        self.assertEqual(invalid_period.json()["error"]["code"], "invalid_date_range")

        invalid_target = self.client.post("/api/v1/settlement-runs", json={
            "property_id": 1, "unit_id": 1, "year": 2025,
        })
        self.assertEqual(invalid_target.status_code, 422, invalid_target.text)
        self.assertEqual(invalid_target.json()["error"]["code"], "invalid_request")

        missing_run = self.client.get("/api/v1/settlement-runs/not-a-run")
        self.assertEqual(missing_run.status_code, 422, missing_run.text)
        self.assertEqual(missing_run.json()["error"]["code"], "invalid_value")

        lookup = self.client.get("/api/v1/settlement-runs", params={
            "property_id": 1, "year": 2025,
        })
        self.assertEqual(lookup.json(), {"id": None})

    def test_openapi_declares_settlement_amounts_as_strings(self) -> None:
        schemas = self.client.get("/openapi.json").json()["components"]["schemas"]
        for model_name, field_names in (
            ("SettlementTotalsResponse", ("costs", "advances", "balance")),
            ("SettlementLeaseResponse", ("allocated_costs", "advances_paid", "balance")),
            ("SettlementLineResponse", ("period_amount", "share")),
            ("AllocationPeriodResponse", ("period_amount", "share")),
            ("SettlementPaymentResponse", ("amount",)),
        ):
            for field_name in field_names:
                with self.subTest(model=model_name, field=field_name):
                    field = schemas[model_name]["properties"][field_name]
                    self.assertEqual(field["type"], "string")


if __name__ == "__main__":
    unittest.main()
