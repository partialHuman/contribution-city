# Changelog

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
