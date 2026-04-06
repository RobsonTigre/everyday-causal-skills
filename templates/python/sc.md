# Synthetic Control — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn scpi-pkg

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scpi_pkg.scdata import scdata
from scpi_pkg.scest import scest
from scpi_pkg.scpi import scpi
from scpi_pkg.scplot import scplot
```

## Data Preparation

```python
# --- Load your data ---
# df should be a balanced panel with columns: unit, time, outcome
# One unit is treated starting at treatment_time; remaining units are donors (controls)

treatment_time = 2000       # Period when treatment begins
treated_unit = "UnitA"      # Name/ID of the treated unit

# Inspect panel structure
print(f"Units: {df['unit'].nunique()}")
print(f"Time periods: {df['time'].nunique()}")
print(f"Treated unit: {treated_unit}")
print(f"Treatment time: {treatment_time}")
print(f"Pre-treatment periods: {df[df['time'] < treatment_time]['time'].nunique()}")
print(f"Post-treatment periods: {df[df['time'] >= treatment_time]['time'].nunique()}")

# Verify panel is balanced
panel_check = df.groupby("unit")["time"].count()
assert panel_check.nunique() == 1, "Panel is unbalanced — each unit must have the same time periods"
```

## Estimation — Prepare Data with scdata

```python
# scdata prepares the matrices for synthetic control estimation
# id_var: unit identifier column
# time_var: time period column
# outcome_var: outcome column name
# period_pre: pre-treatment periods (tuple of start, end)
# period_post: post-treatment periods (tuple of start, end)
# unit_tr: treated unit identifier
# unit_co: list of donor (control) unit identifiers

donor_units = [u for u in df["unit"].unique() if u != treated_unit]
time_min = df["time"].min()
time_max = df["time"].max()

sc_data = scdata(
    df=df,
    id_var="unit",
    time_var="time",
    outcome_var="outcome",
    period_pre=(time_min, treatment_time - 1),
    period_post=(treatment_time, time_max),
    unit_tr=treated_unit,
    unit_co=donor_units,
)
```

## Estimation — Point Estimate with scest

```python
# scest estimates the synthetic control weights and treatment effects
sc_est = scest(sc_data, e_method="all")

# Print the estimation summary
print(sc_est)

# Weight concentration: > 60-70% on one donor is a red flag
weights = sc_est.w
print("\n=== Donor Weights ===")
for donor, weight in zip(donor_units, weights.flatten()):
    if abs(weight) > 0.001:  # Show non-trivial weights
        print(f"  {donor}: {weight:.4f}")
```

## Estimation — Prediction Intervals with scpi

```python
# scpi provides prediction intervals (accounts for in-sample uncertainty)
sc_pi = scpi(sc_data, sims=200, cores=1)

print(sc_pi)
```

## Diagnostics — Pre-Treatment Fit

```python
# Pre-treatment RMSPE: lower = better synthetic match. High values mean unreliable counterfactual
pre_periods = range(time_min, treatment_time)

# Actual treated unit outcomes (pre-treatment)
actual_pre = df[(df["unit"] == treated_unit) & (df["time"] < treatment_time)].set_index("time")["outcome"]

# Synthetic control fitted values (pre-treatment)
# Reconstruct from weights and donor data
donor_panel = df[df["unit"].isin(donor_units)].pivot(index="time", columns="unit", values="outcome")
synthetic_pre = donor_panel.loc[donor_panel.index < treatment_time].dot(weights.flatten())

# Pre-treatment RMSPE (Root Mean Squared Prediction Error)
rmspe_pre = np.sqrt(np.mean((actual_pre.values - synthetic_pre.values) ** 2))
print(f"Pre-treatment RMSPE: {rmspe_pre:.4f}")

# Post-treatment RMSPE
actual_post = df[(df["unit"] == treated_unit) & (df["time"] >= treatment_time)].set_index("time")["outcome"]
synthetic_post = donor_panel.loc[donor_panel.index >= treatment_time].dot(weights.flatten())
rmspe_post = np.sqrt(np.mean((actual_post.values - synthetic_post.values) ** 2))
# Post/pre RMSPE ratio: > 2 suggests the treatment gap is real, not noise
print(f"Post-treatment RMSPE: {rmspe_post:.4f}")
print(f"Post/Pre RMSPE ratio: {rmspe_post / rmspe_pre:.2f}")
```

## Results Table

```python
# Treatment effects by post-treatment period
actual_all = df[df["unit"] == treated_unit].set_index("time")["outcome"]
synthetic_all = donor_panel.dot(weights.flatten())

gaps = actual_all - synthetic_all

post_effects = gaps[gaps.index >= treatment_time]
print("=== Treatment Effects by Period ===")
effect_table = pd.DataFrame({
    "Actual": actual_all[actual_all.index >= treatment_time],
    "Synthetic": synthetic_all[synthetic_all.index >= treatment_time],
    "Gap": post_effects,
})
print(effect_table.to_string(float_format="%.4f"))

print(f"\nAverage post-treatment effect: {post_effects.mean():.4f}")
print(f"Pre-treatment RMSPE: {rmspe_pre:.4f}")
print(f"Post/Pre RMSPE ratio: {rmspe_post / rmspe_pre:.2f}")
```

## Visualization

```python
# --- Native scpi plot: treated vs synthetic, gaps, prediction intervals ---
scplot(sc_pi)

# --- Donor weights (no native function; hand-rolled is correct) ---
fig, ax = plt.subplots(figsize=(6, 4))
w_df = pd.DataFrame({"donor": donor_units, "weight": weights.flatten()})
w_df = w_df[w_df["weight"].abs() > 0.001].sort_values("weight", ascending=True)
ax.barh(w_df["donor"], w_df["weight"], color="steelblue")
ax.set_xlabel("Weight")
ax.set_title("Donor Unit Weights")
sns.despine()
plt.tight_layout()
plt.show()
```
