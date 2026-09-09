from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from src.easyprent_accounting.calculations import (
    SettlementExpense,
    SettlementLease,
    calculate_settlement,
    expense_amount_for_period,
)
from src.easyprent_accounting.expense_math import meter_consumption_for_period
from src.easyprent_accounting.services import create_expense, settlement_for_period
from tests.support import in_memory_database


class ExpenseAmountGoldenCases(unittest.TestCase):
    def test_cost_type_amounts(self) -> None:
        cases = (
            {
                "name": "total cost prorated to its overlap",
                "charge_type": "one_time",
                "recurrence": "one_time",
                "amount": "365.00",
                "expense_start": date(2024, 12, 1),
                "expense_end": date(2025, 11, 30),
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 12, 31),
                "expected": Decimal("334.00"),
            },
            {
                "name": "monthly cost counted for each active month",
                "charge_type": "monthly",
                "recurrence": "recurring",
                "amount": "10.00",
                "expense_start": date(2025, 1, 1),
                "expense_end": date(2025, 3, 31),
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 12, 31),
                "expected": Decimal("30.00"),
            },
            {
                "name": "quarterly cost counted for each occurrence",
                "charge_type": "quarterly",
                "recurrence": "recurring",
                "amount": "300.00",
                "expense_start": date(2025, 1, 1),
                "expense_end": date(2025, 12, 31),
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 12, 31),
                "expected": Decimal("1200.00"),
            },
            {
                "name": "yearly cost counted once per active year",
                "charge_type": "yearly",
                "recurrence": "recurring",
                "amount": "366.00",
                "expense_start": date(2024, 3, 1),
                "expense_end": date(2026, 3, 1),
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 12, 31),
                "expected": Decimal("366.00"),
            },
            {
                "name": "consumption cost keeps ten-place price precision",
                "charge_type": "consumption",
                "recurrence": "one_time",
                "amount": "0.3333333333",
                "consumption_value": "3",
                "expense_start": date(2025, 1, 1),
                "expense_end": date(2025, 12, 31),
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 12, 31),
                "expected": Decimal("1.00"),
            },
        )

        for case in cases:
            with self.subTest(case["name"]):
                expense = SettlementExpense(
                    label=case["name"],
                    amount=Decimal(case["amount"]),
                    allocation_method="unit_count",
                    charge_type=case["charge_type"],
                    recurrence=case["recurrence"],
                    interval_name=(
                        case["charge_type"]
                        if case["recurrence"] == "recurring"
                        else None
                    ),
                    expense_start=case["expense_start"],
                    expense_end=case["expense_end"],
                    consumption_value=(
                        Decimal(case["consumption_value"])
                        if "consumption_value" in case
                        else None
                    ),
                )

                actual = expense_amount_for_period(
                    expense,
                    case["period_start"],
                    case["period_end"],
                )

                self.assertEqual(actual, case["expected"])

    def test_total_cost_public_input_uses_total_period_pricing(self) -> None:
        connection = in_memory_database()
        try:
            connection.execute("DELETE FROM expense_items")
            created = create_expense(
                connection,
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Annual total",
                    "beneficiary_name": "Test",
                    "amount": "365.00",
                    "allocation_method": "unit_count",
                    "charge_type": "total",
                    "period_start": "2024-12-01",
                    "period_end": "2025-11-30",
                },
            )

            settlement = settlement_for_period(
                connection,
                1,
                "2025-01-01",
                "2025-12-31",
            )

            self.assertEqual(created["charge_type"], "one_time")
            self.assertEqual(settlement["totals"]["costs"], "334.00")
        finally:
            connection.close()

    def test_open_ended_costs_use_actual_calendar_days(self) -> None:
        cases = (
            {
                "name": "monthly cost starting mid-month",
                "interval": "monthly",
                "amount": "31.00",
                "expense_start": date(2025, 1, 16),
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 1, 31),
                "expected": "16.00",
            },
            {
                "name": "quarterly cost for February",
                "interval": "quarterly",
                "amount": "90.00",
                "expense_start": date(2025, 1, 1),
                "period_start": date(2025, 2, 1),
                "period_end": date(2025, 2, 28),
                "expected": "28.00",
            },
            {
                "name": "yearly cost for leap-year February",
                "interval": "yearly",
                "amount": "366.00",
                "expense_start": date(2024, 1, 1),
                "period_start": date(2024, 2, 1),
                "period_end": date(2024, 2, 29),
                "expected": "29.00",
            },
        )

        for case in cases:
            with self.subTest(case["name"]):
                connection = in_memory_database()
                try:
                    connection.execute("DELETE FROM expense_items")
                    connection.execute(
                        "UPDATE leases SET start_date = '2024-01-01', end_date = NULL"
                    )
                    created = create_expense(
                        connection,
                        {
                            "object_type": "property",
                            "object_id": 1,
                            "expense_category": case["name"],
                            "beneficiary_name": "Test",
                            "amount": case["amount"],
                            "allocation_method": "unit_count",
                            "recurrence": "recurring",
                            "interval": case["interval"],
                            "period_start": case["expense_start"].isoformat(),
                        },
                    )
                    settlement = settlement_for_period(
                        connection,
                        1,
                        case["period_start"].isoformat(),
                        case["period_end"].isoformat(),
                    )

                    self.assertTrue(created["is_open_ended"])
                    self.assertIsNone(created["period_end"])
                    self.assertEqual(created["charge_type"], case["interval"])
                    self.assertEqual(
                        settlement["totals"]["costs"],
                        case["expected"],
                    )
                finally:
                    connection.close()


class MeterConsumptionGoldenCases(unittest.TestCase):
    def test_period_consumption_uses_exact_values_interpolation_and_edge_clamping(self) -> None:
        standard_readings = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 11), Decimal("120")),
            (date(2025, 1, 21), Decimal("150")),
        ]
        cases = (
            {
                "name": "exact boundary readings",
                "readings": standard_readings,
                "period_start": "2025-01-01",
                "period_end": "2025-01-10",
                "expected": Decimal("20"),
            },
            {
                "name": "interpolated boundary readings",
                "readings": standard_readings,
                "period_start": "2025-01-03",
                "period_end": "2025-01-08",
                "expected": Decimal("12"),
            },
            {
                "name": "single leap day between readings",
                "readings": [
                    (date(2024, 2, 28), Decimal("0")),
                    (date(2024, 3, 2), Decimal("30")),
                ],
                "period_start": "2024-02-29",
                "period_end": "2024-02-29",
                "expected": Decimal("10"),
            },
        )

        for case in cases:
            with self.subTest(case["name"]):
                actual = meter_consumption_for_period(
                    case["readings"],
                    case["period_start"],
                    case["period_end"],
                )

                self.assertEqual(actual, case["expected"])


class SettlementGoldenCases(unittest.TestCase):
    def _settlement_with_two_leases(
        self,
        *,
        allocation_method: str,
        first_basis: str,
        second_basis: str,
        amount: str = "100.00",
    ) -> dict:
        connection = in_memory_database()
        try:
            connection.execute("DELETE FROM expense_items")
            connection.execute(
                "UPDATE leases SET start_date = '2025-01-01', end_date = NULL"
            )
            if allocation_method == "area":
                connection.execute(
                    "UPDATE units SET mea_percent = ? WHERE id = 1",
                    (first_basis,),
                )
                connection.execute(
                    "UPDATE units SET mea_percent = ? WHERE id = 2",
                    (second_basis,),
                )
            elif allocation_method == "occupants":
                connection.execute(
                    "UPDATE leases SET occupant_count = ? WHERE id = 1",
                    (first_basis,),
                )
                connection.execute(
                    "UPDATE leases SET occupant_count = ? WHERE id = 2",
                    (second_basis,),
                )
            create_expense(
                connection,
                {
                    "object_type": "property",
                    "object_id": 1,
                    "expense_category": "Golden Case",
                    "beneficiary_name": "Test",
                    "amount": amount,
                    "allocation_method": allocation_method,
                    "recurrence": "one_time",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )
            return settlement_for_period(
                connection,
                1,
                "2025-01-01",
                "2025-12-31",
            )
        finally:
            connection.close()

    def test_allocation_keys(self) -> None:
        cases = (
            {
                "name": "MEA",
                "allocation_method": "area",
                "first_basis": "20",
                "second_basis": "80",
                "expected_shares": ["20.00", "80.00"],
            },
            {
                "name": "occupants",
                "allocation_method": "occupants",
                "first_basis": "1",
                "second_basis": "3",
                "expected_shares": ["25.00", "75.00"],
            },
            {
                "name": "unit count",
                "allocation_method": "unit_count",
                "first_basis": "1",
                "second_basis": "1",
                "expected_shares": ["50.00", "50.00"],
            },
        )

        for case in cases:
            with self.subTest(case["name"]):
                settlement = self._settlement_with_two_leases(
                    allocation_method=case["allocation_method"],
                    first_basis=case["first_basis"],
                    second_basis=case["second_basis"],
                )

                self.assertEqual(
                    [result["allocated_costs"] for result in settlement["results"]],
                    case["expected_shares"],
                )
                self.assertEqual(settlement["totals"]["costs"], "100.00")

    def test_contract_changes_split_costs_by_actual_lease_days(self) -> None:
        cases = (
            {
                "name": "change at mid-year",
                "period_start": date(2025, 1, 1),
                "new_lease_start": date(2025, 7, 1),
                "period_end": date(2025, 12, 31),
                "amount": "365.00",
                "expected_shares": ["181.00", "184.00"],
            },
            {
                "name": "change at start of second quarter",
                "period_start": date(2025, 1, 1),
                "new_lease_start": date(2025, 4, 1),
                "period_end": date(2025, 12, 31),
                "amount": "365.00",
                "expected_shares": ["90.00", "275.00"],
            },
            {
                "name": "change during leap year",
                "period_start": date(2024, 1, 1),
                "new_lease_start": date(2024, 7, 1),
                "period_end": date(2024, 12, 31),
                "amount": "366.00",
                "expected_shares": ["182.00", "184.00"],
            },
        )

        for case in cases:
            with self.subTest(case["name"]):
                old_lease_end = case["new_lease_start"] - timedelta(days=1)
                leases = [
                    SettlementLease(
                        lease_id=1,
                        tenant_name="Previous tenant",
                        unit_label="A-01",
                        unit_area_sqm=Decimal("1"),
                        occupant_count=1,
                        additional_charges_advance=Decimal("0"),
                        lease_start=case["period_start"],
                        lease_end=old_lease_end,
                    ),
                    SettlementLease(
                        lease_id=2,
                        tenant_name="Next tenant",
                        unit_label="A-01",
                        unit_area_sqm=Decimal("1"),
                        occupant_count=1,
                        additional_charges_advance=Decimal("0"),
                        lease_start=case["new_lease_start"],
                        lease_end=None,
                    ),
                ]
                expense = SettlementExpense(
                    label="Annual building cost",
                    amount=Decimal(case["amount"]),
                    allocation_method="unit_count",
                    charge_type="one_time",
                    expense_start=case["period_start"],
                    expense_end=case["period_end"],
                )

                settlement = calculate_settlement(
                    leases,
                    [expense],
                    case["period_start"],
                    case["period_end"],
                )

                self.assertEqual(
                    [result["allocated_costs"] for result in settlement["results"]],
                    case["expected_shares"],
                )
                self.assertEqual(
                    [
                        (
                            result["billing_period_start"],
                            result["billing_period_end"],
                        )
                        for result in settlement["results"]
                    ],
                    [
                        (case["period_start"].isoformat(), old_lease_end.isoformat()),
                        (
                            case["new_lease_start"].isoformat(),
                            case["period_end"].isoformat(),
                        ),
                    ],
                )

    def test_cent_rounding_reconciles_to_the_expense_total(self) -> None:
        cases = (
            {
                "name": "single cent",
                "amount": "0.01",
                "expected_shares": ["0.00", "0.01"],
            },
            {
                "name": "odd cent after an even euro amount",
                "amount": "100.01",
                "expected_shares": ["50.00", "50.01"],
            },
            {
                "name": "three residual cents",
                "amount": "100.03",
                "expected_total": "100.03",
                "expected_shares": ["50.01", "50.02"],
            },
            {
                "name": "ten-place amount rounds below half a cent",
                "amount": "100.0049999999",
                "expected_total": "100.00",
                "expected_shares": ["50.00", "50.00"],
            },
            {
                "name": "half cent rounds away from zero",
                "amount": "100.0050000000",
                "expected_total": "100.01",
                "expected_shares": ["50.00", "50.01"],
            },
        )

        for case in cases:
            with self.subTest(case["name"]):
                settlement = self._settlement_with_two_leases(
                    allocation_method="unit_count",
                    first_basis="1",
                    second_basis="1",
                    amount=case["amount"],
                )
                actual_shares = [
                    result["allocated_costs"] for result in settlement["results"]
                ]

                self.assertEqual(
                    sorted(actual_shares),
                    sorted(case["expected_shares"]),
                )
                expected_total = case.get("expected_total", case["amount"])
                self.assertEqual(settlement["totals"]["costs"], expected_total)
                self.assertEqual(
                    sum(Decimal(share) for share in actual_shares),
                    Decimal(expected_total),
                )


if __name__ == "__main__":
    unittest.main()
