from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.easyprent_accounting.calculations import (
    SettlementExpense,
    SettlementLease,
    calculate_depreciation_schedule,
    expense_amount_for_period,
    calculate_settlement,
)


class SettlementTests(unittest.TestCase):
    def test_settlement_uses_allocation_methods_and_advances(self) -> None:
        leases = [
            SettlementLease(
                lease_id=1,
                tenant_name="Anna",
                unit_label="A-01",
                unit_area_sqm=Decimal("80"),
                occupant_count=2,
                additional_charges_advance=Decimal("200"),
                lease_start=date(2025, 1, 1),
                lease_end=None,
            ),
            SettlementLease(
                lease_id=2,
                tenant_name="Ben",
                unit_label="A-02",
                unit_area_sqm=Decimal("40"),
                occupant_count=1,
                additional_charges_advance=Decimal("150"),
                lease_start=date(2025, 1, 1),
                lease_end=None,
            ),
        ]
        expenses = [
            SettlementExpense(
                label="Heizung",
                amount=Decimal("1200"),
                allocation_method="area",
                charge_type="one_time",
            ),
            SettlementExpense(
                label="Wasser",
                amount=Decimal("300"),
                allocation_method="occupants",
                charge_type="one_time",
            ),
            SettlementExpense(
                label="Reinigung",
                amount=Decimal("240"),
                allocation_method="unit_count",
                charge_type="one_time",
            ),
        ]

        result = calculate_settlement(leases, expenses, date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(result["totals"]["costs"], "1740.00")
        self.assertIsNone(result["totals"]["advances"])
        self.assertEqual(result["results"][0]["allocated_costs"], "1120.00")
        self.assertIsNone(result["results"][0]["balance"])
        self.assertEqual(result["results"][1]["allocated_costs"], "620.00")
        self.assertIsNone(result["results"][1]["balance"])
        heating = result["results"][0]["line_items"][0]
        self.assertEqual(heating["period_amount"], "1200.00")
        self.assertEqual(heating["basis_value"], "80")
        self.assertEqual(heating["basis_total"], "120")

    def test_settlement_respects_partial_year_contract(self) -> None:
        lease = SettlementLease(
            lease_id=3,
            tenant_name="Cara",
            unit_label="B-01",
            unit_area_sqm=Decimal("60"),
            occupant_count=1,
            additional_charges_advance=Decimal("100"),
            lease_start=date(2025, 7, 15),
            lease_end=None,
        )
        result = calculate_settlement(
            [lease],
            [
                SettlementExpense(
                    label="Hausstrom",
                    amount=Decimal("600"),
                    allocation_method="unit_count",
                    charge_type="one_time",
                )
            ],
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        self.assertIsNone(result["results"][0]["advances_paid"])
        self.assertEqual(result["results"][0]["allocated_costs"], "279.45")
        self.assertEqual(result["results"][0]["billing_period_start"], "2025-07-15")
        self.assertEqual(result["results"][0]["billing_period_end"], "2025-12-31")

    def test_settlement_multiplies_monthly_expense_by_overlap_months(self) -> None:
        lease = SettlementLease(
            lease_id=1,
            tenant_name="Anna",
            unit_label="A-01",
            unit_area_sqm=Decimal("80"),
            occupant_count=2,
            additional_charges_advance=Decimal("0"),
            lease_start=date(2025, 1, 1),
            lease_end=None,
        )
        result = calculate_settlement(
            [lease],
            [
                SettlementExpense(
                    label="Hausmeister",
                    amount=Decimal("100"),
                    allocation_method="unit_count",
                    charge_type="monthly",
                    expense_start=date(2025, 3, 1),
                    expense_end=date(2025, 5, 31),
                )
            ],
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        self.assertEqual(result["totals"]["costs"], "300.00")
        self.assertEqual(result["results"][0]["line_items"][0]["share"], "300.00")

    def test_settlement_keeps_consumption_metadata(self) -> None:
        lease = SettlementLease(
            lease_id=1,
            tenant_name="Anna",
            unit_label="A-01",
            unit_area_sqm=Decimal("80"),
            occupant_count=2,
            additional_charges_advance=Decimal("0"),
            lease_start=date(2025, 1, 1),
            lease_end=None,
        )
        result = calculate_settlement(
            [lease],
            [
                SettlementExpense(
                    label="Wasserverbrauch",
                    amount=Decimal("2"),
                    allocation_method="occupants",
                    charge_type="consumption",
                    consumption_unit="m3",
                    consumption_value=Decimal("32.5"),
                )
            ],
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        self.assertEqual(result["totals"]["costs"], "65.00")
        self.assertEqual(result["results"][0]["line_items"][0]["charge_type"], "consumption")
        self.assertEqual(result["results"][0]["line_items"][0]["consumption_unit"], "m3")
        self.assertEqual(result["results"][0]["line_items"][0]["consumption_value"], "32.5")

    def test_settlement_counts_yearly_expense_once_per_year(self) -> None:
        lease = SettlementLease(
            lease_id=1,
            tenant_name="Anna",
            unit_label="A-01",
            unit_area_sqm=Decimal("80"),
            occupant_count=2,
            additional_charges_advance=Decimal("0"),
            lease_start=date(2025, 1, 1),
            lease_end=None,
        )
        result = calculate_settlement(
            [lease],
            [
                SettlementExpense(
                    label="Versicherung",
                    amount=Decimal("500"),
                    allocation_method="unit_count",
                    charge_type="yearly",
                    recurrence="recurring",
                    interval_name="yearly",
                    expense_start=date(2025, 3, 1),
                    expense_end=date(2027, 12, 31),
                )
            ],
            date(2026, 1, 1),
            date(2026, 12, 31),
        )
        self.assertEqual(result["totals"]["costs"], "500.00")

    def test_settlement_counts_quarterly_expense_four_times_per_year(self) -> None:
        lease = SettlementLease(
            lease_id=1,
            tenant_name="Anna",
            unit_label="A-01",
            unit_area_sqm=Decimal("80"),
            occupant_count=2,
            additional_charges_advance=Decimal("0"),
            lease_start=date(2025, 1, 1),
            lease_end=None,
        )
        result = calculate_settlement(
            [lease],
            [
                SettlementExpense(
                    label="Aufzugswartung",
                    amount=Decimal("300"),
                    allocation_method="unit_count",
                    charge_type="quarterly",
                    recurrence="recurring",
                    interval_name="quarterly",
                    expense_start=date(2025, 1, 1),
                    expense_end=date(2025, 12, 31),
                )
            ],
            date(2025, 1, 1),
            date(2025, 12, 31),
        )
        self.assertEqual(result["totals"]["costs"], "1200.00")

    def test_single_date_expense_only_counts_on_matching_day(self) -> None:
        expense = SettlementExpense(
            label="Einmalige Reparatur",
            amount=Decimal("250"),
            allocation_method="unit_count",
            charge_type="one_time",
            expense_start=date(2025, 6, 15),
            expense_end=date(2025, 6, 15),
        )

        inside = expense_amount_for_period(expense, date(2025, 6, 1), date(2025, 6, 30))
        outside = expense_amount_for_period(expense, date(2025, 7, 1), date(2025, 7, 31))

        self.assertEqual(inside, Decimal("250.00"))
        self.assertEqual(outside, Decimal("0"))

    def test_one_time_expense_with_a_period_is_prorated_to_billing_period(self) -> None:
        expense = SettlementExpense(
            label="Warmwasser",
            amount=Decimal("865.92"),
            allocation_method="occupants",
            charge_type="one_time",
            expense_start=date(2024, 12, 1),
            expense_end=date(2025, 11, 30),
        )

        amount = expense_amount_for_period(
            expense, date(2025, 1, 1), date(2025, 12, 31)
        )

        self.assertEqual(amount, Decimal("792.38"))


class DepreciationTests(unittest.TestCase):
    def test_depreciation_schedule_prorates_by_month(self) -> None:
        result = calculate_depreciation_schedule(
            [
                {
                    "asset_name": "Gebäude",
                    "acquisition_cost": "500000",
                    "building_share_percent": "80",
                    "useful_life_years": 40,
                    "placed_in_service": "2025-07-01",
                    "method": "linear",
                }
            ],
            2025,
        )
        self.assertEqual(result["total"], "5000.00")
        self.assertEqual(result["rows"][0]["months_in_year"], 6)


if __name__ == "__main__":
    unittest.main()
