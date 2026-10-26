"""Generate a preview gallery: SVGs, PNG thumbnails, a labelled contact sheet and a JSON manifest.

The gallery is built from the theme and layout registries (see ``cases.py``), uses only the
deterministic fixtures, and never touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contribution_city._version import __version__
from contribution_city.svgcheck import check_svg
from contribution_city.visual import INSTALL_HINT, VisualDependencyError
from contribution_city.visual.baseline import baseline_path, svg_digest
from contribution_city.visual.cases import VisualCase, build_cases, raw_cases
from contribution_city.visual.render import checkerboard, save_png, svg_to_image

MANIFEST_NAME = "manifest.json"
SHEET_NAME = "contact-sheet.png"


def _font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - Pillow < 10.1 has no sized default font
        return ImageFont.load_default()


def select_cases(
    cases: list[VisualCase], ids: list[str] | None = None, tags: list[str] | None = None
) -> list[VisualCase]:
    """Filter cases by id and/or tag; raises KeyError for unknown ids."""
    selected = cases
    if ids:
        known = {c.id for c in cases}
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise KeyError(f"Unknown case id(s): {', '.join(unknown)}")
        selected = [c for c in selected if c.id in set(ids)]
    if tags:
        wanted = set(tags)
        selected = [c for c in selected if wanted & set(c.tags)]
    return selected


def _transparency(image) -> dict[str, Any]:
    """Alpha at the four corners and the share of fully transparent pixels."""
    w, h = image.size
    corners = [image.getpixel(p)[3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    alpha = image.getchannel("A")
    transparent = alpha.histogram()[0] / (w * h)
    return {"corner_alpha": corners, "transparent_ratio": round(transparent, 4)}


def build_contact_sheet(
    entries: list[tuple[VisualCase, Any]],
    columns: int = 4,
    title: str = "Contribution City gallery",
):
    """Arrange thumbnails in a grid with readable labels. Transparent areas show a checkerboard."""
    from PIL import Image, ImageDraw

    if not entries:
        raise ValueError("no thumbnails to arrange")
    tw, th = entries[0][1].size
    label_h, pad, head = 46, 12, 52
    rows = -(-len(entries) // columns)
    width = columns * (tw + pad) + pad
    height = head + rows * (th + label_h + pad) + pad
    sheet = Image.new("RGB", (width, height), (24, 26, 32))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 14), f"{title}  -  {len(entries)} cases", fill=(235, 240, 250), font=_font(22))

    for i, (case, thumb) in enumerate(entries):
        x = pad + (i % columns) * (tw + pad)
        y = head + (i // columns) * (th + label_h + pad)
        cell = checkerboard(thumb.size)
        cell.alpha_composite(thumb)
        sheet.paste(cell.convert("RGB"), (x, y))
        draw.text((x + 2, y + th + 4), case.id, fill=(255, 255, 255), font=_font(15))
        sub = ", ".join(case.tags)
        draw.text((x + 2, y + th + 24), sub, fill=(150, 160, 180), font=_font(12))
    return sheet


def generate_gallery(
    output_dir: Path | str = "gallery",
    cases: list[VisualCase] | None = None,
    thumb_width: int = 360,
    columns: int = 4,
    baseline_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Render every case and write svg/, png/, the contact sheet and manifest.json.

    Returns the manifest dictionary. A case that fails to render is recorded with
    ``"status": "failed"`` and does not stop the others.
    """
    try:
        import PIL  # noqa: F401
        import resvg_py  # noqa: F401
    except ImportError as err:
        raise VisualDependencyError(INSTALL_HINT) from err

    out = Path(output_dir)
    (out / "svg").mkdir(parents=True, exist_ok=True)
    (out / "png").mkdir(parents=True, exist_ok=True)

    unique = build_cases()
    all_cases = unique if cases is None else cases
    by_key = {u.effective_key(): u.id for u in unique}
    unique_ids = {u.id for u in unique}
    removed = [
        {"id": c.id, "same_as": by_key[c.effective_key()]}
        for c in raw_cases()
        if c.id not in unique_ids
    ]

    entries: list[tuple[VisualCase, Any]] = []
    records: list[dict[str, Any]] = []
    for case in all_cases:
        record: dict[str, Any] = {
            "id": case.id,
            "title": case.title,
            "tags": list(case.tags),
            "baseline": case.baseline,
            "pixel_compare": case.pixel_compare,
        }
        try:
            record.update(case.describe())  # also validates the options
            svg = case.render_svg()
            report = check_svg(svg)
            (out / "svg" / f"{case.id}.svg").write_text(svg, encoding="utf-8")
            thumb = svg_to_image(svg, thumb_width)
            save_png(thumb, out / "png" / f"{case.id}.png")
            record.update(
                {
                    "status": "ok" if report.ok else "invalid",
                    "svg": f"svg/{case.id}.svg",
                    "png": f"png/{case.id}.png",
                    "svg_bytes": len(svg.encode("utf-8")),
                    "svg_sha256": svg_digest(svg),
                    "validation": report.to_dict(),
                    "transparency": _transparency(thumb),
                    "baseline_file": (
                        baseline_path(case.id, baseline_dir).as_posix()
                        if case.baseline and baseline_dir
                        else None
                    ),
                }
            )
            entries.append((case, thumb))
        except Exception as err:  # noqa: BLE001 - record and continue
            record.update({"status": "failed", "error": f"{type(err).__name__}: {err}"})
        records.append(record)

    if entries:
        sheet = build_contact_sheet(entries, columns=columns)
        save_png(sheet, out / SHEET_NAME)

    manifest = {
        "contribution_city_version": __version__,
        "thumbnail_width": thumb_width,
        "contact_sheet": SHEET_NAME if entries else None,
        "totals": {
            "cases": len(records),
            "ok": sum(r["status"] == "ok" for r in records),
            "invalid": sum(r["status"] == "invalid" for r in records),
            "failed": sum(r["status"] == "failed" for r in records),
        },
        "duplicates_removed": removed,
        "cases": records,
    }
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
