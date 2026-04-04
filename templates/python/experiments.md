# Experiments (A/B Tests & RCTs) — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn scipy statsmodels scikit-learn

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
```

## Data Preparation

```python
# --- Load your data ---
# df should have columns: outcome, treatment, covariate1, covariate2, ...
# treatment: binary (0 = control, 1 = treated) — randomly assigned
# outcome: continuous or binary response variable

covariates = ["covariate1", "covariate2", "covariate3"]

print("=== Sample Sizes ===")
print(df["treatment"].value_counts().rename({0: "Control", 1: "Treated"}))
print(f"\nTotal N: {len(df)}")
print(f"\n=== Outcome Summary by Group ===")
print(df.groupby("treatment")["outcome"].describe())
```

## Power Analysis (Pre-Experiment Planning)

```python
# Minimum detectable effect (MDE) for a given sample size
# or required sample size for a given MDE

alpha = 0.05          # Significance level
power = 0.80          # Desired power
baseline_mean = 10.0  # Expected control-group mean
baseline_sd = 5.0     # Expected standard deviation (pooled)
mde = 0.5             # Minimum detectable effect size (raw units)

# Cohen's d
cohens_d = mde / baseline_sd

# Required sample size per group (two-sided test)
z_alpha = stats.norm.ppf(1 - alpha / 2)
z_beta = stats.norm.ppf(power)
n_per_group = int(np.ceil(2 * ((z_alpha + z_beta) / cohens_d) ** 2))

print(f"=== Power Analysis ===")
print(f"Alpha: {alpha}, Power: {power}")
print(f"Baseline mean: {baseline_mean}, SD: {baseline_sd}")
print(f"MDE: {mde} (Cohen's d = {cohens_d:.3f})")
print(f"Required N per group: {n_per_group}")
print(f"Total required N: {2 * n_per_group}")

# Power curve: plot power as a function of sample size
n_range = np.arange(50, 2000, 50)
power_curve = []
for n in n_range:
    se = baseline_sd * np.sqrt(2 / n)
    z_effect = mde / se
    achieved_power = 1 - stats.norm.cdf(z_alpha - z_effect)
    power_curve.append(achieved_power)

print(f"\nWith actual N = {len(df)//2} per group:")
se_actual = baseline_sd * np.sqrt(2 / (len(df) // 2))
actual_power = 1 - stats.norm.cdf(z_alpha - mde / se_actual)
print(f"Achieved power: {actual_power:.3f}")
```

## Estimation — Simple Difference in Means

```python
# Two-sample t-test (Welch's, does not assume equal variances)
treated = df.loc[df["treatment"] == 1, "outcome"]
control = df.loc[df["treatment"] == 0, "outcome"]

t_stat, p_value = stats.ttest_ind(treated, control, equal_var=False)
diff = treated.mean() - control.mean()
se_diff = np.sqrt(treated.var() / len(treated) + control.var() / len(control))

print(f"=== Difference in Means ===")
print(f"Treated mean: {treated.mean():.4f}")
print(f"Control mean: {control.mean():.4f}")
print(f"Difference: {diff:.4f} (SE = {se_diff:.4f})")
print(f"t-statistic: {t_stat:.4f}, p-value: {p_value:.4f}")
print(f"95% CI: [{diff - 1.96*se_diff:.4f}, {diff + 1.96*se_diff:.4f}]")
```

## Estimation — Regression Adjustment (Lin Estimator)

```python
# Regression adjustment improves precision by controlling for pre-treatment covariates
# Lin (2013) recommends interacting treatment with demeaned covariates

# Demean covariates (centered at grand mean)
for cov in covariates:
    df[f"{cov}_dm"] = df[cov] - df[cov].mean()

# Build formula: outcome ~ treatment * demeaned_covariates
dm_covs = [f"{c}_dm" for c in covariates]
interactions = " + ".join([f"treatment:{c}" for c in dm_covs])
formula = f"outcome ~ treatment + {' + '.join(dm_covs)} + {interactions}"

lin_model = smf.ols(formula, data=df).fit(cov_type="HC2")
print("=== Regression-Adjusted Estimate (Lin 2013) ===")
print(f"ATE: {lin_model.params['treatment']:.4f}")
print(f"SE (HC2): {lin_model.bse['treatment']:.4f}")
print(f"p-value: {lin_model.pvalues['treatment']:.4f}")
print(f"95% CI: [{lin_model.conf_int().loc['treatment', 0]:.4f}, "
      f"{lin_model.conf_int().loc['treatment', 1]:.4f}]")
```

## Diagnostics — Randomization Balance Checks

```python
# Test whether covariates are balanced across treatment and control
# Under randomization, we expect no systematic differences

print("=== Balance Checks ===")
balance_results = []
for cov in covariates:
    t1 = df.loc[df["treatment"] == 1, cov]
    t0 = df.loc[df["treatment"] == 0, cov]

    # t-test for continuous covariates
    t_stat_bal, p_bal = stats.ttest_ind(t1, t0, equal_var=False)
    smd = (t1.mean() - t0.mean()) / np.sqrt((t1.var() + t0.var()) / 2)

    balance_results.append({
        "covariate": cov,
        "mean_treated": t1.mean(),
        "mean_control": t0.mean(),
        "SMD": smd,
        "t_stat": t_stat_bal,
        "p_value": p_bal,
    })

balance_df = pd.DataFrame(balance_results)
print(balance_df.to_string(index=False, float_format="%.4f"))
```

## Diagnostics — Omnibus Balance Test (ROC-AUC)

```python
# Fit a propensity model and check if treatment is predictable from covariates
# AUC near 0.5 = good balance (treatment is unpredictable)
X_bal = df[covariates].values
y_bal = df["treatment"].values

ps_model = LogisticRegression(max_iter=1000, random_state=42)
ps_model.fit(X_bal, y_bal)
ps_probs = ps_model.predict_proba(X_bal)[:, 1]

auc = roc_auc_score(y_bal, ps_probs)
print(f"\n=== Omnibus Balance (Propensity AUC) ===")
print(f"AUC: {auc:.4f}")
if auc < 0.55:
    print("Good: treatment is essentially unpredictable from covariates")
elif auc < 0.60:
    print("Acceptable: minor imbalance, consider regression adjustment")
else:
    print("WARNING: AUC > 0.60 suggests meaningful imbalance — investigate")

# Chi-squared omnibus test on the propensity model
from statsmodels.discrete.discrete_model import Logit
logit_model = Logit(y_bal, sm.add_constant(X_bal)).fit(disp=0)
lr_stat = logit_model.llr
lr_pval = logit_model.llr_pvalue
print(f"LR chi2 stat: {lr_stat:.2f}, p-value: {lr_pval:.4f}")
```

## Results Table

```python
results_table = pd.DataFrame({
    "Method": [
        "Difference in Means",
        "Regression Adjusted (Lin)",
    ],
    "Estimate": [
        diff,
        lin_model.params["treatment"],
    ],
    "SE": [
        se_diff,
        lin_model.bse["treatment"],
    ],
    "p-value": [
        p_value,
        lin_model.pvalues["treatment"],
    ],
    "CI Lower": [
        diff - 1.96 * se_diff,
        lin_model.conf_int().loc["treatment", 0],
    ],
    "CI Upper": [
        diff + 1.96 * se_diff,
        lin_model.conf_int().loc["treatment", 1],
    ],
})
print("=== Treatment Effect Estimates ===")
print(results_table.to_string(index=False, float_format="%.4f"))
print(f"\nN treated: {len(treated)}, N control: {len(control)}")
print(f"Balance AUC: {auc:.4f}")
```

## Visualization

```python
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# --- Panel 1: Outcome distributions by group ---
ax = axes[0, 0]
ax.hist(control, bins=30, alpha=0.5, color="steelblue", density=True, label="Control")
ax.hist(treated, bins=30, alpha=0.5, color="coral", density=True, label="Treated")
ax.axvline(control.mean(), color="steelblue", linestyle="--", linewidth=1.5)
ax.axvline(treated.mean(), color="coral", linestyle="--", linewidth=1.5)
ax.set_xlabel("Outcome")
ax.set_ylabel("Density")
ax.set_title(f"Outcome by Group (diff = {diff:.3f})")
ax.legend()
sns.despine(ax=ax)

# --- Panel 2: Power curve ---
ax = axes[0, 1]
ax.plot(n_range, power_curve, color="steelblue", linewidth=2)
ax.axhline(0.80, color="red", linestyle="--", linewidth=0.8, label="80% power")
ax.axvline(n_per_group, color="gray", linestyle=":", linewidth=0.8, label=f"Required N = {n_per_group}")
ax.set_xlabel("Sample Size per Group")
ax.set_ylabel("Power")
ax.set_title(f"Power Curve (MDE = {mde}, d = {cohens_d:.2f})")
ax.legend()
sns.despine(ax=ax)

# --- Panel 3: Balance Love plot ---
ax = axes[1, 0]
y_pos = range(len(covariates))
ax.scatter(balance_df["SMD"].abs(), y_pos, marker="o", color="steelblue", s=60, zorder=3)
ax.axvline(0.1, color="red", linestyle="--", linewidth=0.8, label="|SMD| = 0.1")
ax.axvline(0.05, color="orange", linestyle="--", linewidth=0.8, label="|SMD| = 0.05")
ax.set_yticks(list(y_pos))
ax.set_yticklabels(covariates)
ax.set_xlabel("|Standardized Mean Difference|")
ax.set_title("Covariate Balance")
ax.legend(fontsize=8)
sns.despine(ax=ax)

# --- Panel 4: Estimate comparison ---
ax = axes[1, 1]
methods = ["Diff-in-Means", "Lin (Reg Adj)"]
ests = [diff, lin_model.params["treatment"]]
ses = [se_diff, lin_model.bse["treatment"]]
for i, (m, e, s) in enumerate(zip(methods, ests, ses)):
    ax.errorbar(i, e, yerr=1.96 * s, fmt="o", capsize=6, markersize=8,
                color="steelblue", linewidth=2)
ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.set_xticks(range(len(methods)))
ax.set_xticklabels(methods)
ax.set_ylabel("Treatment Effect")
ax.set_title("Estimates with 95% CI")
sns.despine(ax=ax)

plt.tight_layout()
plt.savefig("experiment_results.png", dpi=150)
plt.show()
```
