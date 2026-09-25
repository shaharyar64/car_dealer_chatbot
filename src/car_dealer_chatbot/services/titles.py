"""Deterministic conversation titles (no extra LLM calls).

Once a car is identified the title is based on it and follows what the user did:
"Toyota Corolla Inquiry" -> "Toyota Corolla Dealer" or "Schedule Toyota Corolla Call".
If the user moves on to another car, the title follows the new car.
Before any car is identified, a title is derived from the first meaningful user message.
"""

import re
from typing import Optional

from ..core import Chatbot
from ..core.chatbot import OPTIONS_CARS

DEFAULT_TITLE = "New conversation"
MAX_TITLE_WORDS = 5
MAX_TITLE_LENGTH = 48

_STOPWORDS = {
    "a", "about", "all", "an", "and", "any", "are", "available", "buy", "buying", "can",
    "car", "cars", "could", "do", "does", "find", "for", "get", "have", "hello", "help",
    "hey", "hi", "i", "i'm", "im", "in", "interested", "is", "it", "like", "looking", "me",
    "my", "need", "of", "on", "one", "options", "please", "purchase", "search", "searching",
    "show", "some", "tell", "thanks", "the", "there", "to", "u", "want", "what", "which",
    "with", "would", "you", "your",
}  # fmt: skip


def _car_label(chatbot: Chatbot) -> Optional[str]:
    """'Make Model' of the car being discussed, or of a listed set of cars if they share it."""
    if chatbot.offered != OPTIONS_CARS and chatbot.current_car is not None:
        return f"{chatbot.current_car.make} {chatbot.current_car.model}"
    if chatbot.offered == OPTIONS_CARS and chatbot.candidates:
        make_models = {(car.make, car.model) for car in chatbot.candidates}
        if len(make_models) == 1:
            make, model = make_models.pop()
            return f"{make} {model}"
        makes = {car.make for car in chatbot.candidates}
        if len(makes) == 1:
            return makes.pop()
    return None


def _capitalize(word: str) -> str:
    """Title-case plain words but keep 'BMW', '320i', 'xDrive' as typed."""
    if any(ch.isupper() or ch.isdigit() for ch in word):
        return word
    return word.capitalize()


def title_from_text(text: str) -> Optional[str]:
    """Build a short title from free text, or None if nothing meaningful remains."""
    words = re.findall(r"[A-Za-z0-9][\w.'-]*", text)
    kept = [word for word in words if word.lower() not in _STOPWORDS]
    if not kept:
        return None
    title = " ".join(_capitalize(word) for word in kept[:MAX_TITLE_WORDS])
    return title[:MAX_TITLE_LENGTH].rstrip()


def generate_title(chatbot: Chatbot, user_text: str, current_title: str) -> str:
    """Return the conversation title after a turn has been processed by `chatbot`."""
    label = _car_label(chatbot)
    if label is None:
        if current_title != DEFAULT_TITLE:
            return current_title
        return title_from_text(user_text) or DEFAULT_TITLE

    scheduled_title = f"Schedule {label} Call"
    if chatbot.last_action == "scheduled_call":
        return scheduled_title
    if chatbot.last_action == "dealer_details":
        # A scheduled call is the more meaningful outcome; don't replace it.
        return current_title if current_title == scheduled_title else f"{label} Dealer"
    if label in current_title:
        return current_title
    return f"{label} Inquiry"
