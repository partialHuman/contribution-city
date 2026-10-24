"""Tests for Contribution City CLI interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contribution_city.cli import create_parser, main


class TestCLI:
    """Test suite for CLI commands and argument parsing."""

    @pytest.fixture
    def sample_json(self, tmp_path: Path) -> Path:
        data = {
            "username": "cli-tester",
            "days": [
                {"date": "2025-01-01", "count": 2},
                {"date": "2025-01-02", "count": 8},
                {"date": "2025-01-03", "count": 0},
            ],
        }
        json_file = tmp_path / "test-contributions.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")
        return json_file

    def test_parser_defaults(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["generate", "--input", "test.json"])
        assert args.input_file == "test.json"
        assert args.command == "generate"
        assert args.output_file is None  # Defaults handled in build_config

    def test_cli_generate_success(self, sample_json: Path, tmp_path: Path) -> None:
        out_svg = tmp_path / "output.svg"
        ret = main(
            [
                "generate",
                "--input",
                str(sample_json),
                "--theme",
                "navy-cyan",
                "--output",
                str(out_svg),
            ]
        )
        assert ret == 0
        assert out_svg.is_file()
        content = out_svg.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "@cli-tester" in content

    def test_cli_generate_with_config(self, sample_json: Path, tmp_path: Path) -> None:
        out_svg = tmp_path / "config-output.svg"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            f"""
input: {sample_json.as_posix()}
output: {out_svg.as_posix()}
theme: sunset-neon
layout: compact
""",
            encoding="utf-8",
        )
        ret = main(["generate", "--config", str(cfg_file)])
        assert ret == 0
        assert out_svg.is_file()
        content = out_svg.read_text(encoding="utf-8")
        assert "<svg" in content

    def test_cli_missing_source_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        ret = main(["generate"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "No data source specified" in captured.err

    def test_cli_missing_input_file_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        ret = main(["generate", "--input", "non_existent_file.json"])
        assert ret == 1
        captured = capsys.readouterr()
        assert "Input file not found" in captured.err

    def test_cli_invalid_config_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad_cfg = tmp_path / "bad.yaml"
        bad_cfg.write_text("city:\n  width: 50\n", encoding="utf-8")
        ret = main(["generate", "--config", str(bad_cfg)])
        assert ret == 1
        captured = capsys.readouterr()
        assert "Configuration Error" in captured.err


class TestNewCliOptions:
    def test_auto_appearance_with_light_pair(self, tmp_path: Path) -> None:
        out = tmp_path / "c.svg"
        code = main(
            [
                "generate",
                "--input",
                "examples/sample-contributions.json",
                "--theme",
                "profile",
                "--appearance",
                "auto",
                "--height-mode",
                "linear",
                "--transparent",
                "--no-tooltips",
                "--output",
                str(out),
            ]
        )
        assert code == 0
        svg = out.read_text(encoding="utf-8")
        assert "prefers-color-scheme:light" in svg and "<title>2025" not in svg

    def test_auto_appearance_without_light_pair_fails_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            [
                "generate",
                "--input",
                "examples/sample-contributions.json",
                "--theme",
                "solar-amber",
                "--appearance",
                "auto",
                "--output",
                str(tmp_path / "x.svg"),
            ]
        )
        assert code == 1
        assert "no light variant" in capsys.readouterr().err

    def test_years_need_a_username(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            [
                "generate",
                "--input",
                "examples/sample-contributions.json",
                "--year",
                "2024",
                "--output",
                str(tmp_path / "x.svg"),
            ]
        )
        assert code == 1
        assert "--username" in capsys.readouterr().err

    def test_isometric_layout_is_no_longer_accepted(self) -> None:
        with pytest.raises(SystemExit):
            main(["generate", "--input", "x.json", "--layout", "isometric"])
