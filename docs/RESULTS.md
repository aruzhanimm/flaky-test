# Results and interpretation

[Back to the research overview](../README.md)

All tables below derive from the saved reference artifacts. Decimal values are rounded for display; JSON files retain full precision.

## Main per-class results

| Label | Support | Original F1 | Masked F1 | Original recall | Masked recall |
| :--- | ---: | ---: | ---: | ---: | ---: |
| ID | 794 | 0.9272 | 0.8903 | 0.9786 | 0.9093 |
| NIO | 121 | 0.9959 | 0.9959 | 0.9917 | 0.9917 |
| OD | 126 | 0.3780 | 0.3780 | 0.2460 | 0.2460 |
| TD | 10 | 0.0952 | 0.0000 | 0.1000 | 0.0000 |

ID accounts for most observations and most changed predictions. NIO performance is high but relies on only three projects and a distinctive collector family. OD recall remains low in both conditions. TD has ten examples and no correct masked predictions; this is too little support for strong category-specific generalisation.

## Masking ablations (exploratory)

T = configured test identifiers; R = selected repository identifiers; P = identifier-bearing paths. These are operation subsets of the implemented mask, not disjoint semantic token inventories. Combinations can interact.

| Operation | Pooled macro-F1 | Changed from original | Improved | Harmed |
| :--- | ---: | ---: | ---: | ---: |
| original | 0.5991 | 0 | 0 | 0 |
| T | 0.5660 | 56 | 0 | 56 |
| R | 0.5752 | 46 | 0 | 46 |
| P | 0.5991 | 0 | 0 | 0 |
| TR | 0.5660 | 56 | 0 | 56 |
| TP | 0.5660 | 56 | 0 | 56 |
| RP | 0.5775 | 38 | 0 | 38 |
| full | 0.5660 | 56 | 0 | 56 |

Test-only masking gives the same predictions as the full operation for this corpus. Path-only masking leaves predictions unchanged, which does not mean paths can never matter in another corpus or model.

## Alternative classifier and counterfactual inputs

| Model and input | Pooled macro-F1 |
| :--- | ---: |
| `svc_original` | 0.5782 |
| `svc_full` | 0.5778 |
| `original_model_masked_text` | 0.5956 |
| `masked_model_original_text` | 0.5638 |

Of the 56 main changed cases, 54 retain their correct original prediction when the original fitted model receives masked text. Conversely, 53 already receive the final incorrect prediction when the masked fitted model receives original text. Decision-margin decompositions are saved in `all_changed_cases.json`; they sum direct text and refitted-state shifts. These comparisons indicate a substantial role for retraining but are conditional on fitted models and selected changed cases.

## Surefire-restricted analysis

This subset contains 136 OD/TD tests from 14 repository groups. It changes both the category task and training data, so its scores are not directly comparable to four-label main scores.

| Condition | Pooled macro-F1 |
| :--- | ---: |
| original | 0.4071 |
| full | 0.4267 |
| majority | 0.4809 |
| format | 0.4809 |

The direction of the masking difference reverses in this subset, and both classifiers remain below its majority baseline. This weakens a universal interpretation of the main decrease. Restricting to a collector family reduces one source of heterogeneity but does not produce a controlled four-category corpus.

## Interpretation boundaries

The supported conclusion is that the specified masking operation changes the fitted logistic-regression pipeline's performance on these held-out repository groups. It is not evidence that all identifiers are leakage, that the masked system generalises better, or that failure categories are identified from their underlying mechanisms. An external dataset with broader category/project coverage and less collector confounding would be needed to test those stronger claims.
