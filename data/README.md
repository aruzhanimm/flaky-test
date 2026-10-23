# Local research data

Research logs and the compressed snapshot are not uploaded to this public code repository. Supply the original research workspace data locally as described in [Required local inputs](../docs/REPRODUCIBILITY.md#required-local-inputs).

If you already have the separate reference archive, place it at `artifacts/research-snapshot.tar.xz` and run `python scripts/restore_artifacts.py` to verify and restore it. The expected file checksums are versioned in `artifacts/manifest.json`.
