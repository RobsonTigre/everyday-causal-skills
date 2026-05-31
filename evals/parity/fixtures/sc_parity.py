"""Generate the deterministic shared fixture for the synthetic-control (sc) parity check.

Design goals (so R `Synth` and Python `scpi_pkg` converge to the SAME synthetic
control and therefore the same ATT):

* Balanced panel: 1 treated unit + 8 donor units, 20 periods (12 pre, 8 post).
* A two-factor model drives every unit's outcome. The treated unit's factor
  loadings are an exact convex combination (0.6 / 0.4) of two donors' loadings,
  so the synthetic-control optimum is well-identified and lies INSIDE the convex
  hull. This makes the simplex-constrained weight vector essentially unique, which
  is what lets two different SCM optimizers (Synth's nested V-optimization vs
  scpi's simplex QP) land on the same weights up to a tight tolerance.
* Pre-treatment noise is tiny (so pre-fit is near-perfect and RMSPE -> ~0); this
  removes optimizer-path ambiguity from the weights.
* A known additive treatment effect TRUE_ATT is added to the treated unit in every
  post period, so both recipes should recover ATT ~= TRUE_ATT.

Column contract (consumed by reference/sc.R and reference/sc.py):
    unit   : str   unit id ("treated", "donor_1" ... "donor_8")
    time   : int   1..20
    outcome: float
The treated unit id is "treated"; treatment starts at TREAT_TIME (period 13).
"""
import numpy as np
import pandas as pd

SEED = 20260530
N_DONORS = 8
N_PRE = 12
N_POST = 8
TREAT_TIME = N_PRE + 1          # first treated period (13)
N_PERIODS = N_PRE + N_POST      # 20
TRUE_ATT = 6.0
TREATED_ID = "treated"

OUT_CSV = __file__.replace("sc_parity.py", "sc_parity.csv")


def main():
    rng = np.random.default_rng(SEED)

    # Two common factors over time (smooth-ish trajectories), fixed (deterministic).
    t = np.arange(1, N_PERIODS + 1)
    f1 = 10.0 + 0.8 * t + 3.0 * np.sin(t / 2.0)
    f2 = 5.0 + np.cumsum(rng.normal(0.3, 0.4, N_PERIODS))

    # Donor loadings on the two factors + a donor-specific intercept.
    donor_load1 = rng.uniform(0.5, 1.5, N_DONORS)
    donor_load2 = rng.uniform(0.5, 1.5, N_DONORS)
    donor_intercept = rng.uniform(20.0, 40.0, N_DONORS)

    # Treated unit is an exact convex combination of donor 0 (0.6) and donor 1 (0.4).
    w_true = np.zeros(N_DONORS)
    w_true[0], w_true[1] = 0.6, 0.4
    treated_load1 = donor_load1 @ w_true
    treated_load2 = donor_load2 @ w_true
    treated_intercept = donor_intercept @ w_true

    rows = []

    # Donors. Small idiosyncratic noise everywhere.
    for j in range(N_DONORS):
        noise = rng.normal(0.0, 0.15, N_PERIODS)
        y = donor_intercept[j] + donor_load1[j] * f1 + donor_load2[j] * f2 + noise
        for ti, yi in zip(t, y):
            rows.append({"unit": f"donor_{j + 1}", "time": int(ti),
                         "outcome": round(float(yi), 4)})

    # Treated unit: same factor model with the convex-combination loadings, tiny
    # pre-period noise, plus the known additive effect in post periods.
    noise_tr = rng.normal(0.0, 0.05, N_PERIODS)
    y_tr = treated_intercept + treated_load1 * f1 + treated_load2 * f2 + noise_tr
    y_tr = y_tr + np.where(t >= TREAT_TIME, TRUE_ATT, 0.0)
    for ti, yi in zip(t, y_tr):
        rows.append({"unit": TREATED_ID, "time": int(ti),
                     "outcome": round(float(yi), 4)})

    df = pd.DataFrame(rows).sort_values(["unit", "time"]).reset_index(drop=True)
    df.to_csv(OUT_CSV, index=False)

    # Report ground truth for the spec author.
    print(f"wrote {OUT_CSV}")
    print(f"units={df['unit'].nunique()} periods={df['time'].nunique()} "
          f"rows={len(df)} TREAT_TIME={TREAT_TIME} TRUE_ATT={TRUE_ATT}")
    print(f"true donor weights: donor_1={w_true[0]}, donor_2={w_true[1]}")


if __name__ == "__main__":
    main()
