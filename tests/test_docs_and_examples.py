"""The preview gallery, the README grids, the examples and every documented option stay truthful."""

from __future__ import annotations

import json
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from contribution_city import CityRenderer, ContributionDataSet
from contribution_city.cli import create_parser, main
from contribution_city.config import AppConfig
from contribution_city.previews import (
    CATEGORIES,
    build_previews,
    check_previews,
    checkerboard_preview,
    full_cli,
    generate_previews,
    normalise,
    planned_files,
    preview_specs,
    sample_days,
)
from contribution_city.renderer import RenderConfig
from contribution_city.renderer.layouts import LAYOUT_NAMES
from contribution_city.renderer.presets import (
    BUILDING_STYLES,
    HEIGHT_PRESET_NAMES,
    VIEW_ANGLE_NAMES,
)
from contribution_city.renderer.svg import APPEARANCES, BACKGROUND_MODES, HEIGHT_MODES
from contribution_city.renderer.themes import THEMES
from contribution_city.svgcheck import check_svg

ROOT = Path(__file__).parent.parent
ACTION = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
INPUTS = ACTION["inputs"]
ENUMS = {
    "theme": set(THEMES),
    "layout": set(LAYOUT_NAMES),
    "height-preset": set(HEIGHT_PRESET_NAMES) | {""},
    "height-mode": set(HEIGHT_MODES),
    "building-style": set(BUILDING_STYLES),
    "view-angle": set(VIEW_ANGLE_NAMES),
    "background": set(BACKGROUND_MODES) | {""},
    "appearance": set(APPEARANCES),
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def strip_code(markdown: str) -> str:
    return re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)


# ------------------------------------------------------------------------ the preview gallery


class TestPreviewGallery:
    def test_committed_previews_and_readme_grids_are_up_to_date(self) -> None:
        problems = check_previews(ROOT / "previews", ROOT / "README.md")
        assert not problems, problems

    def test_every_theme_layout_and_option_has_a_preview(self) -> None:
        names = {(s.category, s.name) for s in preview_specs()}
        for theme in THEMES:
            assert ("themes", theme) in names
        for layout in LAYOUT_NAMES:
            assert ("layouts", layout) in names
        assert {"standard", "tall-custom"} <= {n for c, n in names if c == "heights"}
        assert {"detailed", "solid"} == {n for c, n in names if c == "building-styles"}
        assert {"standard-isometric", "low", "high", "top-down"} == {
            n for c, n in names if c == "viewing-angles"
        }
        assert {"solid", "transparent", "transparent-sky"} <= {
            n for c, n in names if c == "backgrounds"
        }
        for preset in ("standard", "tall"):
            for mode in HEIGHT_MODES:
                if mode != "power":
                    assert ("heights", f"{preset}-{mode}") in names

    def test_every_preview_file_exists_is_valid_and_small(self) -> None:
        total = 0
        for res in build_previews():
            path = ROOT / "previews" / res.file
            assert path.is_file(), res.file
            svg = path.read_text(encoding="utf-8")
            assert check_svg(svg).ok, res.file
            total += len(svg.encode())
            assert len(svg.encode()) < 120_000, res.file
        assert total < 3_000_000

    def test_gallery_is_deterministic(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a", tmp_path / "b"
        generate_previews(a)
        generate_previews(b)
        for file in sorted(p for p in a.rglob("*") if p.is_file()):
            assert file.read_bytes() == (b / file.relative_to(a)).read_bytes()

    def test_identical_output_is_stored_once(self) -> None:
        results = build_previews()
        files = [r.file for r in results if r.alias_of is None]
        assert len(files) == len(set(files))
        by_content = {}
        for r in results:
            if r.alias_of is None:
                by_content.setdefault(normalise(r.svg), []).append(r.file)
        assert all(len(v) == 1 for v in by_content.values())
        assert any(r.alias_of for r in results)  # calendar == the default theme preview

    def test_manifest_matches_the_files(self) -> None:
        manifest = json.loads(read("previews/manifest.json"))
        assert manifest["fixture"] == "preview"
        entries = manifest["previews"]
        assert manifest["totals"]["previews"] == len(entries) == len(preview_specs())
        for entry in entries:
            assert (ROOT / "previews" / entry["file"]).is_file()
            if entry["alias_of"] is None:
                assert entry["valid"] is True and entry["errors"] == []
            if entry["checkerboard_companion"]:
                assert (ROOT / "previews" / entry["checkerboard_companion"]).is_file()

    def test_stale_files_are_detected(self, tmp_path: Path) -> None:
        generate_previews(tmp_path)
        (tmp_path / "themes" / "navy-cyan.svg").write_text("<svg/>")
        (tmp_path / "themes" / "removed-theme.svg").write_text("<svg/>")
        (tmp_path / "layouts" / "compact.svg").unlink()
        problems = check_previews(tmp_path)
        assert any("out of date: tmp" in p or "out of date" in p for p in problems)
        assert any("unexpected" in p for p in problems) and any("missing" in p for p in problems)

    def test_readme_grids_are_checked_for_staleness(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(
            read("README.md").replace("--theme cyberpunk", "--theme nope"), encoding="utf-8"
        )
        generate_previews(tmp_path / "previews")
        assert any("grids" in p for p in check_previews(tmp_path / "previews", readme))

    @pytest.mark.parametrize("spec", preview_specs(), ids=lambda s: f"{s.category}/{s.name}")
    def test_documented_flags_reproduce_the_file(self, spec, tmp_path: Path) -> None:
        """Every preview is exactly what `contribution-city generate` makes from its flags."""
        data = tmp_path / "sample.json"
        data.write_text(
            json.dumps({"username": "preview-user", "days": sample_days()}), encoding="utf-8"
        )
        out = tmp_path / "out.svg"
        assert main(["generate", "--input", str(data), "--output", str(out), *full_cli(spec)]) == 0
        rendered = next(r for r in build_previews() if r.spec == spec)
        committed = (ROOT / "previews" / rendered.file).read_text(encoding="utf-8")
        assert normalise(out.read_text(encoding="utf-8")) == normalise(committed)


class TestTransparentPreviews:
    @pytest.mark.parametrize(
        "name", ["transparent", "transparent-sky", "auto-with-auto-appearance"]
    )
    def test_real_files_are_really_transparent(self, name: str) -> None:
        svg = read(f"previews/backgrounds/{name}.svg")
        assert (
            'fill="url(#pv-bg)"' not in svg
            and "<rect" not in svg.split("</defs>")[1].split("<g id")[0]
        )
        from contribution_city.visual.render import svg_to_image

        image = svg_to_image(svg, 300)
        w, h = image.size
        assert [image.getpixel(p)[3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))] == [
            0,
            0,
            0,
            0,
        ]

    def test_solid_preview_is_opaque(self) -> None:
        from contribution_city.visual.render import svg_to_image

        assert svg_to_image(read("previews/backgrounds/solid.svg"), 300).getpixel((0, 0))[3] == 255

    @pytest.mark.parametrize(
        "name", ["transparent", "transparent-sky", "auto-with-auto-appearance"]
    )
    def test_checkerboard_companion_only_adds_a_checkerboard(self, name: str) -> None:
        real = normalise(read(f"previews/backgrounds/{name}.svg"))
        companion = normalise(read(f"previews/backgrounds/{name}.on-checkerboard.svg"))
        assert check_svg(companion).ok
        assert "checker" in companion and "checker" not in real
        inner = real.split("?>", 1)[1].strip()
        assert inner in companion  # the original is embedded unchanged
        from contribution_city.visual.render import svg_to_image

        image = svg_to_image(companion, 300)
        assert image.getpixel((0, 0))[3] == 255  # the checkerboard is opaque

    def test_companion_wrapper_function(self) -> None:
        svg = CityRenderer(RenderConfig(background="transparent", width=200, height=120)).render(
            ContributionDataSet.from_dict({"days": [{"date": "2025-01-01", "count": 3}]})
        )
        wrapped = checkerboard_preview(svg, "x <b>")
        assert check_svg(wrapped).ok and "x &lt;b&gt;" in wrapped


# ------------------------------------------------------------------------ the README grids


@pytest.fixture(scope="module")
def readme() -> str:
    return read("README.md")


class TestReadmeGrids:
    def block(self, readme: str, name: str) -> str:
        m = re.search(
            rf"<!-- previews:{name}:start -->(.*?)<!-- previews:{name}:end -->", readme, re.S
        )
        assert m, name
        return m.group(1)

    def test_grid_1_has_every_theme_with_its_name(self, readme: str) -> None:
        grid = self.block(readme, "themes")
        for theme in THEMES:
            assert (
                f"previews/themes/{theme}.svg" in grid and f"<code>--theme {theme}</code>" in grid
            )

    def test_grid_2_has_every_layout(self, readme: str) -> None:
        grid = self.block(readme, "layouts")
        for layout in LAYOUT_NAMES:
            assert f"<code>--layout {layout}</code>" in grid

    def test_grid_3_has_presets_modes_and_angles(self, readme: str) -> None:
        presets = self.block(readme, "heights-presets")
        assert "standard (default)" in presets and "tall" in presets and "custom" in presets
        for kind in ("standard", "tall"):
            modes = self.block(readme, f"heights-{kind}-modes")
            for mode in HEIGHT_MODES:
                assert f"<code>--height-mode {mode}</code>" in modes
        angles = self.block(readme, "viewing-angles")
        for angle in VIEW_ANGLE_NAMES:
            assert f"<code>--view-angle {angle}</code>" in angles
        styles = self.block(readme, "building-styles")
        assert "--building-style solid" in styles and "--building-style detailed" in styles
        assert "Height preset" in readme and "Height mode" in readme  # the difference is explained

    def test_grid_4_has_every_background_mode(self, readme: str) -> None:
        grid = self.block(readme, "backgrounds")
        for mode in ("solid", "transparent", "transparent-sky"):
            assert f"--background {mode}" in grid
        assert "--background auto" in grid and "on-checkerboard" in grid

    def test_every_grid_image_has_alt_text_and_a_caption(self, readme: str) -> None:
        for name in ("themes", "layouts", "viewing-angles", "backgrounds"):
            grid = self.block(readme, name)
            imgs = re.findall(r"<img [^>]*>", grid)
            assert imgs and all('alt="' in i for i in imgs)
            assert grid.count("<code>") >= len(imgs)


class TestLinksResolve:
    DOCS = [
        "README.md",
        "CHANGELOG.md",
        "examples/README.md",
        "previews/README.md",
        "docs/visual-testing.md",
        *[f"previews/{c}/README.md" for c, _, _ in CATEGORIES],
    ]

    @pytest.mark.parametrize("doc", DOCS)
    def test_every_relative_link_and_image_exists(self, doc: str) -> None:
        path = ROOT / doc
        assert path.is_file(), doc
        text = strip_code(path.read_text(encoding="utf-8"))
        targets = re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(
            r'(?:src|href|srcset)="([^"]+)"', text
        )
        for target in targets:
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue
            assert (path.parent / file_part).exists(), f"{doc}: broken link {target}"

    def test_in_page_anchors_in_the_readme_exist(self) -> None:
        text = strip_code(read("README.md"))
        anchors = {
            re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-")
            for h in re.findall(r"^#{1,6}\s+(.*)$", text, re.M)
        }
        for target in re.findall(r"\]\(#([^)]+)\)", text):
            assert target in anchors, f"README anchor #{target} has no heading"


# ------------------------------------------------------------------------ examples


def with_blocks(doc: dict) -> list[dict]:
    found: list[dict] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            if str(node.get("uses", "")).startswith(
                "partialHuman/contribution-city"
            ) and isinstance(node.get("with"), dict):
                found.append(node["with"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return found


def check_with(block: dict, where: str) -> None:
    for key, value in block.items():
        assert key in INPUTS, f"{where}: '{key}' is not an input of the action"
        if key in ENUMS and "${{" not in str(value):
            assert str(value) in ENUMS[key], f"{where}: {key}={value!r} is not accepted"


class TestExamples:
    WORKFLOWS = sorted((ROOT / "examples/workflows").glob("*.yml"))

    def test_the_expected_examples_exist(self) -> None:
        names = {p.name for p in self.WORKFLOWS}
        assert {
            "basic-city.yml",
            "customized-city.yml",
            "solid-city.yml",
            "heights-and-angles.yml",
            "transparent-city.yml",
            "generate-profile-city.yml",
            "gallery-artifact.yml",
        } <= names
        for cfg in ("all-options", "solid", "transparent", "heights-and-angles"):
            assert (ROOT / f"examples/config/{cfg}.yaml").is_file()

    @pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
    def test_workflows_only_use_real_inputs_with_valid_values(self, path: Path) -> None:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        blocks = with_blocks(doc)
        if path.name == "gallery-artifact.yml":
            assert not blocks  # builds the gallery from the repository instead
            return
        assert blocks, path.name
        for block in blocks:
            check_with(block, path.name)

    @pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
    def test_workflows_use_the_current_action_version(self, path: Path) -> None:
        refs = re.findall(
            r"uses:\s*(partialHuman/contribution-city@\S+)", path.read_text(encoding="utf-8")
        )
        assert all(r == "partialHuman/contribution-city@v1" for r in refs)

    @pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
    def test_permissions_are_minimal(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        commits = "git push" in text
        assert doc["permissions"] == {"contents": "write" if commits else "read"}, path.name
        triggers = doc.get("on") or doc.get(True)
        if commits:
            assert "push" not in triggers and "pull_request" not in triggers  # cannot loop
            assert "[skip ci]" in text and "git diff --staged --quiet" in text

    @pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
    def test_no_token_or_input_is_echoed(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        assert "echo ${{ secrets" not in text and "--token" not in text

    def test_the_customized_example_demonstrates_every_requested_setting(self) -> None:
        keys = set(with_blocks(yaml.safe_load(read("examples/workflows/customized-city.yml")))[0])
        assert {
            "theme", "layout", "building-style", "height-preset", "height-mode",
            "view-angle", "background", "width", "height", "output",
        } <= keys  # fmt: skip

    def test_the_basic_example_only_sets_what_it_needs(self) -> None:
        block = with_blocks(yaml.safe_load(read("examples/workflows/basic-city.yml")))[0]
        assert set(block) == {"username", "token", "output"}

    def test_heights_and_angles_example_covers_every_preset_and_angle(self) -> None:
        doc = yaml.safe_load(read("examples/workflows/heights-and-angles.yml"))
        matrix = doc["jobs"]["generate"]["strategy"]["matrix"]
        assert set(matrix["preset"]) == {"standard", "tall"}
        assert set(matrix["angle"]) == set(VIEW_ANGLE_NAMES)

    def test_transparent_example_shows_both_transparent_modes(self) -> None:
        blocks = with_blocks(yaml.safe_load(read("examples/workflows/transparent-city.yml")))
        assert {b["background"] for b in blocks} == {"transparent", "transparent-sky"}

    CONFIGS = sorted((ROOT / "examples").glob("*.yaml")) + sorted(
        (ROOT / "examples/config").glob("*.yaml")
    )

    @pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
    def test_configurations_validate_and_render(self, path: Path) -> None:
        cfg = AppConfig.from_file(path)
        svg = CityRenderer(cfg.to_render_config()).render(
            ContributionDataSet.from_file(ROOT / "examples/sample-contributions.json")
        )
        assert check_svg(svg).ok

    def test_all_options_file_lists_every_city_key(self) -> None:
        text = read("examples/config/all-options.yaml")
        from dataclasses import fields

        from contribution_city.config import CitySettings

        for f in fields(CitySettings):
            assert re.search(rf"^\s*#?\s*{f.name}:", text, re.M), (
                f"all-options.yaml lacks '{f.name}'"
            )

    def test_solid_example_removes_windows_and_beacons(self) -> None:
        cfg = AppConfig.from_file(ROOT / "examples/config/solid.yaml")
        svg = CityRenderer(cfg.to_render_config()).render(
            ContributionDataSet.from_file(ROOT / "examples/sample-contributions.json")
        )
        assert 'class="w ' not in svg and not re.search(r'class="[NG]\d"', svg)

    def test_transparent_example_has_no_background_rectangle(self) -> None:
        cfg = AppConfig.from_file(ROOT / "examples/config/transparent.yaml")
        svg = CityRenderer(cfg.to_render_config()).render(
            ContributionDataSet.from_file(ROOT / "examples/sample-contributions.json")
        )
        assert 'fill="url(#bg)"' not in svg

    def test_heights_and_angles_example_changes_height_mode_and_camera(self) -> None:
        cfg = AppConfig.from_file(ROOT / "examples/config/heights-and-angles.yaml")
        r = CityRenderer(cfg.to_render_config())
        assert (r.height_preset, r.config.height_mode, r.config.view_angle) == (
            "standard",
            "linear",
            "high",
        )


class TestGuide:
    GUIDE = read("examples/README.md")

    def test_guide_covers_all_nineteen_topics(self) -> None:
        for n in range(1, 20):
            assert re.search(rf"^## {n}\. ", self.GUIDE, re.M), f"guide section {n} is missing"

    def test_every_workflow_snippet_in_the_guide_is_valid(self) -> None:
        blocks = re.findall(r"```yaml\n(.*?)```", self.GUIDE, re.S)
        assert len(blocks) >= 12
        checked = 0
        for i, block in enumerate(blocks):
            doc = yaml.safe_load(textwrap.dedent(block))
            found = with_blocks(doc)
            if not found and isinstance(doc, dict) and doc and set(doc) <= set(INPUTS):
                found = [doc]  # a bare "with:" fragment
            for w in found:
                check_with(w, f"guide snippet {i}")
                checked += 1
        assert checked >= 8

    def test_the_guides_full_workflow_matches_the_shipped_file(self) -> None:
        block = next(
            b
            for b in re.findall(r"```yaml\n(.*?)```", self.GUIDE, re.S)
            if b.startswith("name: Contribution City\n")
        )
        shipped = yaml.safe_load(read("examples/workflows/basic-city.yml"))
        assert yaml.safe_load(block) == shipped

    def test_every_action_input_is_documented_in_the_guide_and_readme(self) -> None:
        for name in INPUTS:
            assert f"`{name}`" in self.GUIDE, f"guide does not document '{name}'"
            assert f"`{name}`" in read("README.md"), f"README does not document '{name}'"

    def test_every_cli_flag_is_documented_in_the_readme(self) -> None:
        parser = create_parser()
        sub = next(
            a
            for a in parser._actions
            if hasattr(a, "choices") and a.choices and "generate" in a.choices
        )
        flags = {
            o
            for a in sub.choices["generate"]._actions
            for o in a.option_strings
            if o.startswith("--") and o != "--help"
        }
        readme = read("README.md")
        missing = sorted(
            f for f in flags if not re.search(r"`[^`\n]*" + re.escape(f) + r"\b", readme)
        )
        assert not missing, f"README does not document: {missing}"

    def test_documented_defaults_equal_the_real_defaults(self) -> None:
        assert (
            INPUTS["layout"]["default"] == "calendar"
            and INPUTS["building-style"]["default"] == "detailed"
        )
        assert (
            INPUTS["view-angle"]["default"] == "isometric"
            and INPUTS["height-mode"]["default"] == "power"
        )
        assert INPUTS["height-preset"]["default"] == "" and INPUTS["background"]["default"] == ""
        assert (
            INPUTS["output"]["default"] == "dist/city.svg"
            and INPUTS["appearance"]["default"] == "fixed"
        )
        for needle in (
            "`standard`",
            "`isometric`",
            "`detailed`",
            "`calendar`",
            "`power`",
            "`dist/city.svg`",
        ):
            assert needle in self.GUIDE


class TestDefaultsAgreeEverywhere:
    """The CLI, a YAML file and the action must produce the same city when nothing is set."""

    def test_cli_yaml_and_python_defaults_are_the_same_city(self, tmp_path: Path) -> None:
        sample = ROOT / "examples/sample-contributions.json"
        data = ContributionDataSet.from_file(sample)
        via_cli = tmp_path / "cli.svg"
        assert main(["generate", "--input", str(sample), "--output", str(via_cli)]) == 0
        via_yaml_cfg = tmp_path / "c.yaml"
        via_yaml_cfg.write_text("theme: navy-cyan\n", encoding="utf-8")
        via_yaml = tmp_path / "yaml.svg"
        assert (
            main(
                [
                    "generate",
                    "--input",
                    str(sample),
                    "--config",
                    str(via_yaml_cfg),
                    "--output",
                    str(via_yaml),
                ]
            )
            == 0
        )
        python_default = CityRenderer(AppConfig.from_dict({}).to_render_config()).render(data)
        assert via_cli.read_text() == via_yaml.read_text() == python_default

    def test_every_new_option_has_the_same_effect_in_cli_yaml_and_python(
        self, tmp_path: Path
    ) -> None:
        sample = ROOT / "examples/sample-contributions.json"
        data = ContributionDataSet.from_file(sample)
        cfg = tmp_path / "all.yaml"
        cfg.write_text(
            "theme: cyberpunk\nlayout: downtown\ncity:\n  height_preset: tall\n  height_mode: sqrt\n"
            "  building_style: solid\n  view_angle: low\n  background: transparent-sky\n",
            encoding="utf-8",
        )
        cli, yml = tmp_path / "cli.svg", tmp_path / "yml.svg"
        assert main(["generate", "--input", str(sample), "--output", str(cli), "--theme", "cyberpunk", "--layout", "downtown",
                     "--height-preset", "tall", "--height-mode", "sqrt", "--building-style", "solid",
                     "--view-angle", "low", "--background", "transparent-sky"]) == 0  # fmt: skip
        assert (
            main(["generate", "--input", str(sample), "--config", str(cfg), "--output", str(yml)])
            == 0
        )
        python = CityRenderer(
            RenderConfig(
                theme="cyberpunk",
                layout="downtown",
                height_preset="tall",
                height_mode="sqrt",
                building_style="solid",
                view_angle="low",
                background="transparent-sky",
            )  # fmt: skip
        ).render(data)
        assert cli.read_text() == yml.read_text() == python

    def test_cli_overrides_yaml_for_the_new_options(self, tmp_path: Path) -> None:
        sample = ROOT / "examples/sample-contributions.json"
        cfg = tmp_path / "c.yaml"
        cfg.write_text(
            "city:\n  height_preset: tall\n  building_style: solid\n  view_angle: low\n",
            encoding="utf-8",
        )
        out = tmp_path / "o.svg"
        assert main(["generate", "--input", str(sample), "--config", str(cfg), "--output", str(out),
                     "--height-preset", "standard", "--building-style", "detailed", "--view-angle", "high"]) == 0  # fmt: skip
        data = ContributionDataSet.from_file(sample)
        expected = CityRenderer(
            RenderConfig(height_preset="standard", building_style="detailed", view_angle="high")
        ).render(data)
        assert out.read_text() == expected


class TestRealSvgFromSamples:
    def test_planned_files_have_no_duplicates_and_all_categories(self) -> None:
        files = planned_files(build_previews())
        for cat, _, _ in CATEGORIES:
            assert f"{cat}/README.md" in files
        assert "README.md" in files and "manifest.json" in files
        ET.fromstring(files["themes/cyberpunk.svg"].encode())
