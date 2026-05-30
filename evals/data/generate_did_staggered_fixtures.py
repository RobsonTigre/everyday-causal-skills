"""Deterministic staggered-DiD fixtures for causal-did evals.

Run: python3 evals/data/generate_did_staggered_fixtures.py   (from repo root)

Writes 4 CSVs with ONLY the columns the model is allowed to see
(unit, time, outcome, first_treat [, X]) and prints each fixture's
ground-truth ATT for pasting into the eval YAMLs.
"""
import numpy as np
import pandas as pd
from diff_diff import generate_staggered_data

OUT = "evals/data"
KEEP = ["unit", "time", "outcome", "first_treat"]


def _true_att(df_full):
    """ATT on the treated = mean of per-row true_effect over treated post-rows."""
    m = (df_full["first_treat"] != 0) & (df_full["time"] >= df_full["first_treat"])
    return float(df_full.loc[m, "true_effect"].mean())


def _from_generator(seed, treatment_effect, dynamic, never_frac, cohorts, n_units, n_periods,
                    effect_growth=0.1):
    df = generate_staggered_data(
        n_units=n_units, n_periods=n_periods, cohort_periods=cohorts,
        never_treated_frac=never_frac, treatment_effect=treatment_effect,
        dynamic_effects=dynamic, effect_growth=effect_growth, seed=seed,
    )
    df = df.rename(columns={"period": "time"})
    att = _true_att(df)
    return df[KEEP].copy(), att


def make_smoke():
    # Homogeneous effect -> true ATT == treatment_effect exactly.
    df, att = _from_generator(seed=42, treatment_effect=5.0, dynamic=False,
                              never_frac=0.35, cohorts=[3, 5], n_units=200, n_periods=8)
    df.to_csv(f"{OUT}/did_staggered_smoke.csv", index=False)
    return "did_staggered_smoke", att


def make_dynamic():
    # Growing effect -> manual TWFE loop is biased; true ATT must be derived.
    df, att = _from_generator(seed=123, treatment_effect=5.0, dynamic=True,
                              never_frac=0.30, cohorts=[4, 7], n_units=300, n_periods=10,
                              effect_growth=0.4)
    df.to_csv(f"{OUT}/did_staggered_dynamic.csv", index=False)
    return "did_staggered_dynamic", att


def make_notyet():
    # No never-treated units -> never_treated control group is impossible.
    df, att = _from_generator(seed=7, treatment_effect=5.0, dynamic=False,
                              never_frac=0.0, cohorts=[3, 5, 7], n_units=300, n_periods=9)
    assert (df["first_treat"] == 0).sum() == 0, "notyet fixture must have NO never-treated units"
    df.to_csv(f"{OUT}/did_staggered_notyet.csv", index=False)
    return "did_staggered_notyet", att


def make_covariates(seed=7):
    # Conditional parallel trends: a covariate X drives a differential time trend
    # AND treatment timing -> unconditional CS is biased; covariates=["X"] recovers tau.
    rng = np.random.default_rng(seed)
    n_units, n_periods, tau, trend_by_x = 250, 8, 4.0, 1.2
    X = rng.normal(0, 1, n_units)
    # Weak X->timing coupling (extra noise) keeps cohorts overlapping in X, so the
    # propensity model has good overlap and the doubly-robust adjustment is reliable.
    # The larger trend_by_x keeps the UNCONDITIONAL estimate clearly biased.
    u = 0.7 * X + rng.normal(0, 1.2, n_units)
    first_treat = np.where(u > 0.7, 3, np.where(u > -0.5, 5, 0))  # 0 = never treated
    unit_fe = rng.normal(0, 1.0, n_units)
    rows = []
    for i in range(n_units):
        g = int(first_treat[i])
        for t in range(n_periods):
            treated_post = 1 if (g != 0 and t >= g) else 0
            y = (unit_fe[i] + 0.2 * t + trend_by_x * X[i] * t
                 + tau * treated_post + rng.normal(0, 0.3))
            rows.append({"unit": i, "time": t, "outcome": y, "first_treat": g, "X": X[i]})
    df = pd.DataFrame(rows)
    assert (df["first_treat"] == 0).sum() > 0, "covariates fixture needs never-treated controls"
    df[["unit", "time", "outcome", "first_treat", "X"]].to_csv(
        f"{OUT}/did_staggered_covariates.csv", index=False)
    return "did_staggered_covariates", tau


if __name__ == "__main__":
    for name, att in [make_smoke(), make_dynamic(), make_notyet(), make_covariates()]:
        print(f"{name:<28} TRUE_ATT={att:.4f}")
