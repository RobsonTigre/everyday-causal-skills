# Matching and Weighting — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn dowhy econml statsmodels scikit-learn

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LogisticRegression
import statsmodels.api as sm
import statsmodels.formula.api as smf
```

## Data Preparation

```python
# --- Load your data ---
# df should have columns: outcome, treatment, covariate1, covariate2, ...
# treatment: binary (0/1)
# covariates: pre-treatment variables for matching/weighting

covariates = ["covariate1", "covariate2", "covariate3"]

print("=== Treatment Distribution ===")
print(df["treatment"].value_counts())
print(f"\nTreatment prevalence: {df['treatment'].mean():.3f}")
print(f"\n=== Covariate Summary by Treatment ===")
print(df.groupby("treatment")[covariates + ["outcome"]].mean().T)
```

## Estimation — Propensity Score (IPW / Inverse Probability Weighting)

```python
# Step 1: Estimate propensity scores with logistic regression
X = df[covariates].values
t = df["treatment"].values

ps_model = LogisticRegression(max_iter=1000, random_state=42)
ps_model.fit(X, t)
df["pscore"] = ps_model.predict_proba(X)[:, 1]

# Clip propensity scores to avoid extreme weights
clip_lower, clip_upper = 0.01, 0.99
df["pscore_clipped"] = df["pscore"].clip(clip_lower, clip_upper)

# Step 2: Compute IPW weights (ATE weights)
df["ipw_weight"] = np.where(
    df["treatment"] == 1,
    1 / df["pscore_clipped"],
    1 / (1 - df["pscore_clipped"])
)

# Step 3: Weighted means for ATE
y1_ipw = np.average(df.loc[df["treatment"] == 1, "outcome"],
                     weights=df.loc[df["treatment"] == 1, "ipw_weight"])
y0_ipw = np.average(df.loc[df["treatment"] == 0, "outcome"],
                     weights=df.loc[df["treatment"] == 0, "ipw_weight"])
ate_ipw = y1_ipw - y0_ipw
print(f"IPW ATE estimate: {ate_ipw:.4f}")

# ATT weights (treated get weight 1, controls get pscore/(1-pscore))
df["att_weight"] = np.where(
    df["treatment"] == 1,
    1.0,
    df["pscore_clipped"] / (1 - df["pscore_clipped"])
)
y1_att = df.loc[df["treatment"] == 1, "outcome"].mean()
y0_att = np.average(df.loc[df["treatment"] == 0, "outcome"],
                     weights=df.loc[df["treatment"] == 0, "att_weight"])
att_ipw = y1_att - y0_att
print(f"IPW ATT estimate: {att_ipw:.4f}")
```

## Estimation — Doubly Robust (AIPW)

```python
# Doubly-robust estimator: consistent if either PS or outcome model is correct
# Step 1: Outcome model (fit separately by treatment status)
outcome_formula = "outcome ~ " + " + ".join(covariates)
mu1_model = smf.ols(outcome_formula, data=df[df["treatment"] == 1]).fit()
mu0_model = smf.ols(outcome_formula, data=df[df["treatment"] == 0]).fit()

# Predicted potential outcomes for all units
df["mu1_hat"] = mu1_model.predict(df)
df["mu0_hat"] = mu0_model.predict(df)

# Step 2: AIPW estimator
n = len(df)
ps = df["pscore_clipped"].values
y = df["outcome"].values
t = df["treatment"].values
mu1 = df["mu1_hat"].values
mu0 = df["mu0_hat"].values

# AIPW for ATE
aipw_1 = (t * y / ps) - ((t - ps) * mu1 / ps)
aipw_0 = ((1 - t) * y / (1 - ps)) + ((t - ps) * mu0 / (1 - ps))
ate_aipw = aipw_1.mean() - aipw_0.mean()

# Standard error via influence function
phi = aipw_1 - aipw_0 - ate_aipw
se_aipw = np.sqrt(np.mean(phi ** 2) / n)

print(f"\nAIPW ATE estimate: {ate_aipw:.4f} (SE = {se_aipw:.4f})")
print(f"95% CI: [{ate_aipw - 1.96*se_aipw:.4f}, {ate_aipw + 1.96*se_aipw:.4f}]")
```

## Estimation — DoWhy Pipeline (Optional)

```python
# Uncomment and use if dowhy is installed
# from dowhy import CausalModel
#
# causal_model = CausalModel(
#     data=df,
#     treatment="treatment",
#     outcome="outcome",
#     common_causes=covariates,
# )
#
# # Identify the causal effect
# identified = causal_model.identify_effect(proceed_when_unidentifiable=True)
#
# # Estimate using propensity score weighting
# estimate_ipw = causal_model.estimate_effect(
#     identified,
#     method_name="backdoor.propensity_score_weighting",
# )
# print(estimate_ipw)
#
# # Refutation: placebo treatment
# refutation = causal_model.refute_estimate(
#     identified, estimate_ipw,
#     method_name="placebo_treatment_refuter",
#     placebo_type="permute",
# )
# print(refutation)
```

## Diagnostics — Propensity Score Overlap

```python
# Overlap check: treated units outside the control PS range have no valid match
print("=== Propensity Score Summary by Group ===")
print(df.groupby("treatment")["pscore"].describe())

# Flag potential positivity violations
extreme_low = (df["pscore"] < 0.02).sum()
extreme_high = (df["pscore"] > 0.98).sum()
print(f"\nPropensity scores < 0.02: {extreme_low}")
print(f"Propensity scores > 0.98: {extreme_high}")
```

## Diagnostics — Covariate Balance (SMD)

```python
# Standardized mean differences: < 0.1 is good, > 0.25 means matching didn't work well enough
def compute_smd(df, cov, treatment_col, weight_col=None):
    """Compute (weighted) standardized mean difference."""
    t1 = df[df[treatment_col] == 1]
    t0 = df[df[treatment_col] == 0]
    if weight_col:
        mean1 = np.average(t1[cov], weights=t1[weight_col])
        mean0 = np.average(t0[cov], weights=t0[weight_col])
    else:
        mean1 = t1[cov].mean()
        mean0 = t0[cov].mean()
    # Pool variance using unweighted variances
    var_pool = (t1[cov].var() + t0[cov].var()) / 2
    return (mean1 - mean0) / np.sqrt(var_pool) if var_pool > 0 else 0

balance_results = []
for cov in covariates:
    smd_raw = compute_smd(df, cov, "treatment")
    smd_ipw = compute_smd(df, cov, "treatment", "ipw_weight")
    balance_results.append({"covariate": cov, "SMD (raw)": smd_raw, "SMD (IPW)": smd_ipw})

balance_df = pd.DataFrame(balance_results)
print("=== Covariate Balance (Standardized Mean Differences) ===")
print(balance_df.to_string(index=False, float_format="%.4f"))
print("\nRule of thumb: |SMD| < 0.1 indicates good balance")
```

## Results Table

```python
results_table = pd.DataFrame({
    "Method": ["IPW (ATE)", "IPW (ATT)", "AIPW (ATE)"],
    "Estimate": [ate_ipw, att_ipw, ate_aipw],
    "SE": [np.nan, np.nan, se_aipw],
    "CI Lower": [np.nan, np.nan, ate_aipw - 1.96 * se_aipw],
    "CI Upper": [np.nan, np.nan, ate_aipw + 1.96 * se_aipw],
})
print("=== Treatment Effect Estimates ===")
print(results_table.to_string(index=False, float_format="%.4f"))
```

## Visualization

```python
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# --- Panel 1: Propensity score overlap ---
ax = axes[0]
ax.hist(df.loc[df["treatment"] == 0, "pscore"], bins=40, alpha=0.5,
        color="steelblue", label="Control", density=True)
ax.hist(df.loc[df["treatment"] == 1, "pscore"], bins=40, alpha=0.5,
        color="coral", label="Treated", density=True)
ax.set_xlabel("Propensity Score")
ax.set_ylabel("Density")
ax.set_title("Propensity Score Overlap")
ax.legend()
sns.despine(ax=ax)

# --- Panel 2: Love plot (SMD before/after) ---
ax = axes[1]
y_pos = range(len(covariates))
ax.scatter(balance_df["SMD (raw)"].abs(), y_pos, marker="o",
           color="gray", s=60, label="Raw", zorder=3)
ax.scatter(balance_df["SMD (IPW)"].abs(), y_pos, marker="s",
           color="steelblue", s=60, label="IPW", zorder=3)
ax.axvline(0.1, color="red", linestyle="--", linewidth=0.8, label="|SMD| = 0.1")
ax.set_yticks(list(y_pos))
ax.set_yticklabels(covariates)
ax.set_xlabel("|Standardized Mean Difference|")
ax.set_title("Covariate Balance (Love Plot)")
ax.legend(fontsize=8)
sns.despine(ax=ax)

# --- Panel 3: Estimate comparison ---
ax = axes[2]
methods = ["IPW\n(ATE)", "IPW\n(ATT)", "AIPW\n(ATE)"]
estimates = [ate_ipw, att_ipw, ate_aipw]
errors = [0, 0, 1.96 * se_aipw]  # SE only available for AIPW
colors = ["steelblue", "steelblue", "coral"]

for i, (m, est, err, c) in enumerate(zip(methods, estimates, errors, colors)):
    ax.errorbar(i, est, yerr=err if err > 0 else None, fmt="o",
                capsize=5, color=c, markersize=8, linewidth=2)

ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.set_xticks(range(len(methods)))
ax.set_xticklabels(methods)
ax.set_ylabel("Treatment Effect Estimate")
ax.set_title("Estimates Comparison")
sns.despine(ax=ax)

plt.tight_layout()
plt.savefig("matching_diagnostics.png", dpi=150)
plt.show()
```
