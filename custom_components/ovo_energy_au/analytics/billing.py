"""Billing-cycle date helpers.

OVO customers can have a billing cycle that starts on a day other than the 1st
(e.g. the 24th, running 24th–23rd). When a ``billing_cycle_day`` greater than 1
is configured, the "this period" figures, daily averages and bill projections
follow that cycle instead of the calendar month.

``billing_cycle_day == 1`` yields exact calendar-month boundaries, so the
default preserves the original behaviour for everyone who hasn't set a cycle day.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def _clamp_day(year: int, month: int, day: int) -> int:
    """Clamp a target day-of-month to the number of days in that month.

    Keeps a cycle day of, say, 31 from overflowing a 30-day month (it lands on
    the last day instead).
    """
    return min(day, calendar.monthrange(year, month)[1])


def _prev_month(year: int, month: int) -> tuple[int, int]:
    """Return the (year, month) immediately before the given month."""
    return (year, month - 1) if month > 1 else (year - 1, 12)


def _next_month(year: int, month: int) -> tuple[int, int]:
    """Return the (year, month) immediately after the given month."""
    return (year, month + 1) if month < 12 else (year + 1, 1)


def current_cycle_bounds(today: date, cycle_day: int) -> tuple[date, date]:
    """Return ``(start, next_start)`` for the billing cycle containing ``today``.

    ``start`` is inclusive and ``next_start`` is exclusive (the first day of the
    following cycle), so the cycle length is ``(next_start - start).days`` and a
    day belongs to the cycle when ``start <= day < next_start``.

    ``cycle_day`` is clamped per-month, so a value of 31 always resolves to the
    last day of a short month. Values <= 1 give calendar-month boundaries.
    """
    cycle_day = max(1, cycle_day)
    start_day = _clamp_day(today.year, today.month, cycle_day)

    if today.day >= start_day:
        # Cycle started earlier this month.
        start = date(today.year, today.month, start_day)
        ny, nm = _next_month(today.year, today.month)
    else:
        # Still in the cycle that started last month.
        py, pm = _prev_month(today.year, today.month)
        start = date(py, pm, _clamp_day(py, pm, cycle_day))
        ny, nm = today.year, today.month

    next_start = date(ny, nm, _clamp_day(ny, nm, cycle_day))
    return start, next_start


def previous_cycle_bounds(today: date, cycle_day: int) -> tuple[date, date]:
    """Return ``(start, next_start)`` for the cycle just before the current one.

    ``next_start`` of the previous cycle equals ``start`` of the current cycle.
    """
    cur_start, _ = current_cycle_bounds(today, cycle_day)
    # Any day inside the previous cycle — the day before the current one starts.
    return current_cycle_bounds(cur_start - timedelta(days=1), cycle_day)


def cycle_length_days(today: date, cycle_day: int) -> int:
    """Return the number of days in the billing cycle containing ``today``."""
    start, next_start = current_cycle_bounds(today, cycle_day)
    return (next_start - start).days
