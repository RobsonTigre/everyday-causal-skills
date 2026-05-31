"""Deterministic single-series ITS fixture for the timeseries parity check.

Run: python3 evals/parity/fixtures/generate_timeseries_parity.py  (from repo root)

A single interrupted time series with a known immediate LEVEL shift and a known
post-intervention TREND change, plus mild AR(1) noise. The point estimands are
recovered identically by least-squares segmented regression in both languages
(R `lm` and Python `statsmodels.ols`), which is the runnable numerical-parity
probe. (The templates' recommended BSTS estimators -- R `CausalImpact`, Python
`causalimpact` -- are NOT cross-comparable here: the Python BSTS port does not
import under the project interpreter, so the only runnable shared estimator is
the classical segmented-regression ITS.)

Columns the recipes may use:
  time        1-based integer time index (linear pre-trend)
  outcome     continuous response
  post        0 before the intervention, 1 from the intervention onward
  time_since  0 pre-intervention; periods since intervention post-intervention
"""
import numpy as np
import pandas as pd

OUT = "evals/parity/fixtures/timeseries_parity.csv"
SEED = 20260530
N_PRE = 60          # pre-intervention periods (>= 50: adequate per assumptions doc)
N_POST = 36         # post-intervention periods
INTERCEPT = 100.0
SLOPE = 0.5         # pre-intervention linear trend per period
LEVEL_SHIFT = 8.0   # true immediate level change at the intervention
TREND_CHANGE = 0.3  # true change in slope after the intervention
AR_RHO = 0.4        # AR(1) coefficient on the noise
NOISE_SD = 1.0


def main():
    rng = np.random.default_rng(SEED)
    total = N_PRE + N_POST
    t = np.arange(total)
    post = (t >= N_PRE).astype(int)
    time_since = np.where(post == 1, t - N_PRE, 0)

    # AR(1) noise from a fixed-seed innovation stream -> fully reproducible.
    eps = rng.normal(0.0, NOISE_SD, total)
    ar = np.zeros(total)
    for i in range(1, total):
        ar[i] = AR_RHO * ar[i - 1] + eps[i]

    outcome = (INTERCEPT + SLOPE * t
               + LEVEL_SHIFT * post + TREND_CHANGE * time_since + ar)

    df = pd.DataFrame({
        "time": t + 1,
        "outcome": np.round(outcome, 4),
        "post": post,
        "time_since": time_since,
    })
    df.to_csv(OUT, index=False)

    # Report ground truth and recovered estimates for tolerance calibration.
    import statsmodels.formula.api as smf
    m = smf.ols("outcome ~ time + post + time_since", data=df).fit()
    print(f"wrote {OUT}  N={len(df)}  N_PRE={N_PRE}  N_POST={N_POST}")
    print(f"TRUE_LEVEL={LEVEL_SHIFT}  TRUE_TREND={TREND_CHANGE}")
    print(f"est_LEVEL={m.params['post']:.6f}  est_TREND={m.params['time_since']:.6f}")


if __name__ == "__main__":
    main()
