"""Generate synthetic dataset for matching L3 eval case."""
import numpy as np
import pandas as pd

np.random.seed(2030)
n = 500

# Covariates
age = np.random.normal(40, 10, n).clip(18, 70)
income = np.random.normal(50000, 15000, n).clip(10000, 120000)
education = np.random.choice([1, 2, 3, 4], n, p=[0.2, 0.3, 0.3, 0.2])

# Treatment assignment depends on covariates (selection on observables)
logit = -2 + 0.03 * (age - 40) + 0.00002 * (income - 50000) + 0.3 * (education - 2)
propensity = 1 / (1 + np.exp(-logit))
treatment = np.random.binomial(1, propensity)

# Outcome: true ATE = 3.0
outcome = (20 + 0.5 * (age - 40) + 0.0003 * (income - 50000) + 2 * education
           + 3.0 * treatment + np.random.normal(0, 5, n))

df = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "treatment": treatment,
    "age": np.round(age, 1),
    "income": np.round(income, 0).astype(int),
    "education": education,
    "outcome": np.round(outcome, 2),
})
df.to_csv("evals/data/matching_ate_l3.csv", index=False)
print(f"Generated matching L3 dataset: n={n}, treated={treatment.sum()}, control={n - treatment.sum()}")
print(f"True ATE = 3.0")
