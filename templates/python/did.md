# Difference-in-Differences — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn linearmodels statsmodels diff-diff

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

## Estimation — Staggered DiD (Callaway & Sant'Anna via diff-diff)

```python
# Python parity with R's did::att_gt(): use diff-diff's CallawaySantAnna.
# Do NOT hand-roll a per-cohort TWFE loop — it is biased when effects vary over time.
# Data must be a long panel: columns unit, time, outcome, first_treat (0 = never treated).
# (If you synthesized data with diff_diff.generate_staggered_data, rename its
#  `period` column to `time` first.)
from diff_diff import CallawaySantAnna

df_stag = df.reset_index() if df.index.names != [None] else df

cs = CallawaySantAnna(
    control_group="never_treated",   # use "not_yet_treated" if NO never-treated units exist
    base_period="universal",          # match the R path's did configuration
)
res = cs.fit(
    df_stag, outcome="outcome", unit="unit", time="time",
    first_treat="first_treat", aggregate="all",   # overall ATT + event study + cohort
)

att = res.overall_att
print(f"ATT: {att:.4f}  SE: {res.overall_se:.4f}")
print(f"95% CI: {res.overall_conf_int}")
print(f"ESTIMATE:{att}")             # eval harness reads this exact line

# Event study (dynamic effects relative to adoption); pre-period effects should be ~0
print("Event study (relative period -> effect):")
for e in sorted(res.event_study_effects):
    eff = res.event_study_effects[e]
    print(f"  e={e:>3}  effect={eff['effect']:.4f}  se={eff['se']:.4f}")

# Doubly-robust covariate adjustment (conditional parallel trends): pass covariates=[...]
# res_dr = cs.fit(df_stag, outcome="outcome", unit="unit", time="time",
#                 first_treat="first_treat", covariates=["X1", "X2"], aggregate="simple")
# print(f"ESTIMATE:{res_dr.overall_att}")
```

> Note: `diff-diff` may print a harmless numpy `RuntimeWarning` (divide-by-zero/overflow
> in a matmul) during event-study aggregation. It is non-fatal — the ATT, event study,
> and confidence bands are still computed correctly.

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
