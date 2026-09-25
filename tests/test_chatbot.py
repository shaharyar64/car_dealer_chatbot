"""Tests for the chatbot's core behaviour on a small sample inventory."""

import pytest

from car_dealer_chatbot.core import Chatbot
from car_dealer_chatbot.core.chatbot import (
    LLM_UNAVAILABLE_MESSAGE,
    MAX_HISTORY_MESSAGES,
    OPTIONS_ACTIONS,
    OPTIONS_CARS,
)
from car_dealer_chatbot.models import Car, Dealer, Intent

from .conftest import FailingLLMClient, FakeLLMClient


@pytest.fixture
def chatbot(sample_cars: list[Car], sample_dealers: list[Dealer]) -> Chatbot:
    """A chatbot backed by the fake LLM client."""
    return Chatbot(sample_cars, sample_dealers, FakeLLMClient())


def test_initial_state(chatbot: Chatbot) -> None:
    assert chatbot.current_car is None and chatbot.offered is None
    assert "which car" in chatbot.get_greeting().lower()


@pytest.mark.parametrize("command", ["exit", "QUIT", " bye "])
def test_exit_commands_end_cli_session(chatbot: Chatbot, command: str) -> None:
    reply, done = chatbot.process_input(command)
    assert done is True
    assert "goodbye" in reply.lower()


def test_empty_input_reprompts(chatbot: Chatbot) -> None:
    reply, done = chatbot.process_input("   ")
    assert done is False
    assert "type a message" in reply


def test_unique_match_shows_car_and_menu(chatbot: Chatbot) -> None:
    reply, done = chatbot.process_input("I want a BMW 3 Series")
    assert done is False
    assert "BMW 3 Series 320i" in reply
    assert "Amsterdam Motors" in reply
    assert chatbot.offered == OPTIONS_ACTIONS


def test_car_not_found_lists_available_makes(chatbot: Chatbot) -> None:
    reply, done = chatbot.process_input("Do you have a Tesla Model 3?")
    assert done is False
    assert "couldn't find" in reply.lower()
    assert "Toyota" in reply and "BMW" in reply


def test_ambiguous_match_lists_numbered_candidates(chatbot: Chatbot) -> None:
    reply, done = chatbot.process_input("I want a Toyota Corolla")
    assert done is False
    assert "(1)" in reply and "(2)" in reply
    assert chatbot.offered == OPTIONS_CARS


def test_pick_candidate_by_number(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    chatbot.process_input("2")
    assert chatbot.offered == OPTIONS_ACTIONS
    assert chatbot.current_car is not None
    assert chatbot.current_car.variant == "1.6 Petrol"


def test_pick_candidate_out_of_range(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    reply, _ = chatbot.process_input("7")
    assert "between 1 and 2" in reply
    assert chatbot.offered == OPTIONS_CARS


def test_narrow_down_by_variant(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    chatbot.process_input("Toyota Corolla hybrid")
    assert chatbot.current_car is not None
    assert chatbot.current_car.variant == "1.8 Hybrid"


def test_dealer_details_by_number(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, done = chatbot.process_input("1")
    assert done is False
    assert "Amsterdam Motors" in reply
    assert "+31 20 234 5678" in reply
    assert "info@amsterdammotors.nl" in reply
    assert "anything else" in reply.lower()
    assert chatbot.offered == OPTIONS_ACTIONS
    assert chatbot.last_action == "dealer_details"


def test_dealer_details_by_free_text(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, done = chatbot.process_input("show me the dealer details please")
    assert done is False
    assert "Amsterdam Motors" in reply


def test_unclear_message_does_not_demand_a_menu_choice(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, done = chatbot.process_input("???")
    assert done is False
    assert "not sure what you mean" in reply
    assert "(1)" not in reply
    assert chatbot.current_car is not None  # context is kept
    assert chatbot.offered == OPTIONS_ACTIONS  # the buttons still work


def test_a_different_car_after_the_menu(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, _ = chatbot.process_input("Volkswagen Golf")
    assert "Rotterdam Car Hub" in reply
    assert chatbot.current_car is not None and chatbot.current_car.model == "Golf"


def test_new_search_after_details(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("1")
    reply, _ = chatbot.process_input("Toyota Corolla")
    assert "(1)" in reply and "(2)" in reply  # two Corolla variants to choose from
    chatbot.process_input("1")
    assert chatbot.current_car is not None and chatbot.current_car.variant == "1.8 Hybrid"


def test_can_schedule_after_seeing_details(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("1")
    chatbot.process_input("2")
    reply, done = chatbot.process_input("tomorrow")
    assert done is False
    assert "Call scheduled with Amsterdam Motors" in reply
    assert chatbot.last_action == "scheduled_call"


def test_schedule_call_confirms_dealer_phone_and_slot(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, _ = chatbot.process_input("Schedule a call please")
    assert "date and time" in reply
    assert chatbot.awaiting_datetime

    reply, done = chatbot.process_input("tomorrow at 3pm")
    assert done is False
    assert not chatbot.awaiting_datetime
    assert "Amsterdam Motors" in reply
    assert "+31 20 234 5678" in reply
    assert "15:00" in reply
    assert chatbot.scheduled_datetime is not None


def test_schedule_with_time_in_one_message(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, _ = chatbot.process_input("Can you schedule a call tomorrow?")
    assert "Call scheduled with Amsterdam Motors" in reply


def test_unparseable_datetime_reprompts(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("2")
    reply, done = chatbot.process_input("whenever")
    assert done is False
    assert "couldn't understand" in reply.lower()
    assert chatbot.awaiting_datetime


def test_past_datetime_rejected(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("2")
    reply, done = chatbot.process_input("yesterday")
    assert done is False
    assert "past" in reply.lower()
    assert chatbot.awaiting_datetime


def test_scheduling_does_not_block_other_requests(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("2")
    reply, _ = chatbot.process_input("Actually show me a Volkswagen Golf instead")
    assert "Volkswagen Golf" in reply and "Rotterdam Car Hub" in reply
    assert not chatbot.awaiting_datetime  # the call was about another car


def test_numbers_only_mean_something_when_options_were_offered(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("1")
    assert "not sure what you mean" in reply


def test_greeting_does_not_search(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("hello!")
    assert "help you find a car" in reply
    assert chatbot.last_intent == "greeting"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("good morning", "Good morning!"),
        ("thanks", "You're welcome"),
        ("Thank you!", "You're welcome"),
        ("okay", "What kind of car"),
        ("sounds good", "What kind of car"),
    ],
)
def test_small_talk_needs_no_llm(
    sample_cars: list[Car], sample_dealers: list[Dealer], text: str, expected: str
) -> None:
    bot = Chatbot(sample_cars, sample_dealers, FailingLLMClient())
    reply, done = bot.process_input(text)
    assert expected in reply and done is False


def test_small_talk_keeps_the_open_list(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    chatbot.process_input("thanks")
    chatbot.process_input("2")
    assert chatbot.current_car is not None and chatbot.current_car.variant == "1.6 Petrol"


def test_body_type_without_data_asks_for_other_criteria(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("Do you have SUVs?")
    assert "don't have body-type information" in reply


def test_unknown_city_is_clarified(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("Show me a BMW in Oslo")
    assert "don't have a dealer in" in reply and "Amsterdam" in reply


def test_missing_dealer_is_handled(sample_dealers: list[Dealer]) -> None:
    orphan = Car("C9", "Lada", "Niva", "1.7 4x4", 2020, 9000, "D999")
    bot = Chatbot([orphan], sample_dealers, FakeLLMClient())
    reply, done = bot.process_input("I want a Lada Niva")
    assert done is False
    assert "temporarily unavailable" in reply
    assert bot.current_car is None


def test_llm_failure_is_reported_gracefully(
    sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    bot = Chatbot(sample_cars, sample_dealers, FailingLLMClient())
    reply, done = bot.process_input("I want a BMW")
    assert reply == LLM_UNAVAILABLE_MESSAGE
    assert done is False


def test_reset_starts_fresh(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.reset()
    assert chatbot.current_car is None and chatbot.history == []


def test_history_is_kept_short(chatbot: Chatbot) -> None:
    for _ in range(MAX_HISTORY_MESSAGES):
        chatbot.process_input("hello")
    assert len(chatbot.history) == MAX_HISTORY_MESSAGES


def test_remembers_what_the_user_said(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("hi my name is shaharyar")
    assert reply.startswith("Hi Shaharyar!")
    assert chatbot.process_input("what is my name")[0] == "Your name is Shaharyar."


def test_facts_outlive_the_message_history(chatbot: Chatbot) -> None:
    chatbot.process_input("my name is shaharyar")
    for _ in range(MAX_HISTORY_MESSAGES):
        chatbot.process_input("hello")
    assert all("shaharyar" not in message for _, message in chatbot.history)
    assert chatbot.process_input("what is my name")[0] == "Your name is Shaharyar."


def test_corrections_replace_earlier_facts(chatbot: Chatbot) -> None:
    chatbot.process_input("my name is shaharyar")
    reply, _ = chatbot.process_input("actually, call me sarah")
    assert reply == "Got it, Sarah! What kind of car are you looking for?"
    assert chatbot.facts == {"name": "Sarah"}
    assert chatbot.process_input("what is my name")[0] == "Your name is Sarah."


def test_recall_without_the_answer_in_context(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("what is my name")
    assert "haven't told me" in reply or "told me that yet" in reply


def test_recall_keeps_the_conversation_where_it_was(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    chatbot.process_input("my name is shaharyar")
    chatbot.process_input("what is my name")
    assert chatbot.offered == OPTIONS_CARS
    assert chatbot.process_input("2")[0].startswith("I found: Toyota Corolla 1.6 Petrol")


def test_facts_are_learned_from_any_intent(
    sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    llm = FakeLLMClient()
    llm.interpret_message = lambda text, context: Intent(  # type: ignore[method-assign]
        "search", car_query="Toyota", facts=(("budget", "up to €25,000"), ("city", "Utrecht"))
    )
    chatbot = Chatbot(sample_cars, sample_dealers, llm)
    chatbot.process_input("A Toyota under 25k in Utrecht please")
    assert chatbot.facts == {"budget": "up to €25,000", "city": "Utrecht"}
    assert "  budget: up to €25,000" in chatbot._context(None)


def test_sharing_information_is_acknowledged_not_misunderstood(
    sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    llm = FakeLLMClient()
    llm.interpret_message = lambda text, context: Intent(  # type: ignore[method-assign]
        "general_question", facts=(("city", "Lahore"),)
    )
    chatbot = Chatbot(sample_cars, sample_dealers, llm)
    reply, _ = chatbot.process_input("I live in Lahore")
    assert reply == "Got it, I'll keep that in mind. What kind of car are you looking for?"


def _restored(chatbot: Chatbot) -> Chatbot:
    """A new chatbot restored from `chatbot`'s exported state."""
    clone = Chatbot(chatbot.cars, chatbot.dealers, chatbot.llm_client)
    clone.restore_state(chatbot.export_state())
    return clone


def test_state_round_trip_with_candidates(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    clone = _restored(chatbot)
    assert clone.offered == OPTIONS_CARS
    assert clone.candidates == chatbot.candidates
    assert clone.history == chatbot.history
    clone.process_input("2")
    assert clone.current_car is not None and clone.current_car.variant == "1.6 Petrol"


def test_state_round_trip_with_facts(chatbot: Chatbot) -> None:
    chatbot.process_input("my name is shaharyar")
    clone = _restored(chatbot)
    assert clone.facts == {"name": "Shaharyar"}
    assert clone.process_input("what is my name")[0] == "Your name is Shaharyar."


def test_restore_ignores_malformed_facts(chatbot: Chatbot) -> None:
    chatbot.restore_state({"facts": {"name": "Shaharyar", "budget": 5, "": "x"}})
    assert chatbot.facts == {"name": "Shaharyar"}
    chatbot.restore_state({"facts": ["name", "Shaharyar"]})
    assert chatbot.facts == {}


def test_state_round_trip_mid_scheduling(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("2")
    clone = _restored(chatbot)
    assert clone.awaiting_datetime
    assert clone.current_dealer == chatbot.current_dealer
    reply, done = clone.process_input("tomorrow")
    assert done is False and "Amsterdam Motors" in reply


def test_state_round_trip_after_scheduling(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    chatbot.process_input("2")
    chatbot.process_input("tomorrow")
    clone = _restored(chatbot)
    assert clone.offered == OPTIONS_ACTIONS
    assert clone.scheduled_datetime == chatbot.scheduled_datetime


def test_state_round_trip_keeps_filters(chatbot: Chatbot) -> None:
    chatbot.process_input("Show me cars above 30k")
    assert _restored(chatbot).filters == chatbot.filters


def test_goodbye_does_not_end_web_conversation(
    sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    bot = Chatbot(sample_cars, sample_dealers, FakeLLMClient(), end_on_exit=False)
    bot.process_input("I want a BMW 3 Series")
    reply, done = bot.process_input("bye")
    assert done is False and "Goodbye" in reply
    reply, done = bot.process_input("I want a Volkswagen Golf")
    assert done is False and "Rotterdam Car Hub" in reply


def test_restored_menu_accepts_a_number(chatbot: Chatbot) -> None:
    chatbot.restore_state({"offered": OPTIONS_ACTIONS, "car_id": "C003", "candidate_ids": []})
    reply, done = chatbot.process_input("1")
    assert done is False and "Amsterdam Motors" in reply


def test_restore_with_unknown_car_starts_over(chatbot: Chatbot) -> None:
    chatbot.restore_state({"offered": OPTIONS_ACTIONS, "car_id": "GONE", "candidate_ids": []})
    assert chatbot.current_car is None and chatbot.offered is None


def test_restore_with_garbage_state_starts_over(chatbot: Chatbot) -> None:
    chatbot.restore_state({"offered": "nonsense", "history": [1, ["x"]], "filters": "bad"})
    assert chatbot.current_car is None and chatbot.offered is None and chatbot.history == []


def test_non_ascii_digit_does_not_crash(chatbot: Chatbot) -> None:
    chatbot.process_input("Toyota Corolla")
    reply, done = chatbot.process_input("²")
    assert done is False and reply


def test_inventory_question_gets_an_overview(chatbot: Chatbot) -> None:
    reply, _ = chatbot.process_input("what cars do you have?")
    assert reply.startswith("We have 4 cars in stock from 3 makes, priced from €24,900 to €52,000.")
    assert "  Makes: BMW, Toyota, Volkswagen" in reply
    assert "  Dealer cities: Amsterdam, Rotterdam, Utrecht" in reply
    assert "Body types" not in reply  # the sample cars have no body type
    assert chatbot.offered is None


@pytest.mark.parametrize(
    ("sort", "header", "first_price"),
    [
        ("price_asc", "Here are our cheapest cars:", "€24,900"),
        ("price_desc", "Here are our most expensive cars:", "€52,000"),
    ],
)
def test_cheapest_or_most_expensive_without_criteria(
    sample_cars: list[Car], sample_dealers: list[Dealer], sort: str, header: str, first_price: str
) -> None:
    llm = FakeLLMClient()
    llm.interpret_message = lambda text, context: Intent("search", sort=sort)  # type: ignore[method-assign]
    chatbot = Chatbot(sample_cars, sample_dealers, llm)
    reply, _ = chatbot.process_input("what is your cheapest car?")
    assert reply.startswith(header)
    assert first_price in chatbot._describe_car(chatbot.candidates[0])
    assert chatbot.offered == OPTIONS_CARS


def _search_bot(
    sample_cars: list[Car], sample_dealers: list[Dealer], car_query: str, **filters: object
) -> Chatbot:
    """A chatbot whose LLM reads every message as a search for `car_query`."""
    llm = FakeLLMClient()
    llm.interpret_message = lambda text, context: Intent(  # type: ignore[method-assign]
        "search", car_query=car_query, **filters
    )
    return Chatbot(sample_cars, sample_dealers, llm)


def test_search_for_several_makes(sample_cars: list[Car], sample_dealers: list[Dealer]) -> None:
    chatbot = _search_bot(sample_cars, sample_dealers, "Toyota, BMW, Volkswagen")
    reply, _ = chatbot.process_input("tell me about toyota, bmw and volkswagen")
    assert reply.startswith("I found 4 Toyota Corolla, BMW and Volkswagen cars:")
    # The makes take turns, so a shortened list still shows each of them.
    assert [car.make for car in chatbot.candidates] == ["Toyota", "BMW", "Volkswagen", "Toyota"]


def test_several_makes_with_a_price_filter(
    sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    chatbot = _search_bot(sample_cars, sample_dealers, "Toyota, BMW", max_price=30000)
    reply, _ = chatbot.process_input("toyota or bmw under 30k")
    assert reply.startswith("I found 2 Toyota Corolla and BMW cars priced up to €30,000:")
    assert {car.make for car in chatbot.candidates} == {"Toyota"}


def test_makes_we_do_not_carry_are_mentioned(
    sample_cars: list[Car], sample_dealers: list[Dealer]
) -> None:
    chatbot = _search_bot(sample_cars, sample_dealers, "Tesla, BMW")
    reply, _ = chatbot.process_input("do you have tesla or bmw?")
    assert reply.startswith("We don't carry Tesla at the moment.")
    assert "BMW 3 Series 320i" in reply
    assert chatbot.filters.car_query == "BMW"

    chatbot = _search_bot(sample_cars, sample_dealers, "Tesla, Lada")
    reply, _ = chatbot.process_input("tesla or lada?")
    assert reply.startswith("Sorry, I couldn't find 'Tesla, Lada' in our inventory.")


# ---------------------------------------------------------------------------------------------
# Contextual follow-ups: short messages that only make sense in light of the conversation so far.


def test_follow_up_options_reuses_the_last_search(chatbot: Chatbot) -> None:
    """'tell me the options' re-shows the search already in progress, not a generic apology."""
    chatbot.process_input("I want a Toyota Corolla")
    reply, done = chatbot.process_input("tell me the options")
    assert done is False
    assert "not sure what you mean" not in reply
    assert "1.8 Hybrid" in reply and "1.6 Petrol" in reply
    assert chatbot.offered == OPTIONS_CARS


def test_pronoun_it_refers_to_the_car_being_discussed(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, done = chatbot.process_input("how much is it?")
    assert done is False
    assert "€52,000" in reply


def test_ordinal_reference_picks_the_right_result(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    reply, done = chatbot.process_input("what's the second one?")
    assert done is False
    assert "1.6 Petrol" in reply
    assert chatbot.current_car is not None and chatbot.current_car.variant == "1.6 Petrol"


def test_their_refers_to_the_dealer_being_discussed(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a BMW 3 Series")
    reply, done = chatbot.process_input("show me their details")
    assert done is False
    assert "Amsterdam Motors" in reply and "+31 20 234 5678" in reply


def test_what_is_my_name_after_stating_it(chatbot: Chatbot) -> None:
    chatbot.process_input("My name is Shaharyar.")
    reply, done = chatbot.process_input("What is my name?")
    assert done is False
    assert reply == "Your name is Shaharyar."


def test_mixed_request_and_personal_fact_are_both_handled(chatbot: Chatbot) -> None:
    """A name stated alongside a request must not derail the request (or vice versa)."""
    reply, done = chatbot.process_input("Show me BMW 3 Series and my name is Shaharyar.")
    assert done is False
    assert "not sure what you mean" not in reply
    assert "BMW 3 Series 320i" in reply
    assert chatbot.facts.get("name") == "Shaharyar"


def test_price_filter_after_search_narrows_the_open_search(chatbot: Chatbot) -> None:
    chatbot.process_input("I want a Toyota Corolla")
    reply, done = chatbot.process_input("only under €27,000")
    assert done is False
    assert chatbot.current_car is not None and chatbot.current_car.variant == "1.6 Petrol"


def test_unrelated_request_switches_away_from_the_open_search(chatbot: Chatbot) -> None:
    """A new topic (scheduling) takes over instead of continuing the interrupted search."""
    chatbot.process_input("I want a Toyota Corolla")
    reply, done = chatbot.process_input("I want to schedule a call.")
    assert done is False
    assert "schedule a call" in reply.lower()
    assert chatbot.pending_action == "schedule_call"

    reply, _ = chatbot.process_input("1")
    assert "date and time" in reply.lower()


def test_reported_bug_options_request_with_a_name_in_the_same_message(chatbot: Chatbot) -> None:
    """
    Reproduces the exact reported failure: a first message mixing a vague request ('tell me the
    options') with an unrelated personal statement must not fall back to the generic apology, and
    the name must still be usable afterwards.
    """
    reply, done = chatbot.process_input("tell me the options my name is shaharyar")
    assert done is False
    assert "not sure what you mean" not in reply
    assert chatbot.facts.get("name") == "Shaharyar"

    reply, done = chatbot.process_input("tell me the options")
    assert done is False
    assert "not sure what you mean" not in reply

    reply, done = chatbot.process_input("what is my name")
    assert done is False
    assert reply == "Your name is Shaharyar."
