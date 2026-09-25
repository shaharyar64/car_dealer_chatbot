"""Main chat area: messages, quick replies, and the message input."""

import logging
from typing import Optional

import streamlit as st

from ..config import LOGGER_NAME
from ..services import ChatService, ConversationNotFoundError, ConversationView, QuickReply
from ..storage import ConversationStore
from . import session, theme
from .formatting import escape_markdown, format_time, text_to_markdown, to_markdown

logger = logging.getLogger(LOGGER_NAME)

ASSISTANT_AVATAR = ":material/directions_car:"
USER_AVATAR = ":material/person:"
INPUT_KEY = "chat_input"
SUGGESTIONS = ["Toyota Corolla", "BMW 3 Series", "Volkswagen Golf", "Mercedes-Benz C-Class"]
SEND_FAILED = "Sorry, something went wrong and your message wasn't sent. Please try again."
NOT_FOUND = "That conversation couldn't be found, so a new chat was started."


def render_chat_page(chat: ChatService, store: ConversationStore) -> None:
    """Draw the open conversation (or the welcome screen) and process a queued message."""
    view = _load_active_conversation(chat, store)
    pending = session.pending_message()

    theme.apply_chat()
    with st.container(key="chat_header"):
        st.markdown(
            f"#### {escape_markdown(view.conversation.title if view else 'New conversation')}"
        )

    if view:
        for message in view.messages:
            _render_message(message.role, message.content, message.created_at)
    elif not pending:
        _render_welcome()

    # Rendered before processing so it is disabled while the bot is thinking.
    st.chat_input(
        "Ask about a car, e.g. 'Toyota Corolla'",
        key=INPUT_KEY,
        max_chars=2000,
        disabled=pending is not None,
        submit_mode="disable",
        on_submit=session.queue_typed_message,
        args=(INPUT_KEY,),
    )

    if pending:
        _process(chat, store, view, pending)
        return

    if view and view.quick_replies:
        _render_quick_replies(view.conversation.id, view.quick_replies)

    notice = session.pop_notice()
    if notice:
        (st.error if notice.level == "error" else st.warning)(notice.text)


def _load_active_conversation(
    chat: ChatService, store: ConversationStore
) -> Optional[ConversationView]:
    conversation_id = session.active_conversation_id()
    if not conversation_id:
        return None
    try:
        return chat.get_conversation(store, conversation_id)
    except ConversationNotFoundError:
        session.start_new_chat()
        session.set_notice("warning", NOT_FOUND)
        return None


def _render_message(role: str, content: str, created_at: Optional[str]) -> None:
    avatar = ASSISTANT_AVATAR if role == "assistant" else USER_AVATAR
    with st.chat_message(role, avatar=avatar):
        st.markdown(to_markdown(content) if role == "assistant" else text_to_markdown(content))
        if created_at:
            st.caption(format_time(created_at))


def _render_welcome() -> None:
    with st.container(key="welcome"):
        theme.welcome_mark()
        st.markdown("## Find your next car")
        st.markdown(
            "Tell me which car you're looking for. I'll check our inventory, show you who sells "
            "it, and help you get the dealer's details or schedule a call."
        )
        st.caption("Try asking about")
    with st.container(key="suggestions", horizontal=True, horizontal_alignment="center"):
        for suggestion in SUGGESTIONS:
            st.button(suggestion, on_click=session.queue_message, args=(suggestion,))


def _render_quick_replies(conversation_id: str, replies: list[QuickReply]) -> None:
    with st.container(key="quick_replies", horizontal=True):
        for reply in replies:
            st.button(
                escape_markdown(reply.label),
                key=f"quick_reply_{conversation_id}_{reply.value}",
                on_click=session.queue_message,
                args=(reply.label, reply.value),
            )


def _process(
    chat: ChatService,
    store: ConversationStore,
    view: Optional[ConversationView],
    pending: session.PendingMessage,
) -> None:
    """Show the user's message and a spinner, run the turn, then rerun to show the reply."""
    _render_message("user", pending.content, None)
    conversation_id = view.conversation.id if view else None
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Thinking..."):
            try:
                if conversation_id is None:
                    conversation_id = chat.start_conversation(store).conversation.id
                chat.send_message(store, conversation_id, pending.content, pending.value)
            except ConversationNotFoundError:
                conversation_id = None
                session.set_notice("warning", NOT_FOUND)
            except Exception:
                logger.exception("Failed to process a chat message")
                session.set_notice("error", SEND_FAILED)
            finally:
                session.clear_pending_message()

    if conversation_id:
        session.show_conversation(conversation_id)
    else:
        session.start_new_chat(keep_notice=True)
    st.rerun()
