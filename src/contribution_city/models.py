"""Normalized contribution data models for Contribution City."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


def parse_date(value: str | date) -> date:
    """Parse a date string (YYYY-MM-DD) or validate a date object."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError as err:
            raise ValueError(f"Invalid date format: '{value}'. Expected YYYY-MM-DD.") from err
    raise TypeError(f"Expected str or date, got {type(value).__name__}")


@dataclass(frozen=True)
class ContributionDay:
    """Represents a single day's contribution activity."""

    date: str
    count: int
    level: int = 0
    weekday: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.count, int):
            try:
                object.__setattr__(self, "count", int(self.count))
            except (ValueError, TypeError) as err:
                raise ValueError(
                    f"Contribution count must be an integer, got: {self.count}"
                ) from err

        if self.count < 0:
            raise ValueError(f"Contribution count cannot be negative: {self.count}")

        # Validate date format
        parsed_date = parse_date(self.date)
        # Normalize date string
        object.__setattr__(self, "date", parsed_date.isoformat())

        # If weekday wasn't set or 0 default, calculate from date
        # GitHub weekday: 0 = Sunday, 1 = Monday, ..., 6 = Saturday
        # Python weekday: 0 = Monday, ..., 6 = Sunday
        # Python -> GitHub: (python_weekday + 1) % 7
        if self.weekday == 0 and parsed_date.weekday() != 6:
            gh_weekday = (parsed_date.weekday() + 1) % 7
            object.__setattr__(self, "weekday", gh_weekday)

        # Calculate level if default 0 and count > 0
        if self.level == 0 and self.count > 0:
            if self.count <= 2:
                computed_level = 1
            elif self.count <= 6:
                computed_level = 2
            elif self.count <= 14:
                computed_level = 3
            else:
                computed_level = 4
            object.__setattr__(self, "level", computed_level)

    @property
    def date_obj(self) -> date:
        """Return the date as a datetime.date object."""
        return parse_date(self.date)

    def to_dict(self) -> dict[str, Any]:
        """Convert to primitive dictionary."""
        return {
            "date": self.date,
            "count": self.count,
            "level": self.level,
            "weekday": self.weekday,
        }


@dataclass
class ContributionDataSet:
    """Normalized collection of contribution days."""

    username: str | None = None
    days: list[ContributionDay] = field(default_factory=list)
    private_contributions: int = 0

    def __post_init__(self) -> None:
        # Sort days chronologically
        self.days.sort(key=lambda d: d.date)

    @property
    def total_contributions(self) -> int:
        """Sum of all contributions across all days."""
        return sum(d.count for d in self.days)

    @property
    def max_count(self) -> int:
        """Maximum daily contribution count."""
        return max((d.count for d in self.days), default=0)

    @property
    def active_days(self) -> int:
        """Number of days with at least one contribution."""
        return sum(1 for d in self.days if d.count > 0)

    @property
    def start_date(self) -> str | None:
        """First date in dataset (YYYY-MM-DD), or None if empty."""
        return self.days[0].date if self.days else None

    @property
    def end_date(self) -> str | None:
        """Last date in dataset (YYYY-MM-DD), or None if empty."""
        return self.days[-1].date if self.days else None

    @property
    def max_streak(self) -> int:
        """Calculate longest run of consecutive calendar days with activity.

        Days missing from the dataset break a streak, so sparse custom data
        is never counted as one long streak.
        """
        longest = 0
        current = 0
        previous: date | None = None
        for day in self.days:
            if day.count > 0:
                today = day.date_obj
                if previous is not None and (today - previous).days == 1:
                    current += 1
                else:
                    current = 1
                previous = today
                longest = max(longest, current)
            else:
                current = 0
                previous = None
        return longest

    @classmethod
    def merge(cls, *datasets: ContributionDataSet) -> ContributionDataSet:
        """Combine several datasets (for example one per year) into one.

        Duplicate dates keep the entry with the highest count.
        """
        by_date: dict[str, ContributionDay] = {}
        username = None
        private = 0
        for ds in datasets:
            username = username or ds.username
            private += ds.private_contributions
            for day in ds.days:
                known = by_date.get(day.date)
                if known is None or day.count > known.count:
                    by_date[day.date] = day
        return cls(username=username, days=list(by_date.values()), private_contributions=private)

    def to_dict(self) -> dict[str, Any]:
        """Convert entire dataset to dictionary."""
        return {
            "username": self.username,
            "total_contributions": self.total_contributions,
            "private_contributions": self.private_contributions,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "days": [d.to_dict() for d in self.days],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize dataset to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Any, username: str | None = None) -> ContributionDataSet:
        """Parse raw dictionary or list into normalized ContributionDataSet."""
        if isinstance(data, list):
            # Flat list of day objects
            days = []
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError(f"Expected day dictionary in list, got {type(item).__name__}")
                days.append(cls._parse_day_dict(item))
            return cls(username=username, days=days)

        if not isinstance(data, dict):
            raise ValueError(
                f"Expected dict or list for contribution data, got {type(data).__name__}"
            )

        # Check for GitHub GraphQL API response wrapper
        # data -> user -> contributionsCollection -> contributionCalendar -> weeks
        if "data" in data and isinstance(data["data"], dict):
            user_data = data["data"].get("user") or {}
            user_login = user_data.get("login") or username
            col = user_data.get("contributionsCollection") or {}
            calendar = col.get("contributionCalendar") or {}
            return cls._from_github_calendar(
                calendar,
                username=user_login,
                private=int(col.get("restrictedContributionsCount") or 0),
            )

        if "contributionsCollection" in data:
            col = data["contributionsCollection"]
            calendar = col.get("contributionCalendar") or {}
            return cls._from_github_calendar(
                calendar,
                username=username,
                private=int(col.get("restrictedContributionsCount") or 0),
            )

        if "contributionCalendar" in data:
            return cls._from_github_calendar(data["contributionCalendar"], username=username)

        # Standard canonical format: {"username": "...", "days": [...]}
        extracted_username = data.get("username", username)
        private = int(data.get("private_contributions") or 0)
        raw_days = data.get("days", [])
        if not isinstance(raw_days, list):
            raise ValueError(f"Field 'days' must be a list, got {type(raw_days).__name__}")

        days = [cls._parse_day_dict(item) for item in raw_days]
        return cls(username=extracted_username, days=days, private_contributions=private)

    @classmethod
    def _parse_day_dict(cls, item: dict[str, Any]) -> ContributionDay:
        """Parse a single day representation."""
        date_val = item.get("date")
        if not date_val:
            raise ValueError(f"Day record missing required 'date' field: {item}")

        # Support both 'count' and GitHub's 'contributionCount'
        count = item.get("count")
        if count is None:
            count = item.get("contributionCount", 0)

        level = item.get("level")
        if level is None:
            raw_lvl = item.get("contributionLevel")
            level_map = {
                "NONE": 0,
                "FIRST_QUARTILE": 1,
                "SECOND_QUARTILE": 2,
                "THIRD_QUARTILE": 3,
                "FOURTH_QUARTILE": 4,
            }
            level = level_map.get(raw_lvl, 0) if isinstance(raw_lvl, str) else 0

        weekday = item.get("weekday", 0)
        return ContributionDay(
            date=str(date_val),
            count=int(count),
            level=int(level),
            weekday=int(weekday),
        )

    @classmethod
    def _from_github_calendar(
        cls, calendar: dict[str, Any], username: str | None = None, private: int = 0
    ) -> ContributionDataSet:
        """Extract days from a GitHub contributionCalendar structure."""
        weeks = calendar.get("weeks", [])
        days: list[ContributionDay] = []
        for week in weeks:
            for day_dict in week.get("contributionDays", []):
                days.append(cls._parse_day_dict(day_dict))
        return cls(username=username, days=days, private_contributions=private)

    @classmethod
    def from_json(cls, json_str: str, username: str | None = None) -> ContributionDataSet:
        """Parse JSON string into ContributionDataSet."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON: {err}") from err
        return cls.from_dict(data, username=username)

    @classmethod
    def from_file(cls, path: str | Path) -> ContributionDataSet:
        """Read and parse dataset from a JSON file path."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Contribution file not found: {p}")
        with open(p, encoding="utf-8") as f:
            content = f.read()
        return cls.from_json(content)
