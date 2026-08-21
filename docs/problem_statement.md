
## **1. Problem statement**

This is a **binary sequence classification problem over time-ordered student-skill interactions**.

Given everything a student has done so far, predict whether their *next* attempt on a given skill will be correct or not. "Struggle" = predicted low probability of correct on next attempt.

("So far" = ordered by `opportunity`, the dataset's per-skill attempt counter — not wall-clock time. EDA confirmed `order_id` is genuinely non-chronological, and no timestamp column exists in this dataset. See Assumptions.)

**2. Inputs and outputs — exact, not vague**

- **Input**: one student's interaction history up to time *t*, plus the target skill they're about to attempt.
- **Output**: a probability between 0 and 1 — P(correct | history).
- **Not the output**: a recommendation of what to teach next. That's a downstream decision layer (compare the probability against a threshold, factor in the prerequisite graph).

**Target variable, exactly**: for a given (student, skill) pair with attempts ordered by `opportunity` = 1..n, each attempt *k* ≥ 2 is one training example — features are built only from attempts 1..*k*-1 of that pair (history), label is `correct` of attempt *k*. Pairs with n = 1 contribute zero training examples (no history to condition on). See `docs/data_quality_and_leakage.md` for the full construction and leakage rules.

**3. Unit of analysis**

**(student, skill)** — attempt-number is really the same axis, unrolled: each (student, skill) pair generates one training example per attempt ≥ 2, ordered by `opportunity` (see Target variable above). (student, skill) is the right *aggregation* unit because there's no knowledge graph or cross-skill signal in scope (`problem_statement.md` §4) — the model conditions only on a student's own history within that one skill, so grouping by (student, skill) is what naturally produces "history up to *k*-1 → predict *k*."

Caveat found in EDA (`notebooks/eda.ipynb`, Section 1): this unit is thinner than it looks — median 5 attempts per pair, but 20% of pairs have exactly 1 attempt (no history at all, contribute nothing) and the 25th percentile sits at 2 attempts. A student can look "warm" in aggregate (median 27 rows) while having only 1-2 prior attempts on the *specific* skill being predicted. This is a cold-start-like effect living inside the in-scope unit of analysis, not just at the new-student boundary named in §6.

**4. Out of scope**

- No deep sequence models (DKT/LSTM/Transformer-based KT) — baseline first. Build prove before reaching for complexity.
- No use of Bloomy's actual curriculum or knowledge graph — public dataset only.
- No claim of production-readiness — no latency SLAs, no drift monitoring, no retraining pipeline. This is a proof-of-concept for the *prediction task*, not an MLOps system.
- No personalization loop (adjusting the lesson path based on the prediction) — that's Bloomy's product layer, not this prototype's job.

**5. Success criteria**

- **Model metric**: **log loss** (primary) — matches the stated output (a probability, not a label) and rewards calibration, not just direction. **PR-AUC** on the minority "incorrect" class as a secondary/diagnostic metric, since accuracy is misleading here: EDA found a 68/32 class split, so a trivial "always predict correct" baseline already scores 67.95% accuracy for free. Precision/recall are deliberately *not* the model metric — both require picking a decision threshold, which §2 already scopes as a downstream decision layer, not part of this prediction task.
- **Project metric** (the one that actually matters for reciprocity): does the README clearly show a founder-legible chain of reasoning — problem → data → simplest defensible model → result → honest limitations → "here's the next step I'd take with your real knowledge graph." A 0.71 AUC with clear reasoning beats a 0.79 AUC with no narrative, because I'm being evaluated on judgment, not leaderboard performance.

**6. Assumptions**

- Assumes "struggle" ≈ "predicted incorrect" — acknowledge this is a simplification; real struggle might also mean *slow but eventually correct*, which my label doesn't capture. Naming what my proxy label fails to represent is a stronger signal than pretending the proxy is perfect.
- Assumes cold-start (a brand-new student with no history) is out of scope — flaged as a known limitation rather than quietly ignoring it.
- Assumes `opportunity` (not `order_id`, and not a real timestamp — none exists in this dataset) is a valid ordering signal within a (student, skill) pair. Verified in EDA: sorting by `order_id` preserves the correct `opportunity` order for 98.15% of pairs but breaks it for 1.85% (`order_id` ties can't resolve close-together events). Cross-skill temporal claims (e.g. "this happened before that, across skills") are not supportable from this data at all.
- Assumes columns describing the outcome of the attempt being predicted (`hint_count`, `attempt_count`, `ms_first_response`, `overlap_time`, `first_action`, `answer_id`, `answer_text`, `bottom_hint`) are never used as same-row features — only as aggregates over a pair's *prior* attempts (1..*k*-1). Using them same-row would leak the label. See `docs/data_quality_and_leakage.md`.

