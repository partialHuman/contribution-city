"""Deterministic contribution fixtures for visual tests.

Every fixture is generated from fixed dates and a tiny integer generator, so the results never
depend on the current date, the network, a GitHub account or Python's random module.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from contribution_city.models import ContributionDataSet

YEAR_START = date(2025, 1, 1)
YEAR_DAYS = 365


def _lcg(seed: int) -> Callable[[], int]:
    """Small deterministic pseudo-random generator (minimal-standard LCG)."""
    state = seed

    def step() -> int:
        nonlocal state
        state = (state * 48271) % 2147483647
        return state

    return step


def _days(counts: list[int], start: date = YEAR_START) -> list[dict]:
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "count": count}
        for i, count in enumerate(counts)
    ]


def full_year() -> ContributionDataSet:
    """A realistic year: weekday work, quiet weekends, a few busy spells."""
    rnd = _lcg(2025)
    counts = []
    for i in range(YEAR_DAYS):
        day = YEAR_START + timedelta(days=i)
        base = rnd() % 9
        if day.weekday() >= 5:  # weekend
            base = base // 3
        if 120 <= i < 150 or 260 <= i < 280:  # busy spells
            base += 6 + rnd() % 10
        if rnd() % 7 == 0:  # idle day
            base = 0
        counts.append(base)
    counts[200] = 38  # one standout day
    return ContributionDataSet.from_dict({"username": "fixture-user", "days": _days(counts)})


def minimal() -> ContributionDataSet:
    return ContributionDataSet.from_dict({"username": "minimal", "days": _days([0, 3, 12, 25])})


def empty() -> ContributionDataSet:
    return ContributionDataSet.from_dict({"username": "empty", "days": []})


def isolated_peaks() -> ContributionDataSet:
    counts = [0] * YEAR_DAYS
    for index, value in ((20, 120), (110, 300), (230, 90), (340, 200)):
        counts[index] = value
    return ContributionDataSet.from_dict({"username": "peaks", "days": _days(counts)})


def uniform() -> ContributionDataSet:
    return ContributionDataSet.from_dict({"username": "uniform", "days": _days([5] * YEAR_DAYS)})


def long_streak() -> ContributionDataSet:
    counts = [0] * YEAR_DAYS
    for i in range(60, 240):  # 180 consecutive active days with a rising trend
        counts[i] = 1 + (i - 60) // 12
    return ContributionDataSet.from_dict({"username": "streak", "days": _days(counts)})


def special_chars() -> ContributionDataSet:
    """User-controlled text that must be escaped (username is rendered in the header)."""
    return ContributionDataSet.from_dict(
        {"username": "a<b>&\"'c</text><script>x</script>", "days": _days([2, 8, 0, 15, 4, 30])}
    )


def two_years() -> ContributionDataSet:
    """18 months spanning two calendar years, for year and date-range selections."""
    rnd = _lcg(7)
    start = date(2024, 7, 1)
    counts = [(rnd() % 6) if rnd() % 4 else 0 for _ in range(548)]
    return ContributionDataSet.from_dict({"username": "two-years", "days": _days(counts, start)})


def extreme() -> ContributionDataSet:
    return ContributionDataSet.from_dict(
        {"username": "extreme", "days": _days([0, 1, 10**6, 7, 10**9])}
    )


FIXTURES: dict[str, Callable[[], ContributionDataSet]] = {
    "full-year": full_year,
    "minimal": minimal,
    "empty": empty,
    "isolated-peaks": isolated_peaks,
    "uniform": uniform,
    "long-streak": long_streak,
    "special-chars": special_chars,
    "extreme": extreme,
    "two-years": two_years,
}

# Title shown in the header for the special-characters case
HOSTILE_TITLE = "</text><script>alert(1)</script>\"&'<"


def build_fixture(name: str) -> ContributionDataSet:
    """Return a fresh copy of a named fixture."""
    try:
        return FIXTURES[name]()
    except KeyError:
        valid = ", ".join(FIXTURES)
        raise KeyError(f"Unknown fixture '{name}'. Available fixtures: {valid}") from None
