"""Background modes: semantics, precedence over the legacy flag, and real transparency."""

from __future__ import annotations

import warnings

import pytest

from contribution_city.config import AppConfig, ConfigError
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.svg import BACKGROUND_MODES
from contribution_city.svgcheck import check_svg
from contribution_city.visual.fixtures import build_fixture
from contribution_city.visual.render import composite, svg_to_image

DARK, LIGHT = (12, 14, 22), (250, 250, 252)


def render(**options) -> str:
    return CityRenderer(RenderConfig(show_header=False, **options)).render(build_fixture("minimal"))


def has_bg_rect(svg: str) -> bool:
    return 'fill="url(#bg)"' in svg


def has_stars(svg: str) -> bool:
    return 'id="sky-stars"' in svg


class TestModes:
    def test_all_documented_modes_exist(self) -> None:
        assert BACKGROUND_MODES == ("solid", "transparent", "transparent-sky", "auto")

    def test_solid_has_rectangle_and_stars(self) -> None:
        svg = render(background="solid")
        assert has_bg_rect(svg) and has_stars(svg)

    def test_transparent_has_neither(self) -> None:
        svg = render(background="transparent")
        assert not has_bg_rect(svg) and not has_stars(svg)

    def test_transparent_sky_keeps_stars_but_no_rectangle(self) -> None:
        svg = render(background="transparent-sky")
        assert not has_bg_rect(svg) and has_stars(svg)

    def test_auto_is_solid_for_fixed_palettes(self) -> None:
        svg = render(background="auto", appearance="fixed")
        assert has_bg_rect(svg) and has_stars(svg)

    def test_auto_lets_the_page_show_through_when_appearance_is_auto(self) -> None:
        svg = render(background="auto", appearance="auto", theme="profile")
        assert not has_bg_rect(svg) and has_stars(svg)

    def test_stars_can_still_be_hidden(self) -> None:
        assert not has_stars(render(background="transparent-sky", show_stars=False))
        assert not has_stars(render(background="solid", show_stars=False))

    def test_invalid_mode_is_rejected_with_choices(self) -> None:
        with pytest.raises(ValueError, match="transparent-sky"):
            CityRenderer(RenderConfig(background="clear"))

    @pytest.mark.parametrize("mode", BACKGROUND_MODES)
    def test_every_mode_is_valid_svg(self, mode: str) -> None:
        assert check_svg(render(background=mode)).ok


class TestLegacyFlagAndPrecedence:
    def test_default_is_unchanged_solid(self) -> None:
        svg = render()
        assert has_bg_rect(svg) and has_stars(svg)

    def test_legacy_transparent_flag_still_works(self) -> None:
        svg = render(transparent=True)
        assert not has_bg_rect(svg) and not has_stars(svg)

    def test_background_wins_over_the_flag(self) -> None:
        svg = render(transparent=True, background="transparent-sky")
        assert not has_bg_rect(svg) and has_stars(svg)

    def test_contradictory_settings_warn_and_background_wins(self) -> None:
        with pytest.warns(UserWarning, match="overrides transparent"):
            svg = render(transparent=True, background="solid")
        assert has_bg_rect(svg)

    def test_consistent_settings_do_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            render(transparent=True, background="transparent")
            render(transparent=False, background="solid")

    def test_same_effective_result_as_the_old_flag(self) -> None:
        assert render(transparent=True) == render(background="transparent")


class TestRealTransparency:
    """Render to pixels and look at the corners, on both a light and a dark surface."""

    @staticmethod
    def corner(svg: str, surface=None) -> tuple[int, int, int, int]:
        image = composite(svg_to_image(svg, 300), surface)
        return image.getpixel((0, 0))

    @pytest.mark.parametrize("mode", ["transparent", "transparent-sky"])
    def test_corner_is_fully_transparent(self, mode: str) -> None:
        assert self.corner(render(background=mode))[3] == 0

    @pytest.mark.parametrize("mode", ["transparent", "transparent-sky"])
    @pytest.mark.parametrize("surface", [DARK, LIGHT])
    def test_page_colour_shows_through(self, mode: str, surface: tuple[int, int, int]) -> None:
        px = self.corner(render(background=mode), surface)
        assert px[:3] == surface

    @pytest.mark.parametrize("surface", [DARK, LIGHT])
    def test_solid_hides_the_surface(self, surface: tuple[int, int, int]) -> None:
        px = self.corner(render(background="solid"), surface)
        assert px[3] == 255 and px[:3] != surface

    def test_no_stray_opaque_pixels_in_transparent_sky_corners(self) -> None:
        image = svg_to_image(render(background="transparent-sky"), 300)
        w, h = image.size
        for point in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            assert image.getpixel(point)[3] == 0

    def test_transparent_sky_has_some_visible_stars(self) -> None:
        sky = svg_to_image(render(background="transparent-sky"), 560)
        plain = svg_to_image(render(background="transparent"), 560)
        assert sky.getchannel("A").getbbox() != plain.getchannel("A").getbbox() or (
            sum(1 for a in sky.getchannel("A").getdata() if a)
            > sum(1 for a in plain.getchannel("A").getdata() if a)
        )


class TestConfigurationAndPrecedence:
    def test_config_file_background(self) -> None:
        cfg = AppConfig.from_dict({"city": {"background": "transparent-sky"}})
        assert cfg.to_render_config().background == "transparent-sky"

    def test_invalid_background_in_config(self) -> None:
        with pytest.raises(ConfigError, match="background"):
            AppConfig.from_dict({"city": {"background": "nope"}})

    def test_legacy_transparent_in_config_still_parses(self) -> None:
        cfg = AppConfig.from_dict({"city": {"transparent": True}})
        assert cfg.to_render_config().transparent is True
        assert cfg.to_render_config().background is None
