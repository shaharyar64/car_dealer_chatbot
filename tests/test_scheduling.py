"""Tests for deterministic call-slot resolution."""

from datetime import date, datetime, time

import pytest

from car_dealer_chatbot.models import SlotParts, resolve_slot, slot_parts_from_dict

# Friday 25 September 2026, 19:20
NOW = datetime(2026, 9, 25, 19, 20)


@pytest.mark.parametrize(
    "parts, expected",
    [
        # Same weekday, time already passed -> next week
        (SlotParts(weekday="friday", time_of_day=time(15)), datetime(2026, 10, 2, 15, 0)),
        # Same weekday, time still ahead -> today
        (SlotParts(weekday="friday", time_of_day=time(21)), datetime(2026, 9, 25, 21, 0)),
        # Upcoming weekday
        (SlotParts(weekday="monday", time_of_day=time(9, 30)), datetime(2026, 9, 28, 9, 30)),
        # Tomorrow, default time
        (SlotParts(days_from_today=1), datetime(2026, 9, 26, 10, 0)),
        # Explicit calendar date wins over everything else
        (
            SlotParts(explicit_date=date(2026, 12, 20), weekday="monday", time_of_day=time(14)),
            datetime(2026, 12, 20, 14, 0),
        ),
        # Time only, already passed today -> tomorrow
        (SlotParts(time_of_day=time(9)), datetime(2026, 9, 26, 9, 0)),
        # Time only, still ahead today -> today
        (SlotParts(time_of_day=time(20)), datetime(2026, 9, 25, 20, 0)),
    ],
)
def test_resolve_slot(parts: SlotParts, expected: datetime) -> None:
    assert resolve_slot(parts, NOW) == expected


def test_resolve_slot_nothing_mentioned() -> None:
    assert resolve_slot(SlotParts(), NOW) is None


def test_slot_parts_from_llm_arguments() -> None:
    parts = slot_parts_from_dict(
        {"explicit_date": "", "days_from_today": -1, "weekday": "Friday", "time": "15:00"}
    )
    assert parts == SlotParts(weekday="friday", time_of_day=time(15))


def test_slot_parts_discard_malformed_values() -> None:
    parts = slot_parts_from_dict(
        {"explicit_date": "20/12", "days_from_today": "soon", "weekday": "funday", "time": "3pm"}
    )
    assert parts.is_empty()
