"""Tests for escaping, light/dark output, auto-fit, height modes and file size."""

from __future__ import annotations

import json
import os
import re
import xml.dom.minidom
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contribution_city.models import ContributionDataSet
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.themes import LIGHT_PAIRS, THEMES

ROOT = Path(__file__).parent.parent
SNAPSHOT = Path(__file__).parent / "snapshots" / "tiny_default.svg"


@pytest.fixture(scope="module")
def sample() -> ContributionDataSet:
    data = json.loads((ROOT / "examples/sample-contributions.json").read_text(encoding="utf-8"))
    return ContributionDataSet.from_dict(data)


@pytest.fixture
def tiny() -> ContributionDataSet:
    return ContributionDataSet.from_dict(
        {
            "username": "tiny",
            "days": [
                {"date": "2025-01-01", "count": 0},
                {"date": "2025-01-02", "count": 3},
                {"date": "2025-01-03", "count": 12},
                {"date": "2025-01-04", "count": 25},
            ],
        }
    )


def _well_formed(svg: str) -> None:
    xml.dom.minidom.parseString(svg.encode("utf-8"))


class TestEscaping:
    HOSTILE = '</text><script>alert(1)</script>"&<'

    def test_custom_title_is_escaped(self, tiny: ContributionDataSet) -> None:
        svg = CityRenderer(RenderConfig(custom_title=self.HOSTILE)).render(tiny)
        _well_formed(svg)
        assert "<script>" not in svg

    def test_username_is_escaped(self) -> None:
        ds = ContributionDataSet.from_dict(
            {"username": 'a<b>&"c', "days": [{"date": "2025-01-01", "count": 3}]}
        )
        svg = CityRenderer().render(ds)
        _well_formed(svg)
        assert "a<b>" not in svg

    def test_title_with_header_off_still_escaped(self, tiny: ContributionDataSet) -> None:
        svg = CityRenderer(RenderConfig(custom_title=self.HOSTILE, show_header=False)).render(tiny)
        _well_formed(svg)


class TestEveryCombinationIsValidXml:
    @pytest.mark.parametrize("theme", sorted(THEMES))
    @pytest.mark.parametrize("layout", ["calendar", "compact"])
    def test_theme_layout_matrix(self, theme: str, layout: str, tiny: ContributionDataSet) -> None:
        _well_formed(CityRenderer(RenderConfig(theme=theme, layout=layout)).render(tiny))

    @pytest.mark.parametrize("theme", sorted(LIGHT_PAIRS))
    def test_auto_appearance(self, theme: str, tiny: ContributionDataSet) -> None:
        svg = CityRenderer(RenderConfig(theme=theme, appearance="auto")).render(tiny)
        _well_formed(svg)
        assert "prefers-color-scheme:light" in svg

    @pytest.mark.parametrize("mode", ["power", "linear", "sqrt", "log"])
    def test_height_modes(self, mode: str, tiny: ContributionDataSet) -> None:
        _well_formed(CityRenderer(RenderConfig(height_mode=mode)).render(tiny))

    def test_sample_dataset_all_flags_off(self, sample: ContributionDataSet) -> None:
        cfg = RenderConfig(
            show_windows=False,
            show_stars=False,
            show_header=False,
            show_platform=False,
            show_zero_tiles=False,
            show_tooltips=False,
            transparent=True,
            auto_fit=False,
            pixel_art=False,
        )
        _well_formed(CityRenderer(cfg).render(sample))


class TestAppearance:
    def test_theme_without_light_pair_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="no light variant"):
            CityRenderer(RenderConfig(theme="sunset-neon", appearance="auto"))

    def test_unknown_appearance_rejected(self) -> None:
        with pytest.raises(ValueError, match="appearance"):
            CityRenderer(RenderConfig(appearance="sepia"))

    def test_fixed_has_no_media_query(self, tiny: ContributionDataSet) -> None:
        assert "prefers-color-scheme" not in CityRenderer().render(tiny)

    def test_transparent_drops_background_and_stars(self, tiny: ContributionDataSet) -> None:
        svg = CityRenderer(RenderConfig(transparent=True)).render(tiny)
        assert 'fill="url(#bg)"' not in svg
        assert "sky-stars" not in svg


class TestAccessibility:
    def test_root_has_title_desc_and_role(self, tiny: ContributionDataSet) -> None:
        svg = CityRenderer().render(tiny)
        root = ET.fromstring(svg.encode("utf-8"))
        assert root.attrib["role"] == "img"
        assert root.find("{http://www.w3.org/2000/svg}title") is not None
        desc = root.find("{http://www.w3.org/2000/svg}desc")
        assert desc is not None and "40 contributions" in (desc.text or "")


class TestHeightModes:
    def test_linear_is_proportional_above_minimum(self) -> None:
        r = CityRenderer(RenderConfig(height_mode="linear", min_building_height=6.0))
        h10 = r._calculate_building_height(10, 100) - 6.0
        h20 = r._calculate_building_height(20, 100) - 6.0
        h50 = r._calculate_building_height(50, 100) - 6.0
        assert h20 == pytest.approx(2 * h10, abs=0.2)
        assert h50 == pytest.approx(5 * h10, abs=0.5)

    def test_busiest_day_reaches_max_height(self) -> None:
        r = CityRenderer(RenderConfig(height_mode="linear", max_building_height=100.0))
        assert r._calculate_building_height(40, 40) == 100.0

    def test_unknown_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="height_mode"):
            CityRenderer(RenderConfig(height_mode="cubic"))


class TestAutoFit:
    @staticmethod
    def _bounds(svg: str) -> tuple[float, float, float, float]:
        import re

        nums = [
            float(n)
            for n in re.findall(r'points="([^"]+)"', svg)
            for n in n.replace(",", " ").split()
        ]
        xs, ys = nums[0::2], nums[1::2]
        return min(xs), max(xs), min(ys), max(ys)

    def test_city_stays_inside_canvas(self, sample: ContributionDataSet) -> None:
        svg = CityRenderer().render(sample)
        x0, x1, y0, y1 = self._bounds(svg)
        assert x0 >= 0 and x1 <= 1200 and y0 >= 0 and y1 <= 680

    def test_fit_uses_more_of_the_canvas_than_fixed_tiles(
        self, sample: ContributionDataSet
    ) -> None:
        fit = self._bounds(CityRenderer(RenderConfig(auto_fit=True)).render(sample))
        fixed = self._bounds(CityRenderer(RenderConfig(auto_fit=False)).render(sample))
        assert (fit[1] - fit[0]) > (fixed[1] - fixed[0])

    def test_larger_canvas_grows_the_city(self, sample: ContributionDataSet) -> None:
        small = self._bounds(CityRenderer(RenderConfig(width=900, height=500)).render(sample))
        big = self._bounds(CityRenderer(RenderConfig(width=1800, height=1000)).render(sample))
        assert (big[1] - big[0]) > (small[1] - small[0])


class TestOutputSize:
    def test_sample_is_much_smaller_than_before(self, sample: ContributionDataSet) -> None:
        # The first version produced about 308 KB for this dataset
        assert len(CityRenderer().render(sample).encode("utf-8")) < 160_000

    def test_no_tooltips_is_smaller(self, sample: ContributionDataSet) -> None:
        with_tips = len(CityRenderer().render(sample))
        without = len(CityRenderer(RenderConfig(show_tooltips=False)).render(sample))
        assert without < with_tips

    def test_empty_tiles_have_no_tooltips(self, tiny: ContributionDataSet) -> None:
        svg = CityRenderer().render(tiny)
        assert "2025-01-01:" not in svg  # no tooltip for the 0-contribution day
        assert "2025-01-02: 3 contributions" in svg


# Some tools embed provenance metadata (for example C2PA manifests) into saved SVG files.
# It is not part of the rendering, so the snapshot comparison ignores it.
_EMBEDDED_METADATA = re.compile(r'\s+xmlns:c2pa="[^"]*"|<metadata>.*?</metadata>', re.DOTALL)


def _normalize(svg: str) -> str:
    return _EMBEDDED_METADATA.sub("", svg)


class TestSnapshot:
    def test_tiny_default_matches_snapshot(self, tiny: ContributionDataSet) -> None:
        svg = _normalize(CityRenderer().render(tiny))
        if os.environ.get("UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
            SNAPSHOT.write_text(svg, encoding="utf-8")
        expected = _normalize(SNAPSHOT.read_text(encoding="utf-8"))
        assert svg == expected, "Rendered SVG changed. If intended, run: UPDATE_SNAPSHOTS=1 pytest"
