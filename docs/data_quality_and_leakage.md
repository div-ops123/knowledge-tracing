# Data quality and leakage-safe modeling notes

Reference doc backing the decisions in `problem_statement.md`, with reasons. Source of truth for the *why*; `notebooks/eda.ipynb` is the source of truth for the numbers. All figures below come from that notebook's executed output — re-run it if the raw CSV ever changes.

## 1. Missing values — action per column

| Column | % missing | Mechanism (confirmed in EDA) | Action | Reason |
|---|---|---|---|---|
| `answer_id` | 90.74% | Only populated for `choose_1`/`choose_n` answer types (~97.5% populated there; ~100% null for `algebra`/`fill_in_1`/`open_response`) | Not used as a raw feature | Describes the outcome of the attempt being predicted — same-row leakage risk (§3), not a missingness problem |
| `answer_text` | 18.04% | Populated for `fill_in_1` (87.5%) and, contrary to the source schema's claim of "fill-in only," also for `algebra` (90.8%). Null for `choose_1`/`choose_n`/`open_response`. | Not used as a raw feature | Same as `answer_id` — describes the current attempt's outcome |
| `bottom_hint` | 84.80% | Null iff `hint_count == 0` (99.999% correspondence). Non-null values are exactly `{0., 1.}`. | Fill missing with `0` | "No hint requested" logically implies "did not request all hints" — a domain-justified fill, not a statistical imputation. Still same-row-leakage-restricted (§3) |
| `skill_name` | 14.97% | Co-occurs with `skill_id` nulls but is *not* identical to them: 12,364 rows have a valid `skill_id` with a missing `skill_name` label | Drop rows on **`skill_id`** null, never filter on `skill_name` | `skill_id` is the canonical key (verified 1:1 with `skill_name` where both are present — zero `skill_id`s map to more than one name). Filtering on `skill_name` would discard 12k usable rows for no reason |
| `opportunity_original` | 14.52% | Null if `original == 0` (scaffolding row) | Dropped along with `skill_id`-null rows | Scaffolding rows without an original-problem opportunity count aren't part of the (student, skill) sequence anyway |
| `skill_id` | 12.62% | Null for 65.9% of scaffolding rows (`original == 0`) **and** 3.6% of main-problem rows (`original == 1`) — not purely a scaffolding artifact | **Drop the row** | No skill tag → no target skill → the row can't serve as a training example under the (student, skill) unit of analysis. Not imputable — there's no sensible "average skill" |

General rule: none of this is missing-at-random. No mean/median/mode imputation anywhere in this dataset — every null here is either structural (governed by another column) or unusable for its intended role.

## 2. Rows dropped for format errors

- **Negative `ms_first_response` / `overlap_time`** (8 and 11 rows respectively, min -7,759,575 ms): physically impossible (timers can't run backward). Drop these rows. Negligible volume (0.0015%).
- **`skill_id` null** (66,326 rows, 12.62%): see §1. Drop.
- Everything else that looked anomalous on inspection turned out to be a legitimate state, not an error — kept, not dropped:
  - `attempt_count == 0` (22,153 rows): legitimate — a hint requested before any attempt. Don't treat 0 as "missing."
  - `hint_count > hint_total`: never occurs (0 rows) — invariant holds, no action needed.
  - `type` constant at `"MasterySection"` across all rows: not an error, just a zero-information column in this particular export. Drop the column (not rows) — it can't help any model.

## 3. Leakage guard — same-row outcome columns

**This is the most important rule in this document.** The prediction task is: given attempts 1..*k*-1 of a (student, skill) pair, predict `correct` of attempt *k*. Several columns describe **what happened during attempt *k* itself** — using them as same-row features would let the model see the outcome of the thing it's predicting.

Columns that must **only** be used as aggregates/lags over a pair's *prior* attempts (never same-row):
`hint_count`, `attempt_count`, `ms_first_response`, `overlap_time`, `first_action`, `answer_id`, `answer_text`, `bottom_hint`.

This isn't stated anywhere in `docs/data_schema.md` — it's a domain-knowledge deduction (standard temporal-leakage concern in knowledge tracing / any sequential-prediction setup) combined with reading each column's definition carefully: all eight describe properties **of the response event**, not properties known before the student attempted it. Example of the failure mode if ignored: `hint_count` on the row being predicted is a near-tautological predictor of `correct` on that same row (a hint was needed because the student was struggling on *that* attempt) — a model trained on it would look artificially strong and be useless once deployed, because at prediction time (before the attempt happens) `hint_count` for that attempt doesn't exist yet.

Correct usage: build historical aggregates instead, e.g. `mean(hint_count)` over attempts 1..*k*-1 of the same pair, `count(attempts so far)`, `rolling accuracy`, etc.

Related redundancy note: `ms_first_response` and `overlap_time` are highly correlated (r=0.946, 69.8% exactly equal) but not identical — `overlap_time` runs ahead of `ms_first_response` on multi-attempt rows. Both are subject to the same leakage restriction; once aggregated as historical features they'll likely be near-redundant, so check multicollinearity before keeping both.

## 4. Training data construction (no leakage)

1. Drop rows per §1/§2 (null `skill_id`, negative times).
2. Group by (`user_id`, `skill_id`); sort each group by `opportunity`.
3. For each group with n attempts, emit one training example per attempt *k* = 2..n:
   - **Label**: `correct` at `opportunity == k`.
   - **Features**: aggregates computed only from `opportunity` 1..*k*-1 in that same group (see §3 for which columns are eligible at all).
   - Groups with n = 1 emit zero examples — this is automatic from the construction, not a separate filtering step. (41,982 pairs → 417,226 valid history→next-attempt examples, per EDA.)
4. **Split**: chronological, not random-row and not fully-random-by-student.
   - Within each (student, skill) group, hold out the last attempt (or last ~20%) as test, train on the earlier portion — this directly matches "predict the next attempt given real prior history."
   - Never shuffle rows across the whole dataset before splitting — that leaks a pair's own future into its own past, and leaks one student's other rows across train/test.
   - Full unseen-student holdout is not required (cold-start is explicitly out of scope in `problem_statement.md` §6) but is a reasonable secondary diagnostic to check the model isn't just memorizing specific students.

## 5. Outliers

Right-skewed count/time columns (`ms_first_response`, `overlap_time`, `attempt_count`, `hint_count`) should **not** be trimmed with a blind IQR rule — on data this skewed, IQR flags a large share of legitimate high values (e.g. `attempt_count` of 20+ is very plausibly a genuinely struggling student, exactly the signal this project cares about). Preferred approach, in order of preference:
1. `log1p` transform on the aggregated historical features (compresses the tail without deleting rows).
2. Percentile-based winsorizing (e.g. cap at the 99th percentile) if log-transform alone isn't enough.
3. Only drop rows for genuine impossibilities (negative times, §2) — never drop rows just for being numerically extreme.

Plan: try `log1p` first, evaluate against the baseline model, only add winsorizing if it measurably helps. Don't decide this by inspection alone.

## 6. Encoding

- **Low cardinality** (`tutor_mode` [2], `original` [2], `first_action` [3], `answer_type` [5]): one-hot, no special handling needed. Checking their relationship with the target first is about *feature selection* (worth keeping at all), not about *how* to encode — one-hot is safe regardless.
- **`tutor_mode == "test"`** (333 rows, 0.06%): don't drop just for being rare. `test` shows a 75.1% correct rate vs. `tutor`'s 67.9% — a real-looking gap, but n=333 means any learned effect will be high-variance. One-hot it and let the model down-weight it naturally.
- **`skill_id`** (123 distinct, high cardinality) is the primary key for the modeling unit, not just a feature — use `skill_id`, not `skill_name` (redundant label, confirmed 1:1 in EDA). Naive one-hot is workable but sparse; consider target encoding with proper cross-validation, or rely on native categorical handling if using a tree-based model. Checking the relationship with the target first matters here specifically to pick the right encoding *method* (avoid target-encoding leakage), unlike the low-cardinality columns above.

## 7. Class imbalance and metric

`correct`: 67.95% / 32.05% (moderate, not severe). Trivial "always correct" baseline = 67.95% accuracy — accuracy is not a usable metric here.

- **Primary metric: log loss.** The stated deliverable (`problem_statement.md` §2) is a calibrated probability, not a label — log loss (or Brier score) is the proper scoring rule for that, and rewards confidence calibration, not just ranking.
- **Secondary/diagnostic: PR-AUC** on the "incorrect" class (not ROC-AUC — ROC-AUC can look deceptively good under imbalance when the minority class is the one that matters).
- **Not the metric: precision/recall.** Both require a decision threshold, and thresholding is explicitly a downstream decision layer (`problem_statement.md` §2), out of scope for the prediction task itself. Once a real intervention trade-off exists, recall on "incorrect" likely matters more than precision (missing a real struggler costs more than a false alarm) — but that's a business call to make explicitly later, not to bake into the model metric now.
- **Imbalance remedy**: class weighting (`class_weight="balanced"` / `scale_pos_weight`) preferred over resampling (SMOTE etc.) — the imbalance is moderate, not severe, so synthetic resampling is unlikely to be worth its added complexity/risk.

## 8. Open items (documented, not yet resolved)

- `first_action` has an undocumented third value (`2`, 8,688 rows / 1.7%) beyond the schema's documented "attempt" (0) / "hint" (1). Treat as unknown/other category rather than guessing its meaning.
- `assistment_id` is undocumented by the source site but now empirically understood: 1-to-many with `problem_id` (every `problem_id` belongs to exactly one `assistment_id`; 2,990 `assistment_id`s span multiple `problem_id`s — likely a main problem plus its scaffolding steps grouped under one assistment).

---

# Feature table design

Per (`user_id`, `skill_id`) group, sorted by `opportunity`, for each target attempt k = 2..n:

**Target**: `target_correct` = `correct` at `opportunity == k`

**Identifiers** (kept for traceability, not necessarily model inputs): `user_id`, `skill_id`, `skill_name` (via a global `skill_id → skill_name` lookup, since EDA confirmed this is a clean 1:1 mapping — don't pick a possibly-null same-row value), `opportunity` (=k)

**Same-row, safe** (properties of the problem/context, known *before* the attempt happens — not outcome data, so not subject to the §3 leakage rule): `original`, `answer_type`, `tutor_mode`, all taken from the target row (k)

**Historical aggregates** (computed only from rows with `opportunity` 1..k-1 in the same group):
- `n_prior_attempts` (= k-1)
- `prior_correct_count`, `prior_correct_rate`
- `prior_hint_count_mean`
- `prior_attempt_count_mean`
- `prior_ms_first_response_mean` (on `log1p`-transformed values, per §5)
- `prior_overlap_time_mean` (on `log1p`-transformed values, per §5)
- `prior_hint_used_rate` (fraction of prior attempts with `hint_count > 0`)

**Split**: `split` column = `"test"` for the last attempt (max `opportunity`) in each group, `"train"` for everything else — per §4's chronological holdout rule. (Expected: 33,603 test rows [groups with n≥2], 383,623 train rows, 417,226 total — matches EDA's 417,226 valid-example figure.)

`data/processed/modeling_dataset.parquet` — 417,216 rows (383,613 train / 33,603 test), 17 columns. That's 10 fewer rows are skill-tagged rows with negative timestamps.