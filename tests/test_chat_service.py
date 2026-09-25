"""Tests for conversation management: flow, titles and session isolation."""

import pytest

from car_dealer_chatbot.core.chatbot import LLM_UNAVAILABLE_MESSAGE
from car_dealer_chatbot.models import Car, Dealer
from car_dealer_chatbot.services import (
    ChatService,
    ConversationNotFoundError,
    InvalidTitleError,
)
from car_dealer_chatbot.storage import ConversationStore

from .conftest import FailingLLMClient, FakeLLMClient


@pytest.fixture
def chat(sample_cars: list[Car], sample_dealers: list[Dealer]) -> ChatService:
    return ChatService(sample_cars, sample_dealers, FakeLLMClient())


def test_new_conversation_starts_with_greeting(store: ConversationStore, chat: ChatService) -> None:
    view = chat.start_conversation(store)
    assert view.conversation.title == "New conversation"
    assert [m.role for m in view.messages] == ["assistant"]
    assert "which car" in view.messages[0].content.lower()


def test_schedule_call_flow_with_quick_replies(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id

    turn = chat.send_message(store, cid, "I want a BMW 3 Series")
    assert "Amsterdam Motors" in turn.assistant_message.content
    assert [r.value for r in turn.quick_replies] == ["1", "2"]
    assert turn.conversation.title == "BMW 3 Series Inquiry"

    turn = chat.send_message(store, cid, "Schedule a call", value="2")
    assert turn.user_message.content == "Schedule a call"
    assert "date and time" in turn.assistant_message.content

    turn = chat.send_message(store, cid, "tomorrow at 3pm")
    reply = turn.assistant_message.content
    assert "Amsterdam Motors" in reply and "+31 20 234 5678" in reply and "15:00" in reply
    assert turn.conversation.is_done is False
    assert turn.conversation.title == "Schedule BMW 3 Series Call"
    assert [r.value for r in turn.quick_replies] == ["1", "2"]  # the chat continues


def test_chat_continues_with_another_car(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")
    chat.send_message(store, cid, "View dealer details", value="1")
    turn = chat.send_message(store, cid, "bye")
    assert turn.conversation.is_done is False

    turn = chat.send_message(store, cid, "I want a Volkswagen Golf")
    assert "Rotterdam Car Hub" in turn.assistant_message.content
    assert turn.conversation.title == "Volkswagen Golf Inquiry"


def test_dealer_details_flow(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")
    turn = chat.send_message(store, cid, "View dealer details", value="1")
    assert "info@amsterdammotors.nl" in turn.assistant_message.content
    assert turn.conversation.is_done is False
    assert turn.conversation.title == "BMW 3 Series Dealer"


def test_ambiguous_match_offers_candidates(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    turn = chat.send_message(store, cid, "I want a Toyota Corolla")
    labels = [r.label for r in turn.quick_replies]
    assert labels == ["Toyota Corolla 1.8 Hybrid (2023)", "Toyota Corolla 1.6 Petrol (2023)"]

    turn = chat.send_message(store, cid, labels[1], value="2")
    assert "1.6 Petrol" in turn.assistant_message.content
    assert turn.user_message.content == labels[1]


def test_stale_quick_reply_value_falls_back_to_text(
    store: ConversationStore, chat: ChatService
) -> None:
    cid = chat.start_conversation(store).conversation.id
    turn = chat.send_message(store, cid, "I want a BMW 3 Series", value="9")
    assert "Amsterdam Motors" in turn.assistant_message.content


def test_car_not_found(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    turn = chat.send_message(store, cid, "Do you have a Tesla Model 3?")
    assert "couldn't find" in turn.assistant_message.content.lower()
    assert turn.conversation.title == "Tesla Model 3"
    assert turn.conversation.is_done is False


def test_llm_outage_returns_friendly_reply(
    store: ConversationStore, sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    chat = ChatService(sample_cars, sample_dealers, FailingLLMClient())
    cid = chat.start_conversation(store).conversation.id
    turn = chat.send_message(store, cid, "I want a BMW")
    assert turn.assistant_message.content == LLM_UNAVAILABLE_MESSAGE


def test_sessions_have_separate_histories(chat: ChatService) -> None:
    """Two independent ConversationStores never see each other's conversations."""
    store, other_store = ConversationStore(), ConversationStore()
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")
    other_cid = chat.start_conversation(other_store).conversation.id
    chat.send_message(other_store, other_cid, "I want a Volkswagen Golf")

    assert [c.id for c in chat.list_conversations(store)] == [cid]
    assert [c.id for c in chat.list_conversations(other_store)] == [other_cid]

    with pytest.raises(ConversationNotFoundError):
        chat.get_conversation(other_store, cid)
    with pytest.raises(ConversationNotFoundError):
        chat.send_message(other_store, cid, "1")
    assert len(chat.get_conversation(store, cid).messages) == 3


def test_unknown_conversation_id_raises(store: ConversationStore, chat: ChatService) -> None:
    chat.start_conversation(store)
    assert chat.list_conversations(ConversationStore()) == []
    with pytest.raises(ConversationNotFoundError):
        chat.get_conversation(store, "not-a-real-id")


def test_multiple_conversations_in_one_session(store: ConversationStore, chat: ChatService) -> None:
    first = chat.start_conversation(store).conversation.id
    chat.send_message(store, first, "I want a BMW 3 Series")
    second = chat.start_conversation(store).conversation.id
    chat.send_message(store, second, "I want a Volkswagen Golf")

    listed = chat.list_conversations(store)
    assert [c.id for c in listed] == [second, first]  # most recent first
    assert [c.title for c in listed] == ["Volkswagen Golf Inquiry", "BMW 3 Series Inquiry"]

    # Each conversation keeps its own flow state.
    turn = chat.send_message(store, first, "View dealer details", value="1")
    assert "Amsterdam Motors" in turn.assistant_message.content
    turn = chat.send_message(store, second, "View dealer details", value="1")
    assert "Rotterdam Car Hub" in turn.assistant_message.content


def test_conversation_state_lives_in_the_store_not_the_service(
    store: ConversationStore,
    chat: ChatService,
    sample_cars: list[Car],
    sample_dealers: list[Dealer],
) -> None:
    """ChatService keeps no per-conversation state of its own: it's all in the store."""
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")
    before = chat.get_conversation(store, cid)

    other_chat = ChatService(sample_cars, sample_dealers, FakeLLMClient())
    after = other_chat.get_conversation(store, cid)
    assert after.messages == before.messages
    assert [r.value for r in after.quick_replies] == ["1", "2"]

    turn = other_chat.send_message(store, cid, "2")
    assert "date and time" in turn.assistant_message.content


def test_facts_are_remembered_across_turns(
    store: ConversationStore,
    chat: ChatService,
    sample_cars: list[Car],
    sample_dealers: list[Dealer],
) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "hi my name is shaharyar")
    chat.send_message(store, cid, "I want a BMW 3 Series")

    other_chat = ChatService(sample_cars, sample_dealers, FakeLLMClient())
    turn = other_chat.send_message(store, cid, "what is my name")
    assert turn.assistant_message.content == "Your name is Shaharyar."

    turn = other_chat.send_message(store, cid, "actually, call me Sarah")
    turn = other_chat.send_message(store, cid, "what is my name")
    assert turn.assistant_message.content == "Your name is Sarah."


def test_new_conversation_does_not_inherit_facts(store: ConversationStore, chat: ChatService) -> None:
    first = chat.start_conversation(store).conversation.id
    chat.send_message(store, first, "my name is shaharyar")

    second = chat.start_conversation(store).conversation.id
    turn = chat.send_message(store, second, "what is my name")
    assert "Shaharyar" not in turn.assistant_message.content
    assert "told me that yet" in turn.assistant_message.content


def test_rename_keeps_the_chosen_title(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")

    renamed = chat.rename_conversation(store, cid, "  My   next car  ")
    assert renamed.title == "My next car" and renamed.title_locked

    # Automatic titles no longer replace it.
    turn = chat.send_message(store, cid, "View dealer details", value="1")
    assert turn.conversation.title == "My next car"


def test_rename_rejects_empty_titles_and_unknown_ids(
    store: ConversationStore, chat: ChatService
) -> None:
    cid = chat.start_conversation(store).conversation.id
    with pytest.raises(InvalidTitleError):
        chat.rename_conversation(store, cid, "   ")
    with pytest.raises(ConversationNotFoundError):
        chat.rename_conversation(store, "not-a-real-id", "Title")
    assert chat.get_conversation(store, cid).conversation.title == "New conversation"


def test_delete_removes_conversation_and_messages(
    store: ConversationStore, chat: ChatService
) -> None:
    keep = chat.start_conversation(store).conversation.id
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")

    with pytest.raises(ConversationNotFoundError):
        chat.delete_conversation(store, "not-a-real-id")
    chat.delete_conversation(store, cid)

    assert [c.id for c in chat.list_conversations(store)] == [keep]
    with pytest.raises(ConversationNotFoundError):
        chat.get_conversation(store, cid)
    assert store.list_messages(cid) == []  # messages were removed along with the conversation
    with pytest.raises(ConversationNotFoundError):
        chat.delete_conversation(store, cid)


def test_failed_turn_stores_nothing(
    store: ConversationStore, chat: ChatService, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = chat.start_conversation(store).conversation.id

    def boom(*args: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(FakeLLMClient, "interpret_message", boom)
    with pytest.raises(RuntimeError):
        chat.send_message(store, cid, "I want a BMW")
    assert len(chat.get_conversation(store, cid).messages) == 1


def test_buttons_do_not_lock_the_conversation(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")
    chat.send_message(store, cid, "View dealer details", value="1")

    turn = chat.send_message(store, cid, "Actually show me a Toyota Corolla instead")
    assert "(1)" in turn.assistant_message.content
    assert [r.label for r in turn.quick_replies] == [
        "Toyota Corolla 1.8 Hybrid (2023)",
        "Toyota Corolla 1.6 Petrol (2023)",
    ]
    assert turn.conversation.title == "Toyota Corolla Inquiry"


def test_follow_up_context_survives_between_turns(
    store: ConversationStore, chat: ChatService
) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a Toyota Corolla")  # each turn restores saved state
    turn = chat.send_message(store, cid, "Tell me about the second one")
    assert "1.6 Petrol" in turn.assistant_message.content
    turn = chat.send_message(store, cid, "Who is the dealer?")
    assert "contact@utrechtauto.nl" in turn.assistant_message.content


def test_scheduled_call_then_keep_chatting(store: ConversationStore, chat: ChatService) -> None:
    cid = chat.start_conversation(store).conversation.id
    chat.send_message(store, cid, "I want a BMW 3 Series")
    chat.send_message(store, cid, "Schedule a call", value="2")
    chat.send_message(store, cid, "tomorrow")
    turn = chat.send_message(store, cid, "thanks")
    assert "You're welcome" in turn.assistant_message.content
    turn = chat.send_message(store, cid, "I want a Volkswagen Golf")
    assert "Rotterdam Car Hub" in turn.assistant_message.content
    assert turn.conversation.is_done is False
