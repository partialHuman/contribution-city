"""Static quality checks for generated SVG files (no rendering needed).

The checks cover what a renderer would silently tolerate but a browser, an accessibility tool or a
security review would not: well-formed XML, unique ids, references that resolve, no external
resources or active content, and a viewBox that matches the declared size.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field

SVG_NS = "http://www.w3.org/2000/svg"
_URL_REF = re.compile(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)")
_FORBIDDEN_TAGS = {"script", "foreignObject", "image", "iframe", "object", "embed", "use", "a"}
_EXTERNAL_PATTERNS = ("http://", "https://", "//", "javascript:", "data:", "file:")


@dataclass
class SvgReport:
    """Result of :func:`check_svg`; ``ok`` is True only when ``errors`` is empty."""

    well_formed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ids: int = 0
    references: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def check_svg(svg: str) -> SvgReport:
    """Validate a generated SVG string and return a report (never raises)."""
    report = SvgReport()
    try:
        root = ET.fromstring(svg.encode("utf-8"))
    except ET.ParseError as err:
        report.errors.append(f"not well-formed XML: {err}")
        return report
    report.well_formed = True

    if _local(root.tag) != "svg" or not root.tag.startswith("{" + SVG_NS):
        report.errors.append("root element is not an SVG element in the SVG namespace")
        return report

    # --- dimensions
    width, height = root.get("width"), root.get("height")
    view_box = root.get("viewBox", "").split()
    if not (width and height and len(view_box) == 4):
        report.errors.append("missing width, height or viewBox")
    else:
        try:
            if (float(view_box[2]), float(view_box[3])) != (float(width), float(height)):
                report.errors.append("viewBox size differs from width/height")
            if float(width) <= 0 or float(height) <= 0:
                report.errors.append("non-positive canvas size")
        except ValueError:
            report.errors.append("width, height or viewBox is not numeric")

    # --- ids, references, forbidden content
    ids: dict[str, int] = {}
    refs: list[str] = []
    for el in root.iter():
        name = _local(el.tag)
        if name in _FORBIDDEN_TAGS:
            report.errors.append(f"forbidden element <{name}>")
        for attr, value in el.attrib.items():
            attr_name = _local(attr)
            if attr_name == "id":
                ids[value] = ids.get(value, 0) + 1
            elif attr_name == "href":
                if value.startswith("#"):
                    refs.append(value[1:])
                else:
                    report.errors.append(f"external or non-fragment href: {value!r}")
            elif attr_name == "aria-labelledby":
                refs.extend(value.split())
            elif attr_name.startswith("on"):
                report.errors.append(f"event handler attribute {attr_name!r}")
            if any(p in value for p in ("javascript:",)):
                report.errors.append(f"script URL in attribute {attr_name!r}")
            for match in _URL_REF.finditer(value):
                target = match.group(2)
                if target.startswith("#"):
                    refs.append(target[1:])
                else:
                    report.errors.append(f"external url() reference: {target!r}")
        if name == "style" and el.text:
            if "@import" in el.text:
                report.errors.append("@import in <style>")
            for match in _URL_REF.finditer(el.text):
                target = match.group(2)
                if not target.startswith("#"):
                    report.errors.append(f"external url() in <style>: {target!r}")
                else:
                    refs.append(target[1:])

    duplicates = sorted(i for i, n in ids.items() if n > 1)
    if duplicates:
        report.errors.append(f"duplicate ids: {', '.join(duplicates)}")
    missing = sorted({r for r in refs if r not in ids})
    if missing:
        report.errors.append(f"references to missing ids: {', '.join(missing)}")
    report.ids, report.references = len(ids), len(refs)

    # --- accessibility basics (not an audit)
    if root.get("role") != "img":
        report.warnings.append("root element has no role='img'")
    ns = "{" + SVG_NS + "}"
    if root.find(ns + "title") is None:
        report.warnings.append("no <title> element")
    if root.find(ns + "desc") is None:
        report.warnings.append("no <desc> element")
    return report
