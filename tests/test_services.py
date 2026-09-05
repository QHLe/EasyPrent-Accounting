from __future__ import annotations

import sqlite3
import unittest
from decimal import Decimal

from src.easyprent_accounting.db import SCHEMA, seed_demo_data
from src.easyprent_accounting.services import (
    archive_object,
    create_building,
    create_expense,
    create_meter,
    create_meter_reading,
    create_room,
    create_unit,
    delete_meter_reading,
    delete_object,
    list_overview,
    restore_object,
    settlement_for_period,
    update_meter,
    update_expense,
    update_unit,
    _total_amount_for_expense_period,
)


class ExpenseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        seed_demo_data(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_create_expense_stores_monthly_charge_type(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "building",
                "object_id": 1,
                "label": "Winterdienst",
                "amount": "85.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-11-01",
                "period_end": "2026-02-28",
            },
        )
        self.assertEqual(created["charge_type"], "monthly")
        self.assertEqual(created["object_type"], "building")
        self.assertEqual(created["object_id"], 1)

        row = self.connection.execute(
            "SELECT charge_type, object_type, object_id FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(row["charge_type"], "monthly")
        self.assertEqual(row["object_type"], "building")
        self.assertEqual(row["object_id"], 1)

    def test_create_expense_stores_quarterly_charge_type(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "building",
                "object_id": 1,
                "label": "Aufzugswartung",
                "amount": "300.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "quarterly",
                "period_start": "2025-01-01",
                "period_end": "2025-03-31",
            },
        )
        self.assertEqual(created["charge_type"], "quarterly")
        self.assertEqual(created["total_amount"], "300.00")

    def test_create_expense_stores_category_and_beneficiary(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "expense_category": "Hausreinigung",
                "beneficiary_name": "Firma Sauber GmbH",
                "label": "Treppenhausreinigung Maerz",
                "amount": "85.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-03-01",
                "period_end": "2025-03-31",
            },
        )

        row = self.connection.execute(
            "SELECT label, expense_category, beneficiary_name FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(created["label"], "Treppenhausreinigung Maerz")
        self.assertEqual(created["expense_category"], "Hausreinigung")
        self.assertEqual(created["beneficiary_name"], "Firma Sauber GmbH")
        self.assertEqual(row["label"], "Treppenhausreinigung Maerz")
        self.assertEqual(row["expense_category"], "Hausreinigung")
        self.assertEqual(row["beneficiary_name"], "Firma Sauber GmbH")

    def test_create_expense_derives_label_from_expense_category_when_missing(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "expense_category": "Versicherung",
                "beneficiary_name": "Allianz SE",
                "amount": "275.00",
                "allocation_method": "area",
                "recurrence": "one_time",
                "booking_date": "2025-05-01",
            },
        )

        row = self.connection.execute(
            "SELECT label, expense_category FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(created["label"], "Versicherung")
        self.assertEqual(created["expense_category"], "Versicherung")
        self.assertEqual(row["label"], "Versicherung")
        self.assertEqual(row["expense_category"], "Versicherung")

    def test_create_expense_stores_single_date_for_one_time_cost(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Türreparatur",
                "amount": "240.00",
                "allocation_method": "unit_count",
                "recurrence": "one_time",
                "booking_date": "2025-06-15",
            },
        )

        row = self.connection.execute(
            "SELECT object_type, object_id, booking_date, period_start, period_end FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(created["object_type"], "unit")
        self.assertEqual(created["object_id"], 1)
        self.assertEqual(created["booking_date"], "2025-06-15")
        self.assertEqual(row["booking_date"], "2025-06-15")
        self.assertEqual(row["period_start"], "2025-06-15")
        self.assertEqual(row["period_end"], "2025-06-15")

    def test_create_expense_allows_open_ended_recurring_costs(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "label": "Hausmeister",
                "amount": "50.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-01-01",
            },
        )

        self.assertTrue(created["is_open_ended"])
        self.assertIsNone(created["period_end"])

    def test_create_expense_requires_consumption_unit_for_consumption_costs(self) -> None:
        with self.assertRaises(ValueError) as error:
            create_expense(
                self.connection,
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasser",
                    "amount": "320.00",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )

        self.assertIn("consumption_unit", str(error.exception))
        self.assertIn("meter_id", str(error.exception))

    def test_create_expense_with_manual_consumption_calculates_total_amount(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Wasser",
                "beneficiary_name": "Wasserbetriebe",
                "label": "Wasserverbrauch A-01",
                "amount": "0.30",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "consumption_unit": "m3",
                "consumption_value": "120",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        row = self.connection.execute(
            "SELECT consumption_value, conversion_factor FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(Decimal(created["effective_consumption_value"]), Decimal("120"))
        self.assertEqual(created["total_amount"], "36.00")
        self.assertEqual(Decimal(str(row["consumption_value"])), Decimal("120"))
        self.assertEqual(Decimal(str(row["conversion_factor"])), Decimal("1"))

    def test_create_expense_accepts_ten_decimal_amount(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Gas",
                "beneficiary_name": "Stadtwerke",
                "label": "Gaspreis genau",
                "amount": "0.1234567891",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "consumption_unit": "kWh",
                "consumption_value": "100",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        self.assertEqual(created["amount"], "0.1234567891")
        self.assertEqual(created["total_amount"], "12.35")

    def test_create_expense_rejects_more_than_ten_decimal_places(self) -> None:
        with self.assertRaises(ValueError) as error:
            create_expense(
                self.connection,
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "expense_category": "Gas",
                    "beneficiary_name": "Stadtwerke",
                    "label": "Gaspreis zu fein",
                    "amount": "0.12345678901",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "consumption_unit": "kWh",
                    "consumption_value": "100",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )

        self.assertIn("amount", str(error.exception))
        self.assertIn("10", str(error.exception))

    def test_create_non_consumption_expense_accepts_ten_decimal_places(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Hausmeister",
                "beneficiary_name": "Service Team",
                "label": "Hausmeisterkosten",
                "amount": "12.3456789012",
                "allocation_method": "unit_count",
                "recurrence": "one_time",
                "booking_date": "2025-05-01",
            },
        )

        self.assertEqual(created["amount"], "12.3456789012")

    def test_create_expense_calculates_recurring_total_day_accurate(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Hausmeister",
                "beneficiary_name": "Service Team",
                "label": "Hausmeister Januar",
                "amount": "310.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-01-10",
                "period_end": "2025-01-20",
            },
        )

        self.assertEqual(created["charge_type"], "monthly")
        self.assertEqual(created["total_amount"], "110.00")

    def test_total_cost_with_period_is_prorated_for_tenant_period(self) -> None:
        _, amount = _total_amount_for_expense_period(
            self.connection,
            {"charge_type": "one_time", "amount": "365.00", "period_start": "2025-01-01", "period_end": "2025-12-31"},
            "2025-07-01",
            "2025-12-31",
        )
        self.assertEqual(amount, "184.00")

    def test_settlement_reconciles_rounded_shares_with_period_amount(self) -> None:
        self.connection.execute("DELETE FROM expense_items")
        self.connection.execute("UPDATE leases SET start_date = '2025-01-01' WHERE id = 2")
        self.connection.execute(
            """
            INSERT INTO expense_items (
                property_id, object_type, object_id, expense_category,
                beneficiary_name, label, amount, allocation_method,
                charge_type, recurrence, period_start, period_end
            ) VALUES (1, 'property', 1, 'Warmwasser', 'Versorger',
                      'Warmwasser', '100.00', 'occupants', 'one_time',
                      'one_time', '2024-12-01', '2025-11-30')
            """
        )
        self.connection.commit()

        settlement = settlement_for_period(
            self.connection, 1, "2025-01-01", "2025-12-31"
        )
        line_items = [result["line_items"][0] for result in settlement["results"]]

        self.assertEqual(line_items[0]["period_amount"], "91.51")
        self.assertEqual(
            sum((Decimal(item["share"]) for item in line_items), start=Decimal("0")),
            Decimal("91.51"),
        )

    def test_manual_consumption_is_prorated_when_no_meter_curve_exists(self) -> None:
        unit, amount = _total_amount_for_expense_period(
            self.connection,
            {
                "charge_type": "consumption",
                "amount": "2.00",
                "consumption_unit": "kWh",
                "consumption_value": "365",
                "conversion_factor": "1",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
            "2025-07-01",
            "2025-12-31",
        )
        self.assertEqual(unit, "kWh")
        self.assertEqual(amount, "368.00")

    def test_create_expense_calculates_yearly_total_day_accurate_with_leap_year(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Versicherung",
                "beneficiary_name": "Allianz SE",
                "amount": "366.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "yearly",
                "period_start": "2024-02-01",
                "period_end": "2024-02-29",
            },
        )

        self.assertEqual(created["charge_type"], "yearly")
        self.assertEqual(created["total_amount"], "29.00")

    def test_create_expense_yearly_full_anchor_cycle_equals_year_amount(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Heizung",
                "beneficiary_name": "Stadtwerke",
                "amount": "1200.00",
                "allocation_method": "area",
                "recurrence": "recurring",
                "interval": "yearly",
                "period_start": "2023-12-01",
                "period_end": "2024-11-30",
            },
        )

        self.assertEqual(created["charge_type"], "yearly")
        self.assertEqual(created["total_amount"], "1200.00")

    def test_create_expense_yearly_partial_anchor_cycle_uses_daily_share(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Heizung",
                "beneficiary_name": "Stadtwerke",
                "amount": "1200.00",
                "allocation_method": "area",
                "recurrence": "recurring",
                "interval": "yearly",
                "period_start": "2023-12-01",
                "period_end": "2024-06-30",
            },
        )

        self.assertEqual(created["charge_type"], "yearly")
        self.assertEqual(created["total_amount"], "698.36")

    def test_create_meter_and_reading_store_target_and_unit(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler Küche",
                "meter_type": "water",
                "unit": "m3",
            },
        )
        reading = create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-03-31",
                "reading_value": "125.4",
            },
        )

        meter_row = self.connection.execute(
            "SELECT object_type, object_id, unit FROM meters WHERE id = ?",
            (meter["id"],),
        ).fetchone()
        reading_row = self.connection.execute(
            "SELECT meter_id, reading_date, reading_value FROM meter_readings WHERE id = ?",
            (reading["id"],),
        ).fetchone()

        self.assertEqual(meter["object_type"], "unit")
        self.assertEqual(meter["object_id"], 1)
        self.assertEqual(meter["unit"], "m3")
        self.assertEqual(meter_row["object_type"], "unit")
        self.assertEqual(meter_row["object_id"], 1)
        self.assertEqual(reading_row["meter_id"], meter["id"])
        self.assertEqual(reading_row["reading_date"], "2025-03-31")
        self.assertEqual(str(reading_row["reading_value"]), "125.4")

    def test_update_meter_allows_correcting_master_data(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler Küche",
                "meter_type": "water",
                "unit": "m3",
                "serial_number": "ALT-1",
            },
        )

        updated = update_meter(
            self.connection,
            meter["id"],
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler Bad",
                "meter_type": "Kaltwasser",
                "unit": "m3",
                "serial_number": "NEU-2",
            },
        )

        self.assertEqual(updated["label"], "Wasserzähler Bad")
        self.assertEqual(updated["meter_type"], "Kaltwasser")
        self.assertEqual(updated["serial_number"], "NEU-2")

    def test_update_meter_rejects_unit_change_with_existing_readings(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler Küche",
                "unit": "m3",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-03-31",
                "reading_value": "125.4",
            },
        )

        with self.assertRaisesRegex(ValueError, "unit cannot be changed"):
            update_meter(
                self.connection,
                meter["id"],
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserzähler Küche",
                    "unit": "l",
                },
            )

    def test_create_meter_reading_rejects_non_increasing_later_value(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Stromzähler A-01",
                "meter_type": "power",
                "unit": "kWh",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-03-01",
                "reading_value": "100",
            },
        )

        with self.assertRaises(ValueError) as error:
            create_meter_reading(
                self.connection,
                {
                    "meter_id": meter["id"],
                    "reading_date": "2025-04-01",
                    "reading_value": "95",
                },
            )

        self.assertIn("previous", str(error.exception))

    def test_create_meter_reading_accepts_equal_values(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Stromzähler A-02",
                "meter_type": "power",
                "unit": "kWh",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-03-01",
                "reading_value": "100",
            },
        )

        equal_later = create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-05-01",
                "reading_value": "100",
            },
        )
        equal_between = create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-04-01",
                "reading_value": "100",
            },
        )

        self.assertEqual(equal_later["reading_value"], "100")
        self.assertEqual(equal_between["reading_value"], "100")

    def test_create_meter_reading_rejects_value_above_later_reading(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler A-01",
                "meter_type": "water",
                "unit": "m3",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-03-01",
                "reading_value": "100",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-05-01",
                "reading_value": "150",
            },
        )

        with self.assertRaises(ValueError) as error:
            create_meter_reading(
                self.connection,
                {
                    "meter_id": meter["id"],
                    "reading_date": "2025-04-01",
                    "reading_value": "160",
                },
            )

        self.assertIn("later", str(error.exception))

    def test_create_meter_reading_rejects_duplicate_date(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Heizzähler A-01",
                "meter_type": "heating",
                "unit": "kWh",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-03-01",
                "reading_value": "100",
            },
        )

        with self.assertRaises(ValueError) as error:
            create_meter_reading(
                self.connection,
                {
                    "meter_id": meter["id"],
                    "reading_date": "2025-03-01",
                    "reading_value": "110",
                },
            )

        self.assertIn("reading_date", str(error.exception))

    def test_delete_meter_reading_removes_entry_and_updates_overview(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Heizzähler A-01",
                "meter_type": "heating",
                "unit": "kWh",
            },
        )
        first = create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-01-15",
                "reading_value": "10",
            },
        )
        second = create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-02-15",
                "reading_value": "18",
            },
        )

        deleted = delete_meter_reading(self.connection, second["id"])
        overview = list_overview(self.connection)
        remaining_row = self.connection.execute(
            "SELECT id FROM meter_readings WHERE id = ?",
            (second["id"],),
        ).fetchone()

        self.assertEqual(deleted["id"], second["id"])
        self.assertEqual(deleted["deleted"], True)
        self.assertIsNone(remaining_row)
        self.assertEqual(overview["meters"][0]["latest_reading_date"], first["reading_date"])
        self.assertEqual(str(overview["meters"][0]["latest_reading_value"]), first["reading_value"])
        self.assertEqual(overview["meters"][0]["reading_count"], 1)
        self.assertEqual(len(overview["meter_readings"]), 1)

    def test_delete_meter_reading_rejects_unknown_id(self) -> None:
        with self.assertRaises(ValueError) as error:
            delete_meter_reading(self.connection, 9999)

        self.assertIn("not found", str(error.exception))

    def test_create_expense_accepts_meter_for_consumption_costs(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler Bad",
                "meter_type": "water",
                "unit": "m3",
            },
        )

        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserkosten Bad",
                "amount": "320.00",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "meter_id": meter["id"],
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        row = self.connection.execute(
            "SELECT meter_id, consumption_unit, conversion_factor, consumption_value FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(created["meter_id"], meter["id"])
        self.assertEqual(created["consumption_unit"], "m3")
        self.assertEqual(created["meter_unit"], "m3")
        self.assertEqual(row["meter_id"], meter["id"])
        self.assertEqual(row["consumption_unit"], "m3")
        self.assertEqual(Decimal(str(row["conversion_factor"])), Decimal("1"))
        self.assertIsNone(row["consumption_value"])

    def test_create_expense_requires_conversion_factor_for_different_meter_unit(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Gaszähler Bad",
                "meter_type": "gas",
                "unit": "m3",
            },
        )

        with self.assertRaises(ValueError) as error:
            create_expense(
                self.connection,
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Gasverbrauch Bad",
                    "amount": "0.12",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "meter_id": meter["id"],
                    "consumption_unit": "kWh",
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )

        self.assertIn("conversion_factor", str(error.exception))

    def test_create_expense_rejects_meter_from_different_target_object(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 2,
                "label": "Wasserzähler A-02",
                "meter_type": "water",
                "unit": "m3",
            },
        )

        with self.assertRaises(ValueError) as error:
            create_expense(
                self.connection,
                {
                    "object_type": "unit",
                    "object_id": 1,
                    "label": "Wasserkosten A-01",
                    "amount": "320.00",
                    "allocation_method": "occupants",
                    "charge_type": "consumption",
                    "meter_id": meter["id"],
                    "period_start": "2025-01-01",
                    "period_end": "2025-12-31",
                },
            )

        self.assertIn("same target object", str(error.exception))

    def test_create_expense_with_meter_and_conversion_calculates_total_amount(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Gaszähler A-01",
                "meter_type": "gas",
                "unit": "m3",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-01-01",
                "reading_value": "100",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2026-01-01",
                "reading_value": "130",
            },
        )

        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Gaskosten A-01",
                "amount": "0.12",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "meter_id": meter["id"],
                "consumption_unit": "kWh",
                "conversion_factor": "10.5",
                "consumption_value": "999",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        row = self.connection.execute(
            """
            SELECT meter_id, consumption_unit, consumption_value, conversion_factor
            FROM expense_items
            WHERE id = ?
            """,
            (created["id"],),
        ).fetchone()
        self.assertEqual(created["meter_id"], meter["id"])
        self.assertEqual(created["meter_unit"], "m3")
        self.assertEqual(created["consumption_unit"], "kWh")
        self.assertEqual(Decimal(created["effective_consumption_value"]), Decimal("315"))
        self.assertEqual(created["total_amount"], "37.80")
        self.assertEqual(Decimal(str(row["conversion_factor"])), Decimal("10.5"))
        self.assertIsNone(row["consumption_value"])

    def test_create_expense_uses_linear_interpolation_for_meter_consumption(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler A-01",
                "meter_type": "water",
                "unit": "m3",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-01-01",
                "reading_value": "100",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-01-31",
                "reading_value": "130",
            },
        )

        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserverbrauch Mitte Januar",
                "amount": "1.00",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "meter_id": meter["id"],
                "period_start": "2025-01-11",
                "period_end": "2025-01-21",
            },
        )

        self.assertEqual(Decimal(created["effective_consumption_value"]), Decimal("11"))
        self.assertEqual(created["total_amount"], "11.00")

    def test_consumption_expense_without_end_date_uses_latest_meter_reading(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserzähler A-01",
                "meter_type": "water",
                "unit": "m3",
            },
        )
        create_meter_reading(
            self.connection,
            {"meter_id": meter["id"], "reading_date": "2025-01-01", "reading_value": "100"},
        )
        create_meter_reading(
            self.connection,
            {"meter_id": meter["id"], "reading_date": "2025-02-15", "reading_value": "130"},
        )

        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wasserkosten A-01",
                "amount": "1.50",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "meter_id": meter["id"],
                "period_start": "2025-01-01",
                "period_end": "",
            },
        )

        self.assertEqual(created["period_end"], "2025-02-14")
        self.assertEqual(Decimal(created["effective_consumption_value"]), Decimal("30"))
        self.assertEqual(created["total_amount"], "45.00")

    def test_update_expense_changes_existing_cost(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Türreparatur",
                "amount": "240.00",
                "allocation_method": "unit_count",
                "recurrence": "one_time",
                "booking_date": "2025-06-15",
            },
        )

        updated = update_expense(
            self.connection,
            created["id"],
            {
                "object_type": "building",
                "object_id": 1,
                "label": "Gebäudereinigung",
                "amount": "75.00",
                "allocation_method": "area",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-01-01",
                "period_end": "2025-03-31",
            },
        )

        row = self.connection.execute(
            """
            SELECT object_type, object_id, label, amount, allocation_method, charge_type,
                   recurrence, interval_name, booking_date, period_start, period_end
            FROM expense_items
            WHERE id = ?
            """,
            (created["id"],),
        ).fetchone()
        self.assertEqual(updated["label"], "Gebäudereinigung")
        self.assertEqual(updated["charge_type"], "monthly")
        self.assertEqual(row["object_type"], "building")
        self.assertEqual(row["object_id"], 1)
        self.assertEqual(row["label"], "Gebäudereinigung")

    def test_recurring_expense_without_end_date_remains_open_ended(self) -> None:
        baseline = settlement_for_period(self.connection, 1, "2025-01-01", "2025-03-31")
        created = create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Hausmeisterservice",
                "amount": "80.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-01-15",
                "period_end": "",
            },
        )

        row = self.connection.execute(
            "SELECT period_end FROM expense_items WHERE id = ?", (created["id"],)
        ).fetchone()
        self.assertTrue(created["is_open_ended"])
        self.assertIsNone(created["period_end"])
        self.assertEqual(row["period_end"], "9999-12-31")

        settlement = settlement_for_period(self.connection, 1, "2025-01-01", "2025-03-31")
        self.assertEqual(
            Decimal(settlement["totals"]["costs"]) - Decimal(baseline["totals"]["costs"]),
            Decimal("203.87"),
        )

    def test_settlement_uses_meter_based_consumption_total(self) -> None:
        baseline = settlement_for_period(self.connection, 1, "2025-01-01", "2025-12-31")
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Heizzähler A-01",
                "meter_type": "heating",
                "unit": "kWh",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-01-01",
                "reading_value": "100",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2026-01-01",
                "reading_value": "125",
            },
        )
        create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Heizstrom A-01",
                "amount": "2.00",
                "allocation_method": "unit_count",
                "charge_type": "consumption",
                "meter_id": meter["id"],
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        settlement = settlement_for_period(self.connection, 1, "2025-01-01", "2025-12-31")

        self.assertEqual(
            Decimal(settlement["totals"]["costs"]) - Decimal(baseline["totals"]["costs"]),
            Decimal("50.00"),
        )
        created_line = next(
            item
            for result in settlement["results"]
            for item in result["line_items"]
            if item["label"] == "Heizstrom A-01"
        )
        self.assertEqual(created_line["expense_category"], "Heizstrom A-01")

    def test_settlement_limits_tenant_consumption_to_expense_period(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 2,
                "label": "Heizzähler A-02",
                "meter_type": "heating",
                "unit": "kWh",
            },
        )
        for reading_date, reading_value in (
            ("2025-01-01", "0"),
            ("2025-07-01", "100"),
            ("2026-01-01", "200"),
        ):
            create_meter_reading(
                self.connection,
                {
                    "meter_id": meter["id"],
                    "reading_date": reading_date,
                    "reading_value": reading_value,
                },
            )
        create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 2,
                "label": "Heizstrom zweites Halbjahr",
                "amount": "2.00",
                "allocation_method": "unit_count",
                "charge_type": "consumption",
                "meter_id": meter["id"],
                "period_start": "2025-07-01",
                "period_end": "2025-12-31",
            },
        )

        settlement = settlement_for_period(
            self.connection, 1, "2025-01-01", "2025-12-31"
        )
        tenant_result = next(
            result for result in settlement["results"] if result["lease_id"] == 2
        )
        line_item = next(
            item
            for item in tenant_result["line_items"]
            if item["label"] == "Heizstrom zweites Halbjahr"
        )

        self.assertEqual(line_item["period_amount"], "200.00")
        self.assertEqual(line_item["share"], "200.00")
        self.assertEqual(line_item["tenant_consumption_value"], "100")

    def test_settlement_does_not_count_sequential_leases_as_two_units(self) -> None:
        self.connection.execute("DELETE FROM expense_items")
        self.connection.execute(
            "UPDATE leases SET unit_id = 1, start_date = '2025-01-01', end_date = '2025-06-30' WHERE id = 1"
        )
        self.connection.execute(
            "UPDATE leases SET unit_id = 1, start_date = '2025-07-01', end_date = '2025-12-31' WHERE id = 2"
        )
        self.connection.execute(
            """
            INSERT INTO expense_items (
                property_id, object_type, object_id, expense_category,
                beneficiary_name, label, amount, allocation_method,
                charge_type, recurrence, period_start, period_end
            ) VALUES (1, 'unit', 1, 'Jahreskosten', 'Dienstleister',
                      'Jahreskosten Wohnung', '365.00', 'unit_count',
                      'one_time', 'one_time', '2025-01-01', '2025-12-31')
            """
        )
        self.connection.commit()

        settlement = settlement_for_period(
            self.connection, 1, "2025-01-01", "2025-12-31"
        )

        self.assertEqual(settlement["totals"]["costs"], "365.00")
        self.assertEqual(
            [result["allocated_costs"] for result in settlement["results"]],
            ["181.00", "184.00"],
        )
        self.assertEqual(
            settlement["results"][0]["line_items"][0]["allocation_periods"],
            [
                {
                    "period_start": "2025-01-01",
                    "period_end": "2025-06-30",
                    "period_amount": "181.00",
                    "share": "181.00",
                }
            ],
        )
        self.assertEqual(
            settlement["results"][1]["line_items"][0]["allocation_periods"],
            [
                {
                    "period_start": "2025-07-01",
                    "period_end": "2025-12-31",
                    "period_amount": "184.00",
                    "share": "184.00",
                }
            ],
        )

    def test_settlement_uses_room_area_shares_for_area_allocation(self) -> None:
        self.connection.execute("DELETE FROM expense_items")
        first_room = create_room(
            self.connection,
            {"unit_id": 1, "label": "Zimmer Nord", "area_share_percent": "25"},
        )
        second_room = create_room(
            self.connection,
            {"unit_id": 1, "label": "Zimmer Süd", "area_share_percent": "75"},
        )
        self.connection.execute(
            "UPDATE leases SET room_id = ? WHERE id = ?", (first_room["id"], 1)
        )
        self.connection.execute(
            """
            UPDATE leases
            SET unit_id = 1, room_id = ?, start_date = '2025-01-01'
            WHERE id = 2
            """,
            (second_room["id"],),
        )
        self.connection.execute(
            """
            INSERT INTO expense_items (
                property_id, object_type, object_id, expense_category,
                beneficiary_name, label, amount, allocation_method,
                charge_type, recurrence, period_start, period_end
            ) VALUES (1, 'property', 1, 'Flächenkosten', 'Dienstleister',
                      'Flächenkosten', '100.00', 'area', 'one_time',
                      'one_time', '2025-01-01', '2025-12-31')
            """
        )
        self.connection.commit()

        settlement = settlement_for_period(
            self.connection, 1, "2025-01-01", "2025-12-31"
        )

        self.assertEqual(
            [result["allocated_costs"] for result in settlement["results"]],
            ["25.00", "75.00"],
        )
        self.assertEqual(
            [result["line_items"][0]["basis_value"] for result in settlement["results"]],
            ["8.524025", "25.572075"],
        )

    def test_settlement_uses_mea_instead_of_informative_unit_area(self) -> None:
        self.connection.execute("DELETE FROM expense_items")
        self.connection.execute("UPDATE units SET mea_percent = 20 WHERE id = 1")
        self.connection.execute("UPDATE units SET mea_percent = 80 WHERE id = 2")
        self.connection.execute("UPDATE leases SET start_date = '2025-01-01' WHERE id = 2")
        self.connection.execute(
            """
            INSERT INTO expense_items (
                property_id, object_type, object_id, expense_category,
                beneficiary_name, label, amount, allocation_method,
                charge_type, recurrence, period_start, period_end
            ) VALUES (1, 'property', 1, 'Gemeinschaftskosten', 'Verwaltung',
                      'Gemeinschaftskosten', '100.00', 'area', 'one_time',
                      'one_time', '2025-01-01', '2025-12-31')
            """
        )
        self.connection.commit()

        settlement = settlement_for_period(
            self.connection, 1, "2025-01-01", "2025-12-31"
        )

        self.assertEqual(
            [result["allocated_costs"] for result in settlement["results"]],
            ["20.00", "80.00"],
        )
        self.assertEqual(
            [result["line_items"][0]["basis_value"] for result in settlement["results"]],
            ["20", "80"],
        )

    def test_settlement_includes_monthly_and_consumption_expenses(self) -> None:
        create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "label": "Rauchwarnmelder",
                "amount": "12.00",
                "allocation_method": "unit_count",
                "recurrence": "recurring",
                "interval": "monthly",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )
        create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "label": "Wasser Verbrauch",
                "amount": "900.00",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "consumption_unit": "m3",
                "consumption_value": "120.0",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )

        settlement = settlement_for_period(self.connection, 1, "2025-01-01", "2025-12-31")
        labels = {
            line_item["label"]
            for result in settlement["results"]
            for line_item in result["line_items"]
        }

        self.assertIn("Rauchwarnmelder", labels)
        self.assertIn("Wasser Verbrauch", labels)

    def test_create_expense_maps_recurring_yearly_to_yearly_charge_type(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "label": "Versicherung",
                "amount": "450.00",
                "allocation_method": "area",
                "recurrence": "recurring",
                "interval": "yearly",
                "period_start": "2025-01-01",
                "period_end": "2027-12-31",
            },
        )
        self.assertEqual(created["charge_type"], "yearly")
        row = self.connection.execute(
            "SELECT charge_type, recurrence, interval_name FROM expense_items WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(row["charge_type"], "yearly")
        self.assertEqual(row["recurrence"], "recurring")
        self.assertEqual(row["interval_name"], "yearly")

    def test_settlement_excludes_archived_expenses(self) -> None:
        created = create_expense(
            self.connection,
            {
                "object_type": "property",
                "object_id": 1,
                "label": "Archivierte Wartung",
                "amount": "111.00",
                "allocation_method": "unit_count",
                "charge_type": "one_time",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )
        archive_object(self.connection, "expenses", created["id"])

        settlement = settlement_for_period(self.connection, 1, "2025-01-01", "2025-12-31")
        labels = {
            line_item["label"]
            for result in settlement["results"]
            for line_item in result["line_items"]
        }

        self.assertNotIn("Archivierte Wartung", labels)

    def test_settlement_includes_expenses_from_building_unit_and_room_targets(self) -> None:
        room = create_room(
            self.connection,
            {
                "unit_id": 1,
                "label": "Abstellraum",
            },
        )
        create_expense(
            self.connection,
            {
                "object_type": "building",
                "object_id": 1,
                "label": "Gebäudereinigung",
                "amount": "300.00",
                "allocation_method": "unit_count",
                "recurrence": "one_time",
                "booking_date": "2025-04-01",
            },
        )
        create_expense(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Wohnungswartung",
                "amount": "120.00",
                "allocation_method": "unit_count",
                "recurrence": "one_time",
                "booking_date": "2025-04-02",
            },
        )
        create_expense(
            self.connection,
            {
                "object_type": "room",
                "object_id": room["id"],
                "label": "Zimmeranstrich",
                "amount": "90.00",
                "allocation_method": "unit_count",
                "recurrence": "one_time",
                "booking_date": "2025-04-03",
            },
        )

        settlement = settlement_for_period(self.connection, 1, "2025-01-01", "2025-12-31")
        labels = {
            line_item["label"]
            for result in settlement["results"]
            for line_item in result["line_items"]
        }

        self.assertIn("Gebäudereinigung", labels)
        self.assertIn("Wohnungswartung", labels)
        self.assertIn("Zimmeranstrich", labels)
        line_items_by_tenant = {
            result["tenant_name"]: {
                line_item["label"] for line_item in result["line_items"]
            }
            for result in settlement["results"]
        }
        self.assertIn("Gebäudereinigung", line_items_by_tenant["Anna Schulz"])
        self.assertIn("Gebäudereinigung", line_items_by_tenant["Tim Wagner"])
        self.assertIn("Wohnungswartung", line_items_by_tenant["Anna Schulz"])
        self.assertNotIn("Wohnungswartung", line_items_by_tenant["Tim Wagner"])
        self.assertIn("Zimmeranstrich", line_items_by_tenant["Anna Schulz"])
        self.assertNotIn("Zimmeranstrich", line_items_by_tenant["Tim Wagner"])

    def test_list_overview_includes_meters_with_latest_reading(self) -> None:
        meter = create_meter(
            self.connection,
            {
                "object_type": "unit",
                "object_id": 1,
                "label": "Heizzähler A-01",
                "meter_type": "heating",
                "unit": "kWh",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-01-15",
                "reading_value": "10",
            },
        )
        create_meter_reading(
            self.connection,
            {
                "meter_id": meter["id"],
                "reading_date": "2025-02-15",
                "reading_value": "18",
            },
        )

        overview = list_overview(self.connection)
        meter_row = overview["meters"][0]

        self.assertEqual(meter_row["label"], "Heizzähler A-01")
        self.assertEqual(meter_row["unit"], "kWh")
        self.assertEqual(meter_row["object_type"], "unit")
        self.assertEqual(meter_row["object_name"], "A-01")
        self.assertEqual(meter_row["latest_reading_date"], "2025-02-15")
        self.assertEqual(str(meter_row["latest_reading_value"]), "18")
        self.assertEqual(meter_row["reading_count"], 2)

        reading_rows = overview["meter_readings"]
        self.assertEqual(len(reading_rows), 2)
        self.assertEqual(reading_rows[0]["meter_id"], meter["id"])
        self.assertEqual(reading_rows[0]["reading_date"], "2025-01-15")
        self.assertEqual(reading_rows[1]["reading_date"], "2025-02-15")
        self.assertEqual(reading_rows[1]["meter_label"], "Heizzähler A-01")


if __name__ == "__main__":
    unittest.main()


class PropertyRelationshipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        seed_demo_data(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_create_building_allows_standalone_without_property(self) -> None:
        created = create_building(
            self.connection,
            {
                "property_id": None,
                "name": "Einzelgebaeude Nord",
                "year_built": 2004,
                "street": "Nordweg 5",
                "city": "Berlin",
                "postal_code": "10115",
            },
        )
        row = self.connection.execute(
            "SELECT property_id, name, street, city, postal_code FROM buildings WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertIsNone(row["property_id"])
        self.assertEqual(row["name"], "Einzelgebaeude Nord")
        self.assertEqual(row["street"], "Nordweg 5")
        self.assertEqual(row["city"], "Berlin")
        self.assertEqual(row["postal_code"], "10115")

    def test_create_unit_allows_standalone_without_building(self) -> None:
        created = create_unit(
            self.connection,
            {
                "building_id": None,
                "label": "Whg-Solo-1",
                "area_sqm": "58.5",
                "mea_percent": "12.5",
                "room_count": 2,
                "street": "Sonnenallee 10",
                "city": "Berlin",
                "postal_code": "12045",
            },
        )
        row = self.connection.execute(
            "SELECT building_id, label, mea_percent, street, city, postal_code FROM units WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertIsNone(row["building_id"])
        self.assertEqual(row["label"], "Whg-Solo-1")
        self.assertEqual(row["mea_percent"], 12.5)
        self.assertEqual(row["street"], "Sonnenallee 10")
        self.assertEqual(row["city"], "Berlin")
        self.assertEqual(row["postal_code"], "12045")

    def test_create_unit_requires_mea_percent(self) -> None:
        with self.assertRaises(ValueError) as error:
            create_unit(
                self.connection,
                {
                    "building_id": None,
                    "label": "Whg-Solo-1",
                    "area_sqm": "58.5",
                    "room_count": 2,
                    "street": "Sonnenallee 10",
                    "city": "Berlin",
                    "postal_code": "12045",
                },
            )

        self.assertIn("mea_percent", str(error.exception))

    def test_create_unit_inherits_address_from_building(self) -> None:
        created = create_unit(
            self.connection,
            {
                "building_id": 1,
                "label": "A-04",
                "area_sqm": "56.0",
                "mea_percent": "10",
                "room_count": 2,
                "street": "Abweichende Straße 1",
                "city": "Hamburg",
                "postal_code": "20095",
            },
        )

        row = self.connection.execute(
            "SELECT street, city, postal_code FROM units WHERE id = ?", (created["id"],)
        ).fetchone()
        self.assertEqual(dict(row), {"street": "Lindenweg 12", "city": "Berlin", "postal_code": "10439"})

    def test_update_unit_inherits_address_from_new_building(self) -> None:
        building = create_building(
            self.connection,
            {
                "property_id": 1,
                "name": "Haus B",
                "year_built": 2010,
                "street": "Birkenstraße 7",
                "city": "Potsdam",
                "postal_code": "14467",
            },
        )

        update_unit(
            self.connection,
            1,
            {
                "building_id": building["id"],
                "label": "A-01",
                "area_sqm": "74.5",
                "mea_percent": "34.1",
                "room_count": 3,
                "street": "Abweichende Straße 1",
                "city": "Hamburg",
                "postal_code": "20095",
            },
        )

        row = self.connection.execute(
            "SELECT street, city, postal_code FROM units WHERE id = 1"
        ).fetchone()
        self.assertEqual(dict(row), {"street": "Birkenstraße 7", "city": "Potsdam", "postal_code": "14467"})

    def test_create_room_requires_unit(self) -> None:
        with self.assertRaises(ValueError):
            create_room(
                self.connection,
                {
                    "unit_id": None,
                    "label": "Zimmer 1",
                },
            )

    def test_create_room_belongs_to_unit(self) -> None:
        created = create_room(
            self.connection,
            {
                "unit_id": 1,
                "label": "Zimmer links",
            },
        )
        row = self.connection.execute(
            "SELECT unit_id, label FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(row["unit_id"], 1)
        self.assertEqual(row["label"], "Zimmer links")

    def test_create_room_stores_area_share_percent(self) -> None:
        created = create_room(
            self.connection,
            {
                "unit_id": 1,
                "label": "Zimmer links",
                "area_share_percent": "37.5",
            },
        )

        row = self.connection.execute(
            "SELECT area_share_percent FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()

        self.assertEqual(created["area_share_percent"], "37.5")
        self.assertEqual(row["area_share_percent"], 37.5)

    def test_create_room_rejects_area_share_outside_percentage_range(self) -> None:
        with self.assertRaises(ValueError) as error:
            create_room(
                self.connection,
                {
                    "unit_id": 1,
                    "label": "Zimmer links",
                    "area_share_percent": "100.01",
                },
            )

        self.assertIn("between 0 and 100", str(error.exception))

    def test_create_room_rejects_more_rooms_than_unit_allows(self) -> None:
        create_room(
            self.connection,
            {
                "unit_id": 2,
                "label": "Zimmer 1",
            },
        )
        create_room(
            self.connection,
            {
                "unit_id": 2,
                "label": "Zimmer 2",
            },
        )

        with self.assertRaises(ValueError) as error:
            create_room(
                self.connection,
                {
                    "unit_id": 2,
                    "label": "Zimmer 3",
                },
            )

        self.assertIn("room_count", str(error.exception))

    def test_list_overview_enriches_object_relationships_for_preview(self) -> None:
        create_room(
            self.connection,
            {
                "unit_id": 1,
                "label": "Wohnzimmer",
            },
        )

        overview = list_overview(self.connection)
        property_row = overview["properties"][0]
        building_row = overview["buildings"][0]
        unit_row = overview["units"][0]
        room_row = overview["rooms"][0]
        expense_row = overview["expenses"][0]

        self.assertEqual(property_row["name"], "Wohnpark Lindenhof")
        self.assertEqual(property_row["building_count"], 1)
        self.assertEqual(property_row["unit_count"], 3)
        self.assertEqual(property_row["room_count"], 1)

        self.assertEqual(building_row["name"], "Haus A")
        self.assertEqual(building_row["property_name"], "Wohnpark Lindenhof")
        self.assertEqual(building_row["unit_count"], 3)
        self.assertEqual(building_row["room_count"], 1)

        self.assertEqual(unit_row["label"], "A-01")
        self.assertEqual(unit_row["building_name"], "Haus A")
        self.assertEqual(unit_row["property_name"], "Wohnpark Lindenhof")
        self.assertEqual(unit_row["actual_room_count"], 1)

        self.assertEqual(room_row["label"], "Wohnzimmer")
        self.assertEqual(room_row["unit_label"], "A-01")
        self.assertEqual(room_row["building_name"], "Haus A")
        self.assertEqual(room_row["property_name"], "Wohnpark Lindenhof")

        self.assertEqual(expense_row["label"], "Heizung")
        self.assertEqual(expense_row["expense_category"], "Heizung")
        self.assertEqual(expense_row["beneficiary_name"], "Stadtwerke Berlin")
        self.assertEqual(expense_row["object_type"], "property")
        self.assertNotIn("property_name", expense_row)
        self.assertTrue(overview["expense_categories"])
        self.assertIn(
            ("Heizung", "Stadtwerke Berlin"),
            {
                (category["expense_category"], category["beneficiary_name"])
                for category in overview["expense_categories"]
            },
        )

    def test_archive_and_delete_room_requires_archive_first(self) -> None:
        created = create_room(
            self.connection,
            {
                "unit_id": 1,
                "label": "Archivzimmer",
            },
        )

        with self.assertRaises(ValueError) as error:
            delete_object(self.connection, "rooms", created["id"])
        self.assertIn("archived", str(error.exception))

        archived = archive_object(self.connection, "rooms", created["id"])
        row = self.connection.execute(
            "SELECT is_archived, archived_at FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(archived["is_archived"], 1)
        self.assertEqual(row["is_archived"], 1)
        self.assertIsNotNone(row["archived_at"])

        deleted = delete_object(self.connection, "rooms", created["id"])
        remaining = self.connection.execute(
            "SELECT id FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(deleted["id"], created["id"])
        self.assertIsNone(remaining)

    def test_restore_room_clears_archive_state(self) -> None:
        created = create_room(
            self.connection,
            {
                "unit_id": 1,
                "label": "Rueckholzimmer",
            },
        )

        archive_object(self.connection, "rooms", created["id"])
        restored = restore_object(self.connection, "rooms", created["id"])
        row = self.connection.execute(
            "SELECT is_archived, archived_at FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()

        self.assertEqual(restored["is_archived"], 0)
        self.assertIsNone(restored["archived_at"])
        self.assertEqual(row["is_archived"], 0)
        self.assertIsNone(row["archived_at"])

    def test_delete_building_rejects_archived_parent_with_child_units(self) -> None:
        archive_object(self.connection, "buildings", 1)

        with self.assertRaises(ValueError) as error:
            delete_object(self.connection, "buildings", 1)

        self.assertIn("dependencies", str(error.exception))
