"""Tests for SVG isometric city renderer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from contribution_city.models import ContributionDataSet, ContributionDay
from contribution_city.renderer import CityRenderer, RenderConfig, get_theme
from contribution_city.renderer.geometry import IsoProjection, Point2D


class TestGeometry:
    """Test suite for isometric projection math."""

    def test_iso_projection_origin(self) -> None:
        iso = IsoProjection(tile_width=20.0, tile_height=10.0, origin_x=100.0, origin_y=50.0)
        pt = iso.get_tile_top(0, 0)
        assert pt == Point2D(100.0, 50.0)

    def test_iso_projection_steps(self) -> None:
        iso = IsoProjection(tile_width=20.0, tile_height=10.0, origin_x=0.0, origin_y=0.0)
        pt_col1 = iso.get_tile_top(1, 0)
        assert pt_col1 == Point2D(10.0, 5.0)

        pt_row1 = iso.get_tile_top(0, 1)
        assert pt_row1 == Point2D(-10.0, 5.0)

        diamond = iso.get_tile_diamond(0, 0, height_offset=0.0)
        assert len(diamond) == 4
        # Top, Right, Bottom, Left
        assert diamond[0] == Point2D(0.0, 0.0)
        assert diamond[1] == Point2D(10.0, 5.0)
        assert diamond[2] == Point2D(0.0, 10.0)
        assert diamond[3] == Point2D(-10.0, 5.0)


class TestCityRenderer:
    """Test suite for CityRenderer."""

    @pytest.fixture
    def small_dataset(self) -> ContributionDataSet:
        days = [
            ContributionDay(date="2025-01-01", count=0),
            ContributionDay(date="2025-01-02", count=3),
            ContributionDay(date="2025-01-03", count=12),
            ContributionDay(date="2025-01-04", count=25),
        ]
        return ContributionDataSet(username="testuser", days=days)

    def test_render_empty_dataset(self) -> None:
        renderer = CityRenderer()
        svg = renderer.render(ContributionDataSet())
        root = ET.fromstring(svg.encode("utf-8"))
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert "No contribution data to display" in svg

    def test_render_valid_svg(self, small_dataset: ContributionDataSet) -> None:
        renderer = CityRenderer()
        svg = renderer.render(small_dataset)
        root = ET.fromstring(svg.encode("utf-8"))
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.attrib["width"] == "1200"
        assert root.attrib["height"] == "680"
        assert "CONTRIBUTION CITY" in svg
        assert "@testuser" in svg
        assert 'data-count="25"' in svg

    def test_deterministic_output(self, small_dataset: ContributionDataSet) -> None:
        renderer = CityRenderer(RenderConfig(theme="navy-cyan"))
        svg1 = renderer.render(small_dataset)
        svg2 = renderer.render(small_dataset)
        assert svg1 == svg2, "Renderer output must be byte-for-byte identical"

    def test_building_height_scaling(self) -> None:
        cfg = RenderConfig(building_scale=1.0, min_building_height=6.0, max_building_height=100.0)
        renderer = CityRenderer(cfg)

        h0 = renderer._calculate_building_height(0)
        h1 = renderer._calculate_building_height(1)
        h5 = renderer._calculate_building_height(5)
        h50 = renderer._calculate_building_height(50)
        h5000 = renderer._calculate_building_height(5000)

        assert h0 == 0.0
        assert 6.0 < h1 < h5
        assert h5 < h50
        assert h5000 == 100.0  # Clamped to max_building_height

    def test_themes_availability(self, small_dataset: ContributionDataSet) -> None:
        for theme_name in [
            "navy-cyan",
            "matrix-green",
            "sunset-neon",
            "monochrome-slate",
            "solar-amber",
        ]:
            theme = get_theme(theme_name)
            assert theme.name == theme_name
            renderer = CityRenderer(RenderConfig(theme=theme_name))
            svg = renderer.render(small_dataset)
            assert len(svg) > 1000
            # Ensure valid XML
            ET.fromstring(svg.encode("utf-8"))

    def test_invalid_theme_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown theme"):
            get_theme("non-existent-theme")

    def test_compact_layout(self, small_dataset: ContributionDataSet) -> None:
        renderer = CityRenderer(RenderConfig(layout="compact"))
        svg = renderer.render(small_dataset)
        root = ET.fromstring(svg.encode("utf-8"))
        assert root.tag == "{http://www.w3.org/2000/svg}svg"

    def test_feature_flags(self, small_dataset: ContributionDataSet) -> None:
        # Disable windows, stars, header, platform
        cfg = RenderConfig(
            show_windows=False,
            show_stars=False,
            show_header=False,
            show_platform=False,
            show_zero_tiles=False,
        )
        renderer = CityRenderer(cfg)
        svg = renderer.render(small_dataset)

        assert "city-hud" not in svg
        assert "sky-stars" not in svg
        assert "city-platform" not in svg
        ET.fromstring(svg.encode("utf-8"))
