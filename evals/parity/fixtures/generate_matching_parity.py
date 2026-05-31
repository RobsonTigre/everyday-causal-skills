"""Deterministic fixture generator for the matching parity check.

Selection-on-observables DGP with good propensity overlap so that IPW and AIPW
recover the true effect and agree across R and Python. Writes a CSV with a fixed
seed; regenerating reproduces byte-identical numbers.

Schema: treatment (0/1), x1, x2, x3 (pre-treatment covariates), outcome.
True ATE = ATT = 2.0 (homogeneous additive effect).
"""
import numpy as np
import pandas as pd

SEED = 20260530
N = 1200
TRUE_EFFECT = 2.0
OUT_PATH = "evals/parity/fixtures/matching_parity.csv"


def main() -> None:
    rng = np.random.default_rng(SEED)

    # Pre-treatment covariates (standardized-ish, continuous so logistic PS is smooth)
    x1 = rng.normal(0.0, 1.0, N)
    x2 = rng.normal(0.0, 1.0, N)
    x3 = rng.normal(0.0, 1.0, N)

    # Propensity: moderate selection -> good overlap (coeffs kept small)
    logit = -0.20 + 0.60 * x1 - 0.40 * x2 + 0.30 * x3
    pscore = 1.0 / (1.0 + np.exp(-logit))
    treatment = (rng.uniform(size=N) < pscore).astype(int)

    # Outcome: confounders enter linearly; homogeneous treatment effect = TRUE_EFFECT
    outcome = (
        1.0
        + 1.5 * x1
        + 1.0 * x2
        - 0.5 * x3
        + TRUE_EFFECT * treatment
        + rng.normal(0.0, 1.0, N)
    )

    df = pd.DataFrame(
        {
            "treatment": treatment,
            "x1": np.round(x1, 6),
            "x2": np.round(x2, 6),
            "x3": np.round(x3, 6),
            "outcome": np.round(outcome, 6),
        }
    )
    df.to_csv(OUT_PATH, index=False)
    print(
        f"wrote {OUT_PATH}: n={N}, treated={int(treatment.sum())}, "
        f"control={int(N - treatment.sum())}, true_effect={TRUE_EFFECT}, "
        f"ps_range=[{pscore.min():.3f},{pscore.max():.3f}]"
    )


if __name__ == "__main__":
    main()
