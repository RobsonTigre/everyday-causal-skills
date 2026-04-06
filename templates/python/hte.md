# HTE Analysis — Python Template (econml)

## Prerequisites

```python
# pip install econml scikit-learn matplotlib numpy pandas
from econml.dml import CausalForestDML, LinearDML
from econml.policy import DRPolicyTree
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.tree import plot_tree
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
```

## Data Preparation

```python
# Load data
df = pd.read_csv("data.csv")

# Define variables:
# Y = outcome (1D array)
# T = treatment (1D array, binary 0/1)
# X = effect modifiers (variables you think drive heterogeneity)
# W = confounders (variables needed for identification)
#
# KEY DISTINCTION (econml-specific):
# - W enters ONLY the first-stage nuisance models (propensity + outcome)
# - X enters the second-stage CATE model
# - A variable can (and often should) be in BOTH X and W
# - When in doubt, include the variable in both X and W
# - Putting a confounder only in X (not W) biases estimates
# - Putting a variable only in W means it cannot drive heterogeneity
Y = df["outcome"].values
T = df["treatment"].values
X = df[["age", "income", "gender"]].values  # Effect modifiers
W = df[["age", "income"]].values            # Confounders (age, income are both)
```

## Step 1: LinearDML first pass (interpretable coefficients)

```python
# Fast, interpretable screen for heterogeneity.
# Gives "for each unit increase in age, the treatment effect changes by beta."
ldml = LinearDML(
    model_y=GradientBoostingRegressor(n_estimators=100, max_depth=3),
    model_t=GradientBoostingClassifier(n_estimators=100, max_depth=3),
    cv=5,                  # 5-fold cross-fitting (do NOT turn this off)
    random_state=42
)
ldml.fit(Y, T, X=X, W=W)

# Summary with confidence intervals
print(ldml.summary())
# Significant coefficients = evidence of linear heterogeneity
```

## Step 2: Causal Forest (nonparametric CATE estimation)

### For RCT data (known propensity):
```python
# If treatment was randomly assigned, supply the known propensity.
from sklearn.dummy import DummyClassifier
est = CausalForestDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3),
    model_t=DummyClassifier(strategy="prior"),  # Known propensity
    n_estimators=2000,
    cv=5,
    random_state=42
)
est.fit(Y, T, X=X, W=W)
```

### For observational data:
```python
est = CausalForestDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3),
    model_t=GradientBoostingClassifier(n_estimators=200, max_depth=3),
    n_estimators=2000,
    cv=5,                  # Cross-fitting — do NOT bypass this
    random_state=42
)
est.fit(Y, T, X=X, W=W)
```

### Extract individual-level CATEs:
```python
cate = est.effect(X)
print(f"CATE summary: mean={cate.mean():.3f}, std={cate.std():.3f}, "
      f"min={cate.min():.3f}, max={cate.max():.3f}")

plt.hist(cate, bins=50, edgecolor='black')
plt.axvline(cate.mean(), color='red', linewidth=2, label=f'Mean CATE={cate.mean():.3f}')
plt.xlabel("Conditional Average Treatment Effect")
plt.title("Distribution of Estimated CATEs")
plt.legend()
plt.show()
```

### Variable importance:
```python
varimp = est.feature_importances_
feature_names = ["age", "income", "gender"]  # Match your X columns
sorted_idx = np.argsort(varimp)[::-1]

plt.barh([feature_names[i] for i in sorted_idx],
         [varimp[i] for i in sorted_idx])
plt.xlabel("Importance")
plt.title("Variable Importance for Treatment Effect Heterogeneity")
plt.show()
```

## Step 3: Validation — BLP, GATES, CLAN, TOC

### Step 3a: BLP test
```python
# Regress doubly-robust outcomes on CATE predictions.
# Significant coefficient = forest captures real heterogeneity.
from sklearn.linear_model import LinearRegression
from scipy import stats

cate_centered = cate - cate.mean()
# Approximate DR outcomes using the forest's out-of-bag predictions
ate_est = est.ate(X, T0=0, T1=1)
print(f"ATE estimate: {ate_est:.4f}")

# Inference on the CATE model
cate_inference = est.effect_inference(X)
print(f"Mean CATE: {cate_inference.mean_point:.4f}")
print(f"Mean CATE CI: {cate_inference.mean_normal_ci()}")
```

### Step 3b: GATES (Sorted Group Average Treatment Effects)
```python
# Sort by predicted CATE, estimate actual ATE per quintile
quintiles = pd.qcut(cate, 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
gates = {}
for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
    mask = quintiles == q
    gate_inf = est.effect_inference(X[mask])
    gates[q] = {
        "gate": gate_inf.mean_point,
        "ci_lower": gate_inf.mean_normal_ci()[0][0],
        "ci_upper": gate_inf.mean_normal_ci()[1][0],
    }

gates_df = pd.DataFrame(gates).T
print(gates_df)

# Plot
plt.errorbar(range(5), gates_df["gate"],
             yerr=[gates_df["gate"] - gates_df["ci_lower"],
                   gates_df["ci_upper"] - gates_df["gate"]],
             fmt='o', capsize=5)
plt.axhline(y=ate_est, color='red', linestyle='--', label='ATE')
plt.xticks(range(5), gates_df.index)
plt.xlabel("CATE Quintile (lowest to highest)")
plt.ylabel("Group Average Treatment Effect")
plt.title("GATES")
plt.legend()
plt.show()
```

### Step 3c: CLAN
```python
# What characterizes high vs low CATE groups?
df_with_q = df.copy()
df_with_q["quintile"] = quintiles.values
high = df_with_q[df_with_q["quintile"] == "Q5"]
low = df_with_q[df_with_q["quintile"] == "Q1"]

clan = pd.DataFrame({
    "mean_high": high[feature_names].mean(),
    "mean_low": low[feature_names].mean(),
    "difference": high[feature_names].mean() - low[feature_names].mean(),
})
print(clan)
```

### Step 3d: Stability check
```python
# Re-run with different seed. Check if variable importance is stable.
est_check = CausalForestDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3),
    model_t=GradientBoostingClassifier(n_estimators=200, max_depth=3),
    n_estimators=2000, cv=5, random_state=999
)
est_check.fit(Y, T, X=X, W=W)
varimp_check = est_check.feature_importances_

print("Seed 42 top-3:", [feature_names[i] for i in np.argsort(varimp)[::-1][:3]])
print("Seed 999 top-3:", [feature_names[i] for i in np.argsort(varimp_check)[::-1][:3]])
```

## Step 4: Interpretation + Policy

### Step 4a: Threshold rule (default)
```python
cost = 0  # User specifies; default 0 if free/unknown
treat_rule = cate > cost

print(f"Threshold rule (CATE > {cost}):")
print(f"  Fraction treated: {treat_rule.mean():.3f}")
print(f"  Expected welfare (treated): {(cate[treat_rule] - cost).sum():.2f}")
print(f"  Treat-all welfare: {(cate - cost).sum():.2f}")
print(f"  Treat-none welfare: 0")
```

### Step 4b: Policy tree (opt-in)
```python
# Interpretable targeting rule via doubly-robust policy tree
pt = DRPolicyTree(max_depth=2, min_samples_leaf=50)
pt.fit(Y, T, X=X, W=W)

policy = pt.predict(X)
print(f"Policy tree treats: {policy.mean():.3f} of units")
print(f"Threshold rule treats: {treat_rule.mean():.3f} of units")

# Visualize the policy tree (econml trees use sklearn internals)
fig, ax = plt.subplots(figsize=(14, 6))
plot_tree(
    pt.tree_model_ if hasattr(pt, "tree_model_") else pt,
    feature_names=feature_names,
    filled=True, rounded=True,
    fontsize=9, ax=ax
)
ax.set_title("Policy Tree: Who Should Be Treated?")
plt.tight_layout()
plt.show()
```

### Step 4c: Fairness check
```python
# Does the policy correlate with protected attributes?
from scipy.stats import chi2_contingency
if "gender" in df.columns:
    ct = pd.crosstab(policy, df["gender"])
    print("\nFairness check — treatment by gender:")
    print(ct)
    chi2, p, _, _ = chi2_contingency(ct)
    print(f"Chi-squared: {chi2:.2f}, p-value: {p:.4f}")
```
