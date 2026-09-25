"""Data models for cars and dealers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Car:
    """Represents a car in the inventory."""

    car_id: str
    make: str
    model: str
    variant: str
    year: int
    price: int
    dealer_id: str
    body_type: str = ""  # e.g. "SUV", "Hatchback"; empty if the data doesn't say

    def __str__(self) -> str:
        """Return a human-readable representation."""
        return f"{self.make} {self.model} {self.variant} ({self.year})"


@dataclass(frozen=True)
class Dealer:
    """Represents a car dealer."""

    dealer_id: str
    name: str
    city: str
    phone: str
    email: str

    def __str__(self) -> str:
        """Return a human-readable representation."""
        return f"{self.name} in {self.city}"
