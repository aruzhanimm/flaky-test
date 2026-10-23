# Reproducibility guide

[Back to the research overview](../README.md)

## What is frozen?

The separately held `artifacts/research-snapshot.tar.xz` (not uploaded to this repository) contains 95 byte-preserved source files: the paired corpus and audit, selected source metadata, repository identities, four reference result directories, and real parser regression fixtures. The masking tests exercise the entire final corpus. `artifacts/manifest.json` records every restored path, size and SHA-256. Large archive indexes, raw download caches and redundant per-fold extension checkpoints are omitted; consolidated predictions, fits and splits are retained.

The corpus SHA-256 is:

```text
4fbee74d76717535e80f7c40841852784a23c1907954e8227ad2ae31f87c5127
```

The original reference environment recorded Python 3.12.14, Windows 11, scikit-learn 1.9.1, NumPy 2.5.4 and SciPy 1.18.1. `requirements-analysis.txt` preserves the recorded package pins. The `main_v3` and `main_v3_repeat` runs have identical prediction-file bytes, vocabulary hashes and coefficient hashes in that recorded environment.

## Three different checks

| Level | Command | What it establishes |
| :--- | :--- | :--- |
| Artifact integrity | `python scripts/restore_artifacts.py` | Included bytes agree with the published manifest |
| Independent arithmetic | `python scripts/validate_results.py main_v3 --repeat main_v3_repeat` | Scores recompute from predictions; partitions are disjoint; recorded repeat matches |
| New execution | `python scripts/evaluate.py --name my_main` | The current machine can train and evaluate the full paired experiment |

An artifact check is not a fresh model fit. A new model fit is not a fresh verification of every upstream archive member. `verify_corpus.py` performs the latter only when the original extracted diagnostic members and first-failure records are available through the acquisition route.

## Portable versus byte-identical runs

The demo checks the expected prediction for the selected held-out case and reports coefficient equality with the reference. The extension requires matching main predictions and vocabulary, and records whether all reference coefficients also match. With `--strict-reference-hashes`, differing coefficient bytes cause either command to fail.

A floating-point change can alter coefficient bytes even when all predictions match. For a repeat within the same environment, `validate_results.py my_main --repeat my_repeat` still requires exact prediction bytes and exact coefficient/vocabulary fingerprints. Do not compare a fresh coefficient hash with the Windows reference and infer that a prediction necessarily changed.

## Repository preparation changes

The publication copy preserves the original corpus, saved results, protocol bytes and numerical settings. Changes are limited to portable coefficient reporting, run-output path containment, the acquisition timestamp/evidence-directory handling, read-only validation by default, regression fixtures with whole-corpus masking checks, a checksum-verified restore utility, documentation, plotting and CI. Reference `code_sha256` entries describe the historical source files, including scripts not distributed here; they are not hashes of this publication copy. Fresh runs record the source hashes they actually execute.

## Regenerate figures

```bash
python scripts/plot_figures.py
```

The script reads restored `data/processed/audit.json` and `results/main_v3/metrics.json`. It writes three SVG figures under `docs/figures/`. All numeric marks come from those files. Mermaid diagrams in the README document the process and render directly on GitHub.

## Automated checks

The GitHub Actions workflow installs the pinned environment and runs code tests. Tests requiring real diagnostic fixtures are explicitly skipped when those files are absent. If a reference archive is supplied locally, the same workflow can also restore it and audit saved results and the demo. The public checkout has no data archive, so a successful public CI run covers code tests only. See `docs/VALIDATION.json` for the actual local publication checks and platform; workflow success must be read from GitHub's Actions status.

## Common problems

- **Missing corpus or result file:** run the restore command first.
- **Existing file differs:** the restore utility refuses to replace local edits. Preserve or move the changed file, then restore again.
- **Run already exists:** use a new `--name`; existing experiment directories are intentionally preserved.
- **Coefficient mismatch in strict mode:** compare environments and the reported prediction checks before interpreting the mismatch.
- **Package installation fails:** use Python 3.12 and inspect the resolver error. Do not silently replace the recorded versions while claiming an exact reproduction.
- **Remote acquisition is deferred:** retain the partial cache and respect the source server's retry limit. The offline snapshot route does not require these downloads.

## Required local inputs

The research archive is not included in the public code repository. From the original research workspace, copy:

- `data/processed/`: corpus, audit and exclusion/duplicate records.
- `data/audit/metadata_inventory.json` and `repository_identities.json`: reconstruction and masking metadata.
- `results/main_v3/`, `results/main_v3_repeat/`, `results/main_v3_three_labels/`, `results/extension_v4/`: complete saved predictions, splits and fits, in addition to the aggregate metrics visible here.
- For real parser fixtures: `data/log_sample/`, `data/first_failures/` and `data/extracted/`.
- For optional upstream acquisition: `data/source/` with the three metadata CSVs and saved Zenodo metadata records.

Alternatively, if you already possess the separately held reference archive, the restore script and versioned manifest provide a checksum-verified way to populate these paths. This repository does not provide a download URL for that archive. The full experiments require these inputs; code-only CI does not claim to reproduce them.
