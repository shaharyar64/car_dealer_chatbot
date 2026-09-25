"""Logging configuration."""

import logging
from typing import Optional

from .config import PROJECT_ROOT, Config

LOGGER_NAME = "car_dealer_chatbot"
LOG_FILE = PROJECT_ROOT / "logs" / "chatbot.log"


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure the application logger once.

    Full logs go to logs/chatbot.log; only warnings and errors reach the
    console so they don't clutter the chat. Safe to call repeatedly
    (e.g. on every Streamlit rerun).
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    level_name = (level or Config.get_log_level()).upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning(f"Could not open log file {LOG_FILE}: {exc}")

    return logger
