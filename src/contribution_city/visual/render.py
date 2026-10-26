"""SVG to PNG rendering for visual tests, using resvg (resvg-py).

resvg is a pure-Rust renderer shipped as prebuilt wheels, so it works the same on Linux, macOS and
Windows without system libraries (CairoSVG needs a native Cairo install). Limits worth knowing:
resvg ignores ``@media (prefers-color-scheme)``, so an ``appearance="auto"`` SVG always renders with
its dark palette here, and text uses whatever fonts the machine has.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from contribution_city.visual import INSTALL_HINT, VisualDependencyError

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image

DEFAULT_WIDTH = 560


def _require():
    try:
        import resvg_py
        from PIL import Image
    except ImportError as err:  # pragma: no cover - exercised only without extras
        raise VisualDependencyError(INSTALL_HINT) from err
    return resvg_py, Image


def svg_to_image(svg: str, width: int = DEFAULT_WIDTH) -> Image.Image:
    """Render an SVG string to an RGBA image; transparent areas stay transparent."""
    resvg_py, image_mod = _require()
    data = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width))
    return image_mod.open(io.BytesIO(data)).convert("RGBA")


def composite(image: Image.Image, surface: str | tuple[int, int, int] | None) -> Image.Image:
    """Place an RGBA image on a solid surface colour (``None`` keeps transparency)."""
    if surface is None:
        return image
    _, image_mod = _require()
    base = image_mod.new("RGBA", image.size, surface)
    base.alpha_composite(image)
    return base


def checkerboard(size: tuple[int, int], cell: int = 12) -> Image.Image:
    """Neutral checkerboard that makes transparency visible in previews."""
    _, image_mod = _require()
    board = image_mod.new("RGB", size, (200, 200, 200))
    px = board.load()
    for y in range(size[1]):
        for x in range(size[0]):
            if ((x // cell) + (y // cell)) % 2:
                px[x, y] = (150, 150, 150)
    return board.convert("RGBA")


def save_png(image: Image.Image, path) -> None:
    """Write a PNG with lossless optimisation (smaller baselines, same pixels)."""
    image.save(path, format="PNG", optimize=True)
