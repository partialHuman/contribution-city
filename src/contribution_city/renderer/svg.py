"""SVG Renderer for Contribution City."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from html import escape

from contribution_city.models import ContributionDataSet, ContributionDay
from contribution_city.renderer.geometry import IsoProjection, Point2D, polygon_svg_points
from contribution_city.renderer.themes import LevelPalette, Theme, get_light_pair, get_theme

HEIGHT_MODES = ("power", "linear", "sqrt", "log")
APPEARANCES = ("fixed", "auto")
LAYOUTS = ("calendar", "compact")

# Layout constants (in "base" pixels, scaled together with the city when auto-fit is on)
PLINTH_DEPTH = 16.0
FLOOR_SPACING = 7.0
SIDE_MARGIN = 40.0
BOTTOM_MARGIN = 30.0
COMPACT_STRIDE = 2  # compact layout leaves one empty tile between buildings
MIN_SCALE, MAX_SCALE = 0.5, 3.0

GridItem = tuple[int, int, ContributionDay | None]


@dataclass
class RenderConfig:
    """Configuration options for SVG city rendering."""

    width: int = 1200
    height: int = 680
    theme: str | Theme = "navy-cyan"
    layout: str = "calendar"  # 'calendar' or 'compact'
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
    # Height curve: 'power' (default, sub-linear), 'linear', 'sqrt' or 'log'
    height_mode: str = "power"
    # 'fixed' uses the theme as-is; 'auto' also embeds the light companion of the theme and
    # switches with the viewer's prefers-color-scheme (needs a theme with a light variant)
    appearance: str = "fixed"
    # Skip the background rectangle (and sky stars) so the page shows through
    transparent: bool = False
    # Add hover tooltips to buildings (empty tiles never get tooltips, to keep files small)
    show_tooltips: bool = True
    # Scale the whole city so it fills the canvas
    auto_fit: bool = True
    # crispEdges gives hard pixel-art edges; False uses smooth anti-aliasing
    pixel_art: bool = True


def _luminance(hex_color: str) -> float:
    """Relative luminance (0..1) of a #RRGGBB color."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _css_rules(th: Theme) -> list[str]:
    """CSS rules (class -> colors) for one theme."""
    star_white = th.text_secondary if _luminance(th.bg_top) > 0.5 else "#FFFFFF"
    rules = [
        f".bt{{stop-color:{th.bg_top}}}",
        f".bb{{stop-color:{th.bg_bottom}}}",
        f".gt{{fill:{th.ground_tile_fill};stroke:{th.ground_tile_stroke};stroke-width:.5}}",
        f".pt{{fill:{th.platform_top};stroke:{th.platform_grid};stroke-width:1}}",
        f".pl{{fill:{th.platform_left};stroke:{th.platform_grid};stroke-width:.75}}",
        f".pr{{fill:{th.platform_right};stroke:{th.platform_grid};stroke-width:.75}}",
        f".tp{{fill:{th.text_primary}}}",
        f".ts{{fill:{th.text_secondary}}}",
        f".ta{{fill:{th.text_accent}}}",
        f".sw{{fill:{star_white}}}",
        f".sc{{fill:{th.star_color}}}",
        f".kw{{stroke:{star_white}}}",
        f".kc{{stroke:{th.star_color}}}",
    ]
    for lvl, p in th.levels.items():
        rules += [
            f".R{lvl}{{fill:{p.roof};stroke:{p.stroke};stroke-width:.6}}",
            f".A{lvl}{{fill:{p.left_face};stroke:{p.stroke};stroke-width:.6}}",
            f".Z{lvl}{{fill:{p.right_face};stroke:{p.stroke};stroke-width:.6}}",
            f".WL{lvl}{{stroke:{p.window_lit};opacity:.9}}",
            f".WD{lvl}{{stroke:{p.window_dim};opacity:.4}}",
            f".XL{lvl}{{stroke:{p.window_lit};opacity:.75}}",
            f".XD{lvl}{{stroke:{p.window_dim};opacity:.3}}",
            f".N{lvl}{{stroke:{p.stroke};stroke-width:1}}",
            f".G{lvl}{{fill:{p.antenna_glow}}}",
        ]
    return rules


class CityRenderer:
    """Renders contribution datasets into isometric pixel-art SVG cities."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        cfg = self.config

        if cfg.height_mode not in HEIGHT_MODES:
            raise ValueError(
                f"Unknown height_mode '{cfg.height_mode}'. Choose from: {', '.join(HEIGHT_MODES)}"
            )
        if cfg.appearance not in APPEARANCES:
            raise ValueError(
                f"Unknown appearance '{cfg.appearance}'. Choose from: {', '.join(APPEARANCES)}"
            )
        if cfg.layout.lower() not in LAYOUTS:
            raise ValueError(f"Unknown layout '{cfg.layout}'. Choose from: {', '.join(LAYOUTS)}")

        self.theme = get_theme(cfg.theme) if isinstance(cfg.theme, str) else cfg.theme
        self.light_theme: Theme | None = None
        if cfg.appearance == "auto":
            self.light_theme = get_light_pair(self.theme.name)

        self._max_count = 0
        self._scale = 1.0

    # ------------------------------------------------------------------ public

    def render(self, dataset: ContributionDataSet) -> str:
        """Render contribution dataset into a standalone SVG string."""
        cfg = self.config
        self._max_count = dataset.max_count
        grid_items = self._build_grid(dataset)
        iso = self._calculate_projection(grid_items)

        title, desc = self._accessible_text(dataset)
        shape = "crispEdges" if cfg.pixel_art else "geometricPrecision"

        parts: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cfg.width} {cfg.height}" '
            f'width="{cfg.width}" height="{cfg.height}" shape-rendering="{shape}" '
            f'role="img" aria-labelledby="cc-title cc-desc">',
            f'  <title id="cc-title">{escape(title)}</title>',
            f'  <desc id="cc-desc">{escape(desc)}</desc>',
            self._render_style_and_defs(),
        ]

        if not cfg.transparent:
            parts.append(f'  <rect width="{cfg.width}" height="{cfg.height}" fill="url(#bg)" />')
            if cfg.show_stars:
                parts.append(self._render_stars())

        if cfg.show_platform and grid_items:
            parts.append(self._render_platform(iso, grid_items))

        if grid_items:
            parts.append(self._render_city_blocks(iso, grid_items))
        else:
            parts.append(self._render_empty_state())

        if cfg.show_header:
            parts.append(self._render_header(dataset))

        parts.append("</svg>")
        return "\n".join(parts)

    # ------------------------------------------------------------------ layout

    def _build_grid(self, dataset: ContributionDataSet) -> list[GridItem]:
        """Map days to (col, row, day) grid coordinates."""
        if not dataset.days:
            return []

        days = dataset.days
        layout = self.config.layout.lower()

        if layout == "compact":
            total = len(days)
            cols = math.isqrt(total)
            if cols * cols < total:
                cols += 1
            cols = max(7, int(cols * 1.3))
            return [
                ((idx % cols) * COMPACT_STRIDE, (idx // cols) * COMPACT_STRIDE, day)
                for idx, day in enumerate(days)
            ]

        # 'calendar': GitHub 52-53 weeks x 7 weekdays (0 = Sunday)
        first_date = days[0].date_obj
        first_gh_weekday = (first_date.weekday() + 1) % 7
        anchor_sunday = first_date - timedelta(days=first_gh_weekday)
        return [((day.date_obj - anchor_sunday).days // 7, day.weekday, day) for day in days]

    def _max_base_height(self, grid_items: list[GridItem]) -> float:
        """Tallest building (in unscaled pixels), including its rooftop spire."""
        heights = [
            self._calculate_building_height(day.count, self._max_count)
            for _, _, day in grid_items
            if day and day.count > 0
        ]
        return (max(heights) + 12.0) if heights else 0.0

    def _calculate_projection(self, grid_items: list[GridItem]) -> IsoProjection:
        """Pick scale and origin so the city is centred (and, if enabled, fills the canvas)."""
        cfg = self.config
        tw0, th0 = cfg.tile_width, cfg.tile_height

        if not grid_items:
            self._scale = 1.0
            return IsoProjection(
                tile_width=tw0,
                tile_height=th0,
                origin_x=cfg.width / 2.0,
                origin_y=cfg.height / 2.0,
            )

        margin = 1 if cfg.show_platform else 0
        cols = [item[0] for item in grid_items]
        rows = [item[1] for item in grid_items]
        c0, c1 = min(cols) - margin, max(cols) + margin
        r0, r1 = min(rows) - margin, max(rows) + margin
        max_h = self._max_base_height(grid_items)

        # Extent of the city at scale 1
        ex = (c1 - r0) * (tw0 / 2.0) - (c0 - r1) * (tw0 / 2.0) + tw0
        ey = (c1 + r1) * (th0 / 2.0) - (c0 + r0) * (th0 / 2.0) + th0 + max_h + PLINTH_DEPTH

        header_space = 100.0 if cfg.show_header else 40.0
        avail_w = cfg.width - 2 * SIDE_MARGIN
        avail_h = cfg.height - header_space - BOTTOM_MARGIN

        if cfg.auto_fit:
            scale = min(avail_w / ex, avail_h / ey)
            scale = max(MIN_SCALE, min(MAX_SCALE, scale))
        else:
            scale = 1.0
        self._scale = scale

        tw, th = tw0 * scale, th0 * scale
        center_x = ((c0 - r1) + (c1 - r0)) * (tw / 4.0)
        origin_x = cfg.width / 2.0 - center_x

        city_h = ey * scale
        top_y = header_space + max(0.0, (avail_h - city_h) / 2.0)
        origin_y = top_y + max_h * scale - (c0 + r0) * (th / 2.0)

        return IsoProjection(tile_width=tw, tile_height=th, origin_x=origin_x, origin_y=origin_y)

    # ------------------------------------------------------------------ head / defs

    def _accessible_text(self, dataset: ContributionDataSet) -> tuple[str, str]:
        user = f"@{dataset.username}" if dataset.username else "a developer"
        title = self.config.custom_title or f"Contribution City of {user}"
        if dataset.days:
            desc = (
                f"Isometric pixel-art city of {dataset.total_contributions:,} contributions by "
                f"{user} between {dataset.start_date} and {dataset.end_date}. "
                f"Busiest day: {dataset.max_count} contributions. "
                f"Longest streak: {dataset.max_streak} days."
            )
        else:
            desc = "Contribution city with no contribution data."
        return title, desc

    def _render_style_and_defs(self) -> str:
        rules = _css_rules(self.theme)
        css = "".join(rules)
        if self.light_theme is not None:
            light = "".join(_css_rules(self.light_theme))
            css += f"@media (prefers-color-scheme:light){{{light}}}"
        return (
            f"  <style>{css}"
            "path.w{fill:none;stroke-width:1.2}"
            "</style>\n"
            "  <defs>\n"
            '    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">\n'
            '      <stop offset="0%" class="bt" />\n'
            '      <stop offset="100%" class="bb" />\n'
            "    </linearGradient>\n"
            '    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">\n'
            '      <feGaussianBlur stdDeviation="3" result="blur" />\n'
            '      <feComposite in="SourceGraphic" in2="blur" operator="over" />\n'
            "    </filter>\n"
            "  </defs>"
        )

    def _render_stars(self) -> str:
        """Render deterministic sky constellation of pixel stars."""
        stars: list[str] = ['  <g id="sky-stars" opacity="0.6">']
        w = self.config.width
        h = max(100, int(self.config.height * 0.45))

        for i in range(48):
            seed = (i * 7919 + 104729) % 1000000
            x = (seed * 13) % w
            y = 35 + ((seed * 37) % (h - 35))
            size = 1.0 if (i % 4 != 0) else 1.8
            opacity = round(0.3 + ((seed % 70) / 100.0), 2)
            colored = i % 3 == 0
            stars.append(
                f'    <circle class="{"sc" if colored else "sw"}" cx="{x}" cy="{y}" '
                f'r="{size}" opacity="{opacity}" />'
            )
            if i % 11 == 0:
                cls = "kc" if colored else "kw"
                o = round(opacity * 0.8, 2)
                stars.append(
                    f'    <path class="{cls}" fill="none" stroke-width=".7" opacity="{o}" '
                    f'd="M{x - 3} {y}H{x + 3}M{x} {y - 3}V{y + 3}" />'
                )

        stars.append("  </g>")
        return "\n".join(stars)

    # ------------------------------------------------------------------ platform / blocks

    def _render_platform(self, iso: IsoProjection, grid_items: list[GridItem]) -> str:
        """Render the beveled plinth / island beneath the city."""
        cols = [item[0] for item in grid_items]
        rows = [item[1] for item in grid_items]
        min_c, max_c = min(cols) - 1, max(cols) + 1
        min_r, max_r = min(rows) - 1, max(rows) + 1

        top_corner = iso.get_tile_top(min_c, min_r)
        right_tile = iso.get_tile_top(max_c, min_r)
        right_corner = Point2D(right_tile.x + iso.half_w, right_tile.y + iso.half_h)
        bottom_tile = iso.get_tile_top(max_c, max_r)
        bottom_corner = Point2D(bottom_tile.x, bottom_tile.y + iso.tile_height)
        left_tile = iso.get_tile_top(min_c, max_r)
        left_corner = Point2D(left_tile.x - iso.half_w, left_tile.y + iso.half_h)

        depth = PLINTH_DEPTH * self._scale
        pts_top = [top_corner, right_corner, bottom_corner, left_corner]
        pts_left = [
            left_corner,
            bottom_corner,
            bottom_corner.offset(0, depth),
            left_corner.offset(0, depth),
        ]
        pts_right = [
            bottom_corner,
            right_corner,
            right_corner.offset(0, depth),
            bottom_corner.offset(0, depth),
        ]
        return (
            '  <g id="city-platform">\n'
            f'    <polygon class="pl" points="{polygon_svg_points(pts_left)}" />\n'
            f'    <polygon class="pr" points="{polygon_svg_points(pts_right)}" />\n'
            f'    <polygon class="pt" points="{polygon_svg_points(pts_top)}" />\n'
            "  </g>"
        )

    def _render_city_blocks(self, iso: IsoProjection, grid_items: list[GridItem]) -> str:
        """Render ground tiles (one path) and then buildings sorted back to front."""
        lines: list[str] = ['  <g id="city-blocks">']

        # All empty tiles are flat, so they can be drawn first as a single path
        if self.config.show_zero_tiles:
            segments = []
            for col, row, day in grid_items:
                if day is None or day.count == 0:
                    d = iso.get_tile_diamond(col, row)
                    segments.append("M" + "L".join(f"{p.x:.1f} {p.y:.1f}" for p in d) + "Z")
            if segments:
                lines.append(f'    <path class="gt" d="{"".join(segments)}" />')

        # Depth sorting: sort by (col + row) ascending so background is drawn first
        for col, row, day in sorted(grid_items, key=lambda item: (item[0] + item[1], item[1])):
            if day is not None and day.count > 0:
                lines.append(self._render_building(iso, col, row, day))

        lines.append("  </g>")
        return "\n".join(lines)

    def _calculate_building_height(self, count: int, max_count: int | None = None) -> float:
        """Building height in unscaled pixels for a given contribution count.

        ``power`` (default) grows sub-linearly (count**0.78). ``linear`` makes the height above
        the minimum exactly proportional to the count, ``sqrt`` and ``log`` sit in between.
        All non-default modes are relative to ``max_count`` (the busiest day).
        """
        if count <= 0:
            return 0.0
        cfg = self.config
        mode = cfg.height_mode
        if mode == "power" or not max_count:
            h = cfg.min_building_height + ((count**0.78) * 8.5 * cfg.building_scale)
        else:
            span = cfg.max_building_height - cfg.min_building_height
            if mode == "linear":
                frac = count / max_count
            elif mode == "sqrt":
                frac = math.sqrt(count / max_count)
            else:  # log
                frac = math.log1p(count) / math.log1p(max_count)
            h = cfg.min_building_height + span * frac * cfg.building_scale
        return min(cfg.max_building_height, round(h, 1))

    def _render_building(self, iso: IsoProjection, col: int, row: int, day: ContributionDay) -> str:
        """Render a single 3D isometric building block with rooftop and windows."""
        count, level = day.count, max(1, min(4, day.level))
        palette = self.theme.get_level_palette(level)
        base_h = self._calculate_building_height(count, self._max_count)
        height = base_h * self._scale

        roof_pts = iso.get_tile_diamond(col, row, height_offset=height)
        left_pts = iso.get_left_face(col, row, height)
        right_pts = iso.get_right_face(col, row, height)

        date_str = escape(day.date)
        out: list[str] = [f'    <g data-count="{count}">']
        if self.config.show_tooltips:
            plural = "" if count == 1 else "s"
            out.append(f"      <title>{date_str}: {count} contribution{plural}</title>")

        out.append(f'      <polygon class="A{level}" points="{polygon_svg_points(left_pts)}" />')
        out.append(f'      <polygon class="Z{level}" points="{polygon_svg_points(right_pts)}" />')

        if self.config.show_windows and base_h >= 14.0:
            out.extend(self._render_windows(iso, col, row, height, base_h, level))

        out.append(f'      <polygon class="R{level}" points="{polygon_svg_points(roof_pts)}" />')

        if level >= 3 or count >= 8:
            out.append(self._render_rooftop_accent(iso, col, row, height, level, palette))

        out.append("    </g>")
        return "\n".join(out)

    def _render_windows(
        self,
        iso: IsoProjection,
        col: int,
        row: int,
        height: float,
        base_h: float,
        level: int,
    ) -> list[str]:
        """Illuminated windows: at most four <path> elements per building."""
        top = iso.get_tile_top(col, row)
        hw, hh, s = iso.half_w, iso.half_h, self._scale

        floors = min(int((base_h - 8.0) // FLOOR_SPACING), 14)
        groups: dict[str, list[str]] = {"WL": [], "WD": [], "XL": [], "XD": []}

        for f_idx in range(floors):
            f_off = (6.0 + f_idx * FLOOR_SPACING) * s
            lit = ((col * 37 + row * 19 + f_idx * 13) % 4) != 0
            left_key, right_key = ("WL", "XL") if lit else ("WD", "XD")

            lx1, ly1 = top.x - hw * 0.7, top.y + hh * 0.7 - height + f_off
            lx2, ly2 = top.x - hw * 0.3, top.y + hh * 0.3 - height + f_off
            groups[left_key].append(f"M{lx1:.0f} {ly1:.0f}L{lx2:.0f} {ly2:.0f}")

            rx1, ry1 = top.x + hw * 0.3, top.y + hh * 0.3 - height + f_off
            rx2, ry2 = top.x + hw * 0.7, top.y + hh * 0.7 - height + f_off
            groups[right_key].append(f"M{rx1:.0f} {ry1:.0f}L{rx2:.0f} {ry2:.0f}")

        return [
            f'      <path class="w {key}{level}" d="{"".join(segs)}" />'
            for key, segs in groups.items()
            if segs
        ]

    def _render_rooftop_accent(
        self,
        iso: IsoProjection,
        col: int,
        row: int,
        height: float,
        level: int,
        palette: LevelPalette,
    ) -> str:
        """Render rooftop spire or beacon for top-tier buildings."""
        top = iso.get_tile_top(col, row)
        center_x = round(top.x, 1)
        center_y = round(top.y - height + iso.half_h, 1)
        spire_len = (10.0 if level >= 4 else 6.0) * self._scale
        spire_top_y = round(center_y - spire_len, 1)
        return (
            f'      <path class="N{level}" fill="none" d="M{center_x} {center_y}V{spire_top_y}" />\n'
            f'      <circle class="G{level}" cx="{center_x}" cy="{spire_top_y}" r="1.5" />'
        )

    def _render_empty_state(self) -> str:
        """Render a placeholder when no contributions exist."""
        cx = self.config.width / 2.0
        cy = self.config.height / 2.0
        return (
            f'  <g id="empty-state" text-anchor="middle">'
            f'<text class="ts" x="{cx}" y="{cy}" font-family="monospace" font-size="14">'
            f"No contribution data to display</text></g>"
        )

    # ------------------------------------------------------------------ header

    def _render_header(self, dataset: ContributionDataSet) -> str:
        """Render developer HUD header overlay with city statistics."""
        font_mono = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"

        title = escape(self.config.custom_title or "CONTRIBUTION CITY")
        user_label = f"@{escape(dataset.username)}" if dataset.username else "ANONYMOUS DEVELOPER"
        total_str = f"{dataset.total_contributions:,}"
        max_str = f"{dataset.max_count}"
        streak_str = f"{dataset.max_streak}d"

        info = user_label
        if dataset.start_date and dataset.end_date:
            info += f"  |  {escape(dataset.start_date)} &#8594; {escape(dataset.end_date)}"
        if dataset.private_contributions > 0:
            info += f"  |  +{dataset.private_contributions:,} private"

        w = self.config.width
        header = [
            '  <g id="city-hud" transform="translate(40, 42)">',
            '    <circle class="ta" cx="0" cy="-6" r="4" filter="url(#glow)" />',
            f'    <text class="tp" x="14" y="0" font-family="{font_mono}" '
            f'font-size="18" font-weight="700" letter-spacing="1.5">{title}</text>',
            f'    <text class="ts" x="14" y="20" font-family="{font_mono}" '
            f'font-size="12" letter-spacing="0.5">{info}</text>',
            f'    <g transform="translate({w - 240}, -6)">',
            f'      <text class="ts" x="0" y="6" font-family="{font_mono}" '
            f'font-size="10">CONTRIBUTIONS</text>',
            f'      <text class="ta" x="0" y="24" font-family="{font_mono}" '
            f'font-size="16" font-weight="700">{total_str}</text>',
            f'      <text class="ts" x="100" y="6" font-family="{font_mono}" '
            f'font-size="10">PEAK / STREAK</text>',
            f'      <text class="tp" x="100" y="24" font-family="{font_mono}" '
            f'font-size="16" font-weight="700">{max_str} <tspan class="ts" font-size="11">'
            f"/ {streak_str}</tspan></text>",
            "    </g>",
            "  </g>",
        ]
        return "\n".join(header)
