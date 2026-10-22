"""Tests for normalized contribution data models."""

from __future__ import annotations

from datetime import date

import pytest

from contribution_city.models import ContributionDataSet, ContributionDay


class TestContributionDay:
    """Test suite for ContributionDay."""

    def test_valid_day_creation(self) -> None:
        day = ContributionDay(date="2025-05-10", count=5)
        assert day.date == "2025-05-10"
        assert day.count == 5
        assert day.date_obj == date(2025, 5, 10)
        assert day.level == 2  # auto-computed
        assert day.weekday == 6  # Saturday in GitHub calendar (0=Sun..6=Sat)

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            ContributionDay(date="2025-01-01", count=-1)

    def test_invalid_count_type(self) -> None:
        with pytest.raises(ValueError, match="must be an integer"):
            ContributionDay(date="2025-01-01", count="not-a-number")  # type: ignore[arg-type]

    def test_invalid_date_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid date format"):
            ContributionDay(date="10-05-2025", count=2)

    def test_level_tiers(self) -> None:
        assert ContributionDay(date="2025-01-01", count=0).level == 0
        assert ContributionDay(date="2025-01-01", count=1).level == 1
        assert ContributionDay(date="2025-01-01", count=2).level == 1
        assert ContributionDay(date="2025-01-01", count=5).level == 2
        assert ContributionDay(date="2025-01-01", count=10).level == 3
        assert ContributionDay(date="2025-01-01", count=25).level == 4

    def test_to_dict(self) -> None:
        day = ContributionDay(date="2025-01-01", count=7, level=3, weekday=3)
        d = day.to_dict()
        assert d == {
            "date": "2025-01-01",
            "count": 7,
            "level": 3,
            "weekday": 3,
        }


class TestContributionDataSet:
    """Test suite for ContributionDataSet."""

    def test_empty_dataset(self) -> None:
        ds = ContributionDataSet()
        assert ds.total_contributions == 0
        assert ds.max_count == 0
        assert ds.active_days == 0
        assert ds.start_date is None
        assert ds.end_date is None
        assert ds.max_streak == 0
        assert ds.days == []

    def test_aggregations_and_streaks(self) -> None:
        days = [
            ContributionDay(date="2025-01-01", count=2),
            ContributionDay(date="2025-01-02", count=5),
            ContributionDay(date="2025-01-03", count=0),
            ContributionDay(date="2025-01-04", count=1),
            ContributionDay(date="2025-01-05", count=3),
            ContributionDay(date="2025-01-06", count=8),
        ]
        ds = ContributionDataSet(username="octocat", days=days)
        assert ds.username == "octocat"
        assert ds.total_contributions == 19
        assert ds.max_count == 8
        assert ds.active_days == 5
        assert ds.start_date == "2025-01-01"
        assert ds.end_date == "2025-01-06"
        assert ds.max_streak == 3  # Jan 4, 5, 6

    def test_from_dict_canonical(self) -> None:
        data = {
            "username": "monalisa",
            "days": [
                {"date": "2025-01-01", "count": 4},
                {"date": "2025-01-02", "count": 0},
            ],
        }
        ds = ContributionDataSet.from_dict(data)
        assert ds.username == "monalisa"
        assert len(ds.days) == 2
        assert ds.total_contributions == 4

    def test_from_dict_flat_list(self) -> None:
        data = [
            {"date": "2025-02-01", "count": 10},
            {"date": "2025-02-02", "count": 15},
        ]
        ds = ContributionDataSet.from_dict(data, username="flat-user")
        assert ds.username == "flat-user"
        assert ds.total_contributions == 25

    def test_from_github_graphql_response(self) -> None:
        gh_data = {
            "data": {
                "user": {
                    "login": "octo-dev",
                    "contributionsCollection": {
                        "contributionCalendar": {
                            "totalContributions": 12,
                            "weeks": [
                                {
                                    "contributionDays": [
                                        {
                                            "date": "2025-03-01",
                                            "contributionCount": 7,
                                            "contributionLevel": "THIRD_QUARTILE",
                                            "weekday": 6,
                                        },
                                        {
                                            "date": "2025-03-02",
                                            "contributionCount": 5,
                                            "contributionLevel": "SECOND_QUARTILE",
                                            "weekday": 0,
                                        },
                                    ]
                                }
                            ],
                        }
                    },
                }
            }
        }
        ds = ContributionDataSet.from_dict(gh_data)
        assert ds.username == "octo-dev"
        assert len(ds.days) == 2
        assert ds.total_contributions == 12
        assert ds.days[0].level == 3
        assert ds.days[1].level == 2

    def test_json_serialization_roundtrip(self) -> None:
        ds = ContributionDataSet(
            username="roundtrip-user",
            days=[
                ContributionDay(date="2025-04-01", count=3),
                ContributionDay(date="2025-04-02", count=0),
            ],
        )
        json_str = ds.to_json()
        loaded = ContributionDataSet.from_json(json_str)
        assert loaded.username == ds.username
        assert loaded.total_contributions == ds.total_contributions
        assert len(loaded.days) == len(ds.days)

    def test_from_file_not_found(self, tmp_path: pytest.TempPathFactory) -> None:
        with pytest.raises(FileNotFoundError):
            ContributionDataSet.from_file("non-existent-path.json")

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Malformed JSON"):
            ContributionDataSet.from_json("{invalid json")
