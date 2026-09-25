"""Abstract interface for LLM clients."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..intents import Intent


class LLMError(Exception):
    """Raised when the LLM service cannot be reached or rejects the request."""


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def interpret_message(self, user_text: str, context: str) -> Intent:
        """
        Work out what the user's message asks for.

        Args:
            user_text: The user's latest message
            context: A plain-text summary of the conversation so far (cars listed,
                car being discussed, active filters, recent messages, inventory vocabulary)

        Returns the interpreted Intent ("unclear" if it can't be interpreted).
        """
        pass

    @abstractmethod
    def parse_datetime(
        self, user_text: str, reference_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Parse natural language datetime from user text.

        Args:
            user_text: User's input text with date/time information
            reference_date: Optional reference date for relative dates

        Returns the parsed datetime, or None if parsing fails.
        """
        pass
