"""Tests for deterministic conversation titles."""

import pytest

from car_dealer_chatbot.chatbot import Chatbot
from car_dealer_chatbot.models import Car, Dealer
from car_dealer_chatbot.services.titles import DEFAULT_TITLE, generate_title, title_from_text

from .conftest import FakeLLMClient


@pytest.fixture
def chatbot(sample_cars: list[Car], sample_dealers: list[Dealer]) -> Chatbot:
    return Chatbot(sample_cars, sample_dealers, FakeLLMClient(), end_on_exit=False)


def turn(chatbot: Chatbot, text: str, title: str) -> str:
    """Process one message and return the resulting title."""
    chatbot.process_input(text)
    return generate_title(chatbot, text, title)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Do you have a Tesla Model 3?", "Tesla Model 3"),
        ("i'm looking for a honda civic please", "Honda Civic"),
        ("BMW 330i xDrive", "BMW 330i xDrive"),
        ("hi there!", None),
    ],
)
def test_title_from_text(text: str, expected: str) -> None:
    assert title_from_text(text) == expected


def test_title_for_unique_match(chatbot: Chatbot) -> None:
    assert turn(chatbot, "I want a BMW 3 Series", DEFAULT_TITLE) == "BMW 3 Series Inquiry"


def test_title_for_ambiguous_match_uses_shared_model(chatbot: Chatbot) -> None:
    assert turn(chatbot, "I want a Toyota Corolla", DEFAULT_TITLE) == "Toyota Corolla Inquiry"


def test_greeting_only_keeps_default_title(chatbot: Chatbot) -> None:
    assert turn(chatbot, "hello", DEFAULT_TITLE) == DEFAULT_TITLE


def test_title_follows_actions(chatbot: Chatbot) -> None:
    title = turn(chatbot, "I want a BMW 3 Series", DEFAULT_TITLE)
    title = turn(chatbot, "1", title)
    assert title == "BMW 3 Series Dealer"
    title = turn(chatbot, "2", title)
    assert title == "BMW 3 Series Dealer"  # still choosing a time
    title = turn(chatbot, "tomorrow", title)
    assert title == "Schedule BMW 3 Series Call"
    # Seeing the details again doesn't downgrade the scheduled call.
    assert turn(chatbot, "1", title) == "Schedule BMW 3 Series Call"


def test_title_follows_a_new_car(chatbot: Chatbot) -> None:
    title = turn(chatbot, "I want a BMW 3 Series", DEFAULT_TITLE)
    title = turn(chatbot, "1", title)
    assert turn(chatbot, "Volkswagen Golf", title) == "Volkswagen Golf Inquiry"


def test_exit_keeps_title(chatbot: Chatbot) -> None:
    title = turn(chatbot, "I want a BMW 3 Series", DEFAULT_TITLE)
    assert turn(chatbot, "exit", title) == "BMW 3 Series Inquiry"
