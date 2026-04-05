"""Generate synthetic datasets for new L2 eval cases."""
import numpy as np
import pandas as pd

np.random.seed(2026)

# --- Time series: structural break in pre-period ---
n_periods = 60
treatment_time = 37
break_time = 20

time = np.arange(1, n_periods + 1)
trend = 0.5 * time
structural_break = 3.0 * (time >= break_time)
treatment_effect = 2.0 * (time >= treatment_time)
noise = np.random.normal(0, 1, n_periods)
outcome = 10 + trend + structural_break + treatment_effect + noise

df = pd.DataFrame({
    "time": time,
    "outcome": np.round(outcome, 2),
    "post": (time >= treatment_time).astype(int),
})
df.to_csv("evals/data/timeseries_structural_break.csv", index=False)

# --- Time series: clean ITS ---
np.random.seed(2027)
time = np.arange(1, 61)
treatment_time = 37
trend = 0.3 * time
treatment_effect = 4.0 * (time >= treatment_time)
noise = np.random.normal(0, 1.5, 60)
outcome = 20 + trend + treatment_effect + noise

df = pd.DataFrame({
    "time": time,
    "outcome": np.round(outcome, 2),
    "post": (time >= treatment_time).astype(int),
})
df.to_csv("evals/data/timeseries_clean.csv", index=False)

# --- Experiments: non-compliance ---
np.random.seed(2028)
n = 2000
assigned = np.random.binomial(1, 0.5, n)
comply_treat = np.random.binomial(1, 0.80, n)
comply_control = np.random.binomial(1, 0.05, n)
actual_treatment = np.where(assigned == 1, assigned * comply_treat, comply_control)
outcome = 50 + 4.0 * actual_treatment + np.random.normal(0, 10, n)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "assigned_treatment": assigned,
    "received_treatment": actual_treatment,
    "outcome": np.round(outcome, 2),
})
df.to_csv("evals/data/experiments_noncompliance.csv", index=False)

# --- Matching: good overlap ---
np.random.seed(2029)
n = 1000
x1 = np.random.normal(0, 1, n)
x2 = np.random.normal(0, 1, n)
propensity = 1 / (1 + np.exp(-(0.5 * x1 + 0.3 * x2)))
treatment = np.random.binomial(1, propensity)
outcome = 10 + 2.0 * x1 + 1.5 * x2 + 3.0 * treatment + np.random.normal(0, 2, n)

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "treatment": treatment,
    "x1": np.round(x1, 3),
    "x2": np.round(x2, 3),
    "outcome": np.round(outcome, 2),
})
df.to_csv("evals/data/matching_good_overlap.csv", index=False)


# --- DAG: collider bias (DGP-DAG-01) ---
def generate_dag_collider():
    """Generate collider bias dataset from DGP-DAG-01.

    DGP: gender -> occupation, gender -> wages, ability -> occupation,
    ability -> wages, occupation -> wages.
    Occupation is a collider on the gender-ability path through wages.
    Controlling for occupation alone reverses the sign of the gender effect.

    True ATE of gender on wages: -1.0
    """
    np.random.seed(42)
    n = 10000
    female = np.random.binomial(1, 0.5, n)
    ability = np.random.normal(0, 1, n)
    occupation = 1 + 2 * ability + (-2) * female + np.random.normal(0, 1, n)
    wage = 1 + (-1) * female + 3 * ability + 0.5 * occupation + np.random.normal(0, 1, n)

    df = pd.DataFrame({
        "id": np.arange(1, n + 1),
        "female": female,
        "ability": ability,
        "occupation": np.round(occupation, 2),
        "wage": np.round(wage, 2),
    })
    df.to_csv("evals/data/dag_collider.csv", index=False)
    print("DAG collider dataset generated (n=10000, true ATE=-1.0).")


generate_dag_collider()

print("All L2 datasets generated.")
