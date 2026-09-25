"""Tests for the UI display helpers."""

from datetime import datetime, timezone

import pytest

from car_dealer_chatbot.ui.formatting import (
    escape_markdown,
    format_timestamp,
    history_group,
    text_to_markdown,
    to_markdown,
)

NOW = datetime(2026, 9, 25, 15, 0).astimezone()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def test_escape_markdown_neutralises_formatting() -> None:
    assert escape_markdown("*bold* [link](x) $5") == r"\*bold\* \[link\]\(x\) \$5"


def test_dealer_details_become_bold_labels() -> None:
    text = "Here are the dealer's details:\n\n  Dealer: Utrecht Auto\n  Phone:  +31 30 123"
    assert to_markdown(text) == (
        "Here are the dealer's details:\n\n**Dealer:** Utrecht Auto  \n**Phone:** \\+31 30 123"
    )


def test_two_word_labels_become_bold() -> None:
    text = "In stock:\n  Body types: SUV, Sedan\n  Dealer cities: Utrecht"
    assert to_markdown(text) == (
        "In stock:  \n**Body types:** SUV, Sedan  \n**Dealer cities:** Utrecht"
    )


def test_numbered_options_keep_their_numbers() -> None:
    text = "Would you like to:\n  (1) See details\n  (2) Schedule a call"
    assert to_markdown(text) == (
        "Would you like to:  \n**(1)** See details  \n**(2)** Schedule a call"
    )


def test_user_text_keeps_line_breaks() -> None:
    assert text_to_markdown("line one\n*line two*") == "line one  \n\\*line two\\*"


@pytest.mark.parametrize(
    "moment,expected",
    [
        (datetime(2026, 9, 25, 9, 5), "Today, 09:05"),
        (datetime(2026, 9, 24, 18, 30), "Yesterday, 18:30"),
        (datetime(2026, 9, 1, 12, 0), "Sep 1, 12:00"),
        (datetime(2025, 12, 31, 8, 0), "Dec 31 2025, 08:00"),
    ],
)
def test_format_timestamp(moment: datetime, expected: str) -> None:
    assert format_timestamp(_iso(moment.astimezone()), now=NOW) == expected


@pytest.mark.parametrize(
    "moment,expected",
    [
        (datetime(2026, 9, 25, 1, 0), "Today"),
        (datetime(2026, 9, 24, 1, 0), "Yesterday"),
        (datetime(2026, 9, 20, 1, 0), "Previous 7 days"),
        (datetime(2026, 9, 1, 1, 0), "Previous 30 days"),
        (datetime(2026, 1, 1, 1, 0), "Older"),
    ],
)
def test_history_group(moment: datetime, expected: str) -> None:
    assert history_group(_iso(moment.astimezone()), now=NOW) == expected
