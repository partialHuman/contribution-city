"""Approved reference renders: check against them, and approve new ones only on request."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from contribution_city.visual.cases import VisualCase
from contribution_city.visual.compare import (
    PROFILES,
    DiffResult,
    Tolerance,
    compare_images,
    write_failure_artifacts,
)
from contribution_city.visual.render import DEFAULT_WIDTH, save_png, svg_to_image

DEFAULT_BASELINE_DIR = Path("tests/visual/baselines")
INDEX_NAME = "index.json"

# status values
MATCH, MISMATCH, MISSING, STALE, ERROR = "match", "mismatch", "missing", "stale", "error"


@dataclass
class CheckResult:
    case_id: str
    status: str
    message: str
    diff: DiffResult | None = None

    @property
    def ok(self) -> bool:
        return self.status == MATCH


def baseline_path(case_id: str, base_dir: Path = DEFAULT_BASELINE_DIR) -> Path:
    return Path(base_dir) / f"{case_id}.png"


def _index_path(base_dir: Path) -> Path:
    return Path(base_dir) / INDEX_NAME


def load_index(base_dir: Path = DEFAULT_BASELINE_DIR) -> dict:
    path = _index_path(base_dir)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _renderer_info() -> dict:
    import importlib.metadata as md

    info = {}
    for pkg in ("resvg-py", "Pillow"):
        try:
            info[pkg] = md.version(pkg)
        except md.PackageNotFoundError:  # pragma: no cover
            info[pkg] = "unknown"
    return info


def _normalise_svg(svg: str) -> str:
    """Drop provenance metadata some tools embed, which is not part of the drawing."""
    import re

    return re.sub(r'\s+xmlns:c2pa="[^"]*"|<metadata>.*?</metadata>', "", svg, flags=re.DOTALL)


def svg_digest(svg: str) -> str:
    return hashlib.sha256(_normalise_svg(svg).encode("utf-8")).hexdigest()


def check_case(
    case: VisualCase,
    base_dir: Path = DEFAULT_BASELINE_DIR,
    artifacts_dir: Path | None = None,
    width: int = DEFAULT_WIDTH,
    tolerance: Tolerance | None = None,
) -> CheckResult:
    """Render a case and compare it with its approved baseline. Never writes baselines.

    ``tolerance`` defaults to the case's own profile (see ``compare.PROFILES``).
    """
    from PIL import Image

    path = baseline_path(case.id, base_dir)
    try:
        svg = case.render_svg()
        current = svg_to_image(svg, width)
    except Exception as err:  # noqa: BLE001 - report any rendering failure per case
        return CheckResult(case.id, ERROR, f"render failed: {err}")

    if not path.exists():
        if artifacts_dir:
            write_failure_artifacts(case.id, None, current, None, Path(artifacts_dir))
        return CheckResult(
            case.id,
            MISSING,
            f"no approved baseline at {path}. Review the render, then run "
            "'contribution-city visual approve --yes' to create it.",
        )

    entry = load_index(base_dir).get(case.id)
    if entry and entry.get("key") != case.effective_key():
        return CheckResult(
            case.id,
            STALE,
            "the case settings changed since this baseline was approved; review and re-approve.",
        )

    baseline = Image.open(path).convert("RGBA")
    result = compare_images(baseline, current, tolerance or PROFILES[case.tolerance])
    if result.passed:
        return CheckResult(case.id, MATCH, result.reason, result)
    if artifacts_dir:
        write_failure_artifacts(case.id, baseline, current, result, Path(artifacts_dir))
    return CheckResult(case.id, MISMATCH, result.reason, result)


def check_cases(
    cases: list[VisualCase],
    base_dir: Path = DEFAULT_BASELINE_DIR,
    artifacts_dir: Path | None = None,
    width: int = DEFAULT_WIDTH,
    tolerance: Tolerance | None = None,
) -> list[CheckResult]:
    return [
        check_case(c, base_dir, artifacts_dir, width, tolerance) for c in cases if c.pixel_compare
    ]


def approve_cases(
    cases: list[VisualCase], base_dir: Path = DEFAULT_BASELINE_DIR, width: int = DEFAULT_WIDTH
) -> list[Path]:
    """Write reference images for the given cases. Only called by an explicit command."""
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    index = load_index(base)
    written = []
    for case in cases:
        if not case.pixel_compare:
            continue
        svg = case.render_svg()
        save_png(svg_to_image(svg, width), baseline_path(case.id, base))
        index[case.id] = {
            "key": case.effective_key(),
            "svg_sha256": svg_digest(svg),
            "width": width,
            "title": case.title,
        }
        written.append(baseline_path(case.id, base))
    index["_renderer"] = _renderer_info()
    _index_path(base).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return written


def orphaned_baselines(
    cases: list[VisualCase], base_dir: Path = DEFAULT_BASELINE_DIR
) -> list[Path]:
    """Baseline images that no baseline case refers to any more."""
    known = {c.id for c in cases if c.baseline}
    base = Path(base_dir)
    return sorted(p for p in base.glob("*.png") if p.stem not in known) if base.exists() else []
