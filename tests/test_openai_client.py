"""Tests for OpenAIClient's parsing of LangChain's tool-call responses.

No real API key is needed: `ChatOpenAI` is mocked out entirely, and `self.llm.invoke` is made to
return a canned LangChain response. These exist because `interpret_message`/`parse_datetime` are
never exercised through the real client in the rest of the suite (which uses `FakeLLMClient`), so
a parsing regression here would otherwise only surface against the live API.
"""

from unittest.mock import MagicMock, patch

import pytest

from car_dealer_chatbot.llm.base import LLMError
from car_dealer_chatbot.llm.openai_client import OpenAIClient


def _client() -> OpenAIClient:
    with patch("car_dealer_chatbot.llm.openai_client.ChatOpenAI"):
        return OpenAIClient(api_key="test-key")


def _respond_with(tool_calls: list) -> MagicMock:
    response = MagicMock()
    response.tool_calls = tool_calls
    return response


def test_interpret_message_reads_dict_args_from_langchain() -> None:
    """LangChain parses tool-call arguments into a dict; they must not be re-parsed as JSON."""
    client = _client()
    client.llm.bind_tools.return_value.invoke.return_value = _respond_with(
        [{"name": "interpret_message", "args": {"intent": "search", "car_query": "BMW"}}]
    )
    intent = client.interpret_message("Show me BMWs", "")
    assert intent.name == "search"
    assert intent.car_query == "BMW"


def test_interpret_message_reads_json_string_args() -> None:
    """A raw JSON string in `args` (as some providers/versions return) is still decoded."""
    client = _client()
    client.llm.bind_tools.return_value.invoke.return_value = _respond_with(
        [{"name": "interpret_message", "args": '{"intent": "search", "car_query": "Audi"}'}]
    )
    intent = client.interpret_message("Show me Audis", "")
    assert intent.name == "search"
    assert intent.car_query == "Audi"


def test_interpret_message_falls_back_to_unclear_on_malformed_args() -> None:
    client = _client()
    client.llm.bind_tools.return_value.invoke.return_value = _respond_with(
        [{"name": "interpret_message", "args": "not json"}]
    )
    intent = client.interpret_message("???", "")
    assert intent.name == "unclear"


def test_interpret_message_falls_back_to_unclear_with_no_tool_call() -> None:
    client = _client()
    client.llm.bind_tools.return_value.invoke.return_value = _respond_with([])
    intent = client.interpret_message("hello", "")
    assert intent.name == "unclear"


def test_interpret_message_raises_llm_error_on_api_failure() -> None:
    client = _client()
    client.llm.bind_tools.return_value.invoke.side_effect = RuntimeError("network down")
    with pytest.raises(LLMError):
        client.interpret_message("hello", "")


def test_parse_datetime_reads_dict_args_from_langchain() -> None:
    client = _client()
    client.llm.bind_tools.return_value.invoke.return_value = _respond_with(
        [
            {
                "name": "record_call_slot",
                "args": {
                    "explicit_date": "",
                    "days_from_today": 1,
                    "weekday": "",
                    "time": "15:00",
                },
            }
        ]
    )
    from datetime import datetime

    parsed = client.parse_datetime("tomorrow at 3pm", reference_date=datetime(2026, 1, 1, 9, 0))
    assert parsed is not None
    assert (parsed.day, parsed.hour, parsed.minute) == (2, 15, 0)
