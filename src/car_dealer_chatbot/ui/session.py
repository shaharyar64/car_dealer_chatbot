"""Per-session state for the Streamlit app: conversation store, active chat and queued messages.

- Each browser session gets its own in-memory ConversationStore, created on first use and
  kept in st.session_state for as long as the session lasts. It is never written to disk,
  so a server restart (or a different session) starts with no chat history.
- The open conversation id lives in the URL (?c=<id>), so a refresh reopens it, as long as
  the session (and therefore its store) is still alive.
"""

from dataclasses import dataclass
from typing import Optional

import streamlit as st

from ..storage import ConversationStore

_CONVERSATION_PARAM = "c"
_STORE = "conversation_store"
_PENDING = "pending_message"
_NOTICE = "notice"
_CHAT_ACTION = "chat_action"


@dataclass(frozen=True)
class PendingMessage:
    """A message waiting to be processed: `content` is displayed, `value` goes to the bot."""

    content: str
    value: Optional[str] = None


@dataclass(frozen=True)
class ChatAction:
    """A sidebar menu choice ('rename' or 'delete') waiting to open its dialog."""

    kind: str
    conversation_id: str
    title: str


@dataclass(frozen=True)
class Notice:
    """A one-off message for the user ('warning' or 'error')."""

    level: str
    text: str


# ---------- Conversation store ----------


def get_store() -> ConversationStore:
    """This session's conversation store, created empty on first use."""
    if _STORE not in st.session_state:
        st.session_state[_STORE] = ConversationStore()
    return st.session_state[_STORE]


# ---------- Conversations ----------


def active_conversation_id() -> Optional[str]:
    """The conversation open in this tab, from the URL."""
    return st.query_params.get(_CONVERSATION_PARAM)


def show_conversation(conversation_id: str) -> None:
    """Point the URL at a conversation without touching notices."""
    st.query_params[_CONVERSATION_PARAM] = conversation_id


def open_conversation(conversation_id: str) -> None:
    """Switch to an existing conversation (sidebar click)."""
    show_conversation(conversation_id)
    st.session_state.pop(_PENDING, None)
    st.session_state.pop(_NOTICE, None)


def start_new_chat(keep_notice: bool = False) -> None:
    """Clear the chat window; the conversation is created when the first message is sent."""
    st.query_params.pop(_CONVERSATION_PARAM, None)
    st.session_state.pop(_PENDING, None)
    if not keep_notice:
        st.session_state.pop(_NOTICE, None)


def request_chat_action(kind: str, conversation_id: str, title: str, menu_key: str) -> None:
    """on_click callback of a chat's menu item: close the menu and open the action's dialog."""
    st.session_state[menu_key] = False
    st.session_state[_CHAT_ACTION] = ChatAction(kind, conversation_id, title)


def chat_action() -> Optional[ChatAction]:
    """The chat menu choice whose dialog is open, if any (kept until the dialog closes)."""
    return st.session_state.get(_CHAT_ACTION)


def clear_chat_action() -> None:
    """Close the chat menu dialog (also the on_dismiss callback of the dialogs)."""
    st.session_state.pop(_CHAT_ACTION, None)


# ---------- Messages & notices ----------


def queue_message(content: str, value: Optional[str] = None) -> None:
    """Queue a message to be processed on the next rerun."""
    content = (content or "").strip()
    if content:
        st.session_state[_PENDING] = PendingMessage(content, value)
        st.session_state.pop(_NOTICE, None)


def queue_typed_message(widget_key: str) -> None:
    """on_submit callback for st.chat_input."""
    queue_message(st.session_state.get(widget_key) or "")


def pending_message() -> Optional[PendingMessage]:
    """The message waiting to be processed, if any."""
    return st.session_state.get(_PENDING)


def clear_pending_message() -> None:
    st.session_state.pop(_PENDING, None)


def set_notice(level: str, text: str) -> None:
    st.session_state[_NOTICE] = Notice(level, text)


def pop_notice() -> Optional[Notice]:
    return st.session_state.pop(_NOTICE, None)
