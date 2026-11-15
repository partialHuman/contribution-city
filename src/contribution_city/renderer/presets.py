"""Height presets, building styles and viewing angles.

Three independent ideas, kept apart on purpose:

* A **height preset** is the overall height *profile* of the city: how tall the buildings may get.
* A **height mode** (``power``, ``linear``, ``sqrt``, ``log``; see ``svg.HEIGHT_MODES``) is the
  mathematical *distribution*: how a day's contribution count maps to a height inside that profile.
* A **view angle** is the camera elevation. It changes the projection, not the data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HeightPreset:
    """Base height values (unscaled pixels at the default 18 px tile)."""

    name: str
    description: str
    min_height: float  # height of a day with a single contribution (before the curve)
    max_height: float  # no building may be taller than this
    coefficient: float  # growth of the default ``power`` curve: min + count**0.78 * coefficient


TALL = HeightPreset(
    "tall",
    "The 1.0-1.2 look: towers up to about seven tiles high",
    min_height=6.0,
    max_height=125.0,
    coefficient=8.5,
)
STANDARD = HeightPreset(
    "standard",
    "Proportionate buildings, at most about three tiles high (default since 1.3)",
    min_height=3.0,
    max_height=56.0,
    coefficient=3.8,
)

HEIGHT_PRESETS: dict[str, HeightPreset] = {
    "standard": STANDARD,
    "tall": TALL,
    # 'custom' starts from the tall base values and applies the user's own scale, min and max.
    # It is what 1.2.0 configurations that set building_scale / min / max keep getting.
    "custom": HeightPreset(
        "custom",
        "Your own building_scale and min/max heights on the tall base (as in 1.2.0)",
        TALL.min_height,
        TALL.max_height,
        TALL.coefficient,
    ),
}
HEIGHT_PRESET_NAMES: tuple[str, ...] = tuple(HEIGHT_PRESETS)
DEFAULT_HEIGHT_PRESET = "standard"

# Limits that keep the SVG sane. Values outside are rejected with a readable message.
LIMITS = {
    "building_scale": (0.1, 5.0),
    "min_building_height": (0.0, 40.0),
    "max_building_height": (8.0, 400.0),
    "view_elevation": (10.0, 70.0),
    "canvas": (100, 10000),
}

BUILDING_STYLES: tuple[str, ...] = ("detailed", "solid")
DEFAULT_BUILDING_STYLE = "detailed"


@dataclass(frozen=True)
class ViewAngle:
    """A camera elevation in degrees above the ground plane."""

    name: str
    elevation: float
    description: str

    @property
    def tile_ratio(self) -> float:
        """tile_height / tile_width of a ground tile: sin(elevation)."""
        return math.sin(math.radians(self.elevation))

    @property
    def height_factor(self) -> float:
        """Vertical foreshortening of building heights relative to the 30 degree view."""
        return height_factor(self.elevation)


REFERENCE_ELEVATION = 30.0  # the 2:1 pixel-art projection used since 1.0


def height_factor(elevation: float) -> float:
    """cos(elevation) / cos(30 degrees): 1.0 for the classic view."""
    if elevation == REFERENCE_ELEVATION:
        return 1.0
    return math.cos(math.radians(elevation)) / math.cos(math.radians(REFERENCE_ELEVATION))


VIEW_ANGLES: dict[str, ViewAngle] = {
    a.name: a
    for a in (
        ViewAngle(
            "isometric", 30.0, "Classic 2:1 pixel isometric (the view of every earlier release)"
        ),
        ViewAngle("low", 20.0, "Lower camera: flatter ground, towers read taller"),
        ViewAngle("high", 42.0, "Higher camera: more ground, buildings look shorter"),
        ViewAngle("top-down", 58.0, "Steep, almost plan view: the grid dominates"),
    )
}
VIEW_ANGLE_NAMES: tuple[str, ...] = tuple(VIEW_ANGLES)
DEFAULT_VIEW_ANGLE = "isometric"
