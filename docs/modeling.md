# Modeling notes: baseline experimentation

Reference doc for `notebooks/baseline_model.ipynb`, covering *why* the model choices were made the way they were. Source of truth for the numbers: the notebook's own executed output and `results/metrics.json`.

## 1. Finalized feature set

Feature selection was done in `notebooks/feature_relationships.ipynb` (correlation, VIF, decile, skill-heterogeneity, and history-thinness analysis on `data/processed/modeling_dataset.parquet`, train split only). This table is the result, plus one feature added afterward.

| Column | Decision | Reason |
|---|---|---|
| `prior_correct_rate` | Keep | Dominant predictor (r=0.437, monotonic 37.5%→90.3% across deciles, holds within individual skills — not a pooling artifact). |
| `n_prior_attempts` | Keep | Weak alone (r=0.056) but low VIF (not redundant); also the reliability signal behind `prior_correct_rate` (history-thinness finding, §7 of feature_relationships.ipynb). |
| `prior_hint_used_rate` | Keep | Second-strongest signal (r=-0.338). Chosen over `prior_hint_count_mean` (r=-0.331, near-identical) — the two were redundant (VIF 8.4/7.6), pick one. |
| `prior_hint_count_mean` | **Drop** | Redundant with `prior_hint_used_rate` (see above). |
| `prior_attempt_count_mean` | Keep | Weak alone (r=-0.055) but low VIF (1.03) — not costing multicollinearity, harmless to keep for a regularized linear model. |
| `prior_correct_count` | **Drop** | VIF 15.4 — mechanically `prior_correct_rate` × `n_prior_attempts`, carries no information beyond what those two already capture together. |
| `prior_ms_first_response_mean` | **Drop** | Near-zero correlation with target (r=0.019). |
| `prior_overlap_time_mean` | **Drop** | Weak (r=-0.080) and redundant with `prior_ms_first_response_mean` (VIF 5.7/6.1, r=0.946 at the raw level). Chose to drop both rather than keep either. |
| `original`, `answer_type`, `tutor_mode` | Keep (one-hot) | Real, modest categorical effects on target correct-rate; safe same-row features (properties of the problem, not its outcome — `docs/data_quality_and_leakage.md` §3). |
| `skill_base_rate` (new) | Keep | Per-`skill_id` mean `target_correct`, computed only from train rows, joined onto train and test by `skill_id` (unseen test skills fall back to the overall train mean). Added *after* feature_relationships.ipynb — Section 6 (skill-level heterogeneity check) found that `prior_correct_rate`'s relationship with the target holds within every individual skill (not a Simpson's-paradox artifact), but the *ceiling* differs meaningfully by skill (e.g. 79.1% vs. 96.0% at the top `prior_correct_rate` bin across the four highest-volume skills) — evidence of a per-skill difficulty offset that `prior_correct_rate` alone doesn't capture. |
| `skill_id` (raw) | Not used as a feature | Superseded by `skill_base_rate`. Using the raw 123-category id would force an encoding-method decision (sparse one-hot vs. leakage-prone target encoding) into the very first model; `skill_base_rate` gets the same difficulty-offset signal in one leakage-safe numeric column instead. |
| `user_id`, `skill_name`, `opportunity` | Identifiers only | Not used as model inputs — `user_id` would let the model memorize specific students; `skill_name`/`opportunity` are display/traceability columns, not predictive signal. |

## 2. Model choice

**Model 0 — floor, no fitting**: predict `p = prior_correct_rate` directly. The cheapest possible baseline, using the single strongest known feature with zero modeling effort. Its job is to be the number any real model has to beat — if a fitted model can't clear this, that's a real finding, not a failure to hide.

**Model 1 — logistic regression**: the first fitted model, chosen ahead of a tree-based model for three reasons:
1. It directly optimizes log loss — the project's primary metric (`docs/problem_statement.md` §5) — so there's no mismatch between the training objective and what the model is graded on.
2. Coefficients are directly interpretable, which matches the project's own success criterion of founder-legible reasoning over raw leaderboard performance.
3. `feature_relationships.ipynb`'s decile plots showed roughly monotonic feature-target relationships — the shape logistic regression is suited to. There was no evidence yet of the kind of non-linearity or interaction effects that would justify reaching for a tree model first.

Gradient-boosted trees (LightGBM/XGBoost) are the natural next comparison — they'd use `skill_id` natively instead of needing `skill_base_rate`, and can capture non-linear/interaction effects LR can't — but are deliberately not attempted yet, per `docs/problem_statement.md` §4 ("baseline first, build prove before reaching for complexity").

## 3. Why no `class_weight="balanced"`

`docs/data_quality_and_leakage.md` §7 named class weighting as the preferred imbalance remedy, as a generic statement written before log loss was locked in as the primary metric. That guidance is refined here: class weighting reweights the loss to push the decision boundary toward the minority class, which improves threshold-based metrics (precision/recall) but *distorts fitted probabilities away from the true base rate* — actively hurting log loss, a calibration-sensitive proper scoring rule. The class split here (68/32) is moderate, not severe, so there's no case for accepting worse calibration to fix an imbalance that isn't extreme. The baseline logistic regression uses default `sklearn` weighting (i.e. none).

## 4. Why no hyperparameter tuning yet

The logistic regression uses `sklearn` defaults (`C=1.0`, `max_iter=1000` to ensure convergence). Tuning regularization strength is deferred until after the floor-vs-fit comparison itself is established — tuning a model before confirming it beats the trivial baseline would be solving the wrong problem first.

## 5. Why no MLflow

Considered and rejected for this scope. MLflow (or similar tracking infra) earns its keep with many runs — hyperparameter sweeps, multiple models, a team needing a shared dashboard. This project has ~2-3 runs total (floor, logistic regression, eventually a GBT comparison). Standing up a tracking server/UI for that few runs adds infrastructure weight a reviewer has to understand without adding signal, and is *less* legible to someone skimming the repo than a small JSON file they can open directly.

Instead: `notebooks/baseline_model.ipynb` writes each run's config and metrics to `results/metrics.json` via a `log_run()` helper, and reads it back via `load_runs()` to build the in-notebook comparison table. This is intentionally the whole tracking system — see below for its format.

If this project ever needs real sweeps (e.g. tuning a GBT over many hyperparameter combinations), that's the point where MLflow/W&B would start paying for itself — worth naming as a forward-looking note, not worth building now.

## 6. `results/metrics.json` format

A flat JSON array of run records. Each entry:

```json
{
  "name": "<unique experiment name — log_run() upserts by this key>",
  "timestamp": "<UTC ISO 8601, set automatically>",
  "features": ["<feature names used>"],
  "params": {"<model hyperparameters, if any>": "..."},
  "train_logloss": 0.0,
  "test_logloss": 0.0,
  "train_pr_auc": 0.0,
  "test_pr_auc": 0.0,
  "notes": "<one-line description of what this run is / why>"
}
```

To add a new experiment (e.g. a GBT run), call the same `log_run(name, feature_list, params, metrics, notes)` helper defined in `notebooks/baseline_model.ipynb` with a new, unique `name` — re-running an existing name overwrites that run's own record rather than duplicating it, so the file always reflects the latest state of each named experiment. `load_runs()` reads the whole file back into a DataFrame for comparison.
