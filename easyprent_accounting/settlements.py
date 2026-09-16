"""Settlement inputs, persistence boundary, and the single allocation engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import sqlite3

from .calculations import quantize_money
from .domain import Date as DomainDate, DateRange
from .expense_pricer import ExpensePricer
from .metering import meter_consumption_for_period


@dataclass(frozen=True, slots=True)
class LeaseSnapshot:
    id: int
    tenant_name: str
    unit_label: str
    unit_id: int
    room_id: int | None
    building_id: int | None
    mea_percent: Decimal | None
    area_share_percent: Decimal | None
    occupant_count: int
    additional_charges_advance: Decimal
    start_date: date
    end_date: date | None


@dataclass(frozen=True, slots=True)
class ExpenseSnapshot:
    id: int
    label: str
    category: str
    amount: Decimal
    allocation_method: str
    charge_type: str
    recurrence: str
    interval_name: str | None
    period_start: date
    period_end: date
    object_type: str
    object_id: int
    target_room_unit_id: int | None = None
    meter_id: int | None = None
    consumption_unit: str | None = None
    consumption_value: Decimal | None = None
    conversion_factor: Decimal = Decimal("1")


@dataclass(frozen=True, slots=True)
class MeterReadingSnapshot:
    meter_id: int
    reading_date: date
    reading_value: Decimal


@dataclass(frozen=True, slots=True)
class PaymentSnapshot:
    lease_id: int
    split_guid: str
    booking_date: date
    amount: Decimal
    description: str


@dataclass(frozen=True, slots=True)
class SettlementSnapshot:
    period_start: date
    period_end: date
    property_id: int | None
    unit_id: int | None
    leases: tuple[LeaseSnapshot, ...]
    expenses: tuple[ExpenseSnapshot, ...]
    meter_readings: tuple[MeterReadingSnapshot, ...]
    payments: tuple[PaymentSnapshot, ...]


def _overlap(start_a: date, end_a: date, start_b: date, end_b: date) -> tuple[date, date] | None:
    start, end = max(start_a, start_b), min(end_a, end_b)
    return (start, end) if start <= end else None


def _eligible_leases(expense: ExpenseSnapshot, leases: tuple[LeaseSnapshot, ...]) -> tuple[LeaseSnapshot, ...]:
    if expense.object_type == "building":
        return tuple(lease for lease in leases if lease.building_id == expense.object_id)
    if expense.object_type == "unit":
        return tuple(lease for lease in leases if lease.unit_id == expense.object_id)
    if expense.object_type == "room":
        return tuple(
            lease for lease in leases
            if lease.room_id == expense.object_id
            or (lease.room_id is None and lease.unit_id == expense.target_room_unit_id)
        )
    return leases


def _allocation_basis(lease: LeaseSnapshot, method: str) -> Decimal:
    if method == "area":
        if lease.mea_percent is None:
            raise ValueError("unit requires mea_percent for allocation by MEA")
        if lease.room_id is not None:
            if lease.area_share_percent is None:
                raise ValueError("room lease requires area_share_percent for allocation by MEA")
            return lease.mea_percent * lease.area_share_percent / Decimal("100")
        return lease.mea_percent
    if method == "occupants":
        return Decimal(lease.occupant_count)
    return Decimal("1")


def _consumption_quantity(
    expense: ExpenseSnapshot, snapshot: SettlementSnapshot, start: date, end: date
) -> Decimal | None:
    if expense.charge_type != "consumption":
        return None
    overlap = _overlap(expense.period_start, expense.period_end, start, end)
    if overlap is None:
        return None
    start, end = overlap
    if expense.meter_id is not None:
        readings = [
            (reading.reading_date, reading.reading_value)
            for reading in snapshot.meter_readings
            if reading.meter_id == expense.meter_id
        ]
        readings.sort(key=lambda item: item[0])
        raw = meter_consumption_for_period(readings, start.isoformat(), end.isoformat())
    else:
        raw = expense.consumption_value
        if raw is not None:
            full_days = Decimal((expense.period_end - expense.period_start).days + 1)
            overlap_days = Decimal((end - start).days + 1)
            raw = raw * overlap_days / full_days
    return raw * expense.conversion_factor if raw is not None else None


def _price(
    expense: ExpenseSnapshot, snapshot: SettlementSnapshot, start: date, end: date
) -> Decimal | None:
    consumption = (
        _consumption_quantity(expense, snapshot, start, end)
        if expense.charge_type == "consumption" else None
    )
    return ExpensePricer.amount_for_period(
        amount=expense.amount,
        charge_type=expense.charge_type,
        expense_start=expense.period_start,
        expense_end=expense.period_end,
        period_start=start,
        period_end=end,
        consumption_value=consumption,
    )


def _segments(
    expense: ExpenseSnapshot,
    leases: tuple[LeaseSnapshot, ...],
    snapshot: SettlementSnapshot,
) -> list[dict]:
    coverage = _overlap(
        expense.period_start, expense.period_end,
        snapshot.period_start, snapshot.period_end,
    )
    if coverage is None:
        return []
    coverage_start, coverage_end = coverage
    boundaries = {coverage_start.toordinal(), coverage_end.toordinal() + 1}
    for lease in leases:
        active = _overlap(
            lease.start_date, lease.end_date or coverage_end,
            coverage_start, coverage_end,
        )
        if active is not None:
            boundaries.update((active[0].toordinal(), active[1].toordinal() + 1))

    segments: list[dict] = []
    sorted_boundaries = sorted(boundaries)
    for start_ordinal, next_ordinal in zip(sorted_boundaries, sorted_boundaries[1:]):
        segment_start = date.fromordinal(start_ordinal)
        segment_end = date.fromordinal(next_ordinal - 1)
        active_leases = tuple(
            lease for lease in leases
            if lease.start_date <= segment_start
            and (lease.end_date or coverage_end) >= segment_end
        )
        if not active_leases:
            continue
        amount = _price(expense, snapshot, segment_start, segment_end)
        if amount is None:
            continue
        basis_values = {lease.id: _allocation_basis(lease, expense.allocation_method) for lease in active_leases}
        basis_total = sum(basis_values.values(), start=Decimal("0"))
        if basis_total <= 0:
            continue
        segments.append({
            "period_start": segment_start.isoformat(),
            "period_end": segment_end.isoformat(),
            "period_amount": amount,
            "basis_values": basis_values,
            "basis_total": basis_total,
            "shares": {
                lease.id: amount * basis_values[lease.id] / basis_total
                for lease in active_leases
            },
        })
    return segments


def _rounded_shares(
    segments: list[dict], lease_ids: tuple[int, ...], period_amount: Decimal
) -> dict[int, Decimal]:
    exact = {lease_id: Decimal("0") for lease_id in lease_ids}
    for segment in segments:
        for lease_id, share in segment["shares"].items():
            exact[lease_id] += share
    rounded = {lease_id: quantize_money(value) for lease_id, value in exact.items()}
    difference = quantize_money(sum(exact.values(), start=Decimal("0"))) - sum(
        rounded.values(), start=Decimal("0")
    )
    if difference and rounded:
        largest = max(rounded, key=lambda lease_id: (exact[lease_id], -lease_id))
        rounded[largest] += difference
    remaining = period_amount - sum(rounded.values(), start=Decimal("0"))
    if Decimal("0") < abs(remaining) <= Decimal("0.01") and rounded:
        largest = max(rounded, key=lambda lease_id: (rounded[lease_id], -lease_id))
        rounded[largest] += remaining
    return rounded


def _allocation_periods(segments: list[dict], lease_id: int, total_share: Decimal) -> list[dict[str, str]]:
    periods = [
        {
            "period_start": segment["period_start"],
            "period_end": segment["period_end"],
            "period_amount": f"{segment['period_amount']:.2f}",
            "basis_value": str(segment["basis_values"][lease_id]),
            "basis_total": str(segment["basis_total"]),
            "share": quantize_money(segment["shares"][lease_id]),
            "raw_share": segment["shares"][lease_id],
        }
        for segment in segments if lease_id in segment["shares"]
    ]
    difference = total_share - sum((item["share"] for item in periods), start=Decimal("0"))
    if difference and periods:
        max(periods, key=lambda item: item["raw_share"])["share"] += difference
    return [
        {key: value if isinstance(value, str) else f"{value:.2f}"
         for key, value in period.items() if key != "raw_share"}
        for period in periods
    ]


def calculate_settlement_snapshot(snapshot: SettlementSnapshot) -> dict:
    """Calculate one settlement from immutable, already loaded domain inputs."""
    DateRange(DomainDate(snapshot.period_start), DomainDate(snapshot.period_end))
    active_leases = tuple(
        lease for lease in snapshot.leases
        if _overlap(lease.start_date, lease.end_date or snapshot.period_end,
                    snapshot.period_start, snapshot.period_end) is not None
    )
    results = {
        lease.id: {
            "lease_id": lease.id,
            "tenant_name": lease.tenant_name,
            "unit_label": lease.unit_label,
            "billing_period_start": max(lease.start_date, snapshot.period_start).isoformat(),
            "billing_period_end": min(lease.end_date or snapshot.period_end, snapshot.period_end).isoformat(),
            "allocated_costs": "0.00",
            "advances_paid": "0.00",
            "balance": "0.00",
            "line_items": [],
        }
        for lease in active_leases
    }

    for expense in snapshot.expenses:
        period_amount = _price(expense, snapshot, snapshot.period_start, snapshot.period_end)
        if period_amount is None or period_amount <= 0:
            continue
        eligible = _eligible_leases(expense, active_leases)
        if not eligible:
            continue
        segments = _segments(expense, eligible, snapshot)
        shares = _rounded_shares(segments, tuple(lease.id for lease in eligible), period_amount)
        basis_values = {lease.id: _allocation_basis(lease, expense.allocation_method) for lease in eligible}
        basis_total = sum(basis_values.values(), start=Decimal("0"))
        consumption = _consumption_quantity(
            expense, snapshot, snapshot.period_start, snapshot.period_end
        )
        for lease in eligible:
            billing_start = max(lease.start_date, snapshot.period_start)
            billing_end = min(lease.end_date or snapshot.period_end, snapshot.period_end)
            tenant_consumption = _consumption_quantity(expense, snapshot, billing_start, billing_end)
            item = {
                "source_id": expense.id,
                "label": expense.label,
                "allocation_method": expense.allocation_method,
                "period_amount": f"{period_amount:.2f}",
                "basis_value": str(basis_values[lease.id]),
                "basis_total": str(basis_total),
                "charge_type": expense.charge_type,
                "recurrence": expense.recurrence,
                "interval_name": expense.interval_name,
                "share": f"{shares[lease.id]:.2f}",
                "expense_category": expense.category,
                "allocation_periods": _allocation_periods(segments, lease.id, shares[lease.id]),
                "tenant_consumption_value": str(tenant_consumption) if tenant_consumption is not None else None,
            }
            if expense.consumption_unit:
                item["consumption_unit"] = expense.consumption_unit
            if consumption is not None:
                item["consumption_value"] = str(consumption)
            results[lease.id]["line_items"].append(item)

    total_costs = Decimal("0")
    total_advances = Decimal("0")
    for lease in active_leases:
        row = results[lease.id]
        costs = sum((Decimal(item["share"]) for item in row["line_items"]), start=Decimal("0"))
        payments = sum(
            (
                payment.amount for payment in snapshot.payments
                if payment.lease_id == lease.id
                and snapshot.period_start <= payment.booking_date <= snapshot.period_end
                and lease.start_date <= payment.booking_date
                and (lease.end_date is None or payment.booking_date <= lease.end_date)
            ),
            start=Decimal("0"),
        )
        advances = quantize_money(-payments)
        balance = quantize_money(costs - advances)
        row["allocated_costs"] = f"{costs:.2f}"
        row["advances_paid"] = f"{advances:.2f}"
        row["balance"] = f"{balance:.2f}"
        total_costs += costs
        total_advances += advances
    total_costs = quantize_money(total_costs)
    total_advances = quantize_money(total_advances)
    return {
        "period_start": snapshot.period_start.isoformat(),
        "period_end": snapshot.period_end.isoformat(),
        "results": [results[lease_id] for lease_id in sorted(results)],
        "totals": {
            "costs": f"{total_costs:.2f}",
            "advances": f"{total_advances:.2f}",
            "balance": f"{quantize_money(total_costs - total_advances):.2f}",
        },
        "property_id": snapshot.property_id,
        "unit_id": snapshot.unit_id,
    }


def _decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


class Settlements:
    """Load settlement inputs and expose the calculated period as one use case."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def snapshot_for_period(
        self,
        property_id: int | None,
        period_start: str,
        period_end: str,
        unit_id: int | None = None,
        payment_split_guids: set[str] | None = None,
    ) -> SettlementSnapshot:
        start = DomainDate.from_isoformat(period_start).value
        end = DomainDate.from_isoformat(period_end).value
        DateRange(DomainDate(start), DomainDate(end))
        target_where = "b.property_id = ?" if unit_id is None else "u.id = ?"
        target_value = property_id if unit_id is None else unit_id
        lease_rows = self.connection.execute(
            """
            SELECT l.id, l.unit_id, l.room_id, t.full_name AS tenant_name,
                   CASE WHEN l.room_id IS NOT NULL THEN r.label || ' (' || u.label || ')'
                        ELSE u.label END AS unit_label,
                   u.mea_percent, r.area_share_percent, u.building_id,
                   l.occupant_count, l.additional_charges_advance, l.start_date, l.end_date
            FROM leases l JOIN tenants t ON t.id = l.tenant_id
            JOIN units u ON u.id = l.unit_id
            LEFT JOIN rooms r ON r.id = l.room_id
            LEFT JOIN buildings b ON b.id = u.building_id
            WHERE """ + target_where + " ORDER BY l.id",
            (target_value,),
        ).fetchall()
        expense_rows = self.connection.execute(
            """
            SELECT id, object_type, object_id, expense_category, label, amount,
                   allocation_method, charge_type, recurrence, interval_name,
                   meter_id, consumption_unit, consumption_value, conversion_factor,
                   period_start, period_end,
                   CASE WHEN object_type = 'room'
                        THEN (SELECT unit_id FROM rooms WHERE rooms.id = expense_items.object_id)
                        ELSE NULL END AS target_room_unit_id
            FROM expense_items
            WHERE (property_id = ? OR (? IS NOT NULL AND (
                  (object_type = 'unit' AND object_id = ?)
                  OR (object_type = 'room' AND EXISTS (
                      SELECT 1 FROM rooms target_room
                      WHERE target_room.id = expense_items.object_id AND target_room.unit_id = ?))
                  OR (object_type = 'building' AND object_id =
                      (SELECT building_id FROM units WHERE id = ?)))))
              AND COALESCE(is_archived, 0) = 0
              AND period_end >= ? AND period_start <= ?
            ORDER BY id
            """,
            (property_id, unit_id, unit_id, unit_id, unit_id, period_start, period_end),
        ).fetchall()
        if any(row["allocation_method"] == "area" for row in expense_rows):
            for row in lease_rows:
                if row["mea_percent"] is None:
                    raise ValueError("unit requires mea_percent for allocation by MEA")
                if row["room_id"] is not None and row["area_share_percent"] is None:
                    raise ValueError("room lease requires area_share_percent for allocation by MEA")

        leases = tuple(
            LeaseSnapshot(
                id=int(row["id"]), tenant_name=str(row["tenant_name"]),
                unit_label=str(row["unit_label"]), unit_id=int(row["unit_id"]),
                room_id=row["room_id"], building_id=row["building_id"],
                mea_percent=_decimal(row["mea_percent"]),
                area_share_percent=_decimal(row["area_share_percent"]),
                occupant_count=int(row["occupant_count"]),
                additional_charges_advance=Decimal(str(row["additional_charges_advance"])),
                start_date=date.fromisoformat(row["start_date"]),
                end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
            ) for row in lease_rows
        )
        expenses = tuple(
            ExpenseSnapshot(
                id=int(row["id"]), label=str(row["label"]),
                category=str(row["expense_category"] or row["label"]),
                amount=Decimal(str(row["amount"])),
                allocation_method=str(row["allocation_method"]),
                charge_type=str(row["charge_type"]), recurrence=str(row["recurrence"]),
                interval_name=row["interval_name"],
                period_start=date.fromisoformat(row["period_start"]),
                period_end=date.fromisoformat(row["period_end"]),
                object_type=str(row["object_type"]), object_id=int(row["object_id"]),
                target_room_unit_id=row["target_room_unit_id"], meter_id=row["meter_id"],
                consumption_unit=row["consumption_unit"],
                consumption_value=_decimal(row["consumption_value"]),
                conversion_factor=_decimal(row["conversion_factor"]) or Decimal("1"),
            ) for row in expense_rows
        )
        meter_ids = sorted({expense.meter_id for expense in expenses if expense.meter_id is not None})
        meter_readings: tuple[MeterReadingSnapshot, ...] = ()
        if meter_ids:
            placeholders = ", ".join("?" for _ in meter_ids)
            rows = self.connection.execute(
                "SELECT meter_id, reading_date, reading_value FROM meter_readings "
                f"WHERE meter_id IN ({placeholders}) ORDER BY meter_id, reading_date",
                meter_ids,
            ).fetchall()
            meter_readings = tuple(
                MeterReadingSnapshot(int(row["meter_id"]), date.fromisoformat(row["reading_date"]),
                                     Decimal(str(row["reading_value"])))
                for row in rows
            )
        payment_filter = ""
        payment_params: list[object] = [period_start, period_end]
        if payment_split_guids is not None:
            if not payment_split_guids:
                payment_filter = " AND 1 = 0"
            else:
                payment_filter = " AND gp.split_guid IN (" + ", ".join("?" for _ in payment_split_guids) + ")"
                payment_params.extend(sorted(payment_split_guids))
        payment_rows = self.connection.execute(
            """
            SELECT gp.lease_id, gp.split_guid, gp.booking_date, gp.amount, gp.description
            FROM gnucash_payments gp JOIN leases l ON l.id = gp.lease_id
            WHERE gp.booking_date >= ? AND gp.booking_date <= ?
              AND gp.booking_date >= l.start_date
              AND (l.end_date IS NULL OR gp.booking_date <= l.end_date)
            """ + payment_filter + " ORDER BY gp.booking_date, gp.split_guid",
            payment_params,
        ).fetchall()
        payments = tuple(
            PaymentSnapshot(int(row["lease_id"]), str(row["split_guid"]),
                            date.fromisoformat(row["booking_date"]),
                            Decimal(str(row["amount"])), str(row["description"] or ""))
            for row in payment_rows
        )
        return SettlementSnapshot(start, end, property_id, unit_id, leases, expenses, meter_readings, payments)

    def for_period(
        self,
        property_id: int | None,
        period_start: str,
        period_end: str,
        unit_id: int | None = None,
        payment_split_guids: set[str] | None = None,
    ) -> dict:
        return calculate_settlement_snapshot(
            self.snapshot_for_period(property_id, period_start, period_end, unit_id, payment_split_guids)
        )
