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
