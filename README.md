# Contribution City

[![Tests and Quality Checks](https://github.com/contribution-city/contribution-city/actions/workflows/tests.yml/badge.svg)](https://github.com/contribution-city/contribution-city/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: >=3.10](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)

Transform your GitHub contribution activity into beautiful isometric pixel-art cities rendered as standalone, lightweight SVGs for GitHub profile READMEs and developer dashboards.

---

## Overview1

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
The `contribution-city` command-line tool provides full control over data input, theme selection, layout style, and canvas geometry.
