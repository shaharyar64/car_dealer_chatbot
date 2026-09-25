"""Multi-turn conversation scenarios on the real inventory: context, follow-ups, changes of mind."""

import pytest

from car_dealer_chatbot.core import Chatbot
from car_dealer_chatbot.core.chatbot import OPTIONS_CARS
from car_dealer_chatbot.models import Car, Dealer

from .conftest import FakeLLMClient


@pytest.fixture
def bot(inventory: tuple[list[Car], list[Dealer]]) -> Chatbot:
    cars, dealers = inventory
    return Chatbot(cars, dealers, FakeLLMClient(), end_on_exit=False)


def say(bot: Chatbot, text: str) -> str:
    reply, done = bot.process_input(text)
    assert done is False, "a web conversation never ends by itself"
    assert "conversation has ended" not in reply
    return reply


def test_greeting_then_search(bot: Chatbot) -> None:
    assert "How can I help you find a car" in say(bot, "hi")
    reply = say(bot, "I'm looking for a BMW")
    assert "I found 4 BMW cars" in reply
    assert "BMW X5" in reply and "BMW 1 Series" in reply


def test_change_of_mind_to_another_make(bot: Chatbot) -> None:
    say(bot, "Show me a BMW")
    reply = say(bot, "Actually show me Mercedes instead")
    assert "Mercedes-Benz C-Class" in reply and "Mercedes-Benz GLC" in reply
    assert "BMW" not in reply


def test_follow_up_questions_use_context(bot: Chatbot) -> None:
    reply = say(bot, "Show me BMW 3 Series")
    assert "(1) BMW 3 Series 320i M Sport" in reply
    assert "(2) BMW 3 Series 330i xDrive" in reply

    reply = say(bot, "Tell me about the second one")
    assert "330i xDrive" in reply and "€65,000" in reply

    reply = say(bot, "Who is the dealer?")
    assert "Rotterdam Car Hub" in reply and "+31 10 345 6789" in reply


def test_price_filter_then_refine(bot: Chatbot) -> None:
    reply = say(bot, "Show me cars above €50,000")
    assert "cars priced €50,000 or more" in reply
    assert "(1) Seat Tarraco 2.0 TDI Xcellence (2023) - €51,000" in reply  # cheapest first

    reply = say(bot, "Only BMW")
    assert "I found 3 BMW cars priced €50,000 or more" in reply
    assert "320i" in reply and "330i" in reply and "X5" in reply
    assert "1 Series" not in reply  # €34,500 is below the budget that still applies


def test_dealer_details_then_keep_chatting(bot: Chatbot) -> None:
    say(bot, "I want a BMW 3 Series 320i")
    reply = say(bot, "Show me the dealer details")
    assert "sales@rotcarhub.nl" in reply

    reply = say(bot, "What other cars does this dealer sell?")
    assert "Rotterdam Car Hub (Rotterdam) has these other cars" in reply
    assert "330i xDrive" in reply and "Citroën C5" in reply and "320i" not in reply

    reply = say(bot, "What other cars are available?")
    assert "Besides the BMW 3 Series 320i M Sport" in reply and "Porsche" in reply


def test_scheduling_then_new_search(bot: Chatbot) -> None:
    say(bot, "I want a BMW 3 Series 320i")
    assert "date and time" in say(bot, "I want to schedule a call")

    reply = say(bot, "Friday at 3 PM")
    assert "Call scheduled with Rotterdam Car Hub" in reply and "Friday" in reply
    assert "15:00" in reply

    reply = say(bot, "Now show me other cars")
    assert "we have 78 cars in stock" in reply


def test_casual_conversation(bot: Chatbot) -> None:
    say(bot, "hi")
    assert "You're welcome" in say(bot, "thanks")
    assert "I found 4 BMW cars" in say(bot, "Can you show me BMWs?")


def test_change_of_mind_while_menu_is_offered(bot: Chatbot) -> None:
    say(bot, "I want a BMW 3 Series 320i")
    reply = say(bot, "I changed my mind. Show me other cars above €50,000.")
    assert "other cars priced €50,000 or more" in reply
    assert "Reply (1) or (2)" not in reply and "320i" not in reply


def test_full_context_chain(bot: Chatbot) -> None:
    say(bot, "I'm looking for a BMW")
    say(bot, "Show me the 3 Series")
    assert "€65,000" in say(bot, "What is the price of the second one?")
    assert "Rotterdam Car Hub" in say(bot, "Who sells it?")
    assert "Rotterdam" in say(bot, "Where are they located?")
    assert "Rotterdam Car Hub" in say(bot, "Can I schedule a call?")
    assert bot.awaiting_datetime


def test_cheaper_one_and_something_cheaper(bot: Chatbot) -> None:
    say(bot, "Show me BMW 3 Series")
    assert "320i M Sport" in say(bot, "Tell me about the cheaper one")

    say(bot, "Tell me about the second one")  # the list is still in context
    assert bot.current_car is not None and bot.current_car.variant == "330i xDrive"
    reply = say(bot, "Show me something cheaper")
    assert "320i M Sport" in reply  # the only cheaper BMW 3 Series


def test_ambiguous_reference_is_clarified_then_resolved(bot: Chatbot) -> None:
    say(bot, "Show me BMW 3 Series")
    reply = say(bot, "Who is the dealer?")
    assert "Which car's dealer" in reply and "(2)" in reply
    assert bot.offered == OPTIONS_CARS

    reply = say(bot, "2")
    assert "The BMW 3 Series 330i xDrive (2023) is sold by Rotterdam Car Hub" in reply


def test_body_type_and_price(bot: Chatbot) -> None:
    reply = say(bot, "Do you have SUVs above €80,000?")
    assert "I found 2 SUVs priced €80,000 or more" in reply
    assert "BMW X5" in reply and "Land Rover Defender" in reply


def test_make_in_city(bot: Chatbot) -> None:
    reply = say(bot, "What BMWs are available in Rotterdam?")
    assert "from dealers in Rotterdam" in reply
    assert "320i" in reply and "330i" in reply and "X5" not in reply


def test_price_range(bot: Chatbot) -> None:
    reply = say(bot, "Show me Mercedes cars between €50k and €80k")
    assert "priced between €50,000 and €80,000" in reply
    assert "E-Class" in reply and "GLC" in reply and "C-Class" not in reply


def test_no_results_explains_why(bot: Chatbot) -> None:
    reply = say(bot, "Show me Porsche under 50k")
    assert "couldn't find any Porsche cars priced up to €50,000" in reply
    assert "between €78,900 and €145,000" in reply


def test_compare_listed_cars(bot: Chatbot) -> None:
    say(bot, "Show me BMW 3 Series")
    reply = say(bot, "compare them")
    assert "Here's how they compare" in reply
    assert "€13,000 less than" in reply
