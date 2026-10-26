# Visual testing and the preview gallery

Contribution City renders SVG, so a change can be correct XML and still look wrong. The visual
suite catches that. It needs two extra packages, installed with the dev extra
(`pip install -e ".[dev]"`) or on their own (`pip install "contribution-city[visual]"`):
`resvg-py` (a pure-Rust SVG renderer with prebuilt wheels for Linux, macOS and Windows) and Pillow.

## What is compared

Every visual case is a deterministic combination of **fixture data + filters + render options**.
Fixtures are generated from fixed dates and a small integer generator, so results never depend on
the current date, the network or a GitHub account (`src/contribution_city/visual/fixtures.py`).

| Command | What it does | Writes baselines? |
|---|---|---|
| `contribution-city visual list [--baseline-only]` | Lists cases | no |
| `contribution-city visual check` | Renders the baseline cases and compares them with `tests/visual/baselines` | **never** |
| `contribution-city visual approve --yes` | Renders and stores new reference images | yes (explicit) |
| `contribution-city gallery` | SVG + PNG for every case, contact sheet, `manifest.json` | no |
| `contribution-city check-svg FILE...` | Static checks of any SVG | no |
| `pytest -m baseline` | The pixel comparison as a test | no |

Only a curated subset (about 35 distinct cases) has a baseline; the full gallery (about 50 cases)
is generated on demand and uploaded by CI as an artifact.

## How differences are judged

A pixel is *different* when any channel differs by more than `channel` (default 24 of 255). Different
pixels that sit in a connected patch (3 or more of their 3x3 neighbours differ as well) are
*clustered*: that is what a moved edge, a changed colour or a missing building looks like.
Scattered single-pixel differences along edges are treated as antialiasing noise.

| Setting (`compare.Tolerance`) | Default | Meaning |
|---|---|---|
| `channel` | 24 | Per-channel difference that counts |
| `max_ratio` | 0.4 % | Share of all pixels that may differ at all |
| `max_clustered_ratio` | 0.05 % | Share that may differ in connected patches |
| `max_alpha_diff` | 32 | Transparency must match closely (catches stray backgrounds) |

Profiles: `default`, `text` (looser, for the one case that draws a sentence with system fonts) and
`strict`. Header text depends on installed fonts, so cases with a header are never compared pixel by
pixel; they are covered by the structural SVG checks instead.

## When a check fails

`contribution-city visual check` exits with status 1 and writes, per failing case, into
`visual-artifacts/`:

- `<case>.current.png`, `<case>.baseline.png`
- `<case>.diff.png` (differing pixels in red)
- `<case>.side-by-side.png` (baseline, current, diff)
- `<case>.json` (difference statistics: ratios, maximum channel difference, bounding box)

Statuses: `mismatch` (looks different), `missing` (no approved baseline yet), `stale` (the case's
settings changed after the baseline was approved), `error` (rendering failed). Baseline images that no
case uses any more are reported as `ORPHAN`.

## Changing a baseline on purpose

1. Make your change and run `contribution-city visual check` (it fails and writes artifacts).
2. Look at the images, or run `contribution-city gallery` and open `gallery/contact-sheet.png`.
3. Preview what would be written: `contribution-city visual approve --case theme-cyberpunk`
   (a dry run, exit status 2).
4. Approve it: `contribution-city visual approve --yes --case theme-cyberpunk`
   (omit `--case` to re-approve all).
5. Commit `tests/visual/baselines/` together with the change that caused it.

CI never approves baselines. It only runs `visual check` and uploads artifacts when it fails.

## Adding a theme or layout

Add a dictionary to `src/contribution_city/renderer/palettes.py` (themes) or one entry to
`LAYOUT_SPECS` in `renderer/layouts.py` (layouts). The gallery, the CLI help and the case registry
are generated from those registries, so the new entry appears automatically (`theme-<name>` and
`layout-<name>` cases). Run `contribution-city visual approve --yes --case theme-<name>` after
reviewing it. The tests in `tests/test_themes_layouts.py` check contrast and level separation for
every palette in `palettes.py`.

## The gallery manifest

`gallery/manifest.json` contains, per case: id, title, tags, fixture, filters, the effective settings
(theme, layout, background, appearance, height mode, size, ...), the SVG and PNG paths, size and
SHA-256 of the SVG, the result of the static SVG checks (`validation`), the transparency of the PNG
corners (`transparency`), and `status` (`ok`, `invalid` or `failed`, with the error message). It also
lists cases that were dropped because their effective settings equal an earlier case
(`duplicates_removed`). There are no timestamps, so two runs produce identical manifests.

## Limits

- resvg ignores `@media (prefers-color-scheme)`. An `appearance="auto"` SVG therefore always renders
  with its dark palette in these tests; the light palettes are tested through the `*-light` themes.
- Pixel baselines come from one renderer version (recorded in `baselines/index.json`). A resvg update
  can shift antialiasing; if differences stay within tolerance nothing happens, otherwise review and
  re-approve.
- CI compares pixels on Linux only. The cross-platform test matrix runs everything else.
- This environment cannot run a browser, so how a given browser handles `prefers-color-scheme`
  inside an `<img>` is documented behaviour, not something these tests verify.
