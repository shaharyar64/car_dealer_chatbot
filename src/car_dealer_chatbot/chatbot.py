"""Conversational chatbot for finding cars and connecting users with dealers.

Each message is interpreted on its own merits, with the conversation as context, instead
of as the answer to the bot's previous question. The user can change their mind, ask a
follow-up question or start a new search at any point, and the conversation never ends
by itself.

The chatbot keeps two kinds of state:

- Conversation context (kept until something replaces it): the cars last listed
  (`candidates`, numbered from 1), the car being discussed (`current_car`), the active
  search filters, what the user has told us about themselves and what they want (`facts`,
  e.g. name, city, budget; the latest value wins) and the recent message history.
- The current task (only a hint): the numbered options the last reply offered
  (`offered`), whether the bot just asked for a call time (`awaiting_datetime`) and an
  action waiting for the user to say which car they mean (`pending_action`). Any other
  request simply takes over.
"""

import logging
import re
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime
from difflib import SequenceMatcher
from itertools import zip_longest
from typing import Any, Callable, Optional

from .intents import Intent
from .llm import LLMClient, LLMError
from .logging_config import LOGGER_NAME
from .models import Car, Dealer
from .repository import find_dealer, list_makes, search_cars

logger = logging.getLogger(LOGGER_NAME)

EXIT_COMMANDS = {"exit", "quit", "bye", "goodbye"}
MAX_CANDIDATES_SHOWN = 5
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 400
MAX_FACTS = 30
MAX_FACT_CHARS = 200
MENU_OPTIONS = "  (1) See the dealer's details\n  (2) Schedule a call with the dealer"
FOLLOW_UP = (
    "Is there anything else I can help with?\n" f"{MENU_OPTIONS}\n" "Or ask me about any other car."
)
LLM_UNAVAILABLE_MESSAGE = (
    "Sorry, I'm having trouble reaching the language service right now. "
    "Please try again in a moment."
)
DATETIME_EXAMPLES = "(e.g. 'Friday at 3pm', 'tomorrow at 10am')"

# What the numbers in the last reply referred to, so a bare "2" can be resolved.
OPTIONS_CARS = "cars"
OPTIONS_ACTIONS = "actions"
# Actions that can wait for the user to say which car they mean.
CAR_ACTIONS = ("select_car", "car_details", "dealer_details", "dealer_inventory", "schedule_call")

# Short messages that need no language model to understand.
_SMALL_TALK = {
    "greeting": {
        "hi", "hello", "hey", "hiya", "hi there", "hello there", "hey there", "greetings",
        "good morning", "good afternoon", "good evening", "morning", "evening",
    },
    "thanks": {
        "thanks", "thank you", "thanks a lot", "thank you so much", "thanks so much",
        "many thanks", "thx", "ty", "cheers",
    },
    "acknowledgement": {
        "ok", "okay", "k", "great", "sounds good", "cool", "perfect", "nice", "alright",
        "all right", "got it", "awesome", "fine", "good", "sure",
    },
    "goodbye": {
        "bye", "goodbye", "bye bye", "see you", "see ya", "exit", "quit", "that's all",
        "thats all",
    },
}  # fmt: skip
_BODY_TYPE_SYNONYMS = {
    "saloon": "sedan",
    "hatch": "hatchback",
    "wagon": "estate",
    "station wagon": "estate",
    "estate car": "estate",
    "crossover": "suv",
    "4x4": "suv",
    "coupé": "coupe",
    "cabrio": "convertible",
    "cabriolet": "convertible",
    "roadster": "convertible",
}


@dataclass(frozen=True)
class SearchFilters:
    """The criteria of the most recent car search."""

    car_query: str = ""
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    body_type: str = ""
    city: str = ""

    def is_empty(self) -> bool:
        return self == SearchFilters()


def _normalize(text: str) -> str:
    """Lowercase words only, for matching short conversational messages."""
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def _small_talk(text: str) -> Optional[str]:
    """The small-talk intent of a message consisting only of a pleasantry, if any."""
    normalized = _normalize(text)
    for intent, phrases in _SMALL_TALK.items():
        if normalized in phrases:
            return intent
    return None


def _euros(amount: int) -> str:
    return f"€{amount:,}"


def _query_parts(car_query: str) -> list[str]:
    """A search can name several cars: 'Audi, Dacia, Skoda' -> ['Audi', 'Dacia', 'Skoda']."""
    return [part.strip() for part in car_query.split(",") if part.strip()]


def _join_words(words: list[str]) -> str:
    """['Audi', 'Dacia', 'Skoda'] -> 'Audi, Dacia and Skoda'."""
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def _similar(a: str, b: str) -> bool:
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.8


class Chatbot:
    """Chatbot for finding cars and connecting users with dealers."""

    def __init__(
        self,
        cars: list[Car],
        dealers: list[Dealer],
        llm_client: LLMClient,
        end_on_exit: bool = True,
    ):
        """
        Initialize the chatbot with inventory data and an LLM client.

        With end_on_exit=True (CLI) "exit"/"quit"/"bye" ends the session; with
        end_on_exit=False (web app) nothing ever ends a conversation.
        """
        self.cars = cars
        self.dealers = dealers
        self.llm_client = llm_client
        self.end_on_exit = end_on_exit
        self.body_types = sorted({car.body_type for car in cars if car.body_type})
        self.cities = sorted({dealer.city for dealer in dealers})
        self.reset()

    def reset(self) -> None:
        """Start a fresh conversation."""
        # Conversation context.
        self.candidates: list[Car] = []
        self.current_car: Optional[Car] = None
        self.current_dealer: Optional[Dealer] = None
        self.filters = SearchFilters()
        self.scheduled_datetime: Optional[datetime] = None
        self.history: list[tuple[str, str]] = []
        self.facts: dict[str, str] = {}
        # Current task.
        self.offered: Optional[str] = None
        self.list_open = False  # whether this turn follows a numbered car list
        self.awaiting_datetime = False
        self.pending_action: Optional[str] = None
        # What the last processed message was and achieved (for titles and logging).
        self.last_intent: Optional[str] = None
        self.last_action: Optional[str] = None

    def get_greeting(self) -> str:
        """Return the opening message."""
        return (
            "Hi! Which car are you looking for? You can ask by make or model, "
            "budget, body type or city."
        )

    # ------------------------------------------------------------------ persistence

    def export_state(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the conversation (car ids, not objects)."""
        return {
            "version": 2,
            "car_id": self.current_car.car_id if self.current_car else None,
            "candidate_ids": [car.car_id for car in self.candidates],
            "filters": asdict(self.filters),
            "scheduled_datetime": (
                self.scheduled_datetime.isoformat() if self.scheduled_datetime else None
            ),
            "history": [list(message) for message in self.history],
            "facts": dict(self.facts),
            "offered": self.offered,
            "awaiting_datetime": self.awaiting_datetime,
            "pending_action": self.pending_action,
        }

    def restore_state(self, snapshot: dict[str, Any]) -> None:
        """
        Restore a snapshot produced by export_state.

        Cars are looked up again by id; anything that no longer exists is dropped.
        """
        self.reset()
        cars_by_id = {car.car_id: car for car in self.cars}
        self.candidates = [
            cars_by_id[car_id]
            for car_id in snapshot.get("candidate_ids") or []
            if car_id in cars_by_id
        ]

        car_id = snapshot.get("car_id")
        if car_id:
            car = cars_by_id.get(car_id)
            dealer = find_dealer(car.dealer_id, self.dealers) if car else None
            if car is None or dealer is None:
                logger.warning(f"Snapshot references unavailable car/dealer {car_id!r}")
            else:
                self.current_car, self.current_dealer = car, dealer

        filters = snapshot.get("filters")
        if isinstance(filters, dict):
            known = {f.name for f in fields(SearchFilters)}
            try:
                self.filters = SearchFilters(**{k: v for k, v in filters.items() if k in known})
            except TypeError:
                pass

        if snapshot.get("scheduled_datetime"):
            try:
                self.scheduled_datetime = datetime.fromisoformat(snapshot["scheduled_datetime"])
            except ValueError:
                pass

        for message in snapshot.get("history") or []:
            if (
                isinstance(message, (list, tuple))
                and len(message) == 2
                and all(isinstance(part, str) for part in message)
            ):
                self.history.append((message[0], message[1]))

        facts = snapshot.get("facts")
        if isinstance(facts, dict):
            self._learn(facts.items())

        offered = snapshot.get("offered")
        self.offered = offered if offered in (OPTIONS_CARS, OPTIONS_ACTIONS) else None
        self.awaiting_datetime = bool(snapshot.get("awaiting_datetime"))
        pending = snapshot.get("pending_action")
        self.pending_action = pending if pending in CAR_ACTIONS else None

        if self.current_car is None:
            self.awaiting_datetime = False
            if self.offered == OPTIONS_ACTIONS:
                self.offered = None
        if self.offered == OPTIONS_CARS and not self.candidates:
            self.offered = None

    # ------------------------------------------------------------------ turn handling

    def process_input(self, user_input: str) -> tuple[str, bool]:
        """
        Process one user message.

        Returns a (reply, is_done) tuple; is_done is only True when the CLI user exits.
        """
        user_input = user_input.strip()
        self.last_action = None
        self.last_intent = None

        if not user_input:
            return "Please type a message so I can help you.", False
        if self.end_on_exit and user_input.lower() in EXIT_COMMANDS:
            return "Thank you for using Car Dealer Chatbot. Goodbye!", True

        try:
            reply = self._respond(user_input)
        except LLMError:
            return LLM_UNAVAILABLE_MESSAGE, False
        self._remember(user_input, reply)
        return reply, False

    def _respond(self, text: str) -> str:
        """Work out what the message asks for and do it."""
        previous_offered = self.offered
        self.list_open = previous_offered == OPTIONS_CARS and bool(self.candidates)
        pending = self.pending_action
        self.pending_action = None

        choice = self._numbered_choice(text, pending)
        if choice is not None:
            return choice

        small_talk = _small_talk(text)
        if small_talk:
            intent = Intent(small_talk)
        else:
            intent = self.llm_client.interpret_message(text, self._context(pending))
        self.last_intent = intent.name
        logger.info(f"Intent {intent.name!r} for {text!r}")
        self._learn(intent.facts)

        # Small talk and questions about the conversation leave it exactly where it was.
        if intent.name in _SMALL_TALK:
            self.pending_action = pending
            return self._small_talk_reply(intent.name, text, intent.facts)
        if intent.name == "recall":
            self.pending_action = pending
            return intent.answer or (
                "I don't think you've told me that yet. What would you like me to know?"
            )

        # Replies offer their own numbered options; by default none.
        self.offered = None
        if intent.name == "unclear" and self.awaiting_datetime:
            # Most likely an attempt at a date/time we asked for.
            return self._schedule(text)

        handlers: dict[str, Callable[[Intent, str, Optional[str]], str]] = {
            "search": self._handle_search,
            "select_car": self._handle_car_action,
            "car_details": self._handle_car_action,
            "dealer_details": self._handle_car_action,
            "dealer_inventory": self._handle_car_action,
            "schedule_call": self._handle_car_action,
            "compare": self._handle_compare,
            "provide_datetime": self._handle_datetime,
        }
        handler = handlers.get(intent.name)
        if handler is None:
            self.offered = previous_offered
            if intent.facts:  # the message only told us something about the user
                self.pending_action = pending
                return self._small_talk_reply("acknowledgement", text, intent.facts)
            return self._fallback_reply(intent.name)
        return handler(intent, text, pending)

    def _numbered_choice(self, text: str, pending: Optional[str]) -> Optional[str]:
        """Resolve a bare number against the options the last reply offered."""
        # isdecimal (not isdigit): digits like "²" pass isdigit but int() rejects them.
        if not text.isdecimal():
            return None
        number = int(text)
        if self.offered == OPTIONS_CARS and self.candidates:
            if 1 <= number <= len(self.candidates):
                self.last_intent = "select_car"
                self.offered = None
                return self._run_car_action(pending or "select_car", self.candidates[number - 1])
            self.pending_action = pending
            return (
                f"Please choose a number between 1 and {len(self.candidates)}, "
                "or describe the car differently."
            )
        if self.offered == OPTIONS_ACTIONS and self.current_car and number in (1, 2):
            self.last_intent = "dealer_details" if number == 1 else "schedule_call"
            self.offered = None
            if number == 1:
                return self._show_dealer_details()
            return self._ask_for_datetime()
        return None

    def _remember(self, user_text: str, reply: str) -> None:
        for role, message in (("user", user_text), ("assistant", reply)):
            if len(message) > MAX_HISTORY_CHARS:
                message = message[:MAX_HISTORY_CHARS] + "..."
            self.history.append((role, message))
        self.history = self.history[-MAX_HISTORY_MESSAGES:]

    def _learn(self, facts: Any) -> None:
        """Record (key, value) facts the user stated; newer values replace older ones."""
        for key, value in facts:
            if not isinstance(key, str) or not isinstance(value, str) or not key.strip():
                continue
            key = key.strip()[:MAX_FACT_CHARS]
            self.facts.pop(key, None)  # re-insert so the most recently stated facts come last
            if value.strip():
                self.facts[key] = value.strip()[:MAX_FACT_CHARS]
        while len(self.facts) > MAX_FACTS:
            self.facts.pop(next(iter(self.facts)))

    def _context(self, pending: Optional[str]) -> str:
        """A plain-text summary of the conversation for the language model."""
        lines = [
            f"Makes in stock: {', '.join(list_makes(self.cars))}.",
            f"Dealer cities: {', '.join(self.cities)}.",
        ]
        if self.body_types:
            lines.append(f"Body types in stock: {', '.join(self.body_types)}.")
        if self.facts:
            lines.append("What the customer has told you in this conversation (latest values):")
            lines += [f"  {key}: {value}" for key, value in self.facts.items()]
        if self.history:
            lines.append("Recent messages:")
            lines += [
                f"  {'Customer' if role == 'user' else 'Assistant'}: {message}"
                for role, message in self.history
            ]
        if self.candidates:
            lines.append("Numbered car list in the conversation:")
            lines += [
                f"  {i}. {self._describe_car(car)}"
                for i, car in enumerate(self.candidates, start=1)
            ]
        if self.current_car:
            lines.append(
                f"Car being discussed: {self._describe_car(self.current_car)}, sold by "
                f"{self.current_dealer.name} ({self.current_dealer.city})."
            )
        if not self.filters.is_empty():
            lines.append(f"Last search: {self._describe_filters(self.filters)}.")
        if self.awaiting_datetime and self.current_dealer:
            lines.append(
                "The assistant asked for a date and time for a call with "
                f"{self.current_dealer.name}."
            )
        if pending:
            lines.append(f"The assistant asked which car the customer means (for: {pending}).")
        if self.offered == OPTIONS_ACTIONS:
            lines.append("The assistant offered: (1) the dealer's details, (2) scheduling a call.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ conversation

    def _small_talk_reply(
        self, intent: str, text: str, facts: tuple[tuple[str, str], ...] = ()
    ) -> str:
        if intent == "greeting":
            normalized = _normalize(text)
            if normalized.startswith("good ") or normalized in ("morning", "evening"):
                return f"{text.strip(' !.').capitalize()}! How can I help you find a car today?"
            if self.current_car:
                return (
                    f"Hi again! Would you like to continue with the {self.current_car}, "
                    "or look at something else?"
                )
            name = self.facts.get("name")
            hello = f"Hi {name}!" if name else "Hi!"
            return f"{hello} How can I help you find a car today?"
        if intent == "thanks":
            return (
                "You're welcome! Let me know if you'd like to look at another car "
                "or contact a dealer."
            )
        if intent == "goodbye":
            return (
                "Goodbye, and thanks for chatting! Whenever you're ready, just come back "
                "and tell me which car you're interested in."
            )
        # Acknowledgement, possibly of something the user told us about themselves.
        name = dict(facts).get("name")
        great = "Great!"
        if facts:
            great = f"Got it, {name}!" if name else "Got it, I'll keep that in mind."
        if self.awaiting_datetime and self.current_dealer:
            return (
                f"{great} Just tell me what date and time suit you for the call with "
                f"{self.current_dealer.name} {DATETIME_EXAMPLES}."
            )
        if self.current_car:
            return (
                f"{great} Would you like the dealer's details, to schedule a call, "
                "or to look at other cars?"
            )
        return f"{great} What kind of car are you looking for?"

    def _fallback_reply(self, intent: str) -> str:
        if intent == "general_question":
            return (
                "I'm afraid I don't have information about that. I can help you find cars "
                "in our inventory, share dealer details and schedule a call with a dealer, "
                "who can answer any other questions."
            )
        about = f" about the {self.current_car}" if self.current_car else ""
        return (
            "Sorry, I'm not sure what you mean. You can ask me to find cars "
            "(e.g. 'BMWs under €60,000' or 'SUVs in Rotterdam'), tell you more about a car, "
            f"show a dealer's details or schedule a call{about}."
        )

    # ------------------------------------------------------------------ search

    def _handle_search(self, intent: Intent, text: str, pending: Optional[str]) -> str:
        filters = self._filters_for(intent)
        problem = self._check_filters(filters)
        if problem:
            return problem
        # 'Audi and Tesla': search what we carry and say what we don't.
        parts = _query_parts(filters.car_query)
        unknown = [part for part in parts if not search_cars(part, self.cars)]
        note = ""
        if unknown and len(unknown) < len(parts):
            known = [part for part in parts if part not in unknown]
            filters = replace(filters, car_query=", ".join(known))
            note = f"We don't carry {_join_words(unknown)} at the moment.\n\n"
        self.filters = filters

        if filters.is_empty() and not intent.sort:
            return self._inventory_overview(intent.exclude_current)

        pool = [car for car in self.cars if self._passes(car, filters)]
        matches = self._search(filters.car_query, pool) if filters.car_query else pool
        excluded = None
        if intent.exclude_current and self.current_car in matches:
            excluded = self.current_car
            matches = [car for car in matches if car != excluded]
        matches = self._sorted(matches, intent, filters)

        if not matches:
            return note + self._no_results(filters, excluded)
        if len(matches) == 1:
            return note + self._run_car_action(pending or "select_car", matches[0])
        if pending:
            self.pending_action = pending  # still waiting for the user to pick one car
        other = "other " if excluded else ""
        header = f"{note}I found {len(matches)} {other}{self._describe_filters(filters)}:"
        if filters.is_empty():  # e.g. 'what is your cheapest car?'
            order = "cheapest" if intent.sort == "price_asc" else "most expensive"
            header = f"Here are our {order} {other}cars:"
        return self._list_cars(
            matches,
            header,
            "Which one would you like to know more about? Reply with a number, or ask me to "
            "narrow it down (e.g. by price, body type or city).",
        )

    def _filters_for(self, intent: Intent) -> SearchFilters:
        """The search criteria of this message, merged with the last search if refining."""
        car_query, body_type = self._split_body_type(intent.car_query)
        new = SearchFilters(
            car_query=car_query,
            min_price=intent.min_price,
            max_price=intent.max_price,
            body_type=self._canonical_body_type(intent.body_type) or body_type,
            city=self._canonical_city(intent.city),
        )
        if intent.refine or intent.relative_price:
            base = self.filters
            new = SearchFilters(
                car_query=new.car_query or base.car_query,
                min_price=new.min_price if new.min_price is not None else base.min_price,
                max_price=new.max_price if new.max_price is not None else base.max_price,
                body_type=new.body_type or base.body_type,
                city=new.city or base.city,
            )
            if (
                new.min_price is not None
                and new.max_price is not None
                and new.min_price > new.max_price
            ):
                # The new bound contradicts an old one: the new one wins.
                if intent.min_price is not None:
                    new = replace(new, max_price=None)
                else:
                    new = replace(new, min_price=None)

        reference_price = self._reference_price()
        if intent.relative_price and reference_price:
            if intent.relative_price == "cheaper":
                new = replace(new, max_price=reference_price - 1)
                if new.min_price is not None and new.min_price >= reference_price:
                    new = replace(new, min_price=None)
            else:
                new = replace(new, min_price=reference_price + 1)
                if new.max_price is not None and new.max_price <= reference_price:
                    new = replace(new, max_price=None)
        return new

    def _reference_price(self) -> Optional[int]:
        """The price 'cheaper'/'more expensive' is relative to."""
        if self.current_car and not self.list_open:
            return self.current_car.price
        if self.candidates:
            return min(car.price for car in self.candidates)
        return self.current_car.price if self.current_car else None

    def _canonical_body_type(self, body_type: str) -> str:
        value = body_type.strip().lower()
        if not value:
            return ""
        value = _BODY_TYPE_SYNONYMS.get(value, value)
        for candidate in (value, value.rstrip("s"), _BODY_TYPE_SYNONYMS.get(value.rstrip("s"))):
            for known in self.body_types:
                if candidate and known.lower() == candidate:
                    return known
        return body_type.strip()

    def _split_body_type(self, car_query: str) -> tuple[str, str]:
        """Move body-type words out of a car query: 'BMW SUVs' -> ('BMW', 'SUV')."""
        queries, body_type = [], ""
        for part in _query_parts(car_query):
            kept = []
            for word in part.split():
                canonical = self._canonical_body_type(word)
                if canonical in self.body_types:
                    body_type = canonical
                else:
                    kept.append(word)
            if kept:
                queries.append(" ".join(kept))
        return ", ".join(queries), body_type

    def _canonical_city(self, city: str) -> str:
        value = city.strip().lower()
        if not value:
            return ""
        for known in self.cities:
            if _similar(value, known.lower()):
                return known
        return city.strip()

    def _check_filters(self, filters: SearchFilters) -> Optional[str]:
        """A clarification if the search asks for something the data can't answer."""
        if filters.body_type and filters.body_type not in self.body_types:
            if not self.body_types:
                return (
                    "I'm afraid I don't have body-type information for our cars. I can search "
                    "by make, model, price or dealer city instead. What would you like?"
                )
            return (
                f"We don't have any {filters.body_type} cars at the moment. The body types "
                f"in stock are: {', '.join(self.body_types)}. Would one of those work?"
            )
        if filters.city and filters.city not in self.cities:
            return (
                f"We don't have a dealer in {filters.city}. Our dealers are in: "
                f"{', '.join(self.cities)}. Would one of those work?"
            )
        return None

    def _passes(self, car: Car, filters: SearchFilters) -> bool:
        if filters.min_price is not None and car.price < filters.min_price:
            return False
        if filters.max_price is not None and car.price > filters.max_price:
            return False
        if filters.body_type and car.body_type != filters.body_type:
            return False
        if filters.city:
            dealer = find_dealer(car.dealer_id, self.dealers)
            if dealer is None or dealer.city != filters.city:
                return False
        return True

    @staticmethod
    def _sorted(cars: list[Car], intent: Intent, filters: SearchFilters) -> list[Car]:
        if intent.sort == "price_desc":
            return sorted(cars, key=lambda car: car.price, reverse=True)
        if (
            intent.sort == "price_asc"
            or intent.relative_price
            or filters.min_price is not None
            or filters.max_price is not None
        ):
            return sorted(cars, key=lambda car: car.price)
        return cars

    def _no_results(self, filters: SearchFilters, excluded: Optional[Car]) -> str:
        if filters.car_query and not self._search(filters.car_query, self.cars):
            makes = ", ".join(list_makes(self.cars))
            return (
                f"Sorry, I couldn't find '{filters.car_query}' in our inventory.\n"
                f"We currently carry: {makes}.\n"
                "Which car would you like instead?"
            )
        description = self._describe_filters(filters)
        if excluded:
            return (
                f"The {excluded} is the only one of our {description} at the moment. "
                "Would you like to look at something else?"
            )
        hint = "Would you like to try a different budget, make, body type or city?"
        if filters.car_query:
            same_query = self._search(filters.car_query, self.cars)
            low = min(car.price for car in same_query)
            high = max(car.price for car in same_query)
            price_range = (
                _euros(low) if low == high else f"between {_euros(low)} and {_euros(high)}"
            )
            hint = (
                f"Our {self._query_label(filters.car_query)} cars are priced {price_range}. "
                "Would you like to adjust your search?"
            )
        return f"Sorry, I couldn't find any {description}. {hint}"

    def _search(self, car_query: str, cars: list[Car]) -> list[Car]:
        """
        Cars matching any part of the query ('Audi, Dacia, Skoda').

        The parts take turns, so a shortened list still shows some of each.
        """
        found: list[Car] = []
        for group in zip_longest(*(search_cars(part, cars) for part in _query_parts(car_query))):
            found += [car for car in group if car is not None and car not in found]
        return found

    def _query_label(self, car_query: str) -> str:
        """How the inventory spells what the user searched for ('bmws' -> 'BMW')."""
        parts = _query_parts(car_query)
        if len(parts) > 1:
            return _join_words([self._query_label(part) for part in parts])
        matches = search_cars(car_query, self.cars)
        if not matches:
            return car_query
        if len({(car.make, car.model) for car in matches}) == 1 and len(matches) > 1:
            return f"{matches[0].make} {matches[0].model}"
        if len({car.make for car in matches}) == 1 and len(matches) > 1:
            return matches[0].make
        return car_query

    def _inventory_overview(self, exclude_current: bool) -> str:
        opening = (
            f"Besides the {self.current_car}, we" if exclude_current and self.current_car else "We"
        )
        makes = list_makes(self.cars)
        low = min(car.price for car in self.cars)
        high = max(car.price for car in self.cars)
        lines = [
            f"{opening} have {len(self.cars)} cars in stock from {len(makes)} makes, "
            f"priced from {_euros(low)} to {_euros(high)}.",
            "",
            f"  Makes: {', '.join(makes)}",
        ]
        if self.body_types:
            lines.append(f"  Body types: {', '.join(self.body_types)}")
        lines += [
            f"  Dealer cities: {', '.join(self.cities)}",
            "",
            "Tell me a make or model, a budget (e.g. 'under €30,000'), a body type or a city, "
            "and I'll find matching cars.",
        ]
        return "\n".join(lines)

    def _describe_filters(self, filters: SearchFilters) -> str:
        """E.g. 'BMW SUVs priced €50,000 or more from dealers in Munich'."""
        body = filters.body_type
        if body:
            body = body if body.isupper() else body.lower()
            body = f"{body}s"
        label = self._query_label(filters.car_query) if filters.car_query else ""
        if label and body:
            noun = f"{label} {body}"
        elif label:
            noun = f"{label} cars"
        else:
            noun = body or "cars"
        parts = [noun]
        if filters.min_price is not None and filters.max_price is not None:
            parts.append(
                f"priced between {_euros(filters.min_price)} and {_euros(filters.max_price)}"
            )
        elif filters.min_price is not None:
            parts.append(f"priced {_euros(filters.min_price)} or more")
        elif filters.max_price is not None:
            parts.append(f"priced up to {_euros(filters.max_price)}")
        if filters.city:
            parts.append(f"from dealers in {filters.city}")
        return " ".join(parts)

    # ------------------------------------------------------------------ one car

    def _handle_car_action(self, intent: Intent, text: str, pending: Optional[str]) -> str:
        """Select a car, show its details or dealer, list its dealer's cars, or book a call."""
        action = intent.name
        if action == "select_car" and pending:
            action = pending  # e.g. "the second one" after "which car do you mean?"
        car = self._resolve_car(intent, action)
        if car is None:
            return self._ask_which_car(intent, action)
        if action == "schedule_call" and intent.mentions_datetime:
            error = self._focus(car)
            return error or self._schedule(text)
        return self._run_car_action(action, car, exclude_current=intent.exclude_current)

    def _run_car_action(self, action: str, car: Car, exclude_current: bool = False) -> str:
        error = self._focus(car)
        if error:
            return error
        if action == "car_details":
            return self._show_car_details()
        if action == "dealer_details":
            return self._show_dealer_details()
        if action == "dealer_inventory":
            return self._show_dealer_inventory(exclude_current)
        if action == "schedule_call":
            return self._ask_for_datetime()
        return self._show_selected_car()

    def _resolve_car(self, intent: Intent, action: str) -> Optional[Car]:
        """The single car the message refers to, or None if it's unclear."""
        shown = self.candidates
        if intent.positions:
            position = intent.positions[0]
            return shown[position - 1] if 1 <= position <= len(shown) else None
        if intent.reference in ("cheapest", "most_expensive") and shown:
            pick = min if intent.reference == "cheapest" else max
            return pick(shown, key=lambda car: car.price)
        if intent.car_query:
            pools = [shown, [self.current_car] if self.current_car else [], self.cars]
            for pool in pools:
                matches = search_cars(intent.car_query, pool) if pool else []
                if len(matches) == 1:
                    return matches[0]
                if matches:
                    return None
            return None
        if self.list_open and len(shown) > 1:
            # "Who sells it?" right after a list of several cars is ambiguous...
            if intent.reference == "current" and self.current_car in shown:
                return self.current_car  # ...unless it clearly means the car being discussed.
            return None
        if self.current_car:
            return self.current_car
        if len(shown) == 1:
            return shown[0]
        return None

    def _ask_which_car(self, intent: Intent, action: str) -> str:
        """Ask the user to say which car they mean; the action runs once they do."""
        purpose = {
            "car_details": "Which car would you like to know more about?",
            "dealer_details": "Which car's dealer would you like to know about?",
            "dealer_inventory": "Which car's dealer do you mean?",
            "schedule_call": "Which car would you like to schedule a call about?",
        }.get(action, "Which car do you mean?")
        if action != "select_car":
            self.pending_action = action

        options: list[Car] = []
        if intent.car_query:
            options = search_cars(intent.car_query, self.candidates) or search_cars(
                intent.car_query, self.cars
            )
            if not options:
                makes = ", ".join(list_makes(self.cars))
                return (
                    f"Sorry, I couldn't find '{intent.car_query}' in our inventory.\n"
                    f"We currently carry: {makes}.\n"
                    "Which car would you like instead?"
                )
        elif intent.positions and self.candidates:
            return (
                f"I only listed {len(self.candidates)} cars. Please choose a number between "
                f"1 and {len(self.candidates)}, or tell me the make and model."
            )
        elif len(self.candidates) > 1:
            options = self.candidates

        if len(options) > 1:
            return self._list_cars(
                options, purpose, "Reply with a number, or describe the car more specifically."
            )
        return f"{purpose} Tell me the make and model (e.g. 'BMW 3 Series')."

    def _focus(self, car: Car) -> Optional[str]:
        """Make `car` the car being discussed; returns an error if its dealer is missing."""
        dealer = find_dealer(car.dealer_id, self.dealers)
        if dealer is None:
            logger.warning(f"Car {car.car_id} references unknown dealer {car.dealer_id}")
            return (
                f"I found the {car.make} {car.model} {car.variant}, but its dealer "
                "information is temporarily unavailable. Would you like to search for another car?"
            )
        if car != self.current_car:
            self.awaiting_datetime = False
        self.current_car, self.current_dealer = car, dealer
        return None

    def _show_selected_car(self) -> str:
        car, dealer = self.current_car, self.current_dealer
        self.offered = OPTIONS_ACTIONS
        return (
            f"I found: {self._describe_car(car, with_city=False)}, sold by "
            f"{dealer.name} ({dealer.city}).\n\n"
            f"Would you like to:\n{MENU_OPTIONS}"
        )

    def _show_car_details(self) -> str:
        car, dealer = self.current_car, self.current_dealer
        self.offered = OPTIONS_ACTIONS
        body = f"  Body:    {car.body_type}\n" if car.body_type else ""
        return (
            f"Here are the details of the {car.make} {car.model} {car.variant}:\n\n"
            f"  Make:    {car.make}\n"
            f"  Model:   {car.model}\n"
            f"  Variant: {car.variant}\n"
            f"  Year:    {car.year}\n"
            f"{body}"
            f"  Price:   {_euros(car.price)}\n"
            f"  Dealer:  {dealer.name} ({dealer.city})\n\n"
            f"Would you like to:\n{MENU_OPTIONS}"
        )

    def _show_dealer_details(self) -> str:
        """Show the selected dealer's contact details, then offer further help."""
        dealer = self.current_dealer
        self.last_action = "dealer_details"
        self.offered = OPTIONS_ACTIONS
        return (
            f"The {self.current_car} is sold by {dealer.name}. Here are the dealer's details:\n\n"
            f"  Dealer: {dealer.name}\n"
            f"  City:   {dealer.city}\n"
            f"  Phone:  {dealer.phone}\n"
            f"  Email:  {dealer.email}\n\n"
            f"Feel free to contact them directly!\n\n{FOLLOW_UP}"
        )

    def _show_dealer_inventory(self, exclude_current: bool) -> str:
        dealer = self.current_dealer
        cars = [car for car in self.cars if car.dealer_id == dealer.dealer_id]
        if exclude_current:
            cars = [car for car in cars if car != self.current_car]
        if not cars:
            return (
                f"{dealer.name} doesn't have any other cars in stock right now. "
                "Would you like to look at cars from other dealers?"
            )
        other = "other " if exclude_current else ""
        return self._list_cars(
            cars,
            f"{dealer.name} ({dealer.city}) has these {other}cars in stock:",
            "Would you like to know more about one of them? Reply with a number.",
        )

    # ------------------------------------------------------------------ comparing

    def _handle_compare(self, intent: Intent, text: str, pending: Optional[str]) -> str:
        cars: list[Car] = []
        if intent.positions:
            cars = [
                self.candidates[position - 1]
                for position in intent.positions
                if 1 <= position <= len(self.candidates)
            ]
        for query in intent.car_queries or ((intent.car_query,) if intent.car_query else ()):
            matches = search_cars(query, self.candidates) or search_cars(query, self.cars)
            cars += matches[:MAX_CANDIDATES_SHOWN]
        if not cars and len(self.candidates) > 1:
            cars = list(self.candidates)
        if len(cars) == 1 and self.current_car and self.current_car not in cars:
            cars.insert(0, self.current_car)
        cars = list(dict.fromkeys(cars))  # drop duplicates, keep order
        if len(cars) < 2:
            return (
                "Which cars would you like to compare? Name them "
                "(e.g. 'BMW 320i and Audi A4') or use their numbers from the list."
            )

        cars = sorted(cars, key=lambda car: car.price)[:MAX_CANDIDATES_SHOWN]
        cheapest, priciest = cars[0], cars[-1]
        summary = (
            f"The {cheapest} is the cheapest, {_euros(priciest.price - cheapest.price)} "
            f"less than the {priciest}."
        )
        if cheapest.price == priciest.price:
            summary = "They are the same price."
        newest = max(cars, key=lambda car: car.year)
        if any(car.year != newest.year for car in cars):
            summary += f" The {newest.make} {newest.model} {newest.variant} is the newest."
        return self._list_cars(
            cars,
            "Here's how they compare:",
            f"{summary}\n\nWould you like to know more about one of them? Reply with a number.",
        )

    # ------------------------------------------------------------------ scheduling

    def _handle_datetime(self, intent: Intent, text: str, pending: Optional[str]) -> str:
        if self.current_car is None:
            self.pending_action = "schedule_call"
            return "I'd be happy to schedule a call. Which car are you interested in?"
        return self._schedule(text)

    def _ask_for_datetime(self) -> str:
        self.awaiting_datetime = True
        return (
            f"Sure! What date and time would suit you for a call with "
            f"{self.current_dealer.name}? {DATETIME_EXAMPLES}"
        )

    def _schedule(self, text: str) -> str:
        """Parse the preferred call slot and confirm it."""
        self.awaiting_datetime = True
        parsed = self.llm_client.parse_datetime(text, reference_date=datetime.now())
        if parsed is None:
            return (
                "I couldn't understand that date/time. "
                "Please try again (e.g. 'Friday at 3pm', 'tomorrow at 10am', '2026-12-20 14:30'), "
                "or ask me something else."
            )
        if parsed <= datetime.now():
            return "That time is in the past. Please choose a future date and time."

        self.scheduled_datetime = parsed
        self.awaiting_datetime = False
        self.offered = OPTIONS_ACTIONS
        self.last_action = "scheduled_call"
        dealer = self.current_dealer
        slot = parsed.strftime("%A %d %B %Y at %H:%M")
        return (
            f"Call scheduled with {dealer.name} ({dealer.phone}) on {slot} "
            f"about the {self.current_car}.\n"
            f"The dealer will call you then.\n\n{FOLLOW_UP}"
        )

    # ------------------------------------------------------------------ formatting

    def _list_cars(self, cars: list[Car], header: str, footer: str) -> str:
        """Show a numbered car list the user can refer back to."""
        self.candidates = cars[:MAX_CANDIDATES_SHOWN]
        self.offered = OPTIONS_CARS
        options = "\n".join(
            f"  ({i}) {self._describe_car(car)}" for i, car in enumerate(self.candidates, start=1)
        )
        extra = ""
        if len(cars) > MAX_CANDIDATES_SHOWN:
            extra = (
                f"\n  ...and {len(cars) - MAX_CANDIDATES_SHOWN} more - "
                "tell me more about what you want to narrow it down."
            )
        return f"{header}\n{options}{extra}\n\n{footer}"

    def _describe_car(self, car: Car, with_city: bool = True) -> str:
        """E.g. 'BMW 3 Series 330i xDrive (2023) - €65,000 - Rotterdam'."""
        text = f"{car.make} {car.model} {car.variant} ({car.year}) - {_euros(car.price)}"
        dealer = find_dealer(car.dealer_id, self.dealers) if with_city else None
        return f"{text} - {dealer.city}" if dealer else text
