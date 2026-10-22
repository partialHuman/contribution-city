"""Isometric geometry and coordinate projection utilities for Contribution City."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


class Point2D(NamedTuple):
    """2D screen coordinate point."""

    x: float
    y: float

    def offset(self, dx: float, dy: float) -> Point2D:
        """Return point offset by dx, dy."""
        return Point2D(self.x + dx, self.y + dy)


@dataclass(frozen=True)
class IsoProjection:
    """Handles 2:1 dimetric (pixel-art isometric) coordinate calculations.

    Grid coordinates (col, row) map to screen coordinates:
    x = origin_x + (col - row) * (tile_width / 2)
    y = origin_y + (col + row) * (tile_height / 2)
    """

    tile_width: float = 16.0
    tile_height: float = 8.0
    origin_x: float = 0.0
    origin_y: float = 0.0

    @property
    def half_w(self) -> float:
        """Half of tile width."""
        return self.tile_width / 2.0

    @property
    def half_h(self) -> float:
        """Half of tile height."""
        return self.tile_height / 2.0

    def get_tile_top(self, col: int, row: int) -> Point2D:
        """Return top vertex of tile at (col, row)."""
        x = self.origin_x + (col - row) * self.half_w
        y = self.origin_y + (col + row) * self.half_h
        return Point2D(round(x, 2), round(y, 2))

    def get_tile_diamond(self, col: int, row: int, height_offset: float = 0.0) -> list[Point2D]:
        """Return 4 vertices of the horizontal tile face at given height offset.

        Order: Top, Right, Bottom, Left.
        """
        top = self.get_tile_top(col, row)
        y = top.y - height_offset
        x = top.x
        return [
            Point2D(x, y),
            Point2D(x + self.half_w, y + self.half_h),
            Point2D(x, y + self.tile_height),
            Point2D(x - self.half_w, y + self.half_h),
        ]

    def get_left_face(self, col: int, row: int, height: float) -> list[Point2D]:
        """Return 4 vertices for the left vertical face of the building block.

        Order: Top-Left, Top-Bottom, Base-Bottom, Base-Left.
        """
        top = self.get_tile_top(col, row)
        x = top.x
        y = top.y
        return [
            Point2D(x - self.half_w, y - height + self.half_h),
            Point2D(x, y - height + self.tile_height),
            Point2D(x, y + self.tile_height),
            Point2D(x - self.half_w, y + self.half_h),
        ]

    def get_right_face(self, col: int, row: int, height: float) -> list[Point2D]:
        """Return 4 vertices for the right vertical face of the building block.

        Order: Top-Bottom, Top-Right, Base-Right, Base-Bottom.
        """
        top = self.get_tile_top(col, row)
        x = top.x
        y = top.y
        return [
            Point2D(x, y - height + self.tile_height),
            Point2D(x + self.half_w, y - height + self.half_h),
            Point2D(x + self.half_w, y + self.half_h),
            Point2D(x, y + self.tile_height),
        ]


def polygon_svg_points(points: list[Point2D]) -> str:
    """Format points into SVG polygon points attribute string."""
    return " ".join(f"{p.x:.1f},{p.y:.1f}" for p in points)
