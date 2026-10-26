"""Visual regression: the comparison engine, baselines, artifacts and the gallery.

Ordinary test runs only *read* baselines. Writing them needs the explicit command
``contribution-city visual approve --yes`` (the tests below use a temporary directory for that).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("PIL")
pytest.importorskip("resvg_py")

from PIL import Image  # noqa: E402

from contribution_city.cli import main  # noqa: E402
from contribution_city.visual import baseline as bl  # noqa: E402
from contribution_city.visual.cases import (  # noqa: E402
    VisualCase,
    baseline_cases,
    build_cases,
    get_case,
    raw_cases,
)
from contribution_city.visual.compare import (  # noqa: E402
    DEFAULT,
    STRICT,
    Tolerance,
    compare_images,
    write_failure_artifacts,
)
from contribution_city.visual.fixtures import FIXTURES, build_fixture  # noqa: E402
from contribution_city.visual.gallery import (  # noqa: E402
    build_contact_sheet,
    generate_gallery,
    select_cases,
)
from contribution_city.visual.render import composite, svg_to_image  # noqa: E402

BASELINES = Path(__file__).parent / "visual" / "baselines"


# --------------------------------------------------------------------------- baselines


@pytest.mark.baseline
class TestApprovedBaselines:
    @pytest.mark.parametrize("case", baseline_cases(), ids=lambda c: c.id)
    def test_current_render_matches_the_approved_baseline(
        self, case: VisualCase, tmp_path: Path
    ) -> None:
        result = bl.check_case(case, BASELINES, artifacts_dir=tmp_path)
        assert result.ok, (
            f"{case.id}: {result.status} - {result.message}\n"
            "If this change is intended, review the images and approve explicitly:\n"
            f"  contribution-city visual approve --yes --case {case.id}"
        )

    def test_every_baseline_case_has_a_file_and_every_file_a_case(self) -> None:
        expected = {c.id for c in baseline_cases()}
        present = {p.stem for p in BASELINES.glob("*.png")}
        assert expected == present

    def test_baseline_suite_is_curated_not_exhaustive(self) -> None:
        total_bytes = sum(p.stat().st_size for p in BASELINES.glob("*.png"))
        assert len(baseline_cases()) <= 45
        assert total_bytes < 2_000_000

    def test_index_records_renderer_and_case_keys(self) -> None:
        index = bl.load_index(BASELINES)
        assert "resvg-py" in index["_renderer"]
        for case in baseline_cases():
            assert index[case.id]["key"] == case.effective_key()


class TestCaseRegistry:
    def test_cases_cover_the_required_scenarios(self) -> None:
        ids = {c.id for c in build_cases()}
        required = {
            "layout-compact",
            "layout-dense-grid",
            "layout-downtown",
            "layout-floating-island",
            "layout-wireframe",
            "height-linear",
            "height-sqrt",
            "height-log",
            "background-transparent",
            "background-transparent-sky",
            "appearance-auto-profile",
            "tooltips-off",
            "fit-off",
            "custom-size",
            "year-2025",
            "range-2024-q4",
            "fixture-minimal",
            "fixture-empty",
            "fixture-isolated-peaks",
            "fixture-uniform",
            "fixture-long-streak",
            "fixture-special-chars",
        }
        assert required <= ids

    def test_every_theme_gets_a_case(self) -> None:
        from contribution_city.renderer.themes import THEMES

        assert {f"theme-{n}" for n in THEMES} <= {c.id for c in build_cases()}

    def test_duplicates_are_removed(self) -> None:
        raw, unique = raw_cases(), build_cases()
        assert len(unique) < len(raw)
        keys = [c.effective_key() for c in unique]
        assert len(keys) == len(set(keys))
        ids = {c.id for c in unique}
        assert "background-legacy-transparent" not in ids  # same as background-transparent
        assert "background-solid" not in ids  # same as the default theme case

    def test_case_ids_are_unique(self) -> None:
        ids = [c.id for c in raw_cases()]
        assert len(ids) == len(set(ids))

    def test_unknown_case_has_helpful_error(self) -> None:
        with pytest.raises(KeyError, match="Available"):
            get_case("nope")

    def test_describe_lists_the_key_settings(self) -> None:
        d = get_case("layout-downtown").describe()
        for key in (
            "theme",
            "layout",
            "background",
            "appearance",
            "height_mode",
            "width",
            "height",
        ):
            assert key in d
        assert d["layout"] == "downtown"

    def test_fixtures_are_deterministic_and_date_independent(self) -> None:
        for name in FIXTURES:
            a, b = build_fixture(name), build_fixture(name)
            assert [(d.date, d.count) for d in a.days] == [(d.date, d.count) for d in b.days]
        assert build_fixture("full-year").days[0].date == "2025-01-01"
        assert len(build_fixture("full-year").days) == 365

    def test_unknown_fixture_error(self) -> None:
        with pytest.raises(KeyError, match="Available fixtures"):
            build_fixture("nope")


# --------------------------------------------------------------------------- comparison engine


def solid(colour=(30, 30, 40, 255), size=(120, 80)) -> Image.Image:
    return Image.new("RGBA", size, colour)


class TestComparison:
    def test_identical_images_pass_even_with_strict_tolerance(self) -> None:
        r = compare_images(solid(), solid(), STRICT)
        assert r.passed and r.differing_pixels == 0 and r.max_channel_diff == 0

    def test_scattered_antialiasing_noise_is_tolerated(self) -> None:
        a, b = solid(), solid()
        for x in range(0, 120, 17):  # isolated single pixels, moderately different
            b.putpixel((x, (x * 7) % 80), (70, 70, 80, 255))
        r = compare_images(a, b, DEFAULT)
        assert r.passed, r.reason
        assert r.differing_pixels > 0 and r.clustered_pixels == 0

    def test_small_colour_drift_below_channel_tolerance_is_ignored(self) -> None:
        r = compare_images(solid((30, 30, 40, 255)), solid((40, 38, 50, 255)), DEFAULT)
        assert r.passed and r.differing_pixels == 0 and r.max_channel_diff == 10

    def test_a_missing_building_is_a_meaningful_regression(self) -> None:
        a, b = solid(), solid()
        for x in range(40, 70):
            for y in range(20, 60):
                b.putpixel((x, y), (0, 200, 255, 255))
        r = compare_images(a, b, DEFAULT)
        assert not r.passed
        assert r.clustered_pixels > 0 and r.bbox == (40, 20, 70, 60)
        assert "patches" in r.reason

    def test_size_change_fails_with_clear_reason(self) -> None:
        r = compare_images(solid(size=(100, 60)), solid(size=(120, 80)), DEFAULT)
        assert not r.passed and r.size_mismatch and "size changed" in r.reason

    def test_transparency_change_is_caught(self) -> None:
        r = compare_images(solid((30, 30, 40, 0)), solid((30, 30, 40, 255)), DEFAULT)
        assert not r.passed and r.max_alpha_diff == 255

    def test_tolerances_are_configurable(self) -> None:
        a, b = solid(), solid()
        for x in range(10, 30):
            for y in range(10, 30):
                b.putpixel((x, y), (60, 60, 70, 255))
        assert not compare_images(a, b, Tolerance()).passed
        loose = Tolerance(max_ratio=0.2, max_clustered_ratio=0.2)
        assert compare_images(a, b, loose).passed

    def test_statistics_are_reported(self) -> None:
        a, b = solid(), solid()
        for x in range(10):
            b.putpixel((x, 0), (255, 255, 255, 255))
        r = compare_images(a, b, DEFAULT)
        assert r.differing_pixels == 10 and r.max_channel_diff > 200
        assert 0 < r.differing_ratio < 0.01 and r.mean_diff > 0
        assert set(r.to_dict()) >= {
            "passed",
            "reason",
            "differing_ratio",
            "clustered_ratio",
            "bbox",
        }


class TestFailureArtifacts:
    def test_artifacts_include_images_and_a_report(self, tmp_path: Path) -> None:
        a, b = solid(), solid()
        b.putpixel((5, 5), (255, 0, 0, 255))
        result = compare_images(a, b, STRICT)
        write_failure_artifacts("demo", a, b, result, tmp_path)
        for suffix in ("current.png", "baseline.png", "diff.png", "side-by-side.png", "json"):
            assert (tmp_path / f"demo.{suffix}").exists(), suffix
        report = json.loads((tmp_path / "demo.json").read_text())
        assert report["case"] == "demo" and report["result"]["differing_pixels"] == 1
        assert Image.open(tmp_path / "demo.side-by-side.png").width == 3 * 120

    def test_missing_baseline_still_saves_the_current_render(self, tmp_path: Path) -> None:
        case = get_case("fixture-minimal")
        res = bl.check_case(case, tmp_path / "empty", artifacts_dir=tmp_path / "art")
        assert (
            res.status == bl.MISSING and (tmp_path / "art" / "fixture-minimal.current.png").exists()
        )


# --------------------------------------------------------------------------- explicit approval


class TestApprovalWorkflow:
    def test_ordinary_check_never_creates_or_changes_baselines(self, tmp_path: Path) -> None:
        case = get_case("fixture-minimal")
        base = tmp_path / "base"
        res = bl.check_case(case, base)
        assert res.status == bl.MISSING
        assert not base.exists()  # nothing was written

    def test_approve_then_check_passes(self, tmp_path: Path) -> None:
        case = get_case("fixture-minimal")
        bl.approve_cases([case], tmp_path)
        assert bl.baseline_path(case.id, tmp_path).exists()
        assert bl.check_case(case, tmp_path).ok

    def test_changed_render_is_reported_not_silently_accepted(self, tmp_path: Path) -> None:
        case = get_case("fixture-minimal")
        bl.approve_cases([case], tmp_path)
        # tamper with the reference to simulate a rendering regression
        path = bl.baseline_path(case.id, tmp_path)
        img = Image.open(path).convert("RGBA")
        for x in range(40, 140):
            for y in range(40, 140):
                img.putpixel((x, y), (255, 0, 255, 255))
        img.save(path)
        res = bl.check_case(case, tmp_path, artifacts_dir=tmp_path / "art")
        assert res.status == bl.MISMATCH and not res.ok
        assert (tmp_path / "art" / "fixture-minimal.diff.png").exists()
        # still not overwritten
        assert Image.open(path).convert("RGBA").getpixel((50, 50)) == (255, 0, 255, 255)

    def test_stale_baseline_when_case_settings_change(self, tmp_path: Path) -> None:
        case = get_case("fixture-minimal")
        bl.approve_cases([case], tmp_path)
        changed = VisualCase(
            id=case.id, title=case.title, fixture=case.fixture, options={"theme": "cyberpunk"}
        )
        assert bl.check_case(changed, tmp_path).status == bl.STALE

    def test_orphaned_baselines_are_detected(self, tmp_path: Path) -> None:
        (tmp_path / "removed-case.png").write_bytes(b"x")
        assert [p.name for p in bl.orphaned_baselines(build_cases(), tmp_path)] == [
            "removed-case.png"
        ]

    def test_cli_approve_without_yes_is_a_dry_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            [
                "visual",
                "approve",
                "--case",
                "fixture-minimal",
                "--baseline-dir",
                str(tmp_path / "b"),
            ]
        )
        assert code == 2
        assert not (tmp_path / "b").exists()
        assert "Dry run" in capsys.readouterr().out

    def test_cli_approve_yes_then_check(self, tmp_path: Path) -> None:
        base = str(tmp_path / "b")
        assert (
            main(
                ["visual", "approve", "--yes", "--case", "fixture-minimal", "--baseline-dir", base]
            )
            == 0
        )
        assert (
            main(
                [
                    "visual",
                    "check",
                    "--case",
                    "fixture-minimal",
                    "--baseline-dir",
                    base,
                    "--artifacts-dir",
                    str(tmp_path / "a"),
                ]
            )
            == 0
        )

    def test_cli_check_fails_on_missing_baseline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            [
                "visual",
                "check",
                "--case",
                "fixture-minimal",
                "--baseline-dir",
                str(tmp_path / "none"),
                "--artifacts-dir",
                str(tmp_path / "a"),
            ]
        )
        assert code == 1 and "MISSING" in capsys.readouterr().err

    def test_cli_rejects_non_baseline_case(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["visual", "check", "--case", "tooltips-off"]) == 2
        assert "Unknown case" in capsys.readouterr().err

    def test_cli_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["visual", "list", "--baseline-only"]) == 0
        assert "theme-cyberpunk" in capsys.readouterr().out


# --------------------------------------------------------------------------- preview rendering


class TestPreviewRendering:
    def test_png_has_requested_width_and_alpha(self) -> None:
        img = svg_to_image(get_case("background-transparent").render_svg(), 400)
        assert img.size[0] == 400 and img.mode == "RGBA"

    def test_transparent_render_composites_on_dark_and_light(self) -> None:
        img = svg_to_image(get_case("background-transparent").render_svg(), 300)
        assert composite(img, (0, 0, 0)).getpixel((0, 0))[:3] == (0, 0, 0)
        assert composite(img, (255, 255, 255)).getpixel((0, 0))[:3] == (255, 255, 255)

    def test_rendering_is_reproducible(self) -> None:
        svg = get_case("theme-cyberpunk").render_svg()
        a, b = svg_to_image(svg, 300), svg_to_image(svg, 300)
        assert a.tobytes() == b.tobytes()


# --------------------------------------------------------------------------- gallery


@pytest.fixture(scope="module")
def gallery(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("gallery")
    return out, generate_gallery(out, thumb_width=240, columns=5)


class TestGallery:
    def test_manifest_totals_and_files(self, gallery) -> None:
        out, manifest = gallery
        totals = manifest["totals"]
        assert totals["cases"] == len(build_cases())
        assert totals["ok"] == totals["cases"] and totals["failed"] == 0 and totals["invalid"] == 0
        on_disk = json.loads((out / "manifest.json").read_text())
        assert on_disk == manifest

    def test_every_entry_maps_to_existing_svg_and_png(self, gallery) -> None:
        out, manifest = gallery
        for rec in manifest["cases"]:
            assert rec["status"] == "ok"
            assert (out / rec["svg"]).is_file() and (out / rec["png"]).is_file()
            assert rec["validation"]["ok"] is True
            digest = hashlib.sha256((out / rec["svg"]).read_text().encode()).hexdigest()
            assert digest == rec["svg_sha256"]

    def test_entries_record_the_requested_settings(self, gallery) -> None:
        _, manifest = gallery
        rec = next(r for r in manifest["cases"] if r["id"] == "combo-cyberpunk-dense-grid")
        assert (rec["theme"], rec["layout"]) == ("cyberpunk", "dense-grid")
        for key in (
            "background",
            "appearance",
            "height_mode",
            "width",
            "height",
            "fixture",
            "tags",
        ):
            assert key in rec

    def test_transparent_cases_report_transparent_corners(self, gallery) -> None:
        _, manifest = gallery
        by_id = {r["id"]: r for r in manifest["cases"]}
        assert by_id["background-transparent"]["transparency"]["corner_alpha"] == [0, 0, 0, 0]
        assert by_id["theme-navy-cyan"]["transparency"]["corner_alpha"] == [255, 255, 255, 255]

    def test_contact_sheet_exists_and_is_big_enough(self, gallery) -> None:
        out, manifest = gallery
        sheet = Image.open(out / manifest["contact_sheet"])
        assert sheet.width >= 5 * 240 and sheet.height > 6 * 100

    def test_duplicates_are_reported(self, gallery) -> None:
        _, manifest = gallery
        removed = {d["id"]: d["same_as"] for d in manifest["duplicates_removed"]}
        assert removed["background-legacy-transparent"] == "background-transparent"

    def test_generation_is_deterministic(self, gallery, tmp_path: Path) -> None:
        _, first = gallery
        second = generate_gallery(tmp_path, thumb_width=240, columns=5)
        assert first == second

    def test_a_failing_case_is_recorded_without_stopping_others(self, tmp_path: Path) -> None:
        good = get_case("fixture-minimal")
        bad = VisualCase(id="broken", title="broken", options={"layout": "no-such-layout"})
        manifest = generate_gallery(tmp_path, [good, bad], thumb_width=200)
        status = {r["id"]: r["status"] for r in manifest["cases"]}
        assert status == {"fixture-minimal": "ok", "broken": "failed"}
        assert (
            "no-such-layout" in next(r for r in manifest["cases"] if r["id"] == "broken")["error"]
        )
        assert manifest["totals"]["failed"] == 1

    def test_select_by_tag_and_id(self) -> None:
        cases = build_cases()
        assert {c.id for c in select_cases(cases, tags=["escaping"])} >= {"fixture-special-chars"}
        assert [c.id for c in select_cases(cases, ids=["tooltips-off"])] == ["tooltips-off"]
        with pytest.raises(KeyError):
            select_cases(cases, ids=["missing"])

    def test_contact_sheet_requires_thumbnails(self) -> None:
        with pytest.raises(ValueError):
            build_contact_sheet([])

    def test_gallery_cli(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(
            [
                "gallery",
                "-o",
                str(tmp_path),
                "--tag",
                "layout",
                "--thumb-width",
                "200",
                "--fail-on-error",
            ]
        )
        assert code == 0
        assert (tmp_path / "contact-sheet.png").exists() and (tmp_path / "manifest.json").exists()
        assert "[gallery]" in capsys.readouterr().out

    def test_gallery_cli_rejects_empty_selection(self, tmp_path: Path) -> None:
        assert main(["gallery", "-o", str(tmp_path), "--case", "nope"]) == 2
