# Difference-in-Differences — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn linearmodels statsmodels

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from linearmodels.panel import PanelOLS
import statsmodels.api as sm
```

## Data Preparation

```python
# --- Load your data ---
# df should have columns: unit, time, outcome, treatment_group, post
# treatment_group: 1 if unit ever treated, 0 if control
# post: 1 if period is after treatment, 0 otherwise

# Create the interaction term for classic 2x2 DiD
df["treated_post"] = df["treatment_group"] * df["post"]

# Set MultiIndex for panel estimation (required by linearmodels)
df = df.set_index(["unit", "time"])
```

## Estimation — Classic Two-Way Fixed Effects

```python
# Classic TWFE DiD with entity and time fixed effects
formula = "outcome ~ treated_post + EntityEffects + TimeEffects"
model = PanelOLS.from_formula(formula, data=df)
result = model.fit(cov_type="clustered", cluster_entity=True)

print(result.summary)

# Extract the ATT estimate
att = result.params["treated_post"]
se = result.std_errors["treated_post"]
ci_low = result.conf_int().loc["treated_post", "lower"]
ci_high = result.conf_int().loc["treated_post", "upper"]
print(f"\nATT: {att:.4f} (SE = {se:.4f})")
print(f"95% CI: [{ci_low:.4f}, {ci_high:.4f}]")
```

## Estimation — Event Study (Leads and Lags)

```python
# Reset index for dummy construction
df_es = df.reset_index()

# Create relative-time variable (periods relative to treatment onset)
# treatment_time: the period when unit first received treatment (NaN for never-treated)
df_es["rel_time"] = df_es["time"] - df_es["treatment_time"]

# Define leads and lags (e.g., 4 periods before to 4 periods after)
leads_lags = range(-4, 5)  # -4, -3, ..., 0, 1, 2, 3, 4

# Create dummies for each relative-time period
# Omit period -1 as the reference category
for k in leads_lags:
    if k == -1:
        continue  # reference period
    col_name = f"rel_{k}" if k < 0 else f"rel_p{k}"
    df_es[col_name] = ((df_es["rel_time"] == k) & (df_es["treatment_group"] == 1)).astype(int)

# Build formula with all lead/lag dummies
dummy_cols = [c for c in df_es.columns if c.startswith("rel_")]
formula_es = "outcome ~ " + " + ".join(dummy_cols) + " + EntityEffects + TimeEffects"

df_es = df_es.set_index(["unit", "time"])
model_es = PanelOLS.from_formula(formula_es, data=df_es)
result_es = model_es.fit(cov_type="clustered", cluster_entity=True)

print(result_es.summary)
```

## Estimation — Staggered DiD (Cohort-Specific ATTs)

```python
# Manual cohort-specific estimation for staggered adoption designs
# Group units by their treatment_time (cohort)
df_stag = df.reset_index()
cohorts = df_stag.loc[df_stag["treatment_group"] == 1, "treatment_time"].unique()

cohort_atts = []
for cohort in sorted(cohorts):
    # Subset: units in this cohort + never-treated controls
    mask = (df_stag["treatment_time"] == cohort) | (df_stag["treatment_group"] == 0)
    sub = df_stag[mask].copy()
    sub["post_cohort"] = (sub["time"] >= cohort).astype(int)
    sub["treat_post"] = sub["treatment_group"] * sub["post_cohort"]
    sub = sub.set_index(["unit", "time"])

    mod = PanelOLS.from_formula(
        "outcome ~ treat_post + EntityEffects + TimeEffects", data=sub
    )
    res = mod.fit(cov_type="clustered", cluster_entity=True)
    cohort_atts.append({
        "cohort": cohort,
        "att": res.params["treat_post"],
        "se": res.std_errors["treat_post"],
    })

cohort_df = pd.DataFrame(cohort_atts)
# Aggregate: weighted average across cohorts (weight by cohort size)
print(cohort_df.to_string(index=False))
```

## Diagnostics — Pre-Trends Test

```python
# Joint test: were treated and control groups already diverging before treatment?
lead_cols = [c for c in dummy_cols if c.startswith("rel_") and not c.startswith("rel_p")]
lead_coefs = result_es.params[lead_cols]
lead_se = result_es.std_errors[lead_cols]

# Visual pre-trends check
print("Pre-treatment coefficients (should be near zero):")
for col in lead_cols:
    pval = result_es.pvalues[col]
    print(f"  {col}: {result_es.params[col]:.4f} (p = {pval:.3f})")
```

## Results Table

```python
# Compile key results into a summary table
results_table = pd.DataFrame({
    "Estimate": [att],
    "Std. Error": [se],
    "CI Lower": [ci_low],
    "CI Upper": [ci_high],
    "p-value": [result.pvalues["treated_post"]],
    "N obs": [result.nobs],
    "N units": [df.index.get_level_values("unit").nunique()],
    "N periods": [df.index.get_level_values("time").nunique()],
}, index=["ATT (TWFE)"])

print(results_table.to_string())
```

## Visualization

```python
# Pre-treatment coefficients should be near zero if parallel trends holds
fig, ax = plt.subplots(figsize=(8, 5))

# Collect coefficients for all leads/lags; add zero for reference period
coefs = []
for k in leads_lags:
    if k == -1:
        coefs.append({"rel_time": k, "coef": 0, "se": 0})
    else:
        col = f"rel_{k}" if k < 0 else f"rel_p{k}"
        coefs.append({
            "rel_time": k,
            "coef": result_es.params[col],
            "se": result_es.std_errors[col],
        })

coef_df = pd.DataFrame(coefs)

ax.errorbar(
    coef_df["rel_time"], coef_df["coef"],
    yerr=1.96 * coef_df["se"],
    fmt="o-", capsize=3, color="steelblue", markersize=5
)
ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.axvline(-0.5, color="red", linestyle=":", linewidth=0.8, label="Treatment onset")
ax.set_xlabel("Periods Relative to Treatment")
ax.set_ylabel("Estimate")
ax.set_title("Event Study — Difference-in-Differences")
ax.legend()
sns.despine()
plt.tight_layout()
plt.savefig("did_event_study.png", dpi=150)
plt.show()
```
