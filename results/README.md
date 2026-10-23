# Reference results

The visible metrics are copied directly from the recorded experiments. Complete predictions, split memberships, fitted-model fingerprints and case analyses must be supplied from the original research workspace; see [required local inputs](../docs/REPRODUCIBILITY.md#required-local-inputs).

| Directory | Purpose |
| :--- | :--- |
| `main_v3` | Final four-label original/masked experiment |
| `main_v3_repeat` | Recorded exact repeat in the same reference environment |
| `main_v3_three_labels` | Sensitivity analysis excluding NIO |
| `extension_v4` | Disclosed post hoc masking, classifier and format checks |

Fresh runs use new directory names and are ignored by Git. The interpretation and metric definitions are documented in [Results](../docs/RESULTS.md).
