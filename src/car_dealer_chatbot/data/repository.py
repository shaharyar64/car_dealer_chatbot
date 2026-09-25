"""Data access layer for cars and dealers."""

import csv
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from ..config import LOGGER_NAME
from ..models import Car, Dealer

logger = logging.getLogger(LOGGER_NAME)


class DataError(Exception):
    """Raised when there's an error loading or accessing data."""


def load_cars(path: Path) -> list[Car]:
    """Load cars from CSV file."""
    try:
        cars = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise DataError(f"Invalid CSV file: {path}")

            for row in reader:
                try:
                    car = Car(
                        car_id=row["car_id"],
                        make=row["make"],
                        model=row["model"],
                        variant=row["variant"],
                        year=int(row["year"]),
                        price=int(row["price"]),
                        dealer_id=row["dealer_id"],
                        body_type=(row.get("body_type") or "").strip(),
                    )
                    cars.append(car)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping malformed car row: {row}. Error: {e}")
                    continue
        return cars
    except DataError:
        raise
    except FileNotFoundError as e:
        raise DataError(f"Cars data file not found: {path}") from e
    except Exception as e:
        raise DataError(f"Error loading cars data: {e}") from e


def load_dealers(path: Path) -> list[Dealer]:
    """Load dealers from CSV file."""
    try:
        dealers = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise DataError(f"Invalid CSV file: {path}")

            for row in reader:
                try:
                    dealer = Dealer(
                        dealer_id=row["dealer_id"],
                        name=row["name"],
                        city=row["city"],
                        phone=row["phone"],
                        email=row["email"],
                    )
                    dealers.append(dealer)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping malformed dealer row: {row}. Error: {e}")
                    continue
        return dealers
    except DataError:
        raise
    except FileNotFoundError as e:
        raise DataError(f"Dealers data file not found: {path}") from e
    except Exception as e:
        raise DataError(f"Error loading dealers data: {e}") from e


def find_dealer(dealer_id: str, dealers: list[Dealer]) -> Optional[Dealer]:
    """Find a dealer by ID."""
    for dealer in dealers:
        if dealer.dealer_id == dealer_id:
            return dealer
    return None


_FUZZY_TOKEN_THRESHOLD = 0.8
_MIN_FUZZY_TOKEN_LENGTH = 4


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, keeping decimals like '1.8' intact."""
    tokens = (token.strip(".") for token in re.findall(r"[\w.]+", text.lower()))
    return [token for token in tokens if token]


def _token_matches(query_token: str, car_tokens: list[str]) -> bool:
    """Return True if a query token matches any car token, tolerating typos."""
    for car_token in car_tokens:
        if query_token == car_token:
            return True
        # Short tokens such as "3" or "gt" must match exactly to avoid noise.
        if (
            len(query_token) >= _MIN_FUZZY_TOKEN_LENGTH
            and SequenceMatcher(None, query_token, car_token).ratio() >= _FUZZY_TOKEN_THRESHOLD
        ):
            return True
    return False


def search_cars(query: str, cars: list[Car]) -> list[Car]:
    """
    Search for cars by make, model and variant.

    Each query token is matched (exactly or fuzzily) against the car's tokens.
    A car qualifies only if a strict majority of query tokens match it, and
    only the best-scoring cars are returned. One result is a unique match;
    several results mean the query is ambiguous; none means not found.
    """
    query_tokens = _tokenize(query or "")
    if not query_tokens:
        return []

    scored: list[tuple[int, Car]] = []
    for car in cars:
        car_tokens = _tokenize(f"{car.make} {car.model} {car.variant}")
        hits = sum(_token_matches(token, car_tokens) for token in query_tokens)
        if hits * 2 > len(query_tokens):
            scored.append((hits, car))

    if not scored:
        return []

    best = max(hits for hits, _ in scored)
    return [car for hits, car in scored if hits == best]


def list_makes(cars: list[Car]) -> list[str]:
    """Return the sorted, distinct car makes in the inventory."""
    return sorted({car.make for car in cars})
