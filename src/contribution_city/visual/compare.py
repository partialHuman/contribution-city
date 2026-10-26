"""Image comparison with tolerances that separate antialiasing noise from real changes.

A pixel is *different* when any channel differs by more than ``channel``. Different pixels count as
*clustered* when at least ``cluster_min`` pixels of their 3x3 neighbourhood are also different, which
is what a moved edge, a changed colour or a missing building looks like. Scattered one-pixel
differences along edges are antialiasing noise and only count towards the loose overall budget.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from contribution_city.visual import INSTALL_HINT, VisualDependencyError

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image


@dataclass(frozen=True)
class Tolerance:
    """How much difference is acceptable before a comparison fails."""

    channel: int = 24  # per-channel difference (0-255) that makes a pixel "different"
    max_ratio: float = 0.004  # at most 0.4 % of all pixels may differ at all
    max_clustered_ratio: float = 0.0005  # at most 0.05 % may differ in a connected patch
    cluster_min: int = 3  # neighbours (incl. itself, 3x3) that make a difference "clustered"
    max_alpha_diff: int = 32  # transparency must match closely (catches stray backgrounds)


STRICT = Tolerance(channel=2, max_ratio=0.0, max_clustered_ratio=0.0, max_alpha_diff=2)
DEFAULT = Tolerance()
# For images with a little text, whose glyph shapes differ between machines
TEXT = Tolerance(channel=64, max_ratio=0.01, max_clustered_ratio=0.004)
PROFILES = {"strict": STRICT, "default": DEFAULT, "text": TEXT}


@dataclass
class DiffResult:
    """Outcome of comparing two renders."""

    passed: bool
    reason: str
    width: int
    height: int
    differing_pixels: int
    differing_ratio: float
    clustered_pixels: int
    clustered_ratio: float
    max_channel_diff: int
    max_alpha_diff: int
    mean_diff: float
    bbox: tuple[int, int, int, int] | None
    size_mismatch: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _pil():
    try:
        from PIL import Image, ImageChops, ImageFilter
    except ImportError as err:  # pragma: no cover
        raise VisualDependencyError(INSTALL_HINT) from err
    return Image, ImageChops, ImageFilter


def compare_images(
    baseline: Image.Image, current: Image.Image, tolerance: Tolerance = DEFAULT
) -> DiffResult:
    """Compare two RGBA images and decide whether the change is acceptable."""
    image_mod, chops, filters = _pil()
    baseline, current = baseline.convert("RGBA"), current.convert("RGBA")
    w, h = current.size

    if baseline.size != current.size:
        return DiffResult(
            passed=False,
            reason=f"size changed from {baseline.size} to {current.size}",
            width=w,
            height=h,
            differing_pixels=w * h,
            differing_ratio=1.0,
            clustered_pixels=w * h,
            clustered_ratio=1.0,
            max_channel_diff=255,
            max_alpha_diff=255,
            mean_diff=255.0,
            bbox=(0, 0, w, h),
            size_mismatch=True,
        )

    diff = chops.difference(baseline, current)
    r, g, b, a = diff.split()
    rgb_max = chops.lighter(chops.lighter(r, g), b)
    max_channel = rgb_max.getextrema()[1]
    max_alpha = a.getextrema()[1]
    worst = chops.lighter(rgb_max, a)

    mask = worst.point(lambda v: 255 if v > tolerance.channel else 0)
    total = w * h
    differing = mask.histogram()[255]

    # Clustered differences: pixels whose 3x3 neighbourhood is mostly different too
    # (padded with an empty border so image edges are not treated as extra neighbours)
    padded = image_mod.new("L", (w + 2, h + 2), 0)
    padded.paste(mask, (1, 1))
    density = padded.filter(filters.BoxBlur(1)).crop((1, 1, w + 1, h + 1))  # 255 * n / 9
    need = int(255 * tolerance.cluster_min / 9) - 1
    clustered_mask = chops.multiply(mask, density.point(lambda v: 255 if v >= need else 0))
    clustered = clustered_mask.histogram()[255]

    hist = worst.histogram()
    mean = sum(i * n for i, n in enumerate(hist)) / total if total else 0.0
    bbox = mask.getbbox()

    ratio = differing / total if total else 0.0
    cratio = clustered / total if total else 0.0

    problems = []
    if ratio > tolerance.max_ratio:
        problems.append(f"{ratio:.4%} of pixels differ (limit {tolerance.max_ratio:.4%})")
    if cratio > tolerance.max_clustered_ratio:
        problems.append(
            f"{cratio:.4%} of pixels differ in patches (limit {tolerance.max_clustered_ratio:.4%})"
        )
    if max_alpha > tolerance.max_alpha_diff:
        problems.append(
            f"transparency changed by up to {max_alpha} (limit {tolerance.max_alpha_diff})"
        )

    return DiffResult(
        passed=not problems,
        reason="; ".join(problems) if problems else "within tolerance",
        width=w,
        height=h,
        differing_pixels=differing,
        differing_ratio=ratio,
        clustered_pixels=clustered,
        clustered_ratio=cratio,
        max_channel_diff=max_channel,
        max_alpha_diff=max_alpha,
        mean_diff=mean,
        bbox=bbox,
    )


def write_failure_artifacts(
    name: str,
    baseline: Image.Image | None,
    current: Image.Image,
    result: DiffResult | None,
    out_dir: Path,
) -> Path:
    """Save current/baseline/diff images and a JSON report for a failed comparison."""
    image_mod, chops, _ = _pil()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / name
    current.save(f"{stem}.current.png")
    if baseline is not None:
        baseline.save(f"{stem}.baseline.png")
        if baseline.size == current.size:
            d = chops.difference(baseline.convert("RGBA"), current.convert("RGBA"))
            r, g, b, a = d.split()
            worst = chops.lighter(chops.lighter(chops.lighter(r, g), b), a)
            mask = worst.point(lambda v: 255 if v > 0 else 0)
            highlight = image_mod.new("RGBA", current.size, (255, 0, 60, 255))
            canvas = image_mod.new("RGBA", current.size, (20, 20, 20, 255))
            canvas.paste(highlight, (0, 0), mask)
            canvas.save(f"{stem}.diff.png")
            side = image_mod.new("RGBA", (current.width * 3, current.height), (0, 0, 0, 255))
            for i, im in enumerate((baseline, current, canvas)):
                side.paste(im, (i * current.width, 0))
            side.save(f"{stem}.side-by-side.png")
    report = {"case": name, "result": result.to_dict() if result else {"reason": "no baseline"}}
    Path(f"{stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out_dir
