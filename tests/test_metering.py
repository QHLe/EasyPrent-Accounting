from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest

from easyprent_accounting.metering import Metering, meter_consumption_for_period
from easyprent_accounting.migration import migrate_database
from tests.legacy_fixture import create_legacy_fixture
from tests.support import in_memory_database


class MeteringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.metering = Metering(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_readings_are_visible_and_can_be_backfilled_only_monotonically(self) -> None:
        meter = self.metering.create_meter(
            {"object_type": "unit", "object_id": 1, "label": "Wasser", "unit": "m3"}
        )
        self.metering.create_reading(
            {"meter_id": meter["id"], "reading_date": "2025-01-01", "reading_value": "100"}
        )
        self.metering.create_reading(
            {"meter_id": meter["id"], "reading_date": "2025-01-11", "reading_value": "120"}
        )
        with self.assertRaisesRegex(ValueError, "later reading"):
            self.metering.create_reading(
                {"meter_id": meter["id"], "reading_date": "2025-01-06", "reading_value": "121"}
            )

        self.metering.create_reading(
            {"meter_id": meter["id"], "reading_date": "2025-01-06", "reading_value": "110"}
        )
        overview = self.metering.list_meters()
        self.assertEqual(overview["meters"][0]["reading_count"], 3)
        self.assertEqual(overview["meters"][0]["latest_reading_date"], "2025-01-11")
        self.assertEqual(
            [reading["reading_date"] for reading in overview["meter_readings"]],
            ["2025-01-01", "2025-01-06", "2025-01-11"],
        )

    def test_consumption_interpolates_for_partial_period(self) -> None:
        meter = self.metering.create_meter(
            {"object_type": "unit", "object_id": 1, "label": "Heizung", "unit": "kWh"}
        )
        for reading_date, reading_value in (("2025-01-01", "100"), ("2025-01-11", "120")):
            self.metering.create_reading(
                {"meter_id": meter["id"], "reading_date": reading_date, "reading_value": reading_value}
            )

        self.assertEqual(
            self.metering.consumption_for_period(meter["id"], "2025-01-03", "2025-01-08"),
            Decimal("12"),
        )

    def test_meter_target_or_unit_cannot_change_after_reading(self) -> None:
        meter = self.metering.create_meter(
            {"object_type": "unit", "object_id": 1, "label": "Wasser", "unit": "m3"}
        )
        self.metering.create_reading(
            {"meter_id": meter["id"], "reading_date": "2025-01-01", "reading_value": "100"}
        )

        with self.assertRaisesRegex(ValueError, "unit cannot be changed"):
            self.metering.update_meter(
                meter["id"],
                {"object_type": "unit", "object_id": 1, "label": "Wasser", "unit": "kWh"},
            )

    def test_meter_must_be_archived_and_unreferenced_before_deletion(self) -> None:
        meter = self.metering.create_meter(
            {"object_type": "unit", "object_id": 1, "label": "Wasser", "unit": "m3"}
        )
        reading = self.metering.create_reading(
            {"meter_id": meter["id"], "reading_date": "2025-01-01", "reading_value": "100"}
        )

        with self.assertRaisesRegex(ValueError, "archived"):
            self.metering.delete_meter(meter["id"])
        archived = self.metering.archive_meter(meter["id"])
        self.assertEqual(archived, self.metering.archive_meter(meter["id"]))
        with self.assertRaisesRegex(ValueError, "dependencies"):
            self.metering.delete_meter(meter["id"])

        self.metering.delete_reading(reading["id"])
        self.assertEqual(self.metering.delete_meter(meter["id"])["deleted"], True)
        self.assertEqual(self.metering.list_meters()["meters"], [])


class MeterInterpolationTests(unittest.TestCase):
    def test_meter_consumption_for_period_uses_linear_interpolation(self) -> None:
        reading_points = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 11), Decimal("120")),
        ]
        consumption = meter_consumption_for_period(
            reading_points,
            "2025-01-03",
            "2025-01-08",
        )
        self.assertEqual(consumption, Decimal("12"))

    def test_meter_consumption_for_period_uses_first_reading_when_period_starts_earlier(self) -> None:
        reading_points = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 11), Decimal("120")),
        ]
        consumption = meter_consumption_for_period(
            reading_points,
            "2024-12-31",
            "2025-01-08",
        )
        self.assertEqual(consumption, Decimal("16"))

    def test_meter_consumption_for_period_uses_latest_reading_when_period_ends_later(self) -> None:
        reading_points = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 11), Decimal("120")),
        ]
        consumption = meter_consumption_for_period(
            reading_points,
            "2025-01-01",
            "2025-01-31",
        )
        self.assertEqual(consumption, Decimal("20"))


class MigratedMeteringTests(unittest.TestCase):
    def test_meter_listing_and_writes_use_v1_target_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            create_legacy_fixture(path)
            migrate_database(path, cutover=True)
            with sqlite3.connect(path) as connection:
                connection.row_factory = sqlite3.Row
                metering = Metering(connection)
                existing = metering.list_meters()
                self.assertTrue(existing["meters"])
                self.assertTrue(
                    all(meter["property_name"] for meter in existing["meters"] if meter["object_type"] == "property")
                )
                property_id = connection.execute("SELECT id FROM properties ORDER BY id LIMIT 1").fetchone()[0]
                created = metering.create_meter(
                    {"object_type": "property", "object_id": property_id, "label": "Neu", "unit": "m3"}
                )
                metering.update_meter(
                    created["id"],
                    {"object_type": "property", "object_id": property_id, "label": "Geändert", "unit": "m3"},
                )
                listed = next(m for m in metering.list_meters()["meters"] if m["id"] == created["id"])
                self.assertEqual((listed["property_id"], listed["label"]), (property_id, "Geändert"))


if __name__ == "__main__":
    unittest.main()
