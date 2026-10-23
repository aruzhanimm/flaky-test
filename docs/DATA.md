# Corpus, schema and provenance

[Back to the research overview](../README.md)

## Sources and selection

The study uses ReproFlake's configured tests and metadata, and its separately archived execution results. The saved Zenodo metadata records are preserved in the separately held research snapshot. The upstream README and three CSV files are restored under `data/source/`; their content and attribution are preserved.

From 1,115 configured records, 1,058 have a confirmed target failure. Revision eligibility removes a further seven, leaving 1,051 canonical tests. Metadata counts, execution counts and final analytical counts are different stages. The exclusion ledger records why each discarded record is absent.

`prepare_corpus.py` validates repository identities and revisions, selects one target failure, deduplicates canonical tests, checks exact cross-project text duplicates, derives both representations and emits the audit. `duplicates.json` additionally records normalised masked/numeric template similarities; those are warnings of similarity, not proof of shared code.

## JSONL schema

Each line of `data/processed/corpus.jsonl` is a self-contained observation.

| Field | Meaning |
| :--- | :--- |
| `sample_id` | Deterministic truncated SHA-256 identifier for the canonical test |
| `canonical_test_id` | Repository network root identifier plus test identity |
| `project_group` | Group used by leave-one-group-out splitting |
| `canonical_repository` | Canonical public repository URL |
| `container`, `source`, `revision` | Archived container, iDoFT/JIRA metadata source and recorded revision |
| `configured_test`, `label` | Target class/method and inherited flaky-test category |
| `original_text`, `masked_text` | Paired cleaned representations |
| `original_sha256`, `masked_sha256` | SHA-256 of the UTF-8 text fields |
| `diagnostic_member` | Original archive path and extracted-member provenance |
| `iteration`, `source_row` | Selected failure iteration and outcome-table row |
| `format` | Diagnostic collector/format family |
| `exception_type`, `review_flags` | Parsed exception and extraction review information |

Repository identities and metadata are needed for ablation reconstruction but are not supplied as separate numerical model features. The source-format baseline explicitly uses the `format` field; the main classifier uses only its selected text field.

## Coverage and confounding

| Retained format | ID | NIO | OD | TD |
| :--- | ---: | ---: | ---: | ---: |
| NonDex report | 794 | 0 | 0 | 0 |
| NIO JSON | 0 | 121 | 0 | 0 |
| Surefire text | 0 | 0 | 126 | 10 |

Source format is therefore entangled with the label. Do not describe the corpus as a balanced or collector-controlled four-category benchmark.

## Rebuilding from public sources

Locally supplied research data is the tested entry point for reproducing model results. The data archive is not uploaded to this repository. The acquisition scripts are also included for source-level auditing. This route uses network requests, an archive directory index, downloaded outcome tables and diagnostic members; it is much larger and slower than restoring the snapshot.

In a separate checkout, supply the original `data/source/` metadata and `data/audit/repository_identities.json` first, then run:

```bash
python scripts/audit_metadata.py
python scripts/index_full_archive.py
python scripts/index_candidates.py
python scripts/collect_run_tables.py
python scripts/audit_outcome_tables.py
python scripts/collect_failure_corpus.py
python scripts/prepare_corpus.py
python scripts/verify_corpus.py
```

This uses the recorded repository identity audit to retain the original grouping decisions. `audit_repositories.py` can refresh that audit, but doing so may change results if public repository state has changed. Rebuilding derived files may change byte-level serialization across systems; always inspect the resulting corpus hash and audit before fitting models. The source-acquisition route was retained from the research project and was not re-downloaded during repository packaging.

The range downloader checks member lengths and CRCs and keeps provenance. Those member checks do not establish a checksum of the entire remote archive; the historical archive audit explicitly records that limitation. Do not delete the rate-limit handling to accelerate a rerun.

## Redistribution

See [THIRD_PARTY.md](../THIRD_PARTY.md). The snapshot is a derived extract of public research data, not a new independently collected benchmark. Upstream package names, stack frames and repository identities remain present; masking is an experimental representation, not a privacy guarantee.
