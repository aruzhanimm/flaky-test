# Method and rationale

[Back to the research overview](../README.md)

## Design and unit of analysis

This is a quantitative, paired computational experiment on an observational corpus. The manipulated input is the log representation: original text versus a deterministic identifier mask. The response is held-out category classification performance. One canonical test supplies one representative confirmed target failure. Repeated executions are used to establish a valid failure record, not counted as independent observations.

Project groups use the recorded canonical repository network root. Fork-related identities therefore remain in the same partition. The frozen repository audit is used for reproduction; a fresh web audit may see different repository state.

## Why project-disjoint evaluation?

The question concerns an unseen project. A row-level random split could reward memorisation of names, related tests or collector-specific templates within the same repository. Leave-one-group-out evaluation holds each observed repository group out once. Every training fold must retain every target category; the code checks this invariant.

The same sample IDs appear in both conditions of a fold. A fresh vectorizer is fitted on each training partition and transforms the held-out logs. No vocabulary or inverse document frequency is learned from evaluation texts.

## Why TF-IDF and logistic regression?

A linear text baseline makes it possible to inspect features and decision-margin contributions. Word unigrams capture individual tokens; bigrams capture short combinations. Balanced class weights address training imbalance, while macro-F1 prevents the majority label from alone determining the pooled score. Neither choice removes limited project coverage or source-format confounding.

Numerical parameters are fixed in `config_model_v3.json`. There is no parameter search, so no validation set is used to select settings. The archived history includes a pilot and parser/masking corrections: version 2 protects framework names, and version 3 corrects JUnit 5 signature handling. The final result should not be presented as an untouched preregistration. Original protocol files retain that history.

## Masking operation

The implementation first protects exception strings, then replaces selected project URL/name fragments, identifier-bearing paths, and the configured test class/method, finally restoring protected exceptions. See `representations.py` and the operation-level ablations in `mask_components.py`.

The mask targets known metadata identifiers. Superclasses, dependencies, other application symbols and formatting can remain. It changes both the text supplied at prediction time and the training vocabulary/model learned from that condition. The counterfactual extension separates these two effects descriptively by applying each fitted model to the other representation.

## Metrics and estimands

For each class, F1 is `2 TP / (2 TP + FP + FN)`, with zero assigned to an undefined denominator. Pooled macro-F1 is the arithmetic mean over the four predefined labels using all out-of-project predictions.

For project `g`, compute macro-F1 over labels present in that held-out project's ground truth. The paired project delta is `F1_masked(g) - F1_original(g)`. Average these deltas with equal project weight. This differs from the difference of pooled macro-F1 values. In particular, a prediction of an unsupported label counts against recall of the supported label, while the unsupported label itself is not added as another fold-level averaging term.

The code resamples the 127 observed project deltas with replacement 5,000 times using seed `20261013` and reports the 2.5th and 97.5th percentiles. This is a descriptive conditional interval. The training sets overlap, rare categories have few projects, and the observed project sample is not a random population sample. No p-value or broad causal claim is made.

## Baselines and exploratory analyses

The majority baseline uses only training-fold label counts. The source-format lookup learns the most frequent label within each training-fold format and falls back to the training majority for an unseen format. Its high performance is a diagnostic of corpus confounding.

The three-label analysis removes NIO and reruns training on 930 tests. The extension adds eight masking combinations, Linear SVC, two counterfactual input/model combinations, and a 136-test Surefire OD/TD subset. These checks do not add an independent external dataset. The extension protocol was written after examination of main results, and its findings are labelled exploratory.

## Threats to validity

- **Selection:** available, attributable target failures may not represent all flaky tests or real CI traffic.
- **Class/project imbalance:** TD has only 10 tests; NIO has 3 projects and is highly concentrated in one repository.
- **Collector confounding:** source formats nearly identify categories; classification need not reflect failure semantics.
- **Residual identifiers:** the transformation is partial and does not guarantee de-identification.
- **Templates:** project separation does not eliminate similar diagnostic templates across projects. The duplicate audit reports normalised similarities.
- **Model dependence:** the smaller Linear SVC delta shows the main finding is not invariant to classifier choice.
- **Inference:** overlapping folds and limited rare-category coverage constrain interval interpretation.
- **Numerics:** predictions and coefficient bytes are different reproducibility targets; see the reproduction guide.
