"""Deterministic IV fixture generator for the R<->Python parity machine.

Writes evals/parity/fixtures/iv_parity.csv. The CSV is the shared, committed,
language-agnostic source of truth (both recipes read the same bytes), so the
generator only needs to run once; re-running with the same seed reproduces it.

DGP (single endogenous regressor, one excluded instrument, one exogenous
control), built so the true structural coefficient on `endogenous` is known:

    instrument  z  ~ N(0, 1)                         (as-if random)
    control     x  ~ N(0, 1)                         (exogenous)
    error       u  ~ N(0, 1)                         (structural, confounds d & y)
    endogenous  d  = 0.9*z + 0.5*x + 0.7*u + 0.5*e_d   (strong first stage)
    outcome     y  = BETA*d + 0.4*x + u + 0.5*e_y      (BETA is the true effect)

Because d is correlated with u (via the 0.7*u term) and u also enters y, OLS of
y on d is biased upward; 2SLS using z recovers BETA. The first stage is strong
by construction (effective/partial F well above any weak-IV threshold).
"""
import numpy as np
import pandas as pd

SEED = 20260530
N = 600
BETA = 1.5  # true causal effect of `endogenous` on `outcome`


def make_fixture(seed: int = SEED, n: int = N, beta: float = BETA) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)            # excluded instrument (as-if random)
    x = rng.normal(size=n)            # exogenous control
    u = rng.normal(size=n)            # structural error (confounder of d and y)
    e_d = rng.normal(size=n)
    e_y = rng.normal(size=n)
    d = 0.9 * z + 0.5 * x + 0.7 * u + 0.5 * e_d
    y = beta * d + 0.4 * x + u + 0.5 * e_y
    # cluster id (for clustered-SE capability checks; 30 clusters)
    cluster = rng.integers(0, 30, size=n)
    return pd.DataFrame({
        "outcome": y,
        "endogenous": d,
        "instrument": z,
        "control": x,
        "cluster": cluster,
    })


if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "..", "parity",
                       "fixtures", "iv_parity.csv")
    out = os.path.abspath(out)
    df = make_fixture()
    df.to_csv(out, index=False)
    print(f"wrote {out}  (n={len(df)}, true BETA={BETA})")
