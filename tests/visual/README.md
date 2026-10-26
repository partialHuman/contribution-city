# Approved visual baselines

`baselines/*.png` are the approved reference renders (560 px wide) of the curated visual cases.
`baselines/index.json` records, per case, the settings fingerprint and the renderer versions used.

Ordinary test runs and `contribution-city visual check` only **read** these files. They change only
when someone runs `contribution-city visual approve --yes` and commits the result.

See [docs/visual-testing.md](../../docs/visual-testing.md) for the workflow.
