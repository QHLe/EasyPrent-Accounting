import sqlite3
from decimal import Decimal

def seed_demo_data(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
        ("EasyPrent Demo Verwaltung", "property_management"),
    )
    organization_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    connection.execute(
        "INSERT INTO users (full_name, email) VALUES (?, ?)",
        ("Maria Becker", "maria@example.com"),
    )
    user_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO memberships (organization_id, user_id, role) VALUES (?, ?, ?)",
        (organization_id, user_id, "manager"),
    )

    connection.execute(
        """
        INSERT INTO properties (organization_id, name, street, city, postal_code)
        VALUES (?, ?, ?, ?, ?)
        """,
        (organization_id, "Wohnpark Lindenhof", "Lindenweg 12", "Berlin", "10439"),
    )
    property_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    connection.execute(
        """
        INSERT INTO buildings (property_id, name, year_built, street, city, postal_code)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (property_id, "Haus A", 1998, "Lindenweg 12", "Berlin", "10439"),
    )
    building_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    units = [
        ("A-01", Decimal("74.5"), Decimal("34.0961"), 3, "Lindenweg 12", "Berlin", "10439"),
        ("A-02", Decimal("61.0"), Decimal("27.9176"), 2, "Lindenweg 12", "Berlin", "10439"),
        ("A-03", Decimal("83.0"), Decimal("37.9863"), 4, "Lindenweg 12", "Berlin", "10439"),
    ]
    unit_ids = []
    for label, area_sqm, mea_percent, room_count, street, city, postal_code in units:
        connection.execute(
            """
            INSERT INTO units (building_id, label, area_sqm, mea_percent, room_count, street, city, postal_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (building_id, label, str(area_sqm), str(mea_percent), room_count, street, city, postal_code),
        )
        unit_ids.append(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    tenants = [
        ("Anna Schulz", "anna@example.com", "030-111111"),
        ("Tim Wagner", "tim@example.com", "030-222222"),
    ]
    tenant_ids = []
    for tenant in tenants:
        connection.execute(
            "INSERT INTO tenants (full_name, email, phone) VALUES (?, ?, ?)",
            tenant,
        )
        tenant_ids.append(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

    leases = [
        (unit_ids[0], tenant_ids[0], "1200.00", "230.00", 2, "2025-01-01", None, "active"),
        (unit_ids[1], tenant_ids[1], "980.00", "190.00", 1, "2025-04-01", None, "active"),
    ]
    connection.executemany(
        """
        INSERT INTO leases (
            unit_id, tenant_id, rent_cold, additional_charges_advance, occupant_count,
            start_date, end_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        leases,
    )

    expenses = [
        (
            property_id,
            "property",
            property_id,
            "Heizung",
            "Stadtwerke Berlin",
            "Heizung",
            "4200.00",
            "area",
            "one_time",
            "one_time",
            None,
            None,
            None,
            None,
            "1",
            "2025-12-31",
            "2025-12-31",
            "2025-12-31",
        ),
        (
            property_id,
            "property",
            property_id,
            "Wasser",
            "Berliner Wasserbetriebe",
            "Wasser",
            "1600.00",
            "occupants",
            "consumption",
            "one_time",
            None,
            None,
            "m3",
            "210.0",
            "1",
            None,
            "2025-01-01",
            "2025-12-31",
        ),
        (
            property_id,
            "property",
            property_id,
            "Hausreinigung",
            "Firma Sauber GmbH",
            "Treppenhausreinigung",
            "75.00",
            "unit_count",
            "monthly",
            "recurring",
            "monthly",
            None,
            None,
            None,
            "1",
            None,
            "2025-01-01",
            "2025-12-31",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO expense_items (
            property_id, object_type, object_id, expense_category, beneficiary_name, label, amount,
            allocation_method, charge_type, recurrence, interval_name, meter_id, consumption_unit,
            consumption_value, conversion_factor, booking_date, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        expenses,
    )

    assets = [
        (property_id, "Gebäudekörper Haus A", "720000.00", "82.0", 40, "2025-01-01", "linear"),
        (property_id, "Dachanierung 2025", "68000.00", "100.0", 20, "2025-07-01", "linear"),
    ]
    connection.executemany(
        """
        INSERT INTO depreciation_assets (
            property_id, asset_name, acquisition_cost, building_share_percent,
            useful_life_years, placed_in_service, method
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        assets,
    )
