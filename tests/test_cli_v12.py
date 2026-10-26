"""CLI and configuration behaviour added in v1.2."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from contribution_city.cli import build_config, create_parser, main
from contribution_city.config import AppConfig
from contribution_city.renderer.layouts import LAYOUT_NAMES
from contribution_city.renderer.themes import THEMES
from contribution_city.svgcheck import check_svg

SAMPLE = "examples/sample-contributions.json"


def gen(tmp_path: Path, *extra: str, name: str = "city.svg") -> tuple[int, Path]:
    out = tmp_path / name
    code = main(["generate", "--input", SAMPLE, "--output", str(out), *extra])
    return code, out


class TestNewChoices:
    @pytest.mark.parametrize("theme", sorted(THEMES))
    def test_every_theme_generates(self, tmp_path: Path, theme: str) -> None:
        code, out = gen(tmp_path, "--theme", theme)
        assert code == 0 and check_svg(out.read_text()).ok

    @pytest.mark.parametrize("layout", LAYOUT_NAMES)
    def test_every_layout_generates(self, tmp_path: Path, layout: str) -> None:
        code, out = gen(tmp_path, "--layout", layout)
        assert code == 0 and check_svg(out.read_text()).ok

    @pytest.mark.parametrize("mode", ["solid", "transparent", "transparent-sky", "auto"])
    def test_every_background_mode_generates(self, tmp_path: Path, mode: str) -> None:
        code, out = gen(tmp_path, "--background", mode)
        assert code == 0 and check_svg(out.read_text()).ok

    def test_unknown_theme_is_rejected_listing_the_valid_names(
        self, tmp_path: Path, capsys
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            gen(tmp_path, "--theme", "neon-habour")
        err = capsys.readouterr().err
        assert exc.value.code == 2 and "neon-habour" in err and "neon-harbor" in err

    def test_unknown_background_is_rejected_by_argparse(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            gen(tmp_path, "--background", "clear")
        assert exc.value.code == 2

    def test_help_documents_new_features_with_examples(self, capsys) -> None:
        with pytest.raises(SystemExit):
            main(["--help"])
        text = capsys.readouterr().out
        for needle in ("cyberpunk", "floating-island", "transparent-sky", "Precedence", "downtown"):
            assert needle in text

    def test_help_lists_every_registered_theme_and_layout(self, capsys) -> None:
        with pytest.raises(SystemExit):
            main(["--help"])
        text = capsys.readouterr().out
        assert all(name in text for name in THEMES)
        assert all(name in text for name in LAYOUT_NAMES)


class TestOutputPaths:
    def test_nested_output_directories_are_created(self, tmp_path: Path) -> None:
        code, out = gen(tmp_path, name="a/b/c/city.svg")
        assert code == 0 and out.is_file()

    def test_output_path_is_reported_on_success(self, tmp_path: Path, capsys) -> None:
        code, out = gen(tmp_path)
        assert code == 0 and str(out) in capsys.readouterr().out

    def test_missing_input_file_is_a_clean_error(self, tmp_path: Path, capsys) -> None:
        code = main(
            [
                "generate",
                "--input",
                str(tmp_path / "nope.json"),
                "--output",
                str(tmp_path / "x.svg"),
            ]
        )
        assert code == 1 and "not found" in capsys.readouterr().err.lower()


class TestPrecedence:
    """defaults < configuration file < command-line options"""

    def write_config(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "cfg.yaml"
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return path

    def parse(self, *argv: str) -> AppConfig:
        return build_config(create_parser().parse_args(["generate", *argv]))

    def test_defaults(self) -> None:
        cfg = self.parse("--input", SAMPLE)
        assert (cfg.theme, cfg.layout, cfg.city.background) == ("navy-cyan", "calendar", None)

    def test_config_file_overrides_defaults(self, tmp_path: Path) -> None:
        path = self.write_config(
            tmp_path, "theme: cyberpunk\nlayout: downtown\ncity:\n  background: transparent\n"
        )
        cfg = self.parse("--input", SAMPLE, "--config", str(path))
        assert (cfg.theme, cfg.layout, cfg.city.background) == (
            "cyberpunk",
            "downtown",
            "transparent",
        )

    def test_command_line_overrides_config_file(self, tmp_path: Path) -> None:
        path = self.write_config(
            tmp_path, "theme: cyberpunk\nlayout: downtown\ncity:\n  background: transparent\n"
        )
        cfg = self.parse(
            "--input",
            SAMPLE,
            "--config",
            str(path),
            "--theme",
            "arctic-glass",
            "--background",
            "solid",
        )
        assert (cfg.theme, cfg.layout, cfg.city.background) == ("arctic-glass", "downtown", "solid")

    def test_background_beats_the_legacy_transparent_flag(self, tmp_path: Path) -> None:
        code, out = gen(tmp_path, "--transparent", "--background", "transparent-sky")
        svg = out.read_text()
        assert code == 0 and 'fill="url(#bg)"' not in svg and 'id="sky-stars"' in svg

    def test_contradictory_flags_warn_and_background_wins(self, tmp_path: Path) -> None:
        with pytest.warns(UserWarning, match="overrides transparent"):
            code, out = gen(tmp_path, "--transparent", "--background", "solid")
        assert code == 0 and 'fill="url(#bg)"' in out.read_text()

    def test_legacy_flag_alone_is_unchanged(self, tmp_path: Path) -> None:
        code, out = gen(tmp_path, "--transparent")
        svg = out.read_text()
        assert code == 0 and 'fill="url(#bg)"' not in svg and 'id="sky-stars"' not in svg

    def test_config_with_years_and_range_is_rejected(self, tmp_path: Path, capsys) -> None:
        path = self.write_config(tmp_path, "years: [2025]\nfrom: 2025-01-01\n")
        code, _ = gen(tmp_path, "--config", str(path))
        assert code == 1 and "either" in capsys.readouterr().err.lower()


class TestOfflineFilters:
    def test_date_range_limits_the_data(self, tmp_path: Path) -> None:
        full = gen(tmp_path, name="full.svg")[1].read_text()
        code, out = gen(tmp_path, "--from", "2025-03-01", "--to", "2025-03-31", name="march.svg")
        assert code == 0 and len(out.read_text()) < len(full)
        assert "2025-03-" in out.read_text() and "2025-07-" not in out.read_text()

    def test_year_and_range_cannot_be_combined(self, tmp_path: Path, capsys) -> None:
        code, _ = gen(tmp_path, "--year", "2025", "--from", "2025-06-01", "--to", "2025-06-30")
        assert code == 1 and "either" in capsys.readouterr().err.lower()


class TestCheckSvgCommand:
    def test_ok_file(self, tmp_path: Path, capsys) -> None:
        _, out = gen(tmp_path)
        assert main(["check-svg", str(out)]) == 0
        assert "OK" in capsys.readouterr().out

    def test_bad_file_fails(self, tmp_path: Path, capsys) -> None:
        bad = tmp_path / "bad.svg"
        bad.write_text("<svg><g></svg>")
        assert main(["check-svg", str(bad)]) == 1
        assert "well-formed" in capsys.readouterr().err

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        assert main(["check-svg", str(tmp_path / "nope.svg")]) == 1

    def test_strict_mode_turns_warnings_into_failures(self, tmp_path: Path) -> None:
        f = tmp_path / "plain.svg"
        f.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2" viewBox="0 0 2 2"/>'
        )
        assert main(["check-svg", str(f)]) == 0
        assert main(["check-svg", "--strict", str(f)]) == 1


class TestVersion:
    def test_package_and_cli_report_the_same_version(self, capsys) -> None:
        import contribution_city

        with pytest.raises(SystemExit):
            main(["--version"])
        assert contribution_city.__version__ in capsys.readouterr().out
        assert re.fullmatch(r"\d+\.\d+\.\d+", contribution_city.__version__)
