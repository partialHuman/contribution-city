# Contribution City

[![Tests and Quality Checks](https://github.com/contribution-city/contribution-city/actions/workflows/tests.yml/badge.svg)](https://github.com/contribution-city/contribution-city/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: >=3.10](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)

Transform your GitHub contribution activity into beautiful isometric pixel-art cities rendered as standalone, lightweight SVGs for GitHub profile READMEs and developer dashboards.

---

## Overview

Contribution City generates an illuminated voxel metropolis from your daily GitHub commit and contribution counts. High-activity periods rise into towering skyscrapers with glowing windows and rooftop spires, while quieter days form sleek tech plinths and foundation slabs across a floating isometric circuit board.

### Key Visual Identity

- **Dark Navy Sky & Plinth**: Midnight indigo and deep navy gradients (`#050813` &rarr; `#0A1128`).
- **Illuminated Cyan Towers**: Bright cyan, cobalt, and electric blue voxel buildings with sub-linear height scaling.
- **Isometric Pixel-Art Details**: Shaded left/right depth faces, illuminated window slivers, and rooftop beacons for top tiers.
- **Deterministic SVG**: Identical inputs and configurations generate byte-for-byte identical SVGs without random jitter.
- **Zero Heavy Dependencies**: Pure Python geometry engine with `pyyaml` for configuration and standard library networking.

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Isometric SVG Renderer | **Implemented (v0.1.0)** | Deterministic 2:1 dimetric projection with depth sorting |
| Normalized Contribution Data Models | **Implemented (v0.1.0)** | Canonical JSON, flat list, and GitHub GraphQL parser |
| Built-in Visual Themes | **Implemented (v0.1.0)** | `navy-cyan`, `matrix-green`, `sunset-neon`, `monochrome-slate`, `solar-amber` |
| Grid Layouts | **Implemented (v0.1.0)** | `calendar` (52-week calendar) and `compact` (square downtown block) |
| Python CLI (`contribution-city`) | **Implemented (v0.2.0)** | Subcommands, options, actionable validation errors |
| YAML Configuration System | **Implemented (v0.2.0)** | Documented schema with validation |
| GitHub GraphQL API Client | **Implemented (v0.3.0)** | Authenticated GraphQL retrieval with rate-limit and error handling |
| Reusable GitHub Action | **Implemented (v0.4.0)** | Composite action (`action.yml`) with automated profile commit workflow |
| Animated SVG / Keyframe Lighting | *Planned (v0.6.0)* | Optional CSS keyframe window and beacon pulses |
| Raster Exports (PNG / WebP) | *Planned (v0.6.0)* | Headless rasterization without heavy system dependencies |
| Interactive 3D Web Viewer | *Planned (v0.9.0)* | WebGL / Three.js interactive city explorer |

---

## Installation

### From Source (Editable Mode)

Requirements: Python 3.10 or later.

```bash
git clone https://github.com/contribution-city/contribution-city.git
cd contribution-city
pip install -e .
```

To install with development dependencies (pytest, ruff):

```bash
pip install -e ".[dev]"
```

---

## Command-Line Interface (CLI)

The `contribution-city` command-line tool provides full control over data input, theme selection, layout style, and canvas geometry.

### 1. Generate from Local / Sample Data (Offline)

Use the included fixture to generate a city without needing an internet connection or GitHub credentials:

```bash
contribution-city generate \
  --input examples/sample-contributions.json \
  --theme navy-cyan \
  --output dist/city.svg
```

Or run directly with Python:

```bash
python -m contribution_city.cli generate \
  --input examples/sample-contributions.json \
  --theme matrix-green \
  --output dist/city-matrix.svg
```

### 2. Generate Live City from GitHub Profile

To fetch real-time contributions from GitHub, provide your username. GitHub's GraphQL API requires an authentication token:

```bash
export GITHUB_TOKEN="ghp_yourPersonalAccessToken"

contribution-city generate \
  --username octocat \
  --theme navy-cyan \
  --output dist/octocat-city.svg
```

You can also pass the token explicitly via `--token`:

```bash
contribution-city generate \
  --username octocat \
  --token "$GITHUB_TOKEN" \
  --output dist/octocat-city.svg
```

### 3. Compact Metropolis Layout

For a dense downtown square instead of the elongated 52-week calendar strip, use `--layout compact`:

```bash
contribution-city generate \
  --input examples/sample-contributions.json \
  --layout compact \
  --width 1000 \
  --height 620 \
  --theme sunset-neon \
  --output dist/city-compact.svg
```

### 4. CLI Options Reference

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--input` | `-i` | `None` | Path to local JSON contribution dataset (offline mode) |
| `--username` | `-u` | `None` | GitHub username to fetch live contributions from |
| `--token` | `-t` | `$GITHUB_TOKEN` | GitHub Personal Access Token or Action token |
| `--config` | `-c` | `None` | Path to YAML configuration file |
| `--output` | `-o` | `dist/city.svg` | Destination path for output SVG |
| `--theme` | | `navy-cyan` | Color palette (`navy-cyan`, `matrix-green`, `sunset-neon`, `monochrome-slate`, `solar-amber`) |
| `--layout` | | `calendar` | Layout style (`calendar`, `compact`, `isometric`) |
| `--width` | | `1200` | Canvas width in pixels (min 300) |
| `--height` | | `680` | Canvas height in pixels (min 200) |
| `--scale` | | `1.0` | Building height scaling factor (0.1 to 5.0) |
| `--no-windows` | | `False` | Disable illuminated pixel windows on building sides |
| `--no-stars` | | `False` | Disable sky constellation stars |
| `--no-header` | | `False` | Disable HUD stats header overlay |
| `--no-platform` | | `False` | Disable ground plinth platform beneath the city |
| `--title` | | `None` | Custom title string in HUD header |
| `--help` | `-h` | | Show help message and examples |
| `--version` | `-v` | | Show program version |

---

## Configuration Reference

You can configure Contribution City using a YAML file. CLI flags always take precedence over configuration file values.

### Example Configuration (`config.yaml`)

```yaml
# GitHub profile or local input
username: octocat-architect
theme: navy-cyan
layout: calendar
output: dist/city.svg

city:
  width: 1200
  height: 680
  tile_width: 18.0
  tile_height: 9.0
  building_scale: 1.0
  min_building_height: 6.0
  max_building_height: 125.0
  show_windows: true
  show_stars: true
  show_header: true
  show_platform: true
  show_zero_tiles: true
```

Run with:

```bash
contribution-city generate --config examples/config.example.yaml
```

---

## Reusable GitHub Action

Contribution City includes a GitHub Action (`action.yml`) that can automatically generate and commit your city visualization to your GitHub profile repository on a daily schedule.

### Consumer Workflow Example (`.github/workflows/profile-city.yml`)

Create this file in your personal profile repository (`<username>/<username>`):

```yaml
name: Update Contribution City

on:
  schedule:
    # Run every day at 00:00 UTC
    - cron: "0 0 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Generate Contribution City
        uses: contribution-city/contribution-city@v0.1.0
        with:
          username: ${{ github.repository_owner }}
          token: ${{ secrets.GITHUB_TOKEN }}
          theme: "navy-cyan"
          layout: "calendar"
          output: "dist/contribution-city.svg"

      - name: Commit and push changes
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add dist/contribution-city.svg
          if git diff --staged --quiet; then
            echo "No changes in city SVG"
          else
            git commit -m "Update Contribution City [skip ci]"
            git push
          fi
```

### Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `username` | No | `${{ github.repository_owner }}` | GitHub username to visualize |
| `token` | No | `${{ github.token }}` | Token with read permission for contributions |
| `theme` | No | `navy-cyan` | Visual theme name |
| `layout` | No | `calendar` | Grid layout (`calendar`, `compact`) |
| `output` | No | `dist/city.svg` | Destination path for SVG |
| `config` | No | `""` | Path to optional YAML config file |
| `input` | No | `""` | Path to local JSON fixture (offline testing) |

### Security & Token Permissions

- **Permissions**: The automated commit step requires `contents: write` permission for `GITHUB_TOKEN`.
- **Public vs. Private Contributions**: By default, standard GitHub tokens access public contribution activity. Private contributions are only included if the token has the necessary private user scope and the user's GitHub profile is configured to include private contributions in their activity graph.
- **Credential Hygiene**: Tokens are transmitted via secure HTTPS headers and are never printed to console logs or embedded in generated SVG files.

---

## Supported Color Themes

| Theme Name | Description | Dominant Colors |
|------------|-------------|-----------------|
| `navy-cyan` | Signature cyberpunk developer theme | Deep navy, electric cyan, cobalt |
| `matrix-green` | Phosphor green terminal matrix | Obsidian, emerald, phosphor lime |
| `sunset-neon` | 80s synthwave vaporwave aesthetic | Midnight purple, neon pink, sunset orange |
| `monochrome-slate` | Clean architectural minimalist | Obsidian, slate gray, ice white |
| `solar-amber` | Warm industrial golden glow | Dark bronze, solar amber, sunburst gold |

---

## Development and Testing

Contribution City follows high standards for code quality, typing, and test coverage.

### Running Tests

Run the complete test suite with `pytest`:

```bash
pytest
```

Run with verbose output:

```bash
python -m pytest -v
```

### Code Formatting & Linting

We use [Ruff](https://github.com/astral-sh/ruff) for fast, consistent linting and formatting:

```bash
# Check code style and common errors
python -m ruff check .

# Check code formatting
python -m ruff format --check .

# Auto-format codebase
python -m ruff format .
```

---

## Versioned Roadmap

- **v0.1.0** *(Current)*:
  - Normalized contribution data models & JSON fixture parser.
  - Deterministic isometric 2:1 dimetric SVG rendering engine.
  - Signature `navy-cyan` visual identity with illuminated building faces, windows, and rooftop spires.
- **v0.2.0** *(Current)*:
  - Command-line interface (`contribution-city generate`).
  - YAML configuration schema with strict validation.
- **v0.3.0** *(Current)*:
  - GitHub GraphQL API client with token authentication and rate-limit handling.
- **v0.4.0** *(Current)*:
  - Reusable composite GitHub Action (`action.yml`) with automated commit workflow example.
- **v0.5.0**:
  - Expanded architectural styles (e.g., neo-brutalist, art-deco spires, floating bridges).
  - Custom palette definitions via user YAML files.
- **v0.6.0**:
  - Optional CSS keyframe animations (twinkling window patterns, beacon pulse).
  - Additional raster exports (PNG / WebP).
- **v0.8.0**:
  - Public Python API and extensible pluggable renderer backends.
- **v0.9.0**:
  - Interactive 3D WebGL browser visualizer prototype.
- **v1.0.0**:
  - Stable CLI and GitHub Action API contracts, GitHub Marketplace publication, and verified releases.

---

## Contributing

Contributions, bug reports, and feature suggestions are welcome!

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/amazing-feature`.
3. Ensure all tests pass (`pytest`) and code is formatted (`ruff check .`, `ruff format .`).
4. Commit your changes: `git commit -m "Add amazing feature"`.
5. Push to the branch: `git push origin feature/amazing-feature`.
6. Open a Pull Request.

---

## License

This project is licensed under the [MIT License](LICENSE).
