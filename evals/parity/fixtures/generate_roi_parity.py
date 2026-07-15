"""Deterministic fixture for the roi parity check.

Run: python3 evals/parity/fixtures/generate_roi_parity.py  (from repo root)

The ROI pipeline is closed-form arithmetic (no estimation), so the parity probe
feeds one fully-specified input set through every pipeline term — varying
eligible population, a rollout ramp, persistence, survival, discounting,
transport and net-incrementality haircuts, recurring costs — and compares the
eight canonical estimands plus the verdict code across R and Python.

Layout: one row per period (t = 0..HORIZON-1) with the per-period columns
(n_eligible, rollout, recurring); scalar inputs are constant columns read from
the first row by the recipes. No randomness — values are chosen to tie back to
the book's personalized-feed example (revenue effect 3.90 x margin 0.60 =
profit 2.34/user/month, CI [1.75, 2.93]).
"""
import numpy as np
import pandas as pd

OUT = "evals/parity/fixtures/roi_parity.csv"
HORIZON = 12

# Scalars (constant columns).
SCALARS = {
    "effect_raw": 3.90,          # revenue per user per month (pre-normalization)
    "ci_lo_raw": 2.9166666667,   # x margin -> 1.75 (book CI lower bound, profit terms)
    "ci_hi_raw": 4.8833333333,   # x margin -> 2.93
    "margin": 0.60,              # normalization: revenue -> profit
    "scaling_factor": 1.0,       # estimand scaling (1.0: ATE, full population)
    "persistence": 0.90,         # lambda
    "survival": 0.97,
    "discount": 0.01,
    "transport": 0.95,
    "net_incrementality": 0.97,
    "one_time": 4e6,
    "hurdle": 0.0,
    "margin_buffer": 2.0,
}


def main():
    t = np.arange(HORIZON)
    df = pd.DataFrame({
        "t": t,
        "n_eligible": 5_000_000 + 25_000 * t,          # growing eligible base
        "rollout": np.minimum(1.0, 0.25 * (t + 1)),    # ramp: .25 .50 .75 then 1
        "recurring": np.full(HORIZON, 1e5),            # per-period maintenance
    })
    for k, v in SCALARS.items():
        df[k] = v
    df.to_csv(OUT, index=False)

    # Report the pipeline outputs for tolerance calibration (not the oracle —
    # hand-derived expectations live in evals/parity/test_roi_known_answers.py).
    s = SCALARS
    w = s["persistence"]**t * s["survival"]**t / (1 + s["discount"])**t
    m = float((df["n_eligible"] * s["scaling_factor"] * df["rollout"] * w).sum()) \
        * s["transport"] * s["net_incrementality"]
    dp0 = s["effect_raw"] * s["margin"]
    inv = s["one_time"] + float((df["recurring"] / (1 + s["discount"])**t).sum())
    print(f"wrote {OUT}  HORIZON={HORIZON}")
    print(f"EFFECTIVE_PERIODS={w.sum():.10f}  M={m:.4f}")
    print(f"PV={dp0 * m:.4f}  INV={inv:.4f}  ROI={(dp0 * m - inv) / inv:.6f}")
    print(f"BREAKEVEN={inv / m:.8f}")


if __name__ == "__main__":
    main()
