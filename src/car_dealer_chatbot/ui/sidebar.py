"""Sidebar: new chat and this browser's chat history (with rename/delete)."""

import streamlit as st

from ..services import ChatService, ConversationNotFoundError, InvalidTitleError
from ..services.chat_service import MAX_CUSTOM_TITLE_LENGTH
from ..storage import Conversation, ConversationStore
from . import session, theme
from .formatting import escape_markdown, format_timestamp, history_group

GONE = "That chat no longer exists."


def render_sidebar(chat: ChatService, store: ConversationStore) -> None:
    """Draw the sidebar with the new-chat button and this session's chat history."""
    active_id = session.active_conversation_id()
    conversations = chat.list_conversations(store)

    with st.sidebar:
        theme.apply_sidebar()
        with st.container(key="sidebar_brand"):
            theme.brand()
        st.button(
            "New chat",
            icon=":material/add:",
            width="stretch",
            on_click=session.start_new_chat,
        )

        theme.section_label("Chat history")
        with st.container(key="history", gap="xxsmall"):
            if not conversations:
                st.caption("No conversations yet. Your chats will appear here.")

            current_group = None
            for conversation in conversations:
                group = history_group(conversation.updated_at)
                if group != current_group:
                    st.caption(group)
                    current_group = group
                _render_history_entry(conversation, conversation.id == active_id)

    action = session.chat_action()
    if action and action.kind == "rename":
        _rename_dialog(chat, store, action.conversation_id, action.title)
    elif action and action.kind == "delete":
        _delete_dialog(chat, store, action.conversation_id, action.title)


def _render_history_entry(conversation: Conversation, is_active: bool) -> None:
    """The chat's button plus its '⋮' menu with Rename and Delete."""
    with st.container(
        key=f"history_row_{conversation.id}",
        horizontal=True,
        gap=None,
        vertical_alignment="center",
    ):
        label = (
            f"{escape_markdown(conversation.title)}  \n"
            f":gray[:small[{escape_markdown(format_timestamp(conversation.created_at))}]]"
        )
        st.button(
            label,
            key=f"conversation_{conversation.id}",
            type="primary" if is_active else "tertiary",
            width="stretch",
            on_click=session.open_conversation,
            args=(conversation.id,),
        )
        menu_key = f"chat_menu_{conversation.id}"
        with st.popover("", icon=":material/more_vert:", type="tertiary", key=menu_key):
            for kind, text, icon in (
                ("rename", "Rename", ":material/edit:"),
                ("delete", "Delete", ":material/delete:"),
            ):
                st.button(
                    text,
                    icon=icon,
                    key=f"{kind}_{conversation.id}",
                    type="tertiary",
                    width="stretch",
                    on_click=session.request_chat_action,
                    args=(kind, conversation.id, conversation.title, menu_key),
                )


@st.dialog("Rename chat", on_dismiss=session.clear_chat_action)
def _rename_dialog(
    chat: ChatService, store: ConversationStore, conversation_id: str, title: str
) -> None:
    with st.form("rename_chat", border=False):
        new_title = st.text_input("Chat name", value=title, max_chars=MAX_CUSTOM_TITLE_LENGTH)
        with st.container(horizontal=True, horizontal_alignment="right"):
            cancelled = st.form_submit_button("Cancel", type="tertiary")
            saved = st.form_submit_button("Save", type="primary")
    if saved:
        try:
            chat.rename_conversation(store, conversation_id, new_title)
        except InvalidTitleError as exc:
            st.error(str(exc))
            return
        except ConversationNotFoundError:
            session.set_notice("warning", GONE)
    if cancelled or saved:
        session.clear_chat_action()
        st.rerun()


@st.dialog("Delete chat?", on_dismiss=session.clear_chat_action)
def _delete_dialog(
    chat: ChatService, store: ConversationStore, conversation_id: str, title: str
) -> None:
    st.markdown(
        f"This will delete **{escape_markdown(title)}** and all of its messages. "
        "This can't be undone."
    )
    with st.container(key="delete_chat_actions", horizontal=True, horizontal_alignment="right"):
        cancelled = st.button("Cancel", key="cancel_delete_chat", type="tertiary")
        confirmed = st.button("Delete", key="confirm_delete_chat", type="primary")
    if confirmed:
        try:
            chat.delete_conversation(store, conversation_id)
        except ConversationNotFoundError:
            pass  # already gone: the result is the same
        if conversation_id == session.active_conversation_id():
            session.start_new_chat()
    if cancelled or confirmed:
        session.clear_chat_action()
        st.rerun()
