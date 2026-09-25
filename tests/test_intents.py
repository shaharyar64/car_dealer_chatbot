"""Tests for turning loosely-typed LLM output into an Intent."""

from car_dealer_chatbot.intents import Intent


def test_full_intent_is_parsed() -> None:
    intent = Intent.from_dict(
        {
            "intent": "search",
            "car_query": " BMW ",
            "car_queries": [],
            "min_price": 50000,
            "max_price": 0,
            "body_type": "SUV",
            "city": "Munich",
            "positions": [],
            "reference": "",
            "relative_price": "",
            "sort": "price_asc",
            "refine": True,
            "exclude_current": False,
            "mentions_datetime": False,
        }
    )
    assert intent == Intent(
        "search",
        car_query="BMW",
        min_price=50000,
        body_type="SUV",
        city="Munich",
        sort="price_asc",
        refine=True,
    )


def test_invalid_values_are_dropped() -> None:
    intent = Intent.from_dict(
        {
            "intent": "order_pizza",
            "min_price": "lots",
            "max_price": -5,
            "positions": [2, "3", "x", 0],
            "reference": "the red one",
            "refine": "false",
            "car_queries": "not a list",
        }
    )
    assert intent.name == "unclear"
    assert intent.min_price is None and intent.max_price is None
    assert intent.positions == (2, 3)
    assert intent.reference == "" and intent.refine is False and intent.car_queries == ()


def test_facts_and_answer_are_parsed() -> None:
    intent = Intent.from_dict(
        {
            "intent": "recall",
            "facts": [
                {"key": "Name", "value": " Shaharyar "},
                {"key": "fuel type", "value": ""},
                {"key": "", "value": "dropped"},
                "not a fact",
            ],
            "answer": " Your name is Shaharyar. ",
        }
    )
    assert intent.name == "recall"
    assert intent.facts == (("name", "Shaharyar"), ("fuel_type", ""))
    assert intent.answer == "Your name is Shaharyar."


def test_empty_output_is_unclear() -> None:
    assert Intent.from_dict({}) == Intent("unclear")
