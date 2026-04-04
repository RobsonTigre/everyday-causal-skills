# Instrumental Variables — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn linearmodels statsmodels

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from linearmodels.iv import IV2SLS
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
```

## Data Preparation

```python
# --- Load your data ---
# df should have columns: outcome, endogenous, instrument
# Plus any exogenous controls: control1, control2, ...

# Inspect key relationships before estimation
print("=== Summary Statistics ===")
print(df[["outcome", "endogenous", "instrument"]].describe())

# Check instrument-endogenous correlation (relevance condition)
corr = df["instrument"].corr(df["endogenous"])
print(f"\nCorr(instrument, endogenous): {corr:.4f}")
```

## Estimation — First Stage

```python
# First stage: regress endogenous variable on instrument + controls
first_stage = smf.ols("endogenous ~ instrument + control1 + control2", data=df).fit()
print("=== First Stage ===")
print(first_stage.summary())

# First-stage F-statistic on the excluded instrument
# Use the F-test for the instrument coefficient specifically
f_test = first_stage.f_test("instrument = 0")
f_stat = float(f_test.fvalue)
f_pval = float(f_test.pvalue)
print(f"\nFirst-stage F-statistic: {f_stat:.2f} (p = {f_pval:.4f})")
print(f"Rule of thumb: F > 10 suggests instrument is not weak")
```

## Estimation — Reduced Form

```python
# Reduced form: regress outcome directly on instrument + controls
reduced_form = smf.ols("outcome ~ instrument + control1 + control2", data=df).fit()
print("=== Reduced Form ===")
print(reduced_form.summary())

# The reduced form coefficient / first-stage coefficient ~ IV estimate
rf_coef = reduced_form.params["instrument"]
fs_coef = first_stage.params["instrument"]
print(f"\nIndirect Wald estimate: {rf_coef / fs_coef:.4f}")
```

## Estimation — Two-Stage Least Squares (2SLS)

```python
# 2SLS via linearmodels
# Syntax: 'outcome ~ exogenous_controls + [endogenous ~ instruments]'
formula_iv = "outcome ~ 1 + control1 + control2 + [endogenous ~ instrument]"
model_iv = IV2SLS.from_formula(formula_iv, data=df)
result_iv = model_iv.fit(cov_type="robust")

print("=== 2SLS Results ===")
print(result_iv.summary)

# Extract the key coefficient
iv_est = result_iv.params["endogenous"]
iv_se = result_iv.std_errors["endogenous"]
iv_ci = result_iv.conf_int().loc["endogenous"]
print(f"\nIV estimate: {iv_est:.4f} (SE = {iv_se:.4f})")
print(f"95% CI: [{iv_ci['lower']:.4f}, {iv_ci['upper']:.4f}]")
```

## Diagnostics

```python
# --- Wu-Hausman Test (endogeneity test) ---
# Compare OLS vs 2SLS; if they differ significantly, endogeneity is present
ols_model = smf.ols("outcome ~ endogenous + control1 + control2", data=df).fit()

# Manual Wu-Hausman: include first-stage residuals in OLS
df["fs_resid"] = first_stage.resid
hausman_test = smf.ols(
    "outcome ~ endogenous + control1 + control2 + fs_resid", data=df
).fit()
hausman_t = hausman_test.tvalues["fs_resid"]
hausman_p = hausman_test.pvalues["fs_resid"]
print(f"Wu-Hausman t-stat on first-stage residual: {hausman_t:.3f} (p = {hausman_p:.4f})")
print("Significant p => evidence of endogeneity; IV is preferred over OLS")

# --- Weak Instrument Diagnostics ---
print(f"\nFirst-stage F: {f_stat:.2f}")
if f_stat < 10:
    print("WARNING: Potential weak instrument (F < 10)")
elif f_stat < 23.1:
    print("NOTE: F > 10 but below Stock-Yogo 5% critical value (23.1 for one instrument)")
else:
    print("Instrument appears strong by Stock-Yogo standards")

# --- Over-identification test (if >1 instrument) ---
# With a single instrument the model is exactly identified; no Sargan test possible
# Uncomment below for over-identified case:
# print(result_iv.wooldridge_overid)
```

## Results Table

```python
# Compare OLS and IV side by side
results_table = pd.DataFrame({
    "OLS": [
        ols_model.params["endogenous"],
        ols_model.bse["endogenous"],
        ols_model.pvalues["endogenous"],
        ols_model.nobs,
    ],
    "IV (2SLS)": [
        iv_est,
        iv_se,
        result_iv.pvalues["endogenous"],
        result_iv.nobs,
    ],
}, index=["Coefficient", "Std. Error", "p-value", "N obs"])

print("=== OLS vs. IV Comparison ===")
print(results_table.to_string())

print(f"\nFirst-stage F: {f_stat:.2f}")
print(f"Wu-Hausman p-value: {hausman_p:.4f}")
```

## Visualization

```python
fig, axes = plt.subplots(1, 3, figsize=(14, 4))

# --- Panel 1: First-stage scatter ---
ax = axes[0]
ax.scatter(df["instrument"], df["endogenous"], alpha=0.3, s=10, color="steelblue")
# Add regression line
x_range = np.linspace(df["instrument"].min(), df["instrument"].max(), 100)
ax.plot(x_range, first_stage.params["Intercept"] + first_stage.params["instrument"] * x_range,
        color="red", linewidth=1.5)
ax.set_xlabel("Instrument")
ax.set_ylabel("Endogenous Variable")
ax.set_title(f"First Stage (F = {f_stat:.1f})")

# --- Panel 2: Reduced-form scatter ---
ax = axes[1]
ax.scatter(df["instrument"], df["outcome"], alpha=0.3, s=10, color="steelblue")
x_range = np.linspace(df["instrument"].min(), df["instrument"].max(), 100)
ax.plot(x_range, reduced_form.params["Intercept"] + reduced_form.params["instrument"] * x_range,
        color="red", linewidth=1.5)
ax.set_xlabel("Instrument")
ax.set_ylabel("Outcome")
ax.set_title("Reduced Form")

# --- Panel 3: OLS vs IV coefficient comparison ---
ax = axes[2]
methods = ["OLS", "2SLS"]
coefs = [ols_model.params["endogenous"], iv_est]
ses = [ols_model.bse["endogenous"], iv_se]
colors = ["gray", "steelblue"]

for i, (method, coef, se, color) in enumerate(zip(methods, coefs, ses, colors)):
    ax.errorbar(i, coef, yerr=1.96 * se, fmt="o", capsize=5,
                color=color, markersize=8, linewidth=2)

ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.set_xticks(range(len(methods)))
ax.set_xticklabels(methods)
ax.set_ylabel("Coefficient Estimate")
ax.set_title("OLS vs. IV Estimates")

for ax in axes:
    sns.despine(ax=ax)

plt.tight_layout()
plt.savefig("iv_diagnostics.png", dpi=150)
plt.show()
```
