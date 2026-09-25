"""Conversation and message management around the Chatbot.

For every turn a Chatbot is rebuilt from the conversation's saved state (its context:
cars listed, car being discussed, filters, recent messages), processes the message, and
its new state is saved back together with both messages. Everything is kept in the
caller's ConversationStore — an in-memory store scoped to one chat session (see
storage/memory_store.py) — so conversations last only as long as that session.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from ..core import Chatbot
from ..core.chatbot import OPTIONS_ACTIONS, OPTIONS_CARS
from ..config import LOGGER_NAME
from ..llm import LLMClient
from ..models import Car, Dealer
from ..storage import Conversation, ConversationStore, Message
from .titles import DEFAULT_TITLE, generate_title

logger = logging.getLogger(LOGGER_NAME)

_LOCK_STRIPES = 64
MAX_CUSTOM_TITLE_LENGTH = 80


class ConversationNotFoundError(Exception):
    """Raised when a conversation doesn't exist in the given store."""


class InvalidTitleError(ValueError):
    """Raised when a new conversation title is empty (message is user-facing)."""


@dataclass(frozen=True)
class QuickReply:
    """A clickable suggested reply: `label` is shown and stored, `value` is sent to the bot."""

    label: str
    value: str


@dataclass(frozen=True)
class ConversationView:
    """A conversation with its full message history and current suggested replies."""

    conversation: Conversation
    messages: list[Message]
    quick_replies: list[QuickReply]


@dataclass(frozen=True)
class TurnResult:
    """Outcome of sending one message."""

    conversation: Conversation
    user_message: Message
    assistant_message: Message
    quick_replies: list[QuickReply]


def quick_replies_for(chatbot: Chatbot) -> list[QuickReply]:
    """
    Buttons for the numbered options the chatbot's last reply offered.

    They are shortcuts only: the user can always type anything else instead.
    """
    if chatbot.offered == OPTIONS_ACTIONS and chatbot.current_car:
        return [QuickReply("View dealer details", "1"), QuickReply("Schedule a call", "2")]
    if chatbot.offered == OPTIONS_CARS and chatbot.candidates:
        return [
            QuickReply(str(car), str(index))
            for index, car in enumerate(chatbot.candidates, start=1)
        ]
    return []


class ChatService:
    """Runs chat turns against whichever ConversationStore it's given."""

    def __init__(self, cars: list[Car], dealers: list[Dealer], llm_client: LLMClient):
        """Share one inventory and LLM client across all sessions' conversations."""
        self.cars = cars
        self.dealers = dealers
        self.llm_client = llm_client
        # Serialise turns per conversation (e.g. a double-submitted message).
        self._locks = [threading.Lock() for _ in range(_LOCK_STRIPES)]

    def _lock_for(self, conversation_id: str) -> threading.Lock:
        return self._locks[hash(conversation_id) % _LOCK_STRIPES]

    def _chatbot_for(self, conversation: Optional[Conversation] = None) -> Chatbot:
        # Web conversations never end, so users can always keep chatting.
        chatbot = Chatbot(self.cars, self.dealers, self.llm_client, end_on_exit=False)
        if conversation is not None:
            chatbot.restore_state(conversation.state)
        return chatbot

    def list_conversations(self, store: ConversationStore) -> list[Conversation]:
        """This session's conversations, most recent first."""
        return store.list_all()

    def start_conversation(self, store: ConversationStore) -> ConversationView:
        """Create a conversation that opens with the chatbot's greeting."""
        chatbot = self._chatbot_for()
        conversation = store.create(DEFAULT_TITLE, chatbot.export_state())
        greeting = store.add_message(conversation.id, "assistant", chatbot.get_greeting())
        logger.info(f"Started conversation {conversation.id}")
        return ConversationView(conversation, [greeting], quick_replies_for(chatbot))

    def get_conversation(self, store: ConversationStore, conversation_id: str) -> ConversationView:
        """Load a conversation with all its messages. Raises ConversationNotFoundError."""
        conversation = store.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        messages = store.list_messages(conversation_id)
        chatbot = self._chatbot_for(conversation)
        return ConversationView(conversation, messages, quick_replies_for(chatbot))

    def rename_conversation(
        self, store: ConversationStore, conversation_id: str, title: str
    ) -> Conversation:
        """
        Give a conversation a chosen title, kept from now on.

        Raises InvalidTitleError (empty title) or ConversationNotFoundError.
        """
        title = " ".join(title.split())[:MAX_CUSTOM_TITLE_LENGTH].rstrip()
        if not title:
            raise InvalidTitleError("Please enter a name for the chat.")
        with self._lock_for(conversation_id):
            renamed = store.rename(conversation_id, title)
        if renamed is None:
            raise ConversationNotFoundError(conversation_id)
        logger.info(f"Renamed conversation {conversation_id}")
        return renamed

    def delete_conversation(self, store: ConversationStore, conversation_id: str) -> None:
        """Delete a conversation with all its messages. Raises ConversationNotFoundError."""
        with self._lock_for(conversation_id):
            deleted = store.delete(conversation_id)
        if not deleted:
            raise ConversationNotFoundError(conversation_id)
        logger.info(f"Deleted conversation {conversation_id}")

    def send_message(
        self,
        store: ConversationStore,
        conversation_id: str,
        content: str,
        value: Optional[str] = None,
    ) -> TurnResult:
        """
        Run one chat turn and store it.

        `content` is what the user typed (or the label of a clicked quick reply) and is
        what gets stored and displayed. `value` is the quick reply's value (e.g. "1"),
        passed to the chatbot instead of `content` if it's still a valid option.
        Nothing is stored if processing fails.
        """
        with self._lock_for(conversation_id):
            conversation = store.get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(conversation_id)

            chatbot = self._chatbot_for(conversation)
            valid_values = {reply.value for reply in quick_replies_for(chatbot)}
            bot_input = value if value in valid_values else content

            reply, is_done = chatbot.process_input(bot_input)
            title = conversation.title
            if not conversation.title_locked:
                title = generate_title(chatbot, content, conversation.title)

            user_message = store.add_message(conversation_id, "user", content)
            assistant_message = store.add_message(conversation_id, "assistant", reply)
            updated = store.update_after_turn(
                conversation_id, title, chatbot.export_state(), is_done
            )
            if updated is None:
                raise ConversationNotFoundError(conversation_id)

        logger.info(f"Conversation {conversation_id}: intent={chatbot.last_intent}")
        return TurnResult(updated, user_message, assistant_message, quick_replies_for(chatbot))
