from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from easyprent_accounting.calculations import calculate_depreciation_schedule, parse_date, quantize_money
from easyprent_accounting.domain import DomainError
from easyprent_accounting.settlements import (
    ExpenseSnapshot, LeaseSnapshot, SettlementSnapshot, calculate_settlement_snapshot,
)


class DomainValueBoundaryTests(unittest.TestCase):
    def test_quantize_money_rejects_non_finite_amount(self) -> None:
        with self.assertRaises(DomainError) as caught:
            quantize_money(Decimal("Infinity"))
        self.assertEqual("invalid_money", caught.exception.code)

    def test_parse_date_maps_malformed_input_to_domain_error(self) -> None:
        with self.assertRaises(DomainError) as caught:
            parse_date("2025-02-29")
        self.assertEqual("invalid_date", caught.exception.code)


def _lease(lease_id: int, name: str, mea: str, occupants: int,
           start: date, end: date | None = None) -> LeaseSnapshot:
    return LeaseSnapshot(
        id=lease_id, tenant_name=name, unit_label=f"A-{lease_id:02d}",
        unit_id=lease_id, room_id=None, building_id=1, mea_percent=Decimal(mea),
        area_share_percent=None, occupant_count=occupants,
        additional_charges_advance=Decimal("0"), start_date=start, end_date=end,
    )


def _expense(expense_id: int, label: str, amount: str, method: str,
             start: date, end: date, charge_type: str = "one_time",
             consumption_value: Decimal | None = None,
             consumption_unit: str | None = None) -> ExpenseSnapshot:
    return ExpenseSnapshot(
        id=expense_id, label=label, category=label, amount=Decimal(amount),
        allocation_method=method, charge_type=charge_type,
        recurrence="recurring" if charge_type in {"monthly", "quarterly", "yearly"} else "one_time",
        interval_name=charge_type if charge_type in {"monthly", "quarterly", "yearly"} else None,
        period_start=start, period_end=end, object_type="property", object_id=1,
        consumption_value=consumption_value, consumption_unit=consumption_unit,
    )


def _calculate(start: date, end: date, leases: list[LeaseSnapshot],
               expenses: list[ExpenseSnapshot]) -> dict:
    return calculate_settlement_snapshot(SettlementSnapshot(
        period_start=start, period_end=end, property_id=1, unit_id=None,
        leases=tuple(leases), expenses=tuple(expenses), meter_readings=(), payments=(),
    ))


class SettlementTests(unittest.TestCase):
    def test_reversed_period_is_rejected_without_expenses(self) -> None:
        with self.assertRaises(DomainError) as caught:
            _calculate(date(2025, 12, 31), date(2025, 1, 1), [], [])
        self.assertEqual("invalid_date_range", caught.exception.code)

    def test_allocation_uses_mea_occupants_and_unit_count(self) -> None:
        start, end = date(2025, 1, 1), date(2025, 12, 31)
        result = _calculate(
            start, end,
            [_lease(1, "Anna", "80", 2, start), _lease(2, "Ben", "40", 1, start)],
            [
                _expense(1, "Heizung", "1200", "area", start, end),
                _expense(2, "Wasser", "300", "occupants", start, end),
                _expense(3, "Reinigung", "240", "unit_count", start, end),
            ],
        )
        self.assertEqual(result["totals"], {"costs": "1740.00", "advances": "0.00", "balance": "1740.00"})
        self.assertEqual([row["allocated_costs"] for row in result["results"]], ["1120.00", "620.00"])
        heating = result["results"][0]["line_items"][0]
        self.assertEqual((heating["period_amount"], heating["basis_value"], heating["basis_total"]),
                         ("1200.00", "80", "120"))

    def test_partial_year_contract_receives_only_active_days(self) -> None:
        start, end = date(2025, 1, 1), date(2025, 12, 31)
        result = _calculate(
            start, end,
            [_lease(3, "Cara", "60", 1, date(2025, 7, 15))],
            [_expense(1, "Hausstrom", "600", "unit_count", start, end)],
        )
        lease = result["results"][0]
        self.assertEqual(lease["allocated_costs"], "279.45")
        self.assertEqual((lease["billing_period_start"], lease["billing_period_end"]),
                         ("2025-07-15", "2025-12-31"))

    def test_monthly_recurrence_is_priced_for_active_months(self) -> None:
        start, end = date(2025, 1, 1), date(2025, 12, 31)
        result = _calculate(
            start, end, [_lease(1, "Anna", "80", 2, start)],
            [_expense(1, "Hausmeister", "100", "unit_count",
                      date(2025, 3, 1), date(2025, 5, 31), "monthly")],
        )
        self.assertEqual(result["totals"]["costs"], "300.00")
        self.assertEqual(result["results"][0]["line_items"][0]["share"], "300.00")

    def test_consumption_metadata_follows_priced_quantity(self) -> None:
        start, end = date(2025, 1, 1), date(2025, 12, 31)
        result = _calculate(
            start, end, [_lease(1, "Anna", "80", 2, start)],
            [_expense(1, "Wasserverbrauch", "2", "occupants", start, end,
                      "consumption", Decimal("32.5"), "m3")],
        )
        item = result["results"][0]["line_items"][0]
        self.assertEqual(result["totals"]["costs"], "65.00")
        self.assertEqual((item["charge_type"], item["consumption_unit"], item["consumption_value"]),
                         ("consumption", "m3", "32.5"))

    def test_yearly_and_quarterly_recurrence(self) -> None:
        start, end = date(2025, 1, 1), date(2025, 12, 31)
        result = _calculate(
            start, end, [_lease(1, "Anna", "80", 2, start)],
            [
                _expense(1, "Versicherung", "500", "unit_count", start, end, "yearly"),
                _expense(2, "Aufzug", "300", "unit_count", start, end, "quarterly"),
            ],
        )
        self.assertEqual(result["totals"]["costs"], "1700.00")
        self.assertEqual([item["share"] for item in result["results"][0]["line_items"]],
                         ["500.00", "1200.00"])


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

    def test_depreciation_rejects_percentage_outside_domain_range(self) -> None:
        asset = {
            "asset_name": "Gebäude",
            "acquisition_cost": "500000",
            "building_share_percent": "100.01",
            "useful_life_years": 40,
            "placed_in_service": "2025-07-01",
            "method": "linear",
        }

        with self.assertRaises(DomainError) as caught:
            calculate_depreciation_schedule([asset], 2025)

        self.assertEqual("invalid_percentage", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
