"""Pytest configuration and shared fixtures."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

from car_dealer_chatbot.config import load_env
from car_dealer_chatbot.data import load_cars, load_dealers
from car_dealer_chatbot.llm.base import LLMClient, LLMError
from car_dealer_chatbot.models import Car, Dealer, Intent
from car_dealer_chatbot.storage import ConversationStore

load_env()


@pytest.fixture
def store() -> ConversationStore:
    """A fresh, empty conversation store for one test."""
    return ConversationStore()


DATA_DIR = Path(__file__).parent.parent / "data"

_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
_DATETIME_WORDS = {"today", "tomorrow", "yesterday", "monday", "friday", "pm", "am"}
_PRICE = re.compile(r"(above|over|more than|under|below|less than|up to)\s*€?\s*([\d,]+)\s*(k?)")
_BETWEEN = re.compile(r"between\s*€?\s*([\d,]+)\s*(k?)\s*and\s*€?\s*([\d,]+)\s*(k?)")
_CITY = re.compile(r"\bin ([a-z]+)")
_NAME = re.compile(r"\b(?:my name is|call me)\s+([a-z]+)")
_RECALL = re.compile(r"^what(?: is|'s) my ([a-z_]+)$")
_FILLER = {
    "i", "i'm", "im", "want", "a", "an", "the", "show", "me", "looking", "for", "do", "you",
    "have", "any", "some", "cars", "car", "only", "actually", "instead", "can", "please",
    "what", "other", "another", "else", "now", "available", "are", "is", "of", "to", "see",
    "find", "search", "forget", "that", "changed", "my", "mind", "something", "cheaper",
    "more", "expensive", "suv", "suvs", "then", "would", "like", "interested", "in",
}  # fmt: skip


def _amount(number: str, k: str) -> int:
    return int(number.replace(",", "")) * (1000 if k else 1)


class FakeLLMClient(LLMClient):
    """Keyword-based stand-in for the OpenAI client (no network calls)."""

    def interpret_message(self, user_text: str, context: str) -> Intent:
        """A rough keyword interpretation, good enough to drive the chatbot in tests."""
        text = user_text.lower().strip(" ?.!")
        if text.isdigit() or text in ("whenever", "???", ""):
            return Intent("unclear")

        # Facts (e.g. "my name is X" / "call me X") are extracted independently of the rest
        # of the message: a personal statement never blanks out or replaces the request, and
        # a request never swallows a personal statement made alongside it.
        original_words = set(re.findall(r"[a-z0-9']+", text))
        facts: tuple[tuple[str, str], ...] = ()
        name = _NAME.search(text)
        if name:
            facts = (("name", name.group(1).capitalize()),)
            text = (text[: name.start()] + " " + text[name.end() :]).strip(" ,.!")

        words = set(re.findall(r"[a-z0-9']+", text))
        if name and not (words - _FILLER - {"hi", "hello", "hey"}):
            # Nothing is left once the name clause is removed: a pure personal statement.
            greeting = "greeting" if original_words & {"hi", "hello", "hey"} else "acknowledgement"
            return Intent(greeting, facts=facts)

        # "what is my X?" is answered only from the conversation context the chatbot passed in.
        recall = _RECALL.match(text)
        if recall:
            fact = re.search(rf"^  {recall.group(1)}: (.+)$", context, re.MULTILINE)
            answer = f"Your {recall.group(1)} is {fact.group(1)}." if fact else ""
            return Intent("recall", answer=answer, facts=facts)

        # "tell me the options" / "what are my options" etc.: re-show the last search, like
        # "show me some options" - not an unclear message just because it names no car.
        if words & {"option", "options"}:
            return Intent("search", refine=True, facts=facts)

        positions = tuple(n for word, n in _ORDINALS.items() if word in words)
        mentions_datetime = bool(words & _DATETIME_WORDS)
        cheapest = "cheaper one" in text or "cheapest one" in text
        reference = (
            "cheapest" if cheapest else ("current" if words & {"it", "their", "theirs"} else "")
        )

        if "compare" in words:
            return Intent("compare", positions=positions, facts=facts)
        if words & {"schedule", "call"}:
            return Intent("schedule_call", mentions_datetime=mentions_datetime, facts=facts)
        if mentions_datetime:
            return Intent("provide_datetime", mentions_datetime=True, facts=facts)
        if "dealer" in words and ("sell" in words or "cars" in words):
            return Intent(
                "dealer_inventory", exclude_current=bool(words & {"other", "else"}), facts=facts
            )
        if words & {"dealer", "sells", "sold", "located", "where", "who", "contact", "their"}:
            return Intent("dealer_details", positions=positions, reference=reference, facts=facts)
        if (
            "tell me" in text
            or "price of" in text
            or "more about" in text
            or "how much" in text
            or cheapest
        ):
            return Intent("car_details", positions=positions, reference=reference, facts=facts)
        if positions:
            return Intent("select_car", positions=positions, facts=facts)

        min_price = max_price = None
        between = _BETWEEN.search(text)
        if between:
            min_price = _amount(between.group(1), between.group(2))
            max_price = _amount(between.group(3), between.group(4))
            text = text.replace(between.group(0), " ")
        for match in _PRICE.finditer(text):
            amount = _amount(match.group(2), match.group(3))
            if match.group(1) in ("above", "over", "more than"):
                min_price = amount
            else:
                max_price = amount
        text = _PRICE.sub(" ", text)
        city = ""
        city_match = _CITY.search(text)
        if city_match:
            city = city_match.group(1)
            text = text.replace(city_match.group(0), " ")
        tokens = (w.strip(".") for w in re.findall(r"[a-z0-9.'-]+", text))
        query = " ".join(w for w in tokens if w and w not in _FILLER)
        body_type = "SUV" if words & {"suv", "suvs"} else ""
        relative = "cheaper" if "cheaper" in words else ""
        exclude = bool(words & {"other", "another", "else"})

        criteria = (query, min_price, max_price, city, body_type, relative)
        if not any(criteria) and not words & {"cars", "car", "other", "else"}:
            return Intent("unclear", facts=facts)
        return Intent(
            "search",
            car_query=query,
            min_price=min_price,
            max_price=max_price,
            body_type=body_type,
            city=city,
            relative_price=relative,
            refine=bool(words & {"only", "then"}) or bool(relative),
            exclude_current=exclude,
            facts=facts,
        )

    def parse_datetime(
        self, user_text: str, reference_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Understand only 'tomorrow', 'friday' (both at 15:00) and 'yesterday'."""
        reference_date = reference_date or datetime.now()
        text = user_text.lower()
        at_three = reference_date.replace(hour=15, minute=0, second=0, microsecond=0)
        if "tomorrow" in text:
            return at_three + timedelta(days=1)
        if "friday" in text:
            return at_three + timedelta(days=(4 - reference_date.weekday() - 1) % 7 + 1)
        if "yesterday" in text:
            return reference_date - timedelta(days=1)
        return None


class FailingLLMClient(FakeLLMClient):
    """LLM client whose every call fails, simulating an outage or bad API key."""

    def interpret_message(self, user_text: str, context: str) -> Intent:
        raise LLMError("service unavailable")

    def parse_datetime(
        self, user_text: str, reference_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        raise LLMError("service unavailable")


@pytest.fixture
def sample_cars() -> list[Car]:
    """Create sample cars for testing."""
    return [
        Car(
            car_id="C001",
            make="Toyota",
            model="Corolla",
            variant="1.8 Hybrid",
            year=2023,
            price=28500,
            dealer_id="D001",
        ),
        Car(
            car_id="C002",
            make="Toyota",
            model="Corolla",
            variant="1.6 Petrol",
            year=2023,
            price=24900,
            dealer_id="D001",
        ),
        Car(
            car_id="C003",
            make="BMW",
            model="3 Series",
            variant="320i",
            year=2023,
            price=52000,
            dealer_id="D002",
        ),
        Car(
            car_id="C004",
            make="Volkswagen",
            model="Golf",
            variant="1.5 TSI",
            year=2023,
            price=35200,
            dealer_id="D003",
        ),
    ]


@pytest.fixture
def sample_dealers() -> list[Dealer]:
    """Create sample dealers for testing."""
    return [
        Dealer(
            dealer_id="D001",
            name="Utrecht Auto Centre",
            city="Utrecht",
            phone="+31 30 123 4567",
            email="contact@utrechtauto.nl",
        ),
        Dealer(
            dealer_id="D002",
            name="Amsterdam Motors",
            city="Amsterdam",
            phone="+31 20 234 5678",
            email="info@amsterdammotors.nl",
        ),
        Dealer(
            dealer_id="D003",
            name="Rotterdam Car Hub",
            city="Rotterdam",
            phone="+31 10 345 6789",
            email="sales@rotcarhub.nl",
        ),
    ]


@pytest.fixture
def sample_csv_files(tmp_path: Path) -> tuple[Path, Path]:
    """Create sample CSV files in a temporary directory."""
    cars_csv = tmp_path / "cars.csv"
    cars_csv.write_text(
        "car_id,make,model,variant,year,price,dealer_id\n"
        "C001,Toyota,Corolla,1.8 Hybrid,2023,28500,D001\n"
        "C002,BMW,3 Series,320i,2023,52000,D002\n"
    )

    dealers_csv = tmp_path / "dealers.csv"
    dealers_csv.write_text(
        "dealer_id,name,city,phone,email\n"
        "D001,Utrecht Auto Centre,Utrecht,+31 30 123 4567,contact@utrechtauto.nl\n"
        "D002,Amsterdam Motors,Amsterdam,+31 20 234 5678,info@amsterdammotors.nl\n"
    )

    return cars_csv, dealers_csv


@pytest.fixture
def inventory() -> tuple[list[Car], list[Dealer]]:
    """The real inventory shipped in data/."""
    return load_cars(DATA_DIR / "cars.csv"), load_dealers(DATA_DIR / "dealers.csv")
