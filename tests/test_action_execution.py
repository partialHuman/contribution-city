"""Run the composite action's own bash script locally with controlled inputs.

This tests the real ``run:`` block from ``action.yml``: input mapping, early validation, output
directories, the documented ``svg-path`` output, and that hostile input values never reach a shell.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from contribution_city.svgcheck import check_svg

ROOT = Path(__file__).parent.parent
ACTION = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
GENERATE = next(s for s in ACTION["runs"]["steps"] if s.get("id") == "generate")


def _find_bash() -> str | None:
    if custom := os.environ.get("CONTRIBUTION_CITY_BASH"):
        return custom
    if sys.platform == "win32":
        for git_bash in (
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Git" / "bin" / "bash.exe",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
            / "Git"
            / "usr"
            / "bin"
            / "bash.exe",
        ):
            if git_bash.is_file():
                return str(git_bash)
    candidate = shutil.which("bash")
    if sys.platform == "win32" and candidate and "WindowsApps" in candidate:
        return None
    return candidate


BASH = _find_bash()

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is required to run the action script")

# Defaults copied from action.yml so each test only states what it changes
DEFAULTS = {
    "IN_USERNAME": "",
    "IN_THEME": ACTION["inputs"]["theme"]["default"],
    "IN_LAYOUT": ACTION["inputs"]["layout"]["default"],
    "IN_APPEARANCE": ACTION["inputs"]["appearance"]["default"],
    "IN_HEIGHT_MODE": ACTION["inputs"]["height-mode"]["default"],
    "IN_YEARS": "",
    "IN_FROM": "",
    "IN_TO": "",
    "IN_BACKGROUND": "",
    "IN_TRANSPARENT": "false",
    "IN_ID_PREFIX": "",
    "IN_TOOLTIPS": "true",
    "IN_AUTO_FIT": "true",
    "IN_RETRIES": "2",
    "IN_CONFIG": "",
    "IN_INPUT": "",
    "IN_OUTPUT": "dist/city.svg",
    "IN_WIDTH": "",
    "IN_HEIGHT": "",
    "IN_SCALE": "",
    "DEFAULT_USER": "octocat",
    "GITHUB_TOKEN": "",
}


@pytest.fixture
def consumer(tmp_path: Path) -> Path:
    """A clean consumer repository: only its own files, the package comes from pip."""
    shutil.copy(ROOT / "examples/sample-contributions.json", tmp_path / "data.json")
    return tmp_path


def run_action(cwd: Path, **overrides: str) -> tuple[subprocess.CompletedProcess, Path]:
    github_output = cwd / "github_output.txt"
    github_output.write_text("")
    env = {
        "PATH": os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")]),
        "HOME": str(cwd),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "GITHUB_OUTPUT": str(github_output),
        **DEFAULTS,
        "IN_INPUT": "data.json",
        **overrides,
    }
    if "APPDATA" in os.environ:
        env["APPDATA"] = os.environ["APPDATA"]
    proc = subprocess.run(
        [BASH, "-c", GENERATE["run"]], cwd=cwd, env=env, capture_output=True, text=True, timeout=120
    )
    return proc, github_output


class TestSuccessfulRuns:
    def test_default_inputs_write_the_svg_and_report_its_path(self, consumer: Path) -> None:
        proc, out = run_action(consumer)
        assert proc.returncode == 0, proc.stderr
        assert (consumer / "dist/city.svg").is_file()
        assert "svg-path=dist/city.svg" in out.read_text()

    def test_nested_output_directories_are_created(self, consumer: Path) -> None:
        proc, out = run_action(consumer, IN_OUTPUT="a/b/c/city.svg")
        assert proc.returncode == 0, proc.stderr
        assert (consumer / "a/b/c/city.svg").is_file()
        assert out.read_text().strip() == "svg-path=a/b/c/city.svg"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"IN_THEME": "cyberpunk", "IN_LAYOUT": "downtown"},
            {"IN_THEME": "arctic-glass", "IN_LAYOUT": "floating-island"},
            {"IN_THEME": "emerald-matrix", "IN_LAYOUT": "wireframe"},
            {"IN_THEME": "copper-forge", "IN_LAYOUT": "dense-grid", "IN_HEIGHT_MODE": "linear"},
            {"IN_THEME": "sunset-grid", "IN_BACKGROUND": "transparent-sky"},
            {"IN_THEME": "neon-harbor", "IN_BACKGROUND": "transparent"},
            {"IN_THEME": "profile", "IN_APPEARANCE": "auto", "IN_BACKGROUND": "auto"},
        ],
    )
    def test_new_options_produce_valid_svg(self, consumer: Path, overrides: dict[str, str]) -> None:
        proc, _ = run_action(consumer, **overrides)
        assert proc.returncode == 0, proc.stderr
        assert check_svg((consumer / "dist/city.svg").read_text()).ok

    def test_background_input_changes_the_output(self, consumer: Path) -> None:
        run_action(consumer, IN_OUTPUT="solid.svg")
        run_action(consumer, IN_OUTPUT="clear.svg", IN_BACKGROUND="transparent")
        assert 'fill="url(#bg)"' in (consumer / "solid.svg").read_text()
        assert 'fill="url(#bg)"' not in (consumer / "clear.svg").read_text()

    def test_legacy_transparent_input_still_works(self, consumer: Path) -> None:
        proc, _ = run_action(consumer, IN_TRANSPARENT="true")
        assert proc.returncode == 0
        assert 'fill="url(#bg)"' not in (consumer / "dist/city.svg").read_text()

    def test_toggles_and_filters_are_passed_through(self, consumer: Path) -> None:
        proc, _ = run_action(
            consumer, IN_TOOLTIPS="false", IN_AUTO_FIT="false", IN_YEARS="2025", IN_ID_PREFIX="demo"
        )
        assert proc.returncode == 0, proc.stderr
        svg = (consumer / "dist/city.svg").read_text()
        assert "<title>2025" not in svg and 'id="demo-title"' in svg

    def test_year_list_with_spaces_is_accepted(self, consumer: Path) -> None:
        proc, _ = run_action(consumer, IN_YEARS="2024, 2025")
        assert proc.returncode == 0, proc.stderr


class TestValidation:
    @pytest.mark.parametrize(
        ("name", "value", "message"),
        [
            ("IN_BACKGROUND", "clear", "Invalid background"),
            ("IN_APPEARANCE", "sepia", "Invalid appearance"),
            ("IN_LAYOUT", "isometric", "Invalid layout"),
            ("IN_HEIGHT_MODE", "cubic", "Invalid height-mode"),
        ],
    )
    def test_bad_enumerated_inputs_fail_early_without_output(
        self, consumer: Path, name: str, value: str, message: str
    ) -> None:
        proc, out = run_action(consumer, **{name: value})
        assert proc.returncode == 2
        assert message in proc.stderr
        assert not (consumer / "dist").exists()
        assert "svg-path" not in out.read_text()

    def test_unknown_theme_is_rejected_by_the_cli_with_a_clear_message(
        self, consumer: Path
    ) -> None:
        proc, _ = run_action(consumer, IN_THEME="nope")
        assert proc.returncode != 0
        assert "nope" in proc.stderr and "neon-harbor" in proc.stderr

    def test_live_mode_without_token_stops_before_any_network_call(self, consumer: Path) -> None:
        proc, _ = run_action(consumer, IN_INPUT="", IN_USERNAME="")
        assert proc.returncode != 0
        assert "authentication" in proc.stderr.lower()


class TestSecurity:
    @pytest.mark.parametrize(
        "payload",
        [
            'x"; touch pwned #',
            "$(touch pwned)",
            "`touch pwned`",
            "a\ntouch pwned",
            "x' ; touch pwned ; '",
        ],
    )
    @pytest.mark.parametrize(
        "name", ["IN_THEME", "IN_OUTPUT", "IN_USERNAME", "IN_YEARS", "IN_CONFIG"]
    )
    def test_hostile_values_never_reach_a_shell(
        self, consumer: Path, name: str, payload: str
    ) -> None:
        overrides = {name: payload}
        if name == "IN_USERNAME":
            overrides["IN_INPUT"] = ""
        run_action(consumer, **overrides)
        assert not (consumer / "pwned").exists()
        assert not list(consumer.rglob("pwned"))

    def test_token_is_never_printed(self, consumer: Path) -> None:
        secret = "ghp_THIS_MUST_NOT_APPEAR_123456"
        proc, out = run_action(consumer, GITHUB_TOKEN=secret)
        assert secret not in proc.stdout + proc.stderr + out.read_text()
        proc, out = run_action(consumer, GITHUB_TOKEN=secret, IN_THEME="nope")
        assert secret not in proc.stdout + proc.stderr

    def test_token_is_not_on_the_command_line(self) -> None:
        assert "--token" not in GENERATE["run"]
        assert "GITHUB_TOKEN" in GENERATE["env"]
