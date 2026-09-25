"""In-memory storage for conversations and messages, scoped to one chat session.

A ConversationStore holds everything for one browser session's chats: nothing is written
to disk or a database, so it disappears when the session ends (tab closed, app restarted).
The UI layer is responsible for keeping one store per Streamlit session (see ui/session.py)
so different visitors never share one.
"""

import itertools
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal, Optional

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    """One chat message in a conversation."""

    id: int
    conversation_id: str
    role: Role
    content: str
    created_at: str


@dataclass(frozen=True)
class Conversation:
    """A chat thread, including the chatbot's saved flow state."""

    id: str
    title: str
    state: dict[str, Any]
    is_done: bool
    created_at: str
    updated_at: str
    title_locked: bool = False  # the chat was renamed, so the title is no longer automatic


def _now() -> str:
    # timespec="microseconds" keeps every timestamp the same length, so sorting the
    # strings gives the same order as sorting the underlying moments.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ConversationStore:
    """In-memory conversations and messages for one chat session."""

    def __init__(self) -> None:
        """Start empty: no conversations, no messages."""
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[Message]] = {}
        self._next_message_id = itertools.count(1)

    def create(self, title: str, state: dict[str, Any]) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=title,
            state=state,
            is_done=False,
            created_at=_now(),
            updated_at=_now(),
        )
        self._conversations[conversation.id] = conversation
        self._messages[conversation.id] = []
        return conversation

    def get(self, conversation_id: str) -> Optional[Conversation]:
        """Fetch a conversation by id, or None if it doesn't exist in this session."""
        return self._conversations.get(conversation_id)

    def rename(self, conversation_id: str, title: str) -> Optional[Conversation]:
        """Give a conversation a chosen title; automatic titles won't replace it."""
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return None
        updated = replace(conversation, title=title, title_locked=True)
        self._conversations[conversation_id] = updated
        return updated

    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation and its messages; False if it didn't exist."""
        self._messages.pop(conversation_id, None)
        return self._conversations.pop(conversation_id, None) is not None

    def list_all(self) -> list[Conversation]:
        """All conversations in this session, most recently active first."""
        return sorted(
            self._conversations.values(),
            key=lambda c: (c.updated_at, c.created_at),
            reverse=True,
        )

    def update_after_turn(
        self, conversation_id: str, title: str, state: dict[str, Any], is_done: bool
    ) -> Optional[Conversation]:
        """Save the new title/state after a chat turn and bump updated_at."""
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return None
        updated = replace(
            conversation, title=title, state=state, is_done=is_done, updated_at=_now()
        )
        self._conversations[conversation_id] = updated
        return updated

    def add_message(self, conversation_id: str, role: Role, content: str) -> Message:
        """Append a message to a conversation."""
        message = Message(
            id=next(self._next_message_id),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=_now(),
        )
        self._messages.setdefault(conversation_id, []).append(message)
        return message

    def list_messages(self, conversation_id: str) -> list[Message]:
        """All messages of a conversation in the order they were sent."""
        return list(self._messages.get(conversation_id, []))
