"""Command-line interface for the car dealer chatbot."""

import sys

from .chatbot import Chatbot
from .config import load_env
from .logging_config import setup_logging
from .repository import DataError
from .services.factory import build_llm_client, load_inventory


def build_chatbot() -> Chatbot:
    """Load configuration and data, and wire up a Chatbot with the configured LLM client."""
    llm_client = build_llm_client()
    cars, dealers = load_inventory()
    return Chatbot(cars=cars, dealers=dealers, llm_client=llm_client)


def main() -> int:
    """Run the interactive chat loop. Returns a process exit code."""
    load_env()
    logger = setup_logging()
    # Replies contain '€' and emoji; don't crash on consoles/pipes with a legacy encoding.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    try:
        chatbot = build_chatbot()
    except (ValueError, DataError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("Car Dealer Chatbot  (type 'exit' to quit)")
    print("=" * 60)
    print(f"\nBot: {chatbot.get_greeting()}\n")

    try:
        while True:
            user_input = input("You: ")
            if not user_input.strip():
                continue
            reply, is_done = chatbot.process_input(user_input)
            print(f"\nBot: {reply}\n")
            if is_done:
                return 0
    except (KeyboardInterrupt, EOFError):
        print("\n\nBot: Goodbye!")
        return 0
    except Exception:
        logger.exception("Unexpected error in chat loop")
        print("\nSomething went wrong. See logs/chatbot.log for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
