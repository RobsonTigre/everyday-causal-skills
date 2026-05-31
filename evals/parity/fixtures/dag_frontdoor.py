"""Deterministic fixture generator for the DAG parity recipe.

Builds a front-door / backdoor structural causal model:

    X -> D, X -> Y        (observed confounder, backdoor path D <- X -> Y)
    U -> D, U -> Y         (UNOBSERVED confounder; column U is included so a
                            recipe could verify it, but adjustment ignores it)
    D -> M -> Y            (full mediator: the entire causal effect of D flows
                            through M -- no direct D -> Y edge)

Properties exploited by the parity recipes:
  * Front-door estimate = (D -> M coef) * (M -> Y | D coef) recovers the total
    D -> Y effect = b_DM * b_MY even though U confounds D and Y.
  * Backdoor adjustment for X alone does NOT close the U path, so the naive
    backdoor OLS of Y ~ D + X is biased -- this is why front-door is the
    identified estimand here.

The generator is fully deterministic (fixed seed, no external state) so R and
Python read byte-identical data from the emitted CSV.

True parameters (see TRUE_* below):
    b_DM = 1.5    (D -> M)
    b_MY = 0.8    (M -> Y)
    Total front-door effect D -> Y via M = b_DM * b_MY = 1.20
"""
import numpy as np
import pandas as pd

SEED = 20260531
N = 5000

# Structural coefficients (ground truth).
B_XD = 0.7      # X -> D
B_UD = 0.9      # U -> D
B_DM = 1.5      # D -> M   (front-door stage 1)
B_MY = 0.8      # M -> Y   (front-door stage 2)
B_XY = 0.6      # X -> Y
B_UY = 1.1      # U -> Y   (unobserved confounding of D and Y)

TRUE_FRONTDOOR = B_DM * B_MY  # = 1.20


def generate(seed: int = SEED, n: int = N) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    X = rng.normal(0.0, 1.0, n)               # observed confounder
    U = rng.normal(0.0, 1.0, n)               # UNOBSERVED confounder
    D = B_XD * X + B_UD * U + rng.normal(0.0, 1.0, n)
    M = B_DM * D + rng.normal(0.0, 1.0, n)     # full mediator
    # Y depends on M (mediated D effect), X and U (confounders) -- NO direct D.
    Y = B_MY * M + B_XY * X + B_UY * U + rng.normal(0.0, 1.0, n)
    return pd.DataFrame({"D": D, "M": M, "Y": Y, "X": X, "U": U})


if __name__ == "__main__":
    import os
    df = generate()
    out = os.path.join(os.path.dirname(__file__), "dag_frontdoor.csv")
    df.to_csv(out, index=False)
    print(f"wrote {out}  rows={len(df)}  true_frontdoor={TRUE_FRONTDOOR:.4f}")
