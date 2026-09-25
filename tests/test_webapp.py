"""UI tests for the Streamlit app using Streamlit's AppTest (fake LLM, in-memory chat history)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import car_dealer_chatbot.services.factory as factory
from car_dealer_chatbot.models import Car, Dealer
from car_dealer_chatbot.services import ChatService
from car_dealer_chatbot.services.factory import AppServices

from .conftest import FakeLLMClient

APP_FILE = str(Path(__file__).parent.parent / "src" / "car_dealer_chatbot" / "webapp.py")


@pytest.fixture(autouse=True)
def services(
    sample_cars: list[Car],
    sample_dealers: list[Dealer],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[AppServices]:
    """Make the app use the fake LLM instead of calling OpenAI."""
    app_services = AppServices(chat=ChatService(sample_cars, sample_dealers, FakeLLMClient()))
    monkeypatch.setattr(factory, "build_services", lambda: app_services)
    st.cache_resource.clear()
    yield app_services
    st.cache_resource.clear()


def open_app() -> AppTest:
    """A fresh browser opening the app."""
    at = AppTest.from_file(APP_FILE, default_timeout=30).run()
    assert not at.exception
    return at


def send(at: AppTest, text: str) -> AppTest:
    at.chat_input[0].set_value(text).run()
    assert not at.exception
    return at


def chat_texts(at: AppTest) -> list[str]:
    return [md.value for msg in at.chat_message for md in msg.markdown]


def history_labels(at: AppTest) -> list[str]:
    return [b.label for b in at.sidebar.button if b.key and b.key.startswith("conversation_")]


def test_chat_opens_directly() -> None:
    at = open_app()
    assert at.chat_input and not at.chat_input[0].disabled
    assert any("Find your next car" in md.value for md in at.main.markdown)
    assert any(b.label == "Toyota Corolla" for b in at.button)  # suggestions
    assert not at.text_input  # no forms stand between the visitor and the chat


def test_chat_flow_quick_replies_and_history() -> None:
    at = open_app()
    assert history_labels(at) == []

    send(at, "I want a BMW 3 Series")
    assert any("Amsterdam Motors" in text for text in chat_texts(at))
    assert history_labels(at)[0].startswith("BMW 3 Series Inquiry")

    next(b for b in at.button if b.label == "View dealer details").click().run()
    assert any("info@amsterdammotors\\.nl" in text for text in chat_texts(at))
    assert not at.chat_input[0].disabled  # the chat can always continue
    assert any(b.label == "Schedule a call" for b in at.button)
    assert history_labels(at)[0].startswith("BMW 3 Series Dealer")


def test_new_chat_keeps_history_and_old_chat_reopens() -> None:
    at = open_app()
    send(at, "I want a BMW 3 Series")
    first_id = at.query_params["c"][0]

    next(b for b in at.sidebar.button if b.label == "New chat").click().run()
    assert "c" not in at.query_params
    send(at, "I want a Volkswagen Golf")
    assert len(history_labels(at)) == 2

    at.sidebar.button(key=f"conversation_{first_id}").click().run()
    texts = chat_texts(at)
    assert any("Amsterdam Motors" in text for text in texts)
    assert not any("Golf" in text for text in texts)


def test_two_browsers_see_only_their_own_history() -> None:
    first = open_app()
    send(first, "I want a BMW 3 Series")
    first_conversation = first.query_params["c"][0]

    second = open_app()
    assert history_labels(second) == []

    # The second browser opening the first one's conversation URL gets a new chat, not its messages.
    second.query_params["c"] = first_conversation
    second.run()
    assert not any("Amsterdam Motors" in text for text in chat_texts(second))
    assert any("couldn't be found" in w.value for w in second.warning)


def open_menu_item(at: AppTest, kind: str, conversation_id: str) -> AppTest:
    at.sidebar.button(key=f"{kind}_{conversation_id}").click().run()
    assert not at.exception
    return at


def test_rename_chat_from_its_menu() -> None:
    at = open_app()
    send(at, "I want a BMW 3 Series")
    cid = at.query_params["c"][0]

    open_menu_item(at, "rename", cid)
    name_input = next(t for t in at.text_input if t.label == "Chat name")
    assert name_input.value == "BMW 3 Series Inquiry"
    name_input.input("Weekend shopping")
    next(b for b in at.button if b.label == "Save").click().run()
    assert not at.exception
    assert history_labels(at)[0].startswith("Weekend shopping")
    assert any("Weekend shopping" in md.value for md in at.main.markdown)

    # The chosen name survives further messages.
    next(b for b in at.button if b.label == "View dealer details").click().run()
    assert history_labels(at)[0].startswith("Weekend shopping")


def test_delete_open_chat_from_its_menu() -> None:
    at = open_app()
    send(at, "I want a BMW 3 Series")
    first_id = at.query_params["c"][0]
    next(b for b in at.sidebar.button if b.label == "New chat").click().run()
    send(at, "I want a Volkswagen Golf")
    second_id = at.query_params["c"][0]

    open_menu_item(at, "delete", second_id)
    assert any("can't be undone" in md.value for md in at.markdown)
    at.button(key="confirm_delete_chat").click().run()
    assert not at.exception

    assert len(history_labels(at)) == 1
    assert at.sidebar.button(key=f"conversation_{first_id}")
    assert "c" not in at.query_params  # the deleted chat was open, so a new chat starts
    assert not any("Golf" in text for text in chat_texts(at))


def test_cancel_delete_keeps_the_chat() -> None:
    at = open_app()
    send(at, "I want a BMW 3 Series")
    cid = at.query_params["c"][0]

    open_menu_item(at, "delete", cid)
    at.button(key="cancel_delete_chat").click().run()
    assert not at.exception
    assert len(history_labels(at)) == 1
    assert at.query_params["c"][0] == cid
