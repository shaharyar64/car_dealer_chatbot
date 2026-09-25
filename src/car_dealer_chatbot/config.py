"""Configuration and environment variable handling."""

import os
from pathlib import Path

from dotenv import load_dotenv

# src/car_dealer_chatbot/config.py -> project root is three levels up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env() -> None:
    """Load environment variables from the project's .env file, if present."""
    load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(env_var: str, default: Path) -> Path:
    """Read a path from the environment, resolving relative paths against the project root."""
    value = os.getenv(env_var)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


class Config:
    """Application configuration."""

    @staticmethod
    def get_openai_api_key() -> str:
        """Get the OpenAI API key from the environment."""
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key or key.startswith("your_") or key == "sk-your-api-key-here":
            raise ValueError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        return key

    @staticmethod
    def get_llm_model() -> str:
        """Get the LLM model name from the environment."""
        return os.getenv("LLM_MODEL", "gpt-4o-mini")

    @staticmethod
    def get_cars_data_path() -> Path:
        """Get the path to the cars CSV file."""
        return _resolve_path("CARS_DATA_PATH", PROJECT_ROOT / "data" / "cars.csv")

    @staticmethod
    def get_dealers_data_path() -> Path:
        """Get the path to the dealers CSV file."""
        return _resolve_path("DEALERS_DATA_PATH", PROJECT_ROOT / "data" / "dealers.csv")

    @staticmethod
    def get_log_level() -> str:
        """Get the logging level from the environment."""
        return os.getenv("LOG_LEVEL", "INFO").upper()
