from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from .calculations import parse_date, quantize_money


def overlap_period(
    first_start: str,
    first_end: str,
    second_start: str,
    second_end: str,
) -> tuple[str, str] | None:
    overlap_start = max(parse_date(first_start), parse_date(second_start))
    overlap_end = min(parse_date(first_end), parse_date(second_end))
    if overlap_start > overlap_end:
        return None
    return overlap_start.isoformat(), overlap_end.isoformat()


def interpolate_meter_reading(
    reading_points: list[tuple[date, Decimal]],
    target_date: date,
) -> Decimal | None:
    if not reading_points:
        return None

    previous_point: tuple[date, Decimal] | None = None
    for current_point in reading_points:
        current_date, current_value = current_point
        if current_date == target_date:
            return current_value
        if current_date > target_date:
            if previous_point is None:
                return None
            previous_date, previous_value = previous_point
            total_days = (current_date - previous_date).days
            if total_days <= 0:
                return previous_value
            elapsed_days = (target_date - previous_date).days
            return previous_value + (
                (current_value - previous_value) * Decimal(elapsed_days) / Decimal(total_days)
            )
        previous_point = current_point

    return None


def meter_consumption_for_period(
    reading_points: list[tuple[date, Decimal]],
    period_start: str,
    period_end: str,
) -> Decimal | None:
    start_date = parse_date(period_start)
    end_date = parse_date(period_end)
    if end_date < start_date:
        return None
    if len(reading_points) < 2:
        return None

    start_value = interpolate_meter_reading(reading_points, start_date)
    end_value = interpolate_meter_reading(reading_points, end_date)
    if start_value is None or end_value is None or end_value < start_value:
        return None
    return end_value - start_value


def day_accurate_recurring_amount(
    amount: Decimal,
    charge_type: str,
    overlap_start: date,
    overlap_end: date,
    anchor_start: date | None = None,
) -> Decimal:
    if overlap_end < overlap_start:
        return Decimal("0")

    if charge_type == "monthly":
        total = Decimal("0")
        current_day = overlap_start
        while current_day <= overlap_end:
            month_days = monthrange(current_day.year, current_day.month)[1]
            month_end = date(current_day.year, current_day.month, month_days)
            segment_end = min(month_end, overlap_end)
            active_days = (segment_end - current_day).days + 1
            total += amount * Decimal(active_days) / Decimal(month_days)
            current_day = date.fromordinal(segment_end.toordinal() + 1)
        return quantize_money(total)

    if charge_type == "yearly":
        if anchor_start is None:
            anchor_start = overlap_start

        def _next_year(start_day: date) -> date:
            try:
                return start_day.replace(year=start_day.year + 1)
            except ValueError:
                # Handle 29-Feb anchors in non-leap years.
                return start_day.replace(year=start_day.year + 1, day=28)

        cycle_start = anchor_start
        while True:
            candidate_next_cycle = _next_year(cycle_start)
            candidate_cycle_end = date.fromordinal(candidate_next_cycle.toordinal() - 1)
            if overlap_start <= candidate_cycle_end:
                break
            cycle_start = candidate_next_cycle

        total = Decimal("0")
        current_day = overlap_start
        while current_day <= overlap_end:
            next_cycle_start = _next_year(cycle_start)
            cycle_end = date.fromordinal(next_cycle_start.toordinal() - 1)
            segment_end = min(cycle_end, overlap_end)
            active_days = (segment_end - current_day).days + 1
            cycle_days = (cycle_end - cycle_start).days + 1
            total += amount * Decimal(active_days) / Decimal(cycle_days)
            current_day = date.fromordinal(segment_end.toordinal() + 1)
            cycle_start = next_cycle_start
        return quantize_money(total)

    return quantize_money(amount)
