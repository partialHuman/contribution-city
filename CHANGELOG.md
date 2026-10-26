# Changelog

## 1.2.0 (development, not released)

### Added
- **Themes:** `neon-harbor`, `cyberpunk`, `emerald-matrix`, `copper-forge`, `arctic-glass`,
  `sunset-grid`. They are plain data in `renderer/palettes.py`; tests check text contrast, level
  separation and window visibility for each.
- **Layouts:** `dense-grid`, `downtown`, `floating-island`, `wireframe`, from a small layout registry
  (`renderer/layouts.py`). `calendar` and `compact` are unchanged.
- **Background modes:** `--background solid | transparent | transparent-sky | auto` (config
  `city.background`, action input `background`). It takes precedence over the legacy `transparent`
  flag, which keeps working; contradictory settings warn.
- **Visual regression suite:** deterministic fixtures, a case registry generated from the theme and
  layout registries, resvg-based PNG rendering, tolerance-based comparison that separates
  antialiasing noise from real changes, approved baselines, failure artifacts (current, baseline,
  diff, side-by-side, JSON) and an explicit `visual approve --yes` command. Baselines are never
  written by tests or CI.
- **Gallery:** `contribution-city gallery` writes SVGs, PNG thumbnails, a labelled contact sheet and a
  deterministic `manifest.json` (settings, validation status, transparency probe, removed duplicates).
- **`check-svg` command and `svgcheck` module:** well-formed XML, unique ids, resolving references,
  no external resources or active content, matching viewBox.
- **`--id-prefix`:** namespaces element ids and scopes the CSS so several SVGs can be inlined in one
  page. Without it the ids are exactly the 1.1.0 ones.
- **Offline `--year`, `--from`, `--to`** now filter `--input` files as well as live data.
- Action: inputs `background` and `id-prefix`; early validation of `layout`, `appearance`,
  `background`, `height-mode`; local execution tests of the real script (including hostile values).
- CI: a `visual` job (baseline comparison, gallery, SVG checks, artifacts) and a `build` job that
  checks the reported version. Example `gallery-artifact.yml` (read-only permissions).

### Changed
- Default output is byte-identical to 1.1.0 for the same input and options (tested against
  references generated from the 1.1.0 source).
- CLI help lists themes and layouts from the registries.
- Window contrast of three palettes added in this cycle was raised after the contrast tests found it
  too low (`neon-harbor`, `emerald-matrix`, `arctic-glass`).

### Fixed
- The gallery records a case with invalid options as `failed` instead of stopping.

## 1.1.0

### Fixed
- **SVG escaping:** `custom_title` and the username were written into the SVG unescaped, which could
  produce invalid XML (a broken image) or inject markup. All text is now escaped.
- **Shell injection in `action.yml`:** inputs were pasted into the bash script. They now reach the
  script only through environment variables, and the token is no longer passed on the command line.
- **Version and name mismatches:** the version now lives in one place (`_version.py`) and is used by
  the package, the build and the HTTP User-Agent. Docs, example workflow, license and author point
  at `partialHuman/contribution-city`.
- **README** contained the whole document twice; it now exists once.
- **`isometric` layout** was only an alias of `calendar`. It was removed from the CLI, the action and
  the config (a helpful error explains that `calendar` is the isometric view).
- **Streaks** no longer treat missing dates in custom data as consecutive days.

### Added
- **Auto-fit:** the city is scaled to fill the canvas (`auto_fit`, `--no-fit` to turn it off).
- **Light and dark:** `appearance: auto` embeds a light palette and follows `prefers-color-scheme`;
  `transparent` removes the background. New themes: `profile`, `profile-light`, `navy-cyan-light`.
- **Height modes:** `power` (default), `linear` (proportional), `sqrt`, `log`.
- **Date ranges and several years:** `--year` (repeatable), `--from`, `--to`.
- **Private contributions:** the count of restricted contributions is read and shown in the header.
- **Retries** with exponential back-off for network errors, 5xx responses and secondary rate limits.
- **Accessibility:** root `<title>`, `<desc>` and `role="img"` with totals.
- **Pixel-art edges** (`crispEdges`) by default (`--smooth` to turn off).
- `compact` layout leaves a tile between buildings so towers no longer hide each other.
- Example workflow publishes to an `output` branch (one commit, no history growth) and shows the
  light/dark `<picture>` setup. Third-party actions are pinned to commit SHAs.

### Changed
- Smaller files: empty tiles are one path with no tooltip, styling uses CSS classes, and windows are
  four paths per building instead of a line each. The sample city went from about 308 KB to about
  140 KB.
- Raising the canvas size now enlarges the city (it used to stay at a fixed 18 px tile size).

## 1.0.0
- Initial release.
