"""Height presets, building styles and viewing angles (new in 1.3)."""

from __future__ import annotations

import math
import re

import pytest

from contribution_city.config import AppConfig, ConfigError
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.layouts import LAYOUT_NAMES
from contribution_city.renderer.presets import (
    BUILDING_STYLES,
    HEIGHT_PRESET_NAMES,
    HEIGHT_PRESETS,
    LIMITS,
    VIEW_ANGLE_NAMES,
    VIEW_ANGLES,
)
from contribution_city.renderer.svg import HEIGHT_MODES
from contribution_city.renderer.themes import THEMES
from contribution_city.svgcheck import check_svg
from contribution_city.visual.fixtures import build_fixture

FULL = build_fixture("full-year")


def render(fixture=FULL, **options) -> str:
    return CityRenderer(RenderConfig(show_header=False, **options)).render(fixture)


def numbers(svg: str) -> list[tuple[float, float]]:
    """Every (x, y) coordinate pair of polygons, ground tiles and window segments."""
    pairs: list[tuple[float, float]] = []
    for pts in re.findall(r'points="([^"]+)"', svg):
        n = [float(v) for v in pts.replace(",", " ").split()]
        pairs += list(zip(n[0::2], n[1::2], strict=False))
    for d in re.findall(r'<path class="(?:gt|w )[^"]*" d="([^"]+)"', svg):
        n = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
        pairs += list(zip(n[0::2], n[1::2], strict=False))
    return pairs


# ---------------------------------------------------------------- height presets


class TestHeightPresets:
    def test_names_and_default(self) -> None:
        assert HEIGHT_PRESET_NAMES == ("standard", "tall", "custom")
        assert CityRenderer(RenderConfig()).height_preset == "standard"

    def test_standard_is_proportionate_tall_is_the_old_look(self) -> None:
        standard, tall = HEIGHT_PRESETS["standard"], HEIGHT_PRESETS["tall"]
        tile = RenderConfig().tile_width
        assert standard.max_height / tile < 3.5  # at most about three tiles high
        assert tall.max_height / tile > 6.5  # the 1.2.0 towers
        assert (tall.min_height, tall.max_height, tall.coefficient) == (6.0, 125.0, 8.5)

    def test_standard_buildings_are_clearly_lower_than_tall(self) -> None:
        std = CityRenderer(RenderConfig())
        tall = CityRenderer(RenderConfig(height_preset="tall"))
        for count in (1, 5, 10, 25, 38):
            assert std._calculate_building_height(count, 38) < tall._calculate_building_height(
                count, 38
            )
        assert std._calculate_building_height(10**6) == 56.0
        assert tall._calculate_building_height(10**6) == 125.0

    def test_standard_never_exceeds_its_maximum(self) -> None:
        r = CityRenderer(RenderConfig())
        assert (
            max(r._calculate_building_height(c, 10**6) for c in (1, 10, 100, 10**4, 10**9)) <= 56.0
        )

    @pytest.mark.parametrize("preset", HEIGHT_PRESET_NAMES)
    def test_every_preset_renders_valid_svg(self, preset: str) -> None:
        assert check_svg(render(height_preset=preset)).ok

    def test_buildings_in_standard_stand_lower_on_the_page(self) -> None:
        """Compare the tallest building's top edge relative to its own base in the SVG."""

        def tallest_wall(svg: str) -> float:
            best = 0.0
            for left in re.findall(r'<polygon class="A\d" points="([^"]+)"', svg):
                n = [float(v) for v in left.replace(",", " ").split()]
                ys = n[1::2]
                best = max(best, max(ys) - min(ys))
            return best

        small = render(auto_fit=False)
        tall = render(auto_fit=False, height_preset="tall")
        assert tallest_wall(small) < tallest_wall(tall) * 0.6

    def test_explicit_preset_with_scale_scales_that_preset(self) -> None:
        base = CityRenderer(RenderConfig(height_preset="standard"))
        bigger = CityRenderer(RenderConfig(height_preset="standard", building_scale=1.5))
        assert bigger._calculate_building_height(8) > base._calculate_building_height(8)
        assert bigger.height_preset == "standard"

    def test_custom_bounds_are_honoured(self) -> None:
        r = CityRenderer(
            RenderConfig(height_preset="custom", min_building_height=10.0, max_building_height=40.0)
        )
        assert r._calculate_building_height(1) >= 10.0
        assert r._calculate_building_height(10**6) == 40.0

    @pytest.mark.parametrize(
        "legacy",
        [{"building_scale": 1.0}, {"min_building_height": 6.0}, {"max_building_height": 125.0}],
    )
    def test_legacy_explicit_values_select_custom_not_standard(self, legacy: dict) -> None:
        assert CityRenderer(RenderConfig(**legacy)).height_preset == "custom"

    def test_explicit_preset_beats_the_legacy_rule(self) -> None:
        assert (
            CityRenderer(RenderConfig(height_preset="tall", building_scale=1.0)).height_preset
            == "tall"
        )

    @pytest.mark.parametrize(
        ("options", "needle"),
        [
            ({"height_preset": "huge"}, "standard"),
            ({"building_scale": 0.0}, "building_scale"),
            ({"building_scale": 6.0}, "building_scale"),
            ({"min_building_height": -1.0}, "min_building_height"),
            ({"min_building_height": 41.0}, "min_building_height"),
            ({"max_building_height": 7.0}, "max_building_height"),
            ({"max_building_height": 401.0}, "max_building_height"),
            ({"min_building_height": 30.0, "max_building_height": 30.5}, "at least 1 higher"),
            ({"building_scale": float("nan")}, "building_scale"),
            ({"width": 50}, "width"),
            ({"height": 20000}, "height"),
        ],
    )
    def test_invalid_values_have_readable_errors(self, options: dict, needle: str) -> None:
        with pytest.raises(ValueError, match=needle):
            CityRenderer(RenderConfig(**options))

    def test_limits_are_documented_in_one_place(self) -> None:
        assert LIMITS["building_scale"] == (0.1, 5.0)
        assert LIMITS["view_elevation"] == (10.0, 70.0)

    def test_extreme_limits_still_produce_a_valid_svg(self) -> None:
        svg = render(height_preset="custom", building_scale=5.0, max_building_height=400.0)
        assert check_svg(svg).ok
        assert check_svg(
            render(height_preset="custom", building_scale=0.1, min_building_height=0)
        ).ok


class TestHeightModesWithPresets:
    @pytest.mark.parametrize("preset", HEIGHT_PRESET_NAMES)
    @pytest.mark.parametrize("mode", HEIGHT_MODES)
    def test_every_mode_works_with_every_preset(self, preset: str, mode: str) -> None:
        r = CityRenderer(RenderConfig(height_preset=preset, height_mode=mode))
        heights = [r._calculate_building_height(c, 40) for c in (1, 5, 10, 20, 40)]
        assert heights == sorted(heights)  # taller days never get shorter buildings
        assert heights[-1] <= r.max_height
        assert check_svg(render(height_preset=preset, height_mode=mode)).ok

    @pytest.mark.parametrize("preset", ["standard", "tall"])
    def test_linear_mode_reaches_the_preset_maximum_on_the_busiest_day(self, preset: str) -> None:
        r = CityRenderer(RenderConfig(height_preset=preset, height_mode="linear"))
        assert r._calculate_building_height(40, 40) == HEIGHT_PRESETS[preset].max_height

    def test_modes_change_the_distribution_not_the_profile(self) -> None:
        for mode in HEIGHT_MODES:
            r = CityRenderer(RenderConfig(height_mode=mode))
            assert r.max_height == 56.0 and r.height_preset == "standard"


# ---------------------------------------------------------------- building style


class TestBuildingStyle:
    def test_names(self) -> None:
        assert BUILDING_STYLES == ("detailed", "solid")

    def test_detailed_is_the_default_and_keeps_windows_and_beacons(self) -> None:
        svg = render(height_preset="tall")
        assert 'class="w ' in svg  # window paths
        assert 'class="G' in svg  # rooftop beacon dots
        assert render() == render(building_style="detailed")

    @pytest.mark.parametrize("preset", HEIGHT_PRESET_NAMES)
    def test_solid_has_no_windows_no_beacons_no_antennas(self, preset: str) -> None:
        svg = render(building_style="solid", height_preset=preset)
        assert 'class="w ' not in svg
        assert not re.search(r'class="[NG]\d"', svg)
        assert "<circle" not in svg.split('<g id="city-blocks">')[1]
        assert "<path" not in re.sub(
            r'<path class="gt"[^>]*/>', "", svg.split('<g id="city-blocks">')[1]
        )

    def test_solid_buildings_are_still_three_shaded_faces(self) -> None:
        svg = render(building_style="solid")
        buildings = svg.count("<g data-count=")
        assert buildings > 100
        for face in ("A", "Z", "R"):
            assert len(re.findall(rf'<polygon class="{face}\d"', svg)) == buildings

    @pytest.mark.parametrize("theme", sorted(THEMES))
    def test_every_theme_renders_solid_cleanly(self, theme: str) -> None:
        svg = render(building_style="solid", theme=theme)
        assert check_svg(svg).ok and 'class="w ' not in svg

    @pytest.mark.parametrize("theme", sorted(THEMES))
    def test_shading_keeps_roof_left_and_right_distinct(self, theme: str) -> None:
        from test_themes_layouts import luminance

        for palette in THEMES[theme].levels.values():
            roof, left, right = (
                luminance(palette.roof),
                luminance(palette.left_face),
                luminance(palette.right_face),
            )
            assert roof > left > right

    def test_solid_faces_have_no_outline_of_another_colour(self) -> None:
        css = re.search(r"<style>(.*?)</style>", render(building_style="solid"), re.S).group(1)
        for rule in re.findall(r"\.([RAZ]\d)\{fill:(#\w+);stroke:(#\w+);", css):
            assert rule[1] == rule[2]

    def test_show_windows_false_in_detailed_style_keeps_the_beacons(self) -> None:
        svg = render(height_preset="tall", show_windows=False)
        assert 'class="w ' not in svg and 'class="G' in svg

    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    def test_solid_works_with_every_layout(self, layout: str) -> None:
        assert check_svg(render(building_style="solid", layout=layout)).ok

    def test_solid_is_smaller_than_detailed(self) -> None:
        assert len(render(building_style="solid")) < len(render())

    def test_unknown_style_has_a_readable_error(self) -> None:
        with pytest.raises(ValueError, match="detailed, solid"):
            CityRenderer(RenderConfig(building_style="glass"))

    def test_solid_keeps_tooltips_and_counts(self) -> None:
        svg = render(building_style="solid")
        assert "contribution" in svg and svg.count("data-count=") == svg.count("<g data-count=")


# ---------------------------------------------------------------- view angles


def first_ground_tile_ratio(svg: str) -> float:
    d = re.search(r'<path class="gt" d="([^"]+)"', svg).group(1)
    first = d.split("Z")[0]
    pts = [tuple(float(v) for v in seg.split()) for seg in first.lstrip("M").split("L")]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (max(ys) - min(ys)) / (max(xs) - min(xs))


class TestViewAngles:
    def test_names_and_default(self) -> None:
        assert VIEW_ANGLE_NAMES == ("isometric", "low", "high", "top-down")
        assert CityRenderer(RenderConfig()).view_elevation == 30.0

    def test_isometric_is_byte_identical_to_the_default_view(self) -> None:
        assert render(view_angle="isometric") == render()

    def test_presets_are_genuinely_different_views(self) -> None:
        svgs = {name: render(view_angle=name) for name in VIEW_ANGLE_NAMES}
        assert len(set(svgs.values())) == len(svgs), (
            "Every view_angle preset must produce a distinct SVG"
        )
        # Verify the exact elevation values documented in presets.py
        expected = {"isometric": 30.0, "low": 20.0, "high": 42.0, "top-down": 58.0}
        for name, deg in expected.items():
            assert VIEW_ANGLES[name].elevation == pytest.approx(deg), (
                f"VIEW_ANGLES[{name!r}].elevation expected {deg}°, "
                f"got {VIEW_ANGLES[name].elevation}°"
            )
        # Presets must be ordered by angular distance from the 30° baseline
        elevations = [VIEW_ANGLES[n].elevation for n in VIEW_ANGLE_NAMES]
        assert elevations == sorted(elevations, key=lambda e: abs(e - 30.0)), (
            "VIEW_ANGLE_NAMES must be ordered by distance from the isometric baseline (30°)"
        )

    @pytest.mark.parametrize("name", VIEW_ANGLE_NAMES)
    def test_tile_shape_follows_the_camera_elevation(self, name: str) -> None:
        ratio = first_ground_tile_ratio(render(view_angle=name, auto_fit=False))
        assert ratio == pytest.approx(math.sin(math.radians(VIEW_ANGLES[name].elevation)), abs=0.01)

    def test_lower_camera_means_flatter_ground_higher_camera_means_rounder(self) -> None:
        ratios = [
            first_ground_tile_ratio(render(view_angle=n, auto_fit=False))
            for n in ("low", "isometric", "high", "top-down")
        ]
        assert ratios == sorted(ratios)

    def test_buildings_are_foreshortened_from_above(self) -> None:
        def wall(svg: str) -> float:
            best = 0.0
            for pts in re.findall(r'<polygon class="A\d" points="([^"]+)"', svg):
                n = [float(v) for v in pts.replace(",", " ").split()]
                best = max(best, max(n[1::2]) - min(n[1::2]))
            return best

        low, iso, top = (
            wall(render(view_angle=v, auto_fit=False, height_preset="tall"))
            for v in ("low", "isometric", "top-down")
        )
        assert low > iso > top

    @pytest.mark.parametrize("angle", VIEW_ANGLE_NAMES)
    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    @pytest.mark.parametrize("preset", ["standard", "tall"])
    def test_city_never_clips_the_canvas(self, angle: str, layout: str, preset: str) -> None:
        svg = render(view_angle=angle, layout=layout, height_preset=preset)
        pairs = numbers(svg)
        xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
        assert min(xs) >= 0 and max(xs) <= 1200 and min(ys) >= 0 and max(ys) <= 680
        ellipse = re.search(
            r'<ellipse class="sh" cx="([\d.]+)" cy="([\d.]+)" rx="([\d.]+)" ry="([\d.]+)"', svg
        )
        if ellipse:
            cx, cy, rx, ry = map(float, ellipse.groups())
            assert cy + ry <= 680 and cx - rx >= 0 and cx + rx <= 1200

    @pytest.mark.parametrize("angle", VIEW_ANGLE_NAMES)
    @pytest.mark.parametrize("size", [(1200, 680), (800, 450), (400, 300)])
    def test_clipping_free_for_other_canvas_sizes(self, angle: str, size: tuple[int, int]) -> None:
        svg = render(view_angle=angle, width=size[0], height=size[1])
        pairs = numbers(svg)
        assert max(p[0] for p in pairs) <= size[0] and max(p[1] for p in pairs) <= size[1]
        assert min(p[0] for p in pairs) >= 0 and min(p[1] for p in pairs) >= 0

    @pytest.mark.parametrize("angle", VIEW_ANGLE_NAMES)
    def test_every_angle_is_valid_svg_with_all_parts_aligned(self, angle: str) -> None:
        svg = render(view_angle=angle, layout="floating-island")
        assert check_svg(svg).ok
        assert svg.count('class="pt"') == 1 and "<ellipse" in svg

    def test_windows_stay_on_their_walls_at_every_angle(self) -> None:
        for angle in VIEW_ANGLE_NAMES:
            svg = render(view_angle=angle, height_preset="tall")
            assert 'class="w ' in svg and check_svg(svg).ok

    def test_numeric_elevation(self) -> None:
        assert first_ground_tile_ratio(render(view_elevation=45, auto_fit=False)) == pytest.approx(
            math.sin(math.radians(45)), abs=0.01
        )

    def test_numeric_elevation_overrides_the_preset_with_a_warning_on_conflict(self) -> None:
        with pytest.warns(UserWarning, match="overrides view_angle"):
            svg = render(view_angle="low", view_elevation=50)
        assert svg == render(view_elevation=50)

    @pytest.mark.parametrize("bad", [9.9, 70.1, -5, 0])
    def test_elevation_limits(self, bad: float) -> None:
        with pytest.raises(ValueError, match="view_elevation"):
            CityRenderer(RenderConfig(view_elevation=bad))

    def test_unknown_view_has_a_readable_error(self) -> None:
        with pytest.raises(ValueError, match="isometric, low, high, top-down"):
            CityRenderer(RenderConfig(view_angle="sideways"))

    def test_legacy_tile_height_still_works_in_the_default_view(self) -> None:
        assert first_ground_tile_ratio(render(tile_height=10.0, auto_fit=False)) == pytest.approx(
            10 / 18, abs=0.01
        )

    def test_background_modes_work_in_every_view(self) -> None:
        for angle in VIEW_ANGLE_NAMES:
            for mode in ("solid", "transparent", "transparent-sky"):
                assert check_svg(render(view_angle=angle, background=mode)).ok

    @pytest.mark.parametrize(
        ("name", "expected_deg"),
        [
            ("isometric", 30.0),
            ("low", 20.0),
            ("high", 42.0),
            ("top-down", 58.0),
        ],
    )
    def test_view_angle_exact_elevation(self, name: str, expected_deg: float) -> None:
        """Each named preset must map to its documented elevation in degrees (B4 fix)."""
        assert VIEW_ANGLES[name].elevation == pytest.approx(expected_deg), (
            f"VIEW_ANGLES[{name!r}].elevation expected {expected_deg}°, "
            f"got {VIEW_ANGLES[name].elevation}°"
        )


# ---------------------------------------------------------------- configuration


class TestConfigurationFile:
    def test_all_new_keys_are_accepted(self) -> None:
        cfg = AppConfig.from_dict(
            {
                "city": {
                    "height_preset": "tall",
                    "building_style": "solid",
                    "view_angle": "low",
                    "min_building_height": 4,
                    "max_building_height": 80,
                    "building_scale": 1.2,
                    "view_elevation": 25,
                }
            }
        )
        rc = cfg.to_render_config()
        assert (rc.height_preset, rc.building_style, rc.view_angle) == ("tall", "solid", "low")
        assert (rc.min_building_height, rc.max_building_height, rc.building_scale) == (
            4.0,
            80.0,
            1.2,
        )
        assert rc.view_elevation == 25.0

    def test_defaults_are_unset_so_the_preset_decides(self) -> None:
        city = AppConfig.from_dict({}).city
        assert city.height_preset is None and city.building_scale is None
        assert (city.building_style, city.view_angle) == ("detailed", None)
        assert CityRenderer(AppConfig.from_dict({}).to_render_config()).height_preset == "standard"

    def test_a_1_2_0_config_with_explicit_heights_keeps_its_look(self) -> None:
        old = {
            "city": {
                "building_scale": 1.0,
                "min_building_height": 6.0,
                "max_building_height": 125.0,
            }
        }
        rc = AppConfig.from_dict(old).to_render_config()
        assert CityRenderer(rc).height_preset == "custom"
        assert CityRenderer(rc).render(FULL) == CityRenderer(
            RenderConfig(height_preset="tall")
        ).render(FULL)

    @pytest.mark.parametrize(
        ("city", "needle"),
        [
            ({"height_preset": "huge"}, "height_preset"),
            ({"building_style": "glass"}, "building_style"),
            ({"view_angle": "sideways"}, "view_angle"),
            ({"view_elevation": 80}, "view_elevation"),
            ({"building_scale": 9}, "building_scale"),
            ({"min_building_height": 50}, "min_building_height"),
            ({"max_building_height": 5}, "max_building_height"),
            ({"min_building_height": 20, "max_building_height": 20}, "at least 1 higher"),
            ({"building_scale": "tall"}, "must be a number"),
        ],
    )
    def test_invalid_values_are_rejected_readably(self, city: dict, needle: str) -> None:
        with pytest.raises(ConfigError, match=needle):
            AppConfig.from_dict({"city": city})

    def test_example_configs_load_and_render(self) -> None:
        from pathlib import Path

        root = Path(__file__).parent.parent
        files = sorted((root / "examples").glob("*.yaml")) + sorted(
            (root / "examples/config").glob("*.yaml")
        )
        assert files
        for f in files:
            cfg = AppConfig.from_file(f)
            assert check_svg(CityRenderer(cfg.to_render_config()).render(FULL)).ok, f.name
