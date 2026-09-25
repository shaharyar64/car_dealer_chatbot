"""What a user message asks for, as interpreted in the context of the conversation."""

from dataclasses import dataclass
from typing import Any, Optional

INTENT_NAMES = (
    "greeting",
    "thanks",
    "acknowledgement",
    "goodbye",
    "search",
    "select_car",
    "car_details",
    "dealer_details",
    "dealer_inventory",
    "compare",
    "schedule_call",
    "provide_datetime",
    "recall",
    "general_question",
    "unclear",
)
REFERENCES = ("", "current", "cheapest", "most_expensive")
RELATIVE_PRICES = ("", "cheaper", "more_expensive")
SORTS = ("", "price_asc", "price_desc")


@dataclass(frozen=True)
class Intent:
    """
    The user's current request plus the car/filter details it mentions.

    Everything except `name` is optional; the chatbot resolves references such as
    "the second one" (`positions`) or "that car" (`reference`) against the conversation.
    `facts` are (key, value) pairs the user stated about themselves or what they want
    (an empty value means "forget it"); `answer` is the reply to a `recall` question.
    """

    name: str
    car_query: str = ""
    car_queries: tuple[str, ...] = ()
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    body_type: str = ""
    city: str = ""
    positions: tuple[int, ...] = ()
    reference: str = ""
    relative_price: str = ""
    sort: str = ""
    refine: bool = False
    exclude_current: bool = False
    mentions_datetime: bool = False
    facts: tuple[tuple[str, str], ...] = ()
    answer: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intent":
        """Build an Intent from loosely-typed LLM output, dropping anything invalid."""

        def text(key: str) -> str:
            return str(data.get(key) or "").strip()

        def choice(key: str, allowed: tuple[str, ...]) -> str:
            value = text(key).lower()
            return value if value in allowed else ""

        def price(key: str) -> Optional[int]:
            try:
                value = int(float(data.get(key) or 0))
            except (TypeError, ValueError):
                return None
            return value if value > 0 else None

        def items(key: str) -> list[Any]:
            value = data.get(key)
            return value if isinstance(value, list) else []

        name = text("intent").lower()
        positions = []
        for item in items("positions"):
            try:
                position = int(item)
            except (TypeError, ValueError):
                continue
            if position > 0:
                positions.append(position)

        facts = []
        for item in items("facts"):
            if not isinstance(item, dict):
                continue
            key = "_".join(str(item.get("key") or "").lower().split())
            if key:
                facts.append((key, str(item.get("value") or "").strip()))

        return cls(
            name=name if name in INTENT_NAMES else "unclear",
            car_query=text("car_query"),
            car_queries=tuple(str(q).strip() for q in items("car_queries") if str(q).strip()),
            min_price=price("min_price"),
            max_price=price("max_price"),
            body_type=text("body_type"),
            city=text("city"),
            positions=tuple(positions),
            reference=choice("reference", REFERENCES),
            relative_price=choice("relative_price", RELATIVE_PRICES),
            sort=choice("sort", SORTS),
            refine=data.get("refine") is True,
            exclude_current=data.get("exclude_current") is True,
            mentions_datetime=data.get("mentions_datetime") is True,
            facts=tuple(facts),
            answer=text("answer"),
        )
