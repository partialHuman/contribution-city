"""City layout presets: how contribution days are placed on the isometric grid.

A layout is a :class:`LayoutSpec` holding a placement function plus a few rendering hints.
Adding a layout means writing one ``place_*`` function and one registry entry.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from contribution_city.models import ContributionDay

GridItem = tuple[int, int, ContributionDay | None]
Placer = Callable[[list[ContributionDay]], list[GridItem]]

COMPACT_STRIDE = 2  # 'compact' leaves one empty tile between buildings


def place_calendar(days: list[ContributionDay]) -> list[GridItem]:
    """GitHub calendar: columns are weeks, rows are weekdays (0 = Sunday)."""
    first_date = days[0].date_obj
    first_gh_weekday = (first_date.weekday() + 1) % 7
    anchor_sunday = first_date - timedelta(days=first_gh_weekday)
    return [((day.date_obj - anchor_sunday).days // 7, day.weekday, day) for day in days]


def place_compact(days: list[ContributionDay]) -> list[GridItem]:
    """Near-square block in date order with one empty tile between buildings."""
    total = len(days)
    cols = math.isqrt(total)
    if cols * cols < total:
        cols += 1
    cols = max(7, int(cols * 1.3))
    return [
        ((idx % cols) * COMPACT_STRIDE, (idx // cols) * COMPACT_STRIDE, day)
        for idx, day in enumerate(days)
    ]


def _square_cols(total: int) -> int:
    return max(7, math.isqrt(total - 1) + 1 if total > 1 else 1)


def place_dense_grid(days: list[ContributionDay]) -> list[GridItem]:
    """Near-square block in date order with no gaps (smallest footprint)."""
    cols = _square_cols(len(days))
    return [(idx % cols, idx // cols, day) for idx, day in enumerate(days)]


def place_downtown(days: list[ContributionDay]) -> list[GridItem]:
    """Busiest days in the centre, quiet days towards the edge.

    Days are no longer in date order (tooltips still carry the date); height still maps directly
    to the day's contributions.
    """
    side = _square_cols(len(days))
    if side * side < len(days):  # pragma: no cover - guarded by _square_cols
        side += 1
    centre = (side - 1) / 2.0
    cells = sorted(
        ((c, r) for c in range(side) for r in range(side)),
        key=lambda cr: ((cr[0] - centre) ** 2 + (cr[1] - centre) ** 2, cr[0], cr[1]),
    )
    ranked = sorted(days, key=lambda d: (-d.count, d.date))
    return [(c, r, day) for (c, r), day in zip(cells, ranked, strict=False)]


@dataclass(frozen=True)
class LayoutSpec:
    """A named layout: placement plus rendering hints."""

    name: str
    description: str
    place: Placer
    wireframe: bool = False  # outlined buildings instead of filled faces
    island: bool = False  # floating platform with an underside
    extra_depth: float = 0.0  # extra unscaled pixels below the city (for auto-fit)


LAYOUT_SPECS: dict[str, LayoutSpec] = {
    spec.name: spec
    for spec in (
        LayoutSpec("calendar", "GitHub calendar grid: weeks by weekdays", place_calendar),
        LayoutSpec("compact", "Spaced square block, one empty tile between towers", place_compact),
        LayoutSpec("dense-grid", "Tight square block without gaps", place_dense_grid),
        LayoutSpec("downtown", "Busiest days clustered in the centre", place_downtown),
        LayoutSpec(
            "floating-island",
            "Square block on a floating rock island",
            place_dense_grid,
            island=True,
        ),
        LayoutSpec(
            "wireframe", "Calendar grid drawn as outlined schematic", place_calendar, wireframe=True
        ),
    )
}

LAYOUT_NAMES: tuple[str, ...] = tuple(LAYOUT_SPECS)
