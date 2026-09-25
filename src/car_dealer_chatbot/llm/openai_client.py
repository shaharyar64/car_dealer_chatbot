"""OpenAI LLM client implementation using LangChain."""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..intents import Intent
from ..logging_config import LOGGER_NAME
from ..scheduling import resolve_slot, slot_parts_from_dict
from .base import LLMClient, LLMError
from .prompts import (
    INTERPRET_MESSAGE_SYSTEM,
    INTERPRET_MESSAGE_TOOLS,
    PARSE_DATETIME_SYSTEM,
    PARSE_DATETIME_TOOLS,
)

logger = logging.getLogger(LOGGER_NAME)


class OpenAIClient(LLMClient):
    """OpenAI GPT-based LLM client using LangChain for structured extraction via tool calling."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = 20.0,
        max_retries: int = 2,
    ):
        """Initialize the LangChain-based OpenAI client."""
        self.model = model
        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0,
            request_timeout=timeout,
            max_retries=max_retries,
        )

    def _call_tool(self, system_prompt: str, user_text: str, tools: list) -> dict[str, Any]:
        """
        Force a single tool call and return its parsed arguments.

        Raises LLMError when the API call itself fails; returns an empty dict
        when the model's response can't be parsed.
        """
        try:
            messages: list[BaseMessage] = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_text),
            ]

            llm = self.llm.bind_tools(tools, tool_choice=tools[0]["function"]["name"])
            response = llm.invoke(messages)
        except Exception as exc:
            logger.error(f"OpenAI API call failed: {type(exc).__name__}: {exc}")
            raise LLMError(str(exc)) from exc

        tool_calls = response.tool_calls
        if not tool_calls:
            logger.warning("OpenAI response contained no tool call")
            return {}
        try:
            args = tool_calls[0]["args"]
        except KeyError as exc:
            logger.warning(f"Tool call had no arguments: {exc}")
            return {}
        # LangChain parses tool-call arguments into a dict itself; only raw JSON needs decoding.
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError as exc:
                logger.warning(f"Could not parse tool arguments: {exc}")
                return {}
        if not isinstance(args, dict):
            logger.warning(f"Unexpected tool arguments type: {type(args).__name__}")
            return {}
        return args

    def interpret_message(self, user_text: str, context: str) -> Intent:
        """Classify the message and extract its car/filter details, given the conversation."""
        system_prompt = f"{INTERPRET_MESSAGE_SYSTEM}\n\nConversation context:\n{context}"
        args = self._call_tool(system_prompt, user_text, INTERPRET_MESSAGE_TOOLS)
        intent = Intent.from_dict(args) if args else Intent("unclear")
        logger.info(f"Interpreted {user_text!r} as {intent}")
        return intent

    def parse_datetime(
        self, user_text: str, reference_date: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Extract slot components with the LLM, then resolve the date deterministically."""
        reference_date = reference_date or datetime.now()
        system_prompt = (
            f"{PARSE_DATETIME_SYSTEM}\n\n"
            f"Current date and time: {reference_date.strftime('%A %Y-%m-%d %H:%M')}"
        )
        args = self._call_tool(system_prompt, user_text, PARSE_DATETIME_TOOLS)
        parts = slot_parts_from_dict(args)
        logger.info(f"Slot parts for {user_text!r}: {parts}")
        return resolve_slot(parts, reference_date)
