"""Deterministic resolution of a requested call slot into a concrete datetime.

The LLM only extracts the pieces the user mentioned (a weekday, "tomorrow",
a time...). Turning those into a calendar date is done here, because models
are unreliable at weekday arithmetic.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_CALL_TIME = time(10, 0)


@dataclass(frozen=True)
class SlotParts:
    """Date/time components mentioned by the user; None means not mentioned."""

    explicit_date: Optional[date] = None
    days_from_today: Optional[int] = None
    weekday: Optional[str] = None
    time_of_day: Optional[time] = None

    def is_empty(self) -> bool:
        """True when the user mentioned no date or time at all."""
        return (
            self.explicit_date is None
            and self.days_from_today is None
            and self.weekday is None
            and self.time_of_day is None
        )


def slot_parts_from_dict(raw: dict[str, Any]) -> SlotParts:
    """Build SlotParts from the LLM's tool arguments, discarding malformed values."""
    explicit_date: Optional[date] = None
    try:
        if raw.get("explicit_date"):
            explicit_date = date.fromisoformat(str(raw["explicit_date"]).strip())
    except ValueError:
        pass

    days_from_today: Optional[int] = None
    try:
        days = int(raw.get("days_from_today", -1))
        if 0 <= days <= 365:
            days_from_today = days
    except (TypeError, ValueError):
        pass

    weekday = str(raw.get("weekday") or "").strip().lower()

    time_of_day: Optional[time] = None
    try:
        if raw.get("time"):
            time_of_day = time.fromisoformat(str(raw["time"]).strip())
    except ValueError:
        pass

    return SlotParts(
        explicit_date=explicit_date,
        days_from_today=days_from_today,
        weekday=weekday if weekday in WEEKDAYS else None,
        time_of_day=time_of_day,
    )


def resolve_slot(parts: SlotParts, now: datetime) -> Optional[datetime]:
    """
    Turn extracted slot parts into a datetime relative to `now`.

    Precedence: explicit date > days from today > weekday > time only.
    A bare weekday means its next occurrence (today only if the time is still ahead).
    Returns None if nothing usable was mentioned.
    """
    if parts.is_empty():
        return None

    slot_time = parts.time_of_day or DEFAULT_CALL_TIME

    if parts.explicit_date is not None:
        day = parts.explicit_date
    elif parts.days_from_today is not None:
        day = now.date() + timedelta(days=parts.days_from_today)
    elif parts.weekday is not None:
        target = WEEKDAYS.index(parts.weekday)
        delta = (target - now.weekday()) % 7
        if delta == 0 and slot_time <= now.time():
            delta = 7
        day = now.date() + timedelta(days=delta)
    else:
        day = now.date() if slot_time > now.time() else now.date() + timedelta(days=1)

    return datetime.combine(day, slot_time)
