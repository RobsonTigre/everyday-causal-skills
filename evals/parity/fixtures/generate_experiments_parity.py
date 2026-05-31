"""Deterministic RCT fixture for the experiments parity check.

Run: python3 evals/parity/fixtures/generate_experiments_parity.py  (from repo root)

A completely-randomized two-arm experiment with three pre-treatment covariates
that are predictive of the outcome (so regression adjustment changes precision)
but balanced across arms (true random assignment). Treatment effect is constant
(tau) so the ATE is identified and equal for diff-in-means and Lin (2013)
regression adjustment in expectation.

Columns the recipes may use:
  treatment  binary 0/1 assignment (Bernoulli(0.5), independent of covariates)
  outcome    continuous response
  X1, X2, X3 pre-treatment covariates (predictive of outcome, balanced)
"""
import numpy as np
import pandas as pd

OUT = "evals/parity/fixtures/experiments_parity.csv"
SEED = 20260531
N = 2000
TAU = 2.0  # true constant ATE


def main():
    rng = np.random.default_rng(SEED)
    X1 = rng.normal(0.0, 1.0, N)
    X2 = rng.normal(0.0, 1.0, N)
    X3 = rng.binomial(1, 0.4, N).astype(float)
    # Independent Bernoulli(0.5) assignment => complete randomization, balanced.
    treatment = rng.binomial(1, 0.5, N).astype(int)
    # Outcome: covariates strongly predictive => adjustment cuts the SE.
    noise = rng.normal(0.0, 1.0, N)
    outcome = (5.0 + 1.5 * X1 - 1.0 * X2 + 2.0 * X3
               + TAU * treatment + noise)
    df = pd.DataFrame({
        "treatment": treatment,
        "outcome": outcome,
        "X1": X1,
        "X2": X2,
        "X3": X3,
    })
    df.to_csv(OUT, index=False)
    # Report ground truth and the two estimates for tolerance calibration.
    t = df.loc[df.treatment == 1, "outcome"]
    c = df.loc[df.treatment == 0, "outcome"]
    print(f"wrote {OUT}  N={len(df)}  TRUE_ATE={TAU}")
    print(f"diff-in-means={t.mean() - c.mean():.6f}  "
          f"n_treated={len(t)}  n_control={len(c)}")


if __name__ == "__main__":
    main()
