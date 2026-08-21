"""Build the leakage-safe (student, skill) next-attempt modeling dataset.

Implements docs/data_quality_and_leakage.md sections 1-5. One output row per
valid training example (student, skill, attempt k>=2): target = correctness
of attempt k, features = aggregates over that pair's attempts 1..k-1 only,
plus same-row context columns that describe the problem (not its outcome)
and are therefore known before the attempt happens.
"""

import os

import numpy as np
import pandas as pd

RAW_PATH = "data/skill_builder_data.csv"
OUT_PATH = "data/processed/modeling_dataset.parquet"


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, encoding="latin-1", low_memory=False)
    df = df.dropna(subset=["skill_id"])
    df = df[(df["ms_first_response"] >= 0) & (df["overlap_time"] >= 0)]
    df["skill_id"] = df["skill_id"].astype(int)
    return df.sort_values(["user_id", "skill_id", "opportunity"]).reset_index(drop=True)


def build_skill_name_lookup(df: pd.DataFrame) -> pd.Series:
    # skill_id -> skill_name is a clean 1:1 mapping (confirmed in EDA); use it
    # instead of the same-row value, which can be null even when skill_id isn't.
    return df.dropna(subset=["skill_name"]).groupby("skill_id")["skill_name"].first()


def prior_sum(df: pd.DataFrame, series: pd.Series) -> pd.Series:
    """Sum of `series` over opportunity 1..k-1 within each (user_id, skill_id) group."""
    cum = series.groupby([df["user_id"], df["skill_id"]]).cumsum()
    return cum - series


def prior_mean(df: pd.DataFrame, series: pd.Series, n_prior: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        return prior_sum(df, series) / n_prior


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["user_id", "skill_id"], sort=False)
    n_prior = g.cumcount()

    log_ms = np.log1p(df["ms_first_response"])
    log_overlap = np.log1p(df["overlap_time"])
    hint_used = (df["hint_count"] > 0).astype(float)

    out = pd.DataFrame(
        {
            "user_id": df["user_id"],
            "skill_id": df["skill_id"],
            "opportunity": df["opportunity"],
            "n_prior_attempts": n_prior,
            "prior_correct_count": prior_sum(df, df["correct"]),
            "prior_correct_rate": prior_mean(df, df["correct"], n_prior),
            "prior_hint_count_mean": prior_mean(df, df["hint_count"], n_prior),
            "prior_attempt_count_mean": prior_mean(df, df["attempt_count"], n_prior),
            "prior_ms_first_response_mean": prior_mean(df, log_ms, n_prior),
            "prior_overlap_time_mean": prior_mean(df, log_overlap, n_prior),
            "prior_hint_used_rate": prior_mean(df, hint_used, n_prior),
            "original": df["original"],
            "answer_type": df["answer_type"],
            "tutor_mode": df["tutor_mode"],
            "target_correct": df["correct"],
        }
    )

    # keep only k>=2 (n_prior_attempts>=1) -- rows with no history can't be examples
    out = out[out["n_prior_attempts"] >= 1].copy()

    skill_name_lookup = build_skill_name_lookup(df)
    out.insert(2, "skill_name", out["skill_id"].map(skill_name_lookup))

    # split: last opportunity per (user_id, skill_id) group is test, rest is train
    is_last = out.groupby(["user_id", "skill_id"])["opportunity"].transform("max") == out["opportunity"]
    out["split"] = np.where(is_last, "test", "train")

    return out.reset_index(drop=True)


def main() -> None:
    raw = load_raw()
    features = build_features(raw)

    os.makedirs("data/processed", exist_ok=True)
    features.to_parquet(OUT_PATH, index=False)

    print(f"Wrote {len(features):,} rows to {OUT_PATH}")
    print(features["split"].value_counts())
    print("\nColumns:", list(features.columns))
    print("\nhead:")
    print(features.head())


if __name__ == "__main__":
    main()
