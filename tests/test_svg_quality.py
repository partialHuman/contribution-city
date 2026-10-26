"""SVG quality and security: escaping, ids, references, external resources, sizes."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from contribution_city.models import ContributionDataSet
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.layouts import LAYOUT_NAMES
from contribution_city.renderer.themes import THEMES
from contribution_city.svgcheck import check_svg
from contribution_city.visual.cases import build_cases
from contribution_city.visual.fixtures import HOSTILE_TITLE, build_fixture

HOSTILE_USER = "a<b>&\"'c</text><script>alert(1)</script>"


def hostile_dataset() -> ContributionDataSet:
    return ContributionDataSet.from_dict(
        {
            "username": HOSTILE_USER,
            "days": [{"date": "2025-01-01", "count": 3}, {"date": "2025-01-02", "count": 9}],
        }
    )


class TestEveryGalleryCaseIsClean:
    @pytest.mark.parametrize("case", build_cases(), ids=lambda c: c.id)
    def test_case_passes_all_static_checks(self, case) -> None:
        report = check_svg(case.render_svg())
        assert report.ok, report.errors
        assert report.well_formed


class TestEscaping:
    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    def test_hostile_text_cannot_inject_markup(self, layout: str) -> None:
        svg = CityRenderer(RenderConfig(layout=layout, custom_title=HOSTILE_TITLE)).render(
            hostile_dataset()
        )
        report = check_svg(svg)
        assert report.ok, report.errors
        root = ET.fromstring(svg.encode())
        assert not [el for el in root.iter() if el.tag.endswith("script")]
        assert "<script" not in svg
        assert HOSTILE_USER not in svg  # the raw string never appears unescaped

    def test_hostile_text_appears_as_text_not_markup(self) -> None:
        svg = CityRenderer(RenderConfig(custom_title=HOSTILE_TITLE)).render(hostile_dataset())
        root = ET.fromstring(svg.encode())
        texts = "".join(el.text or "" for el in root.iter() if el.tag.endswith("text"))
        assert "alert(1)" in texts  # visible as plain text, harmless

    def test_tooltip_titles_contain_only_dates_and_counts(self) -> None:
        svg = CityRenderer().render(hostile_dataset())
        root = ET.fromstring(svg.encode())
        tips = [el.text for el in root.iter() if el.tag.endswith("title") and el.text][1:]
        assert tips and all("contribution" in t and "<" not in t for t in tips)

    def test_id_prefix_is_validated(self) -> None:
        for bad in ('x"y', "1abc", "a b", "a<b", ""):
            with pytest.raises(ValueError, match="id_prefix"):
                CityRenderer(RenderConfig(id_prefix=bad))


class TestNoExternalResources:
    @pytest.mark.parametrize("theme", sorted(THEMES))
    def test_no_remote_urls_or_active_content(self, theme: str) -> None:
        svg = CityRenderer(RenderConfig(theme=theme)).render(build_fixture("full-year"))
        lowered = svg.lower()
        for needle in (
            "http://",
            "https://",
            "@import",
            "<script",
            "<image",
            "javascript:",
            "xlink",
        ):
            if needle == "http://":  # the SVG namespace is the one allowed URL
                assert lowered.count("http://") == 1
            else:
                assert needle not in lowered, needle

    def test_no_foreign_object_or_use_elements(self) -> None:
        svg = CityRenderer().render(build_fixture("full-year"))
        for tag in ("<foreignobject", "<use", "<iframe", "<a "):
            assert tag not in svg.lower()


class TestIdsAndReferences:
    def test_default_ids_are_unique_and_resolve(self) -> None:
        report = check_svg(CityRenderer().render(build_fixture("full-year")))
        assert report.ok and report.ids >= 5 and report.references >= 3

    def test_prefix_makes_two_inlined_svgs_collision_free(self) -> None:
        a = CityRenderer(RenderConfig(id_prefix="one", theme="cyberpunk")).render(
            build_fixture("minimal")
        )
        b = CityRenderer(RenderConfig(id_prefix="two", theme="emerald-matrix")).render(
            build_fixture("minimal")
        )

        def ids(svg: str) -> set[str]:
            return {el.get("id") for el in ET.fromstring(svg.encode()).iter() if el.get("id")}

        assert not ids(a) & ids(b)
        page = f"<html><body>{a.split('?>', 1)[1]}{b.split('?>', 1)[1]}</body></html>"
        ET.fromstring(page)  # one document with both SVGs is still well-formed
        # every CSS rule is scoped to its own SVG so the two themes cannot restyle each other
        css_a = ET.fromstring(a.encode()).find("{http://www.w3.org/2000/svg}style").text
        assert all(rule.strip().startswith(".one") for rule in css_a.split("}") if rule.strip())

    def test_unprefixed_ids_stay_as_in_v110(self) -> None:
        svg = CityRenderer().render(build_fixture("full-year"))
        for legacy in ('id="cc-title"', 'id="bg"', 'id="glow"', 'id="city-hud"', 'id="sky-stars"'):
            assert legacy in svg

    def test_aria_labelledby_targets_exist(self) -> None:
        root = ET.fromstring(
            CityRenderer(RenderConfig(id_prefix="x")).render(build_fixture("minimal")).encode()
        )
        ids = {el.get("id") for el in root.iter() if el.get("id")}
        assert set(root.get("aria-labelledby").split()) <= ids

    def test_checker_catches_problems(self) -> None:
        ns = 'xmlns="http://www.w3.org/2000/svg"'
        cases = {
            "duplicate id": f'<svg {ns} width="1" height="1" viewBox="0 0 1 1"><g id="a"/><g id="a"/></svg>',
            "missing id": f'<svg {ns} width="1" height="1" viewBox="0 0 1 1"><rect fill="url(#nope)"/></svg>',
            "script": f'<svg {ns} width="1" height="1" viewBox="0 0 1 1"><script>x</script></svg>',
            "external": f'<svg {ns} width="1" height="1" viewBox="0 0 1 1"><rect fill="url(http://a/b)"/></svg>',
            "handler": f'<svg {ns} width="1" height="1" viewBox="0 0 1 1"><rect onclick="x()"/></svg>',
            "viewbox": f'<svg {ns} width="10" height="10" viewBox="0 0 5 5"></svg>',
            "malformed": "<svg><g></svg>",
        }
        for label, svg in cases.items():
            assert not check_svg(svg).ok, label


class TestDimensions:
    @pytest.mark.parametrize(("w", "h"), [(1200, 680), (800, 450), (400, 300), (2000, 900)])
    def test_viewbox_matches_canvas(self, w: int, h: int) -> None:
        svg = CityRenderer(RenderConfig(width=w, height=h)).render(build_fixture("minimal"))
        root = ET.fromstring(svg.encode())
        assert (root.get("width"), root.get("height")) == (str(w), str(h))
        assert root.get("viewBox") == f"0 0 {w} {h}"

    def test_root_has_role_title_and_description(self) -> None:
        root = ET.fromstring(CityRenderer().render(build_fixture("full-year")).encode())
        ns = "{http://www.w3.org/2000/svg}"
        assert root.get("role") == "img"
        assert "contributions" in root.find(f"{ns}desc").text
        assert "Contribution City" in root.find(f"{ns}title").text


class TestExtremeAndEmptyData:
    def test_huge_counts_are_capped_not_unbounded(self) -> None:
        r = CityRenderer(RenderConfig(height_mode="linear"))
        assert r._calculate_building_height(10**9, 10**9) == r.config.max_building_height
        assert r._calculate_building_height(10**9) == r.config.max_building_height

    @pytest.mark.parametrize("mode", ["power", "linear", "sqrt", "log"])
    def test_extreme_fixture_every_height_mode(self, mode: str) -> None:
        svg = CityRenderer(RenderConfig(height_mode=mode)).render(build_fixture("extreme"))
        assert check_svg(svg).ok

    def test_empty_dataset_renders_placeholder(self) -> None:
        svg = CityRenderer().render(build_fixture("empty"))
        assert check_svg(svg).ok and "No contribution data" in svg

    def test_negative_counts_are_rejected_by_the_model(self) -> None:
        with pytest.raises(ValueError):
            ContributionDataSet.from_dict({"days": [{"date": "2025-01-01", "count": -1}]})
