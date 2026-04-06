# Regression Discontinuity Design — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn rdrobust rddensity

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from rdrobust import rdrobust, rdplot, rdbwselect
from rddensity import rddensity
```

## Data Preparation

```python
# --- Load your data ---
# df should have columns: outcome, running_var
# running_var: the forcing/running variable (e.g., test score, age, threshold metric)
# cutoff: the value of running_var at which treatment assignment changes

cutoff = 0  # Set your cutoff value

# Center the running variable at the cutoff (optional but common)
df["running_centered"] = df["running_var"] - cutoff

# Create treatment indicator based on the sharp RDD rule
# Adjust >= vs > depending on your assignment rule
df["treated"] = (df["running_var"] >= cutoff).astype(int)

# Inspect data around the cutoff
print("=== Observations by Treatment Status ===")
print(df["treated"].value_counts())
print(f"\nRunning variable range: [{df['running_var'].min():.2f}, {df['running_var'].max():.2f}]")
print(f"Cutoff: {cutoff}")
```

## Estimation — Local Polynomial RD

```python
# Main RD estimate using rdrobust
# Uses local polynomial regression with MSE-optimal bandwidth
Y = df["outcome"].values
X = df["running_var"].values

result = rdrobust(Y, X, c=cutoff)
print(result)

# Extract key estimates
rd_est = result.coef.iloc[0]  # Conventional estimate
rd_se = result.se.iloc[0]
rd_pval = result.pv.iloc[0]
bw_left = result.bws.iloc[0, 0]   # Bandwidth left of cutoff
bw_right = result.bws.iloc[0, 1]  # Bandwidth right of cutoff

print(f"\n=== RD Estimate ===")
print(f"Estimate: {rd_est:.4f} (SE = {rd_se:.4f})")
print(f"p-value: {rd_pval:.4f}")
print(f"Bandwidth: [{bw_left:.4f}, {bw_right:.4f}]")
print(f"Effective N (left): {result.N_h[0]}, (right): {result.N_h[1]}")
```

## Estimation — Bandwidth Sensitivity

```python
# Test robustness to different bandwidth choices
bandwidths = [bw_left * 0.5, bw_left * 0.75, bw_left, bw_left * 1.25, bw_left * 1.5]
bw_results = []

for bw in bandwidths:
    try:
        res = rdrobust(Y, X, c=cutoff, h=bw)
        bw_results.append({
            "bandwidth": bw,
            "estimate": res.coef.iloc[0],
            "se": res.se.iloc[0],
            "pval": res.pv.iloc[0],
            "n_eff": res.N_h[0] + res.N_h[1],
        })
    except Exception as e:
        print(f"Bandwidth {bw:.2f} failed: {e}")

bw_df = pd.DataFrame(bw_results)
print("=== Bandwidth Sensitivity ===")
print(bw_df.to_string(index=False, float_format="%.4f"))
```

## Diagnostics — Manipulation Testing

```python
# Manipulation check: bunching at the cutoff suggests people can control their score
# Density test for manipulation (Cattaneo, Jansson, and Ma 2020)
# If units can manipulate the running variable, the density will jump at the cutoff
density_test = rddensity(X, c=cutoff)
print(f"\n=== Density Test (Manipulation Check) ===")
print(f"T-statistic: {density_test.test.t_jk:.4f}")
print(f"p-value: {density_test.test.p_jk:.4f}")
if density_test.test.p_jk < 0.05:
    print("WARNING: Significant bunching detected — assignment may be manipulated")
else:
    print("No evidence of manipulation at the cutoff")
```

## Diagnostics — Covariate Balance at the Cutoff

```python
# Covariates should pass smoothly through the cutoff — discontinuities signal compound treatment
# Test whether pre-treatment covariates are smooth through the cutoff
# This should show no discontinuity for covariates unaffected by treatment
covariates = ["covariate1", "covariate2"]  # Replace with your covariates

print("\n=== Covariate Balance Tests ===")
for cov in covariates:
    cov_values = df[cov].values
    try:
        cov_result = rdrobust(cov_values, X, c=cutoff)
        est = cov_result.coef.iloc[0]
        pval = cov_result.pv.iloc[0]
        print(f"{cov}: estimate = {est:.4f}, p = {pval:.4f}")
    except Exception as e:
        print(f"{cov}: test failed — {e}")
```

## Results Table

```python
# Compile results
results_table = pd.DataFrame({
    "Conventional": [result.coef.iloc[0], result.se.iloc[0], result.pv.iloc[0]],
    "Bias-Corrected": [result.coef.iloc[1], result.se.iloc[1], result.pv.iloc[1]],
    "Robust": [result.coef.iloc[2], result.se.iloc[2], result.pv.iloc[2]],
}, index=["Estimate", "Std. Error", "p-value"])

print("=== RD Estimates ===")
print(results_table.to_string(float_format="%.4f"))
print(f"\nBandwidth (h): left = {bw_left:.4f}, right = {bw_right:.4f}")
print(f"Effective N: left = {result.N_h[0]}, right = {result.N_h[1]}")
print(f"Kernel: Triangular | Order: 1 (local linear)")
```

## Visualization

```python
# --- RD Plot: binned scatter with local polynomial fits (native rdrobust function) ---
rdplot(Y, X, c=cutoff,
       x_label="Running Variable",
       y_label="Outcome",
       title="RD Plot")

# --- Bandwidth sensitivity plot (no native function; hand-rolled is correct) ---
fig, ax = plt.subplots(figsize=(7, 5))
ax.errorbar(
    bw_df["bandwidth"], bw_df["estimate"],
    yerr=1.96 * bw_df["se"],
    fmt="o-", capsize=4, color="steelblue", markersize=6
)
ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.axvline(bw_left, color="red", linestyle=":", linewidth=0.8, label="Optimal BW")
ax.set_xlabel("Bandwidth")
ax.set_ylabel("RD Estimate")
ax.set_title("Bandwidth Sensitivity")
ax.legend()
sns.despine()
plt.tight_layout()
plt.savefig("rdd_bandwidth_sensitivity.png", dpi=150)
plt.show()
```
