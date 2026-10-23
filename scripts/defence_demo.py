"""Leave-One-Project-Out Cross-Validation Demonstration.

Trains and evaluates the baseline TF-IDF + Logistic Regression model
on a single held-out project fold (ActiveMQ) under original and identifier-masked
failure log conditions.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def load_json(file_path: Path):
    return json.loads(file_path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-reference-hashes", action="store_true")
    args = parser.parse_args()
    # Load configuration and baseline metadata
    config = load_json(ROOT / "config_model_v3.json")
    metrics = load_json(ROOT / "results/main_v3/metrics.json")

    # Load corpus records
    corpus_path = ROOT / "data/processed/corpus.jsonl"
    rows = sorted(
        [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines()],
        key=lambda r: r["sample_id"],
    )

    # Integrity verification
    corpus_hash = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    assert corpus_hash == metrics["corpus_sha256"], "Corpus hash mismatch"

    # Select demonstration case (ActiveMQ fold)
    changed_cases = sorted(
        load_json(ROOT / "results/main_v3/changed_predictions.json"),
        key=lambda r: r["sample_id"],
    )
    target_case = changed_cases[0]
    target_sample = next(r for r in rows if r["sample_id"] == target_case["sample_id"])

    # Split into training and held-out evaluation sets
    target_group = target_sample["project_group"]
    train_samples = [r for r in rows if r["project_group"] != target_group]
    test_samples = [r for r in rows if r["project_group"] == target_group]

    assert {r["project_group"] for r in train_samples}.isdisjoint(
        {r["project_group"] for r in test_samples}
    )
    repo = target_sample["canonical_repository"]
    test_id = target_sample["configured_test"]
    true_label = target_sample["label"]

    print("=" * 70)
    print("Leave-One-Project-Out Evaluation: Single Fold Demonstration")
    print("=" * 70)
    print(f"Corpus size:       {len(rows)} tests across {len({r['project_group'] for r in rows})} projects")
    print(f"Held-out project:  {repo}")
    print(f"Target test:       {test_id}")
    print(f"Ground truth:      {true_label}")
    print(
        f"Partition:         {len(train_samples)} train samples | "
        f"{len(test_samples)} test samples (Disjoint: True)"
    )

    print("\n[Original Failure Log Snippet]")
    print("\n".join(target_sample["original_text"].splitlines()[:6]))

    print("\n[Masked Failure Log Snippet]")
    print("\n".join(target_sample["masked_text"].splitlines()[:6]))

    fits = {
        (f["fold"], f["condition"]): f
        for f in load_json(ROOT / "results/main_v3/fits.json")
    }

    print("\n--- Model Training & Inference ---")
    with threadpool_limits(limits=1):
        for condition, text_field in [("original", "original_text"), ("masked", "masked_text")]:
            # Configure pipeline parameters
            vec_params = dict(config["vectorizer"])
            vec_params["ngram_range"] = tuple(vec_params["ngram_range"])

            pipeline = Pipeline([
                ("tfidf", TfidfVectorizer(**vec_params)),
                ("model", LogisticRegression(**config["classifier"])),
            ])

            # Train on remaining projects
            pipeline.fit(
                [r[text_field] for r in train_samples],
                [r["label"] for r in train_samples],
            )

            # Predict on the held-out sample
            prediction = str(pipeline.predict([target_sample[text_field]])[0])
            assert prediction == target_case["predictions"][condition]

            # Verify coefficient reproducibility
            coef_hash = hashlib.sha256(pipeline.named_steps["model"].coef_.tobytes()).hexdigest()
            hash_equal = coef_hash == fits[(target_case["fold"], condition)]["coef_sha256"]
            if args.strict_reference_hashes:
                assert hash_equal, "Coefficient bytes differ from the recorded reference environment"
            print(f"Reference coefficient bytes equal: {hash_equal}")

            vocab_size = len(pipeline.named_steps["tfidf"].vocabulary_)
            print(
                f"Condition: {condition:<8} | "
                f"Predicted: {prediction:<4} (Truth: {true_label}) | "
                f"Vocabulary size: {vocab_size:,} features"
            )

    print("=" * 70)
    print("Fold execution completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
