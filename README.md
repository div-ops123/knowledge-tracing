# Bloomy Knowledge Tracing Prototype

A leakage-safe baseline that predicts whether a student's next attempt on a skill will be correct, built on the public ASSISTments 2009–2010 dataset — a first, provable pass at Bloomy's stated next frontier: predicting where students are about to struggle.

## What this is, and what it isn't

Bloomy's own stated next frontier is cross-skill and knowledge-graph-aware: predicting that a student is about to struggle on a skill they haven't formally hit yet, using how skills connect to each other.

This prototype proves a narrower, provable piece of that: given a student's own practice history on **one** skill, can a model estimate whether their next attempt on that **same** skill will be correct? That's a real, working primitive — not the whole answer.

Closing the gap to Bloomy's actual ask would need cross-skill interaction data and the knowledge graph structure itself — neither exists in this public dataset, so this project doesn't attempt to fake it. This is the honest, working scope of what a single public benchmark can prove.

## Repo map

| Path | What's in it |
|---|---|
| `docs/problem_statement.md` | The exact question being predicted, scope, and assumptions |
| `docs/data_schema.md` | Column-by-column description of the source dataset |
| `notebooks/eda.ipynb` | Initial exploratory data analysis — data types, missingness, duplicates, whether the data actually supports a time-ordered history |
| `docs/data_quality_and_leakage.md` | Data quality findings and the leakage rules used to build the modeling dataset |
| `scripts/build_modeling_dataset.py` | Builds the leakage-safe modeling dataset from raw data |
| `notebooks/feature_relationships.ipynb` | Feature selection — correlation, VIF, decile, and skill-heterogeneity analysis |
| `notebooks/baseline_model.ipynb` | The two baseline models (floor + logistic regression), trained and evaluated |
| `docs/modeling.md` | Reasoning behind the model choices, metric choices, and experiment-logging setup |
| `results/metrics.json` | Logged metrics for every run |

## Results

Two models, both evaluated on a held-out last-attempt-per-skill test split:

| Model | Train log loss | Test log loss | Train PR-AUC | Test PR-AUC |
|---|---|---|---|---|
| Floor (`p = prior_correct_rate`, no fitting) | 2.38 | 1.96 | 0.58 | 0.53 |
| Logistic regression | 0.51 | 0.42 | 0.61 | 0.53 |

The floor's log loss is bad because a student's raw recent success rate is exactly 0 or 1 whenever they've only tried a skill once or twice — an overconfident number, not a calibrated one. The logistic regression cuts log loss by roughly 4.5x by learning to blend that rate with other signals (skill difficulty, attempt count, hint use) instead of trusting it outright. PR-AUC — a ranking metric, not a calibration one — barely moves between the two, meaning the raw rate was already ranking students in roughly the right order; fitting a model mainly fixes *trustworthiness* of the number, not the ordering. Full reasoning in `docs/modeling.md`.

## Business interpretation

Bloomy's own goal is to move from tracking what a student has done, to predicting where they are about to struggle — so a teacher can step in before the student gets stuck. This prototype tests the simplest version of that idea: given a student's own practice history on a skill, can we guess if their next try will be right or wrong?

Two questions matter here, and they have different answers.

**1. Can we use this to know who needs help first?**

Yes, and it's better than guessing. If you sorted every student's next practice problem by "most likely to go wrong," the students who really are about to struggle would show up nearer the top more often than random chance. It's not perfect — it will still miss some struggling students and flag some who are actually fine — but it's a real, useful head start for deciding where to look first.

**2. Can we trust the exact number it gives, like "80% chance you'll get this right"?**

This is where it gets more interesting. The simplest way to guess is to just use the student's own recent success rate on that skill. But that has a cold-start problem: a student who has only tried a skill once looks either 100% or 0% — even though one try tells you almost nothing. If Bloomy showed that number to a teacher or used it to skip a lesson, it would be confidently wrong exactly for new students — the ones the product most needs to get right, since every student is new to a skill at some point.

The fitted model fixes this, at least partly. Instead of trusting one student's own recent score alone, it also looks at how hard that skill usually is for students in general, and how many times the student has actually practiced it. That way, a brand-new student isn't judged off one lucky or unlucky try — the model leans more on general patterns until it has enough of that student's own history to trust. The result: a confidence number that's much closer to being true, even if still not perfect.

**Bottom line**

This prototype shows the underlying idea works: a student's own practice history carries a real, usable signal about what happens next. That's good enough today to build a "check on these students first" list. It's not yet good enough to hand a teacher or parent a bare percentage and have them trust it fully, or to let the product make big decisions on its own — especially for brand-new students, who are always going to be the hardest case. That gap — and closing it — is exactly the kind of "moving from tracking to predicting" work Bloomy says is its next frontier.

## How to run it

Standard Python setup, no special tooling required:

```
python -m venv .venv
.venv\Scripts\activate      # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```

Then open and run the notebooks in order: `notebooks/eda.ipynb` → `notebooks/feature_relationships.ipynb` → `notebooks/baseline_model.ipynb`.

If you use [uv](https://docs.astral.sh/uv/), `uv sync` followed by `uv run jupyter lab` works too — `requirements.txt` is exported from the same `pyproject.toml`/`uv.lock` the project actually uses, so either path installs the same dependencies.

## Next steps

- **Gradient-boosted trees** (LightGBM/XGBoost) as a complexity comparison — could use raw `skill_id` natively and may capture non-linear/interaction effects logistic regression can't.
- **Hyperparameter tuning** of the logistic regression — skipped here in favor of establishing the floor-vs-fit comparison first.
- **A shrunk/smoothed `prior_correct_rate`** for thin-history rows (a Bayesian average toward `skill_base_rate`, weighted by `n_prior_attempts`) — targets the exact failure mode the floor model exposed.
- The cross-skill, knowledge-graph-aware version of this problem, which is Bloomy's actual ask — this prototype is scoped to prove the within-skill primitive works, not to attempt the full version without the data or graph structure to do it honestly.
