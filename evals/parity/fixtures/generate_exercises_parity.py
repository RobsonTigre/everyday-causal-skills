"""Generate the shared parity fixture for the `exercises` (DGP-generation) method.

The exercises skill does NOT estimate an effect from a fixed dataset — it
*generates* a dataset from a data-generating process (DGP) whose true effect is
known, so a student can later check their work. The R<->Python parity contract
for this method is therefore different from the other methods:

  * The two language generators must declare the SAME known ground truth
    (deterministic; must match exactly).
  * Given the SAME DGP specification (structural equations + coefficients +
    seed), each generator draws its own data with its language-native RNG and
    the appropriate naive estimator must recover the SAME effect within
    Monte-Carlo sampling error.

So the "fixture" here is not a dataset but the DGP *specification* itself: a
one-row CSV of the parameters that BOTH `exercises.R` and `exercises.py` read as
`df` and then use to generate their own data. This mirrors DGP-03 (Classic 2x2
DiD, true ATT = 5.0) from references/dgp-library.md — the simplest DGP with a
clean known effect and a trivially correct cross-language estimator (the 2x2
means-of-means), so recovery is robust and the comparison isolates DGP-spec
parity rather than estimator differences.
"""
import os

import pandas as pd

# DGP-03 specification (single source of truth for both language recipes).
SPEC = {
    "dgp_id": "DGP-03",          # Classic 2x2 DiD from references/dgp-library.md
    "seed": 303,
    "n_stores": 100,
    "n_months": 24,
    "treat_month": 13,
    "true_att": 5.0,             # known ground truth the exercise must recover
    "base": 50.0,
    "store_fe_sd": 3.0,
    "time_trend": 0.2,
    "noise_sd": 2.0,
}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exercises_parity.csv")


def main():
    pd.DataFrame([SPEC]).to_csv(OUT, index=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
