"""Tests for the repository module."""

from pathlib import Path

import pytest

from car_dealer_chatbot.models import Car, Dealer
from car_dealer_chatbot.repository import (
    DataError,
    find_dealer,
    load_cars,
    load_dealers,
    search_cars,
)


class TestLoadCars:
    """Tests for load_cars function."""

    def test_load_cars_success(self, sample_csv_files: tuple[Path, Path]) -> None:
        """Test loading cars from CSV."""
        cars_path, _ = sample_csv_files
        cars = load_cars(cars_path)

        assert len(cars) == 2
        assert cars[0].car_id == "C001"
        assert cars[0].make == "Toyota"
        assert cars[0].model == "Corolla"

    def test_load_cars_file_not_found(self) -> None:
        """Test error when cars file not found."""
        with pytest.raises(DataError, match="not found"):
            load_cars(Path("nonexistent.csv"))

    def test_load_cars_skips_malformed_rows(self, tmp_path: Path) -> None:
        """Rows with missing or non-numeric fields are skipped, valid rows kept."""
        csv_file = tmp_path / "cars.csv"
        csv_file.write_text(
            "car_id,make,model,variant,year,price,dealer_id\n"
            "C001,Toyota,Corolla,1.8 Hybrid,2023,28500,D001\n"
            "C002,BMW,3 Series,320i,not-a-year,52000,D002\n"
        )
        cars = load_cars(csv_file)
        assert [car.car_id for car in cars] == ["C001"]

    def test_load_cars_invalid_csv(self, tmp_path: Path) -> None:
        """Test handling of malformed CSV."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("not a valid csv\nwith\nno headers")

        cars = load_cars(csv_file)
        # Should return empty list or handle gracefully
        assert isinstance(cars, list)


class TestLoadDealers:
    """Tests for load_dealers function."""

    def test_load_dealers_success(self, sample_csv_files: tuple[Path, Path]) -> None:
        """Test loading dealers from CSV."""
        _, dealers_path = sample_csv_files
        dealers = load_dealers(dealers_path)

        assert len(dealers) == 2
        assert dealers[0].dealer_id == "D001"
        assert dealers[0].name == "Utrecht Auto Centre"
        assert dealers[0].city == "Utrecht"

    def test_load_dealers_file_not_found(self) -> None:
        """Test error when dealers file not found."""
        with pytest.raises(DataError, match="not found"):
            load_dealers(Path("nonexistent.csv"))


class TestFindDealer:
    """Tests for find_dealer function."""

    def test_find_dealer_exists(self, sample_dealers: list[Dealer]) -> None:
        """Test finding an existing dealer."""
        dealer = find_dealer("D001", sample_dealers)
        assert dealer is not None
        assert dealer.name == "Utrecht Auto Centre"

    def test_find_dealer_not_found(self, sample_dealers: list[Dealer]) -> None:
        """Test finding a non-existent dealer."""
        dealer = find_dealer("D999", sample_dealers)
        assert dealer is None

    def test_find_dealer_empty_list(self) -> None:
        """Test finding dealer in empty list."""
        dealer = find_dealer("D001", [])
        assert dealer is None


class TestSearchCars:
    """Tests for search_cars function."""

    def test_search_exact_match(self, sample_cars: list[Car]) -> None:
        """Test exact car search."""
        results = search_cars("Toyota Corolla", sample_cars)
        assert len(results) >= 1
        assert any(car.make == "Toyota" and car.model == "Corolla" for car in results)

    def test_search_partial_match_make(self, sample_cars: list[Car]) -> None:
        """Test partial match on make."""
        results = search_cars("Toyota", sample_cars)
        assert len(results) >= 1
        assert all(car.make == "Toyota" for car in results)

    def test_search_partial_match_model(self, sample_cars: list[Car]) -> None:
        """Test partial match on model."""
        results = search_cars("Corolla", sample_cars)
        assert len(results) >= 1
        assert all(car.model == "Corolla" for car in results)

    def test_search_case_insensitive(self, sample_cars: list[Car]) -> None:
        """Test case-insensitive search."""
        results_upper = search_cars("TOYOTA COROLLA", sample_cars)
        results_lower = search_cars("toyota corolla", sample_cars)

        assert len(results_upper) > 0
        assert len(results_lower) > 0

    def test_search_typo_tolerance(self, sample_cars: list[Car]) -> None:
        """Test tolerance for minor typos."""
        results = search_cars("Toyoto", sample_cars)
        # Should find Toyota despite typo
        assert len(results) >= 1

    def test_search_not_found(self, sample_cars: list[Car]) -> None:
        """Test search with no matches."""
        results = search_cars("Unicorn Sparkle", sample_cars)
        assert len(results) == 0

    def test_search_empty_query(self, sample_cars: list[Car]) -> None:
        """Test search with empty query."""
        results = search_cars("", sample_cars)
        assert len(results) == 0

    def test_search_whitespace_only_query(self, sample_cars: list[Car]) -> None:
        """Test search with whitespace-only query."""
        results = search_cars("   ", sample_cars)
        assert len(results) == 0

    def test_search_multiple_ambiguous_results(self, sample_cars: list[Car]) -> None:
        """Test search that returns multiple results."""
        results = search_cars("Corolla", sample_cars)
        # Should return both Corolla variants
        assert len(results) >= 2

    def test_search_specific_variant_narrows_to_one(self, sample_cars: list[Car]) -> None:
        """Adding the variant disambiguates between models with several variants."""
        results = search_cars("Toyota Corolla 1.8 Hybrid", sample_cars)
        assert [car.car_id for car in results] == ["C001"]

    def test_search_single_shared_token_is_not_a_match(self, sample_cars: list[Car]) -> None:
        """'Tesla Model 3' must not match the BMW '3 Series' on the token '3' alone."""
        assert search_cars("Tesla Model 3", sample_cars) == []

    def test_search_ignores_punctuation(self, sample_cars: list[Car]) -> None:
        results = search_cars("bmw, 3-series!", sample_cars)
        assert [car.car_id for car in results] == ["C003"]

    def test_search_ranking(self, sample_cars: list[Car]) -> None:
        """Test that search results are ranked by relevance."""
        results = search_cars("Toyota Corolla", sample_cars)
        if len(results) > 1:
            # The exact match should be ranked higher
            assert results[0].make == "Toyota" and results[0].model == "Corolla"


def test_body_type_is_optional(sample_csv_files: tuple[Path, Path]) -> None:
    cars_csv, _ = sample_csv_files
    assert all(car.body_type == "" for car in load_cars(cars_csv))


def test_shipped_inventory_has_body_types(inventory: tuple[list[Car], list[Dealer]]) -> None:
    cars, _ = inventory
    assert all(car.body_type for car in cars)
    assert {car.body_type for car in cars if car.model == "X5"} == {"SUV"}
