"""Builds the application's components from configuration (shared by the CLI and web app)."""

import logging
from dataclasses import dataclass

from ..config import Config, LOGGER_NAME
from ..data import DataError, load_cars, load_dealers
from ..llm import LLMClient
from ..llm.openai_client import OpenAIClient
from ..models import Car, Dealer
from .chat_service import ChatService

logger = logging.getLogger(LOGGER_NAME)


@dataclass(frozen=True)
class AppServices:
    """The services the UI needs, shared by all visitors of one app process."""

    chat: ChatService


def build_llm_client() -> LLMClient:
    """
    Create the configured LLM client; the one place to change to swap providers.

    Raises ValueError if the API key is missing.
    """
    api_key = Config.get_openai_api_key()
    model = Config.get_llm_model()
    logger.info(f"Using LLM model={model}")
    return OpenAIClient(api_key, model)


def load_inventory() -> tuple[list[Car], list[Dealer]]:
    """Load the car and dealer CSV files. Raises DataError if they are missing or empty."""
    cars = load_cars(Config.get_cars_data_path())
    dealers = load_dealers(Config.get_dealers_data_path())
    if not cars or not dealers:
        raise DataError("Car or dealer data is empty - check the CSV files in data/.")
    logger.info(f"Loaded {len(cars)} cars and {len(dealers)} dealers")
    return cars, dealers


def build_services() -> AppServices:
    """
    Load the CSV data and create the LLM client.

    Raises ValueError (e.g. missing API key) or DataError (bad CSV files).
    """
    llm_client = build_llm_client()
    cars, dealers = load_inventory()

    return AppServices(chat=ChatService(cars, dealers, llm_client))
