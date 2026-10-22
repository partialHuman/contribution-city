"""SVG Renderer for Contribution City."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from contribution_city.models import ContributionDataSet, ContributionDay
from contribution_city.renderer.geometry import IsoProjection, Point2D, polygon_svg_points
from contribution_city.renderer.themes import Theme, get_theme


@dataclass
class RenderConfig:
    """Configuration options for SVG city rendering."""

    width: int = 1200
    height: int = 680
    theme: str | Theme = "navy-cyan"
    layout: str = "calendar"  # 'calendar', 'compact', or 'isometric'
    tile_width: float = 18.0
    tile_height: float = 9.0
    building_scale: float = 1.0
    min_building_height: float = 6.0
    max_building_height: float = 125.0
    show_windows: bool = True
    show_stars: bool = True
    show_header: bool = True
    show_platform: bool = True
    show_zero_tiles: bool = True
    custom_title: str | None = None


class CityRenderer:
    """Renders contribution datasets into isometric pixel-art SVG cities."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        if isinstance(self.config.theme, str):
            self.theme = get_theme(self.config.theme)
        else:
            self.theme = self.config.theme

    def render(self, dataset: ContributionDataSet) -> str:
        """Render contribution dataset into a standalone SVG string."""
        grid_items = self._build_grid(dataset)

        # Calculate bounding box in isometric coordinates to center the city
        iso = self._calculate_projection(grid_items)

        parts: list[str] = []
        parts.append('<?xml version="1.0" encoding="UTF-8"?>')
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.config.width} {self.config.height}" '
            f'width="{self.config.width}" height="{self.config.height}" '
            f'shape-rendering="geometricPrecision">'
        )

        # Definitions / styles / gradients
        parts.append(self._render_defs())

        # Background gradient rect
        parts.append(
            f'  <rect width="{self.config.width}" height="{self.config.height}" '
            f'fill="url(#bgGradient)" />'
        )

        # Sky stars / digital constellation
        if self.config.show_stars:
            parts.append(self._render_stars())

        # Platform base plinth
        if self.config.show_platform and grid_items:
            parts.append(self._render_platform(iso, grid_items))

        # Buildings and ground tiles
        if grid_items:
            parts.append(self._render_city_blocks(iso, grid_items))
        else:
            parts.append(self._render_empty_state())

        # Developer HUD / Header overlay
        if self.config.show_header:
            parts.append(self._render_header(dataset))

        parts.append("</svg>")
        return "\n".join(parts)

    def _build_grid(
        self, dataset: ContributionDataSet
    ) -> list[tuple[int, int, ContributionDay | None]]:
        """Map days to (col, row, day) grid coordinates."""
        if not dataset.days:
            return []

        days = dataset.days
        layout = self.config.layout.lower()

        if layout in ("compact", "compact_grid"):
            # Arrange days into roughly square block grid
            total = len(days)
            cols = math.isqrt(total)
            if cols * cols < total:
                cols += 1
            # 1.5 aspect ratio looks nice isometrically
            cols = max(7, int(cols * 1.3))
            grid: list[tuple[int, int, ContributionDay | None]] = []
            for idx, day in enumerate(days):
                c = idx % cols
                r = idx // cols
                grid.append((c, r, day))
            return grid

        # Default: 'calendar' (GitHub 52-53 weeks x 7 weekdays)
        # Weekdays: 0 (Sun) to 6 (Sat)
        first_date = days[0].date_obj
        # Find anchor Sunday (Sunday on or before first_date)
        first_gh_weekday = (first_date.weekday() + 1) % 7
        anchor_sunday = first_date - timedelta(days=first_gh_weekday)

        grid = []
        for day in days:
            diff_days = (day.date_obj - anchor_sunday).days
            col = diff_days // 7
            row = day.weekday
            grid.append((col, row, day))

        return grid

    def _calculate_projection(
        self, grid_items: list[tuple[int, int, ContributionDay | None]]
    ) -> IsoProjection:
        """Calculate optimal origin_x and origin_y to center city inside canvas."""
        tw = self.config.tile_width
        th = self.config.tile_height

        if not grid_items:
            return IsoProjection(
                tile_width=tw,
                tile_height=th,
                origin_x=self.config.width / 2.0,
                origin_y=self.config.height / 2.0,
            )

        cols = [item[0] for item in grid_items]
        rows = [item[1] for item in grid_items]
        min_c, max_c = min(cols), max(cols)
        min_r, max_r = min(rows), max(rows)

        # Screen coordinates before origin offset:
        # x_raw = (c - r) * (tw / 2)
        # y_raw = (c + r) * (th / 2)
        min_x_raw = (min_c - max_r) * (tw / 2.0) - (tw / 2.0)
        max_x_raw = (max_c - min_r) * (tw / 2.0) + (tw / 2.0)
        min_y_raw = (min_c + min_r) * (th / 2.0)
        max_y_raw = (max_c + max_r) * (th / 2.0) + th

        # Account for building height offset on upper boundary
        header_space = 100.0 if self.config.show_header else 40.0
        available_height = self.config.height - header_space - 40.0

        # Center horizontally
        center_x = (min_x_raw + max_x_raw) / 2.0
        origin_x = (self.config.width / 2.0) - center_x

        # Center vertically in available lower space
        center_y = (min_y_raw + max_y_raw) / 2.0
        target_center_y = header_space + (available_height / 2.0) + 20.0
        origin_y = target_center_y - center_y

        return IsoProjection(
            tile_width=tw,
            tile_height=th,
            origin_x=origin_x,
            origin_y=origin_y,
        )

    def _render_defs(self) -> str:
        """Render SVG definitions, gradients, and filters."""
        th = self.theme
        return f"""  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{th.bg_top}" />
      <stop offset="100%" stop-color="{th.bg_bottom}" />
    </linearGradient>
    <linearGradient id="glowFilter" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{th.text_accent}" stop-opacity="0.8" />
      <stop offset="100%" stop-color="{th.levels[1].roof}" stop-opacity="0.3" />
    </linearGradient>
    <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>"""

    def _render_stars(self) -> str:
        """Render deterministic sky constellation of pixel stars."""
        stars: list[str] = ['  <g id="sky-stars" opacity="0.6">']
        w = self.config.width
        h = max(100, int(self.config.height * 0.45))

        # Deterministic generation using golden ratio & pseudo-random hashing
        for i in range(48):
            seed = (i * 7919 + 104729) % 1000000
            x = (seed * 13) % w
            y = 35 + ((seed * 37) % (h - 35))
            size = 1.0 if (i % 4 != 0) else 1.8
            opacity = round(0.3 + ((seed % 70) / 100.0), 2)
            color = self.theme.star_color if (i % 3 == 0) else "#FFFFFF"
            stars.append(
                f'    <circle cx="{x}" cy="{y}" r="{size}" fill="{color}" opacity="{opacity}" />'
            )
            # Add cross twinkle for a few brighter stars
            if i % 11 == 0:
                stars.append(
                    f'    <line x1="{x - 3}" y1="{y}" x2="{x + 3}" y2="{y}" '
                    f'stroke="{color}" stroke-width="0.7" opacity="{opacity * 0.8}" />'
                )
                stars.append(
                    f'    <line x1="{x}" y1="{y - 3}" x2="{x}" y2="{y + 3}" '
                    f'stroke="{color}" stroke-width="0.7" opacity="{opacity * 0.8}" />'
                )

        stars.append("  </g>")
        return "\n".join(stars)

    def _render_platform(
        self,
        iso: IsoProjection,
        grid_items: list[tuple[int, int, ContributionDay | None]],
    ) -> str:
        """Render the beveled tech plinth / island beneath the city."""
        th = self.theme
        cols = [item[0] for item in grid_items]
        rows = [item[1] for item in grid_items]
        min_c, max_c = min(cols) - 1, max(cols) + 1
        min_r, max_r = min(rows) - 1, max(rows) + 1

        top_corner = iso.get_tile_top(min_c, min_r)
        right_corner = Point2D(
            iso.get_tile_top(max_c, min_r).x + iso.half_w,
            iso.get_tile_top(max_c, min_r).y + iso.half_h,
        )
        bottom_corner = Point2D(
            iso.get_tile_top(max_c, max_r).x,
            iso.get_tile_top(max_c, max_r).y + iso.tile_height,
        )
        left_corner = Point2D(
            iso.get_tile_top(min_c, max_r).x - iso.half_w,
            iso.get_tile_top(min_c, max_r).y + iso.half_h,
        )

        plinth_depth = 16.0

        pts_top = [top_corner, right_corner, bottom_corner, left_corner]
        pts_left_bevel = [
            left_corner,
            bottom_corner,
            bottom_corner.offset(0, plinth_depth),
            left_corner.offset(0, plinth_depth),
        ]
        pts_right_bevel = [
            bottom_corner,
            right_corner,
            right_corner.offset(0, plinth_depth),
            bottom_corner.offset(0, plinth_depth),
        ]

        svg: list[str] = ['  <g id="city-platform">']
        # Platform left bevel
        svg.append(
            f'    <polygon points="{polygon_svg_points(pts_left_bevel)}" '
            f'fill="{th.platform_left}" stroke="{th.platform_grid}" stroke-width="0.75" />'
        )
        # Platform right bevel
        svg.append(
            f'    <polygon points="{polygon_svg_points(pts_right_bevel)}" '
            f'fill="{th.platform_right}" stroke="{th.platform_grid}" stroke-width="0.75" />'
        )
        # Platform top face
        svg.append(
            f'    <polygon points="{polygon_svg_points(pts_top)}" '
            f'fill="{th.platform_top}" stroke="{th.platform_grid}" stroke-width="1.0" />'
        )
        svg.append("  </g>")
        return "\n".join(svg)

    def _render_city_blocks(
        self,
        iso: IsoProjection,
        grid_items: list[tuple[int, int, ContributionDay | None]],
    ) -> str:
        """Render all ground tiles and building blocks sorted by depth."""
        # Depth sorting: sort by (col + row) ascending so background is drawn first
        # Ties broken by row or col
        sorted_items = sorted(grid_items, key=lambda item: (item[0] + item[1], item[1]))

        lines: list[str] = ['  <g id="city-blocks">']

        for col, row, day in sorted_items:
            count = day.count if day else 0
            level = day.level if day else 0

            if count == 0:
                if self.config.show_zero_tiles:
                    lines.append(self._render_ground_tile(iso, col, row, day))
            else:
                lines.append(self._render_building(iso, col, row, count, level, day))

        lines.append("  </g>")
        return "\n".join(lines)

    def _render_ground_tile(
        self, iso: IsoProjection, col: int, row: int, day: ContributionDay | None
    ) -> str:
        """Render an inactive ground pavement tile."""
        diamond = iso.get_tile_diamond(col, row, height_offset=0.0)
        date_str = day.date if day else f"({col},{row})"
        return (
            f'    <polygon points="{polygon_svg_points(diamond)}" '
            f'fill="{self.theme.ground_tile_fill}" '
            f'stroke="{self.theme.ground_tile_stroke}" stroke-width="0.5">'
            f"<title>{date_str}: 0 contributions</title></polygon>"
        )

    def _calculate_building_height(self, count: int) -> float:
        """Calculate building height with logarithmic progression."""
        if count <= 0:
            return 0.0

        # Sub-linear growth: count**0.75 gives distinct steps for 1-5
        # while preventing skyscrapers from dominating the entire canvas
        h = self.config.min_building_height + ((count**0.78) * 8.5 * self.config.building_scale)
        return min(self.config.max_building_height, round(h, 1))

    def _render_building(
        self,
        iso: IsoProjection,
        col: int,
        row: int,
        count: int,
        level: int,
        day: ContributionDay | None,
    ) -> str:
        """Render a single 3D isometric building block with rooftop and windows."""
        height = self._calculate_building_height(count)
        palette = self.theme.get_level_palette(level)

        roof_pts = iso.get_tile_diamond(col, row, height_offset=height)
        left_pts = iso.get_left_face(col, row, height)
        right_pts = iso.get_right_face(col, row, height)

        date_str = day.date if day else f"({col},{row})"
        tooltip = f"{date_str}: {count} contribution{'s' if count != 1 else ''}"

        b_lines: list[str] = [
            f'    <g class="building" data-date="{date_str}" data-count="{count}">'
        ]
        b_lines.append(f"      <title>{tooltip}</title>")

        # Left Face
        b_lines.append(
            f'      <polygon points="{polygon_svg_points(left_pts)}" '
            f'fill="{palette.left_face}" stroke="{palette.stroke}" stroke-width="0.6" />'
        )

        # Right Face
        b_lines.append(
            f'      <polygon points="{polygon_svg_points(right_pts)}" '
            f'fill="{palette.right_face}" stroke="{palette.stroke}" stroke-width="0.6" />'
        )

        # Windows
        if self.config.show_windows and height >= 14.0:
            b_lines.append(self._render_windows(iso, col, row, height, palette))

        # Rooftop Face
        b_lines.append(
            f'      <polygon points="{polygon_svg_points(roof_pts)}" '
            f'fill="{palette.roof}" stroke="{palette.stroke}" stroke-width="0.6" />'
        )

        # High tier details: Rooftop Antenna or Helipad Accent
        if level >= 3 or count >= 8:
            b_lines.append(self._render_rooftop_accent(iso, col, row, height, level, palette))

        b_lines.append("    </g>")
        return "\n".join(b_lines)

    def _render_windows(
        self,
        iso: IsoProjection,
        col: int,
        row: int,
        height: float,
        palette: Any,
    ) -> str:
        """Render illuminated pixel windows on building sides."""
        win_lines: list[str] = []
        top = iso.get_tile_top(col, row)
        hw = iso.half_w
        hh = iso.half_h

        # Calculate number of window floors based on height
        # Floors every ~7 pixels
        floor_spacing = 7.0
        floors = int((height - 8.0) // floor_spacing)
        floors = min(floors, 14)

        for f_idx in range(floors):
            f_offset = 6.0 + f_idx * floor_spacing
            # Deterministic twinkle hash
            lit = ((col * 37 + row * 19 + f_idx * 13) % 4) != 0
            color = palette.window_lit if lit else palette.window_dim
            opacity = "0.9" if lit else "0.4"

            # Left face window sliver:
            # Parallel to left face slope (hw, hh)
            lx1 = round(top.x - hw * 0.7, 1)
            ly1 = round(top.y + hh * 0.7 - height + f_offset, 1)
            lx2 = round(top.x - hw * 0.3, 1)
            ly2 = round(top.y + hh * 0.3 - height + f_offset, 1)

            win_lines.append(
                f'      <line x1="{lx1}" y1="{ly1}" x2="{lx2}" y2="{ly2}" '
                f'stroke="{color}" stroke-width="1.2" opacity="{opacity}" />'
            )

            # Right face window sliver:
            rx1 = round(top.x + hw * 0.3, 1)
            ry1 = round(top.y + hh * 0.3 - height + f_offset, 1)
            rx2 = round(top.x + hw * 0.7, 1)
            ry2 = round(top.y + hh * 0.7 - height + f_offset, 1)

            # Right side is in shadow, slightly dimmer
            r_opacity = "0.75" if lit else "0.3"
            win_lines.append(
                f'      <line x1="{rx1}" y1="{ry1}" x2="{rx2}" y2="{ry2}" '
                f'stroke="{color}" stroke-width="1.2" opacity="{r_opacity}" />'
            )

        return "\n".join(win_lines)

    def _render_rooftop_accent(
        self,
        iso: IsoProjection,
        col: int,
        row: int,
        height: float,
        level: int,
        palette: Any,
    ) -> str:
        """Render rooftop spire or beacon for top-tier buildings."""
        top = iso.get_tile_top(col, row)
        # Rooftop center point
        center_x = round(top.x, 1)
        center_y = round(top.y - height + iso.half_h, 1)

        spire_len = 10.0 if level >= 4 else 6.0
        spire_top_y = round(center_y - spire_len, 1)

        lines: list[str] = [
            f'      <line x1="{center_x}" y1="{center_y}" '
            f'x2="{center_x}" y2="{spire_top_y}" '
            f'stroke="{palette.stroke}" stroke-width="1.0" />',
            f'      <circle cx="{center_x}" cy="{spire_top_y}" r="1.5" '
            f'fill="{palette.antenna_glow}" />',
        ]
        return "\n".join(lines)

    def _render_empty_state(self) -> str:
        """Render a placeholder city pad when no contributions exist."""
        cx = self.config.width / 2.0
        cy = self.config.height / 2.0
        return (
            f'  <g id="empty-state" text-anchor="middle">'
            f'    <text x="{cx}" y="{cy}" fill="{self.theme.text_secondary}" '
            f'font-family="monospace" font-size="14">No contribution data to display</text>'
            f"  </g>"
        )

    def _render_header(self, dataset: ContributionDataSet) -> str:
        """Render developer HUD header overlay with city statistics."""
        th = self.theme
        font_mono = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"

        title = self.config.custom_title or "CONTRIBUTION CITY"
        user_label = f"@{dataset.username}" if dataset.username else "ANONYMOUS DEVELOPER"
        total_str = f"{dataset.total_contributions:,}"
        max_str = f"{dataset.max_count}"
        streak_str = f"{dataset.max_streak}d"

        date_range_str = ""
        if dataset.start_date and dataset.end_date:
            date_range_str = f"{dataset.start_date} &#8594; {dataset.end_date}"

        header: list[str] = [
            '  <g id="city-hud" transform="translate(40, 42)">',
            f'    <circle cx="0" cy="-6" r="4" fill="{th.text_accent}" filter="url(#neonGlow)" />',
            f'    <text x="14" y="0" fill="{th.text_primary}" font-family="{font_mono}" '
            f'font-size="18" font-weight="700" letter-spacing="1.5">{title}</text>',
            f'    <text x="14" y="20" fill="{th.text_secondary}" font-family="{font_mono}" '
            f'font-size="12" letter-spacing="0.5">{user_label}  |  {date_range_str}</text>',
            # Stats Pill Cluster on the right side
            f'    <g transform="translate({self.config.width - 240}, -6)">',
            f'      <text x="0" y="6" fill="{th.text_secondary}" font-family="{font_mono}" '
            f'font-size="10">CONTRIBUTIONS</text>',
            f'      <text x="0" y="24" fill="{th.text_accent}" font-family="{font_mono}" '
            f'font-size="16" font-weight="700">{total_str}</text>',
            f'      <text x="100" y="6" fill="{th.text_secondary}" font-family="{font_mono}" '
            f'font-size="10">PEAK / STREAK</text>',
            f'      <text x="100" y="24" fill="{th.text_primary}" font-family="{font_mono}" '
            f'font-size="16" font-weight="700">{max_str} <tspan font-size="11" fill="{th.text_secondary}">/ {streak_str}</tspan></text>',
            "    </g>",
            "  </g>",
        ]
        return "\n".join(header)
