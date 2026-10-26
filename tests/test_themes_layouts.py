"""Themes and layouts: new presets, validation, and v1.1.0 compatibility."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from contribution_city.config import AppConfig, ConfigError
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.layouts import LAYOUT_NAMES, LAYOUT_SPECS
from contribution_city.renderer.palettes import PALETTE_SPECS
from contribution_city.renderer.themes import THEMES, get_theme
from contribution_city.svgcheck import check_svg
from contribution_city.visual.fixtures import build_fixture

REF = json.loads((Path(__file__).parent / "data/v110/reference.json").read_text(encoding="utf-8"))
NEW_THEMES = [spec["name"] for spec in PALETTE_SPECS]
NEW_LAYOUTS = ["dense-grid", "downtown", "floating-island", "wireframe"]


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    chans = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        chans.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chans[0] + 0.7152 * chans[1] + 0.0722 * chans[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TestNewThemes:
    def test_all_six_requested_themes_exist(self) -> None:
        expected = {
            "neon-harbor",
            "cyberpunk",
            "emerald-matrix",
            "copper-forge",
            "arctic-glass",
            "sunset-grid",
        }
        assert expected <= set(THEMES)
        assert set(NEW_THEMES) == expected

    @pytest.mark.parametrize("name", NEW_THEMES)
    def test_palette_is_complete_and_valid_hex(self, name: str) -> None:
        theme = get_theme(name)
        assert set(theme.levels) == {1, 2, 3, 4}
        colors = [
            theme.bg_top,
            theme.bg_bottom,
            theme.platform_top,
            theme.platform_grid,
            theme.text_primary,
            theme.star_color,
        ]
        for level in theme.levels.values():
            colors += [
                level.roof,
                level.left_face,
                level.right_face,
                level.window_lit,
                level.stroke,
            ]
        assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in colors)
        assert theme.description

    @pytest.mark.parametrize("name", NEW_THEMES)
    def test_text_is_readable_on_the_background(self, name: str) -> None:
        t = get_theme(name)
        assert contrast(t.text_primary, t.bg_top) >= 7.0
        assert contrast(t.text_primary, t.bg_bottom) >= 7.0
        assert contrast(t.text_secondary, t.bg_bottom) >= 4.5

    @pytest.mark.parametrize("name", NEW_THEMES)
    def test_levels_separate_clearly_from_low_to_high(self, name: str) -> None:
        """Roof brightness must rise with the level, with visible steps between levels."""
        roofs = [luminance(get_theme(name).levels[i].roof) for i in (1, 2, 3, 4)]
        assert roofs == sorted(roofs)
        assert all(b - a > 0.015 for a, b in zip(roofs, roofs[1:], strict=False))

    @pytest.mark.parametrize("name", NEW_THEMES)
    def test_towers_stand_out_from_the_ground(self, name: str) -> None:
        t = get_theme(name)
        assert contrast(t.levels[4].roof, t.bg_bottom) >= 4.0
        assert contrast(t.levels[1].roof, t.bg_bottom) >= 1.5

    @pytest.mark.parametrize("name", NEW_THEMES)
    def test_windows_are_visible_on_walls(self, name: str) -> None:
        t = get_theme(name)
        for level in t.levels.values():
            assert contrast(level.window_lit, level.left_face) >= 2.5

    @pytest.mark.parametrize("name", NEW_THEMES)
    def test_theme_renders_a_valid_city_without_extra_filters(self, name: str) -> None:
        svg = CityRenderer(RenderConfig(theme=name)).render(build_fixture("full-year"))
        assert check_svg(svg).ok
        # Only the single glow filter of the header marker; no per-building filters
        assert svg.count("<filter") == 1
        assert svg.count("filter=") == 1

    def test_palettes_live_in_one_place(self) -> None:
        """New themes are data in palettes.py, not hard-coded colour blocks in themes.py."""
        source = (
            Path(__file__).parent.parent / "src/contribution_city/renderer/themes.py"
        ).read_text(encoding="utf-8")
        for name in NEW_THEMES:
            assert f'"{name}"' not in source


class TestThemeValidation:
    def test_unknown_theme_error_lists_valid_names(self) -> None:
        with pytest.raises(ValueError) as err:
            get_theme("neon-habour")
        message = str(err.value)
        assert "neon-habour" in message and "neon-harbor" in message

    def test_config_rejects_unknown_theme(self) -> None:
        with pytest.raises(ConfigError, match="theme"):
            AppConfig.from_dict({"theme": "does-not-exist"})

    def test_theme_names_are_case_insensitive(self) -> None:
        assert get_theme("Neon-Harbor").name == "neon-harbor"


class TestV110Compatibility:
    def test_original_themes_are_unchanged(self) -> None:
        for name, ref in REF["themes"].items():
            t = THEMES[name]
            assert [t.bg_top, t.bg_bottom] == ref["bg"], name
            assert [t.platform_top, t.platform_left, t.platform_right, t.platform_grid] == ref[
                "platform"
            ]
            assert [t.ground_tile_fill, t.ground_tile_stroke] == ref["ground"]
            assert [t.text_primary, t.text_secondary, t.text_accent] == ref["text"]
            assert t.star_color == ref["star"]
            for lvl, vals in ref["levels"].items():
                p = t.levels[int(lvl)]
                assert [
                    p.roof,
                    p.left_face,
                    p.right_face,
                    p.window_lit,
                    p.window_dim,
                    p.antenna_glow,
                    p.stroke,
                ] == vals, f"{name} level {lvl}"

    @pytest.mark.parametrize("case", sorted(REF["renders"]))
    def test_v110_output_is_byte_identical(self, case: str) -> None:
        import hashlib

        ref = REF["renders"][case]
        svg = CityRenderer(RenderConfig(**ref["options"])).render(build_fixture(ref["fixture"]))
        normalised = re.sub(r'\s+xmlns:c2pa="[^"]*"|<metadata>.*?</metadata>', "", svg, flags=re.S)
        assert hashlib.sha256(normalised.encode()).hexdigest() == ref["sha256"], (
            f"'{case}' no longer renders exactly like v1.1.0"
        )

    def test_calendar_and_compact_layouts_still_exist_unchanged(self) -> None:
        assert LAYOUT_NAMES[:2] == ("calendar", "compact")


class TestLayouts:
    def test_requested_layouts_are_registered(self) -> None:
        assert set(NEW_LAYOUTS) <= set(LAYOUT_SPECS)

    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    def test_each_layout_renders_valid_deterministic_svg(self, layout: str) -> None:
        data = build_fixture("full-year")
        first = CityRenderer(RenderConfig(layout=layout)).render(data)
        second = CityRenderer(RenderConfig(layout=layout)).render(build_fixture("full-year"))
        assert first == second
        assert check_svg(first).ok

    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    @pytest.mark.parametrize("fixture", ["minimal", "empty", "uniform", "extreme"])
    def test_layouts_handle_edge_datasets(self, layout: str, fixture: str) -> None:
        svg = CityRenderer(RenderConfig(layout=layout)).render(build_fixture(fixture))
        assert check_svg(svg).ok

    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    def test_every_day_with_activity_becomes_one_building(self, layout: str) -> None:
        data = build_fixture("full-year")
        svg = CityRenderer(RenderConfig(layout=layout)).render(data)
        active = sum(1 for d in data.days if d.count > 0)
        assert svg.count("<g data-count=") == active

    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    def test_city_stays_inside_the_canvas(self, layout: str) -> None:
        svg = CityRenderer(RenderConfig(layout=layout)).render(build_fixture("full-year"))
        nums = [
            float(n)
            for pts in re.findall(r'points="([^"]+)"', svg)
            for n in pts.replace(",", " ").split()
        ]
        xs, ys = nums[0::2], nums[1::2]
        assert min(xs) >= 0 and max(xs) <= 1200 and min(ys) >= 0 and max(ys) <= 680

    def test_unknown_layout_error_lists_choices(self) -> None:
        with pytest.raises(ValueError, match="dense-grid"):
            CityRenderer(RenderConfig(layout="skyscraper"))

    def test_config_accepts_new_layouts(self) -> None:
        for name in NEW_LAYOUTS:
            assert AppConfig.from_dict({"layout": name}).layout == name

    def test_dense_grid_wastes_less_space_than_compact(self) -> None:
        from contribution_city.renderer.layouts import place_compact, place_dense_grid

        def occupancy(items) -> float:
            cells = {(c, r) for c, r, _ in items}
            cols = max(c for c, _ in cells) - min(c for c, _ in cells) + 1
            rows = max(r for _, r in cells) - min(r for _, r in cells) + 1
            return len(cells) / (cols * rows)

        days = build_fixture("full-year").days
        assert occupancy(place_dense_grid(days)) > 0.9
        assert occupancy(place_dense_grid(days)) > 2 * occupancy(place_compact(days))

    def test_dense_grid_has_no_empty_tiles_between_buildings(self) -> None:
        from contribution_city.renderer.layouts import place_dense_grid

        items = place_dense_grid(build_fixture("full-year").days)
        cells = {(c, r) for c, r, _ in items}
        cols = max(c for c, _ in cells) + 1
        rows = max(r for _, r in cells) + 1
        assert len(cells) == len(items) and cols * rows - len(cells) < cols

    def test_downtown_puts_the_busiest_days_in_the_centre(self) -> None:
        from contribution_city.renderer.layouts import place_downtown

        items = place_downtown(build_fixture("full-year").days)
        cx = sum(c for c, _, _ in items) / len(items)
        cy = sum(r for _, r, _ in items) / len(items)

        def dist(item) -> float:
            return ((item[0] - cx) ** 2 + (item[1] - cy) ** 2) ** 0.5

        busiest = sorted(items, key=lambda i: -i[2].count)[:10]
        quietest = sorted(items, key=lambda i: i[2].count)[:10]
        assert max(dist(i) for i in busiest) < min(dist(i) for i in quietest)

    def test_downtown_keeps_height_proportional_to_activity(self) -> None:
        r = CityRenderer(RenderConfig(layout="downtown", height_mode="linear"))
        assert r._calculate_building_height(40, 40) > r._calculate_building_height(20, 40)

    def test_floating_island_has_underside_shadow_and_depth(self) -> None:
        svg = CityRenderer(RenderConfig(layout="floating-island")).render(
            build_fixture("full-year")
        )
        for cls in ("ul1", "ur1", "ul3", "ur3", "sh"):
            assert f'class="{cls}"' in svg or f".{cls}{{" in svg
        assert "<ellipse" in svg
        # decoration lives in the platform group, beneath the buildings
        assert svg.index("<ellipse") < svg.index("<g data-count")

    def test_floating_island_fills_the_canvas_comparably(self) -> None:
        svg = CityRenderer(RenderConfig(layout="floating-island")).render(
            build_fixture("full-year")
        )
        ys = [
            float(n)
            for p in re.findall(r'points="([^"]+)"', svg)
            for n in p.replace(",", " ").split()
        ][1::2]
        assert max(ys) <= 680 and (max(ys) - min(ys)) > 300

    def test_wireframe_has_outlines_without_filled_faces_or_windows(self) -> None:
        svg = CityRenderer(RenderConfig(layout="wireframe")).render(build_fixture("full-year"))
        assert 'class="w ' not in svg  # no window paths
        css = re.search(r"<style>(.*?)</style>", svg, re.S).group(1)
        theme = get_theme("navy-cyan")
        roof_rule = re.search(r"\.R3\{([^}]*)\}", css).group(1)
        assert f"fill:{theme.bg_bottom}" in roof_rule  # opaque "paper" hides lines behind
        assert f"stroke:{theme.levels[3].roof}" in roof_rule

    def test_wireframe_ground_has_no_fill(self) -> None:
        css = re.search(
            r"<style>(.*?)</style>",
            CityRenderer(RenderConfig(layout="wireframe")).render(build_fixture("full-year")),
            re.S,
        ).group(1)
        assert re.search(r"\.gt\{fill:none", css)
