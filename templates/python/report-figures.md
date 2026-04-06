# Report Figure Templates (Python)

Plotting code for `/causal-report` figure generation. Each block is standalone — adapt variable names from the analysis script, save to PNG.

---

## DiD: Parallel Trends

```python
# Parallel trends plot — shows pre-treatment outcome trends for treated vs control
# WHY: Visual evidence for the parallel trends assumption. If trends diverge
# before treatment, the DiD estimate may be biased.

import matplotlib.pyplot as plt
import pandas as pd

# Adapt these variable names from the analysis
# df: DataFrame with columns: time_var, outcome_var, group_var
# treatment_time: when treatment began

fig, ax = plt.subplots(figsize=(8, 5))

for group, label, color in [(0, "Control", "#2166AC"), (1, "Treated", "#B2182B")]:
    group_data = df[df["group_var"] == group].groupby("time_var")["outcome_var"].mean()
    ax.plot(group_data.index, group_data.values, marker="o", label=label,
            color=color, linewidth=1.5, markersize=4)

ax.axvline(x=treatment_time, linestyle="--", color="gray", alpha=0.7)
ax.text(treatment_time, ax.get_ylim()[1], " Treatment", va="top", color="gray")
ax.set_xlabel("Time")
ax.set_ylabel("Outcome")
ax.set_title("Parallel Trends Check")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_01_parallel_trends.png", dpi=300, bbox_inches="tight")
plt.close()
```

## DiD: Event Study

```python
# Event study plot — dynamic treatment effects relative to treatment onset
# WHY: Shows whether the effect appears at treatment time (not before),
# supporting causal interpretation.

import matplotlib.pyplot as plt
import numpy as np

# Adapt: rel_times (array), estimates (array), std_errors (array)
# These come from the event study regression coefficients

fig, ax = plt.subplots(figsize=(8, 5))

ax.scatter(rel_times, estimates, color="#2166AC", s=40, zorder=3)
ax.errorbar(rel_times, estimates, yerr=1.96 * std_errors,
            fmt="none", color="#2166AC", capsize=3, linewidth=1)
ax.axhline(y=0, linestyle="--", color="gray", alpha=0.7)
ax.axvline(x=-0.5, linestyle="--", color="red", alpha=0.5)
ax.set_xlabel("Periods Relative to Treatment")
ax.set_ylabel("Estimated Effect")
ax.set_title("Event Study")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_02_event_study.png", dpi=300, bbox_inches="tight")
plt.close()
```

## IV: First-Stage Scatter

```python
# First-stage scatter — relationship between instrument and endogenous variable
# WHY: Visual evidence of instrument relevance. A strong first stage
# means the instrument meaningfully shifts the treatment variable.

import matplotlib.pyplot as plt
import numpy as np

# Adapt: df with instrument_var and treatment_var columns

fig, ax = plt.subplots(figsize=(8, 5))

ax.scatter(df["instrument_var"], df["treatment_var"], alpha=0.4, color="#2166AC", s=20)

# Add OLS fit line
z = np.polyfit(df["instrument_var"], df["treatment_var"], 1)
p = np.poly1d(z)
x_line = np.linspace(df["instrument_var"].min(), df["instrument_var"].max(), 100)
ax.plot(x_line, p(x_line), color="#B2182B", linewidth=1.5)

ax.set_xlabel("Instrument")
ax.set_ylabel("Treatment (Endogenous Variable)")
ax.set_title("First Stage: Instrument vs Treatment")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_01_first_stage.png", dpi=300, bbox_inches="tight")
plt.close()
```

## RDD: Running Variable Scatter

```python
# RDD scatter — outcome vs running variable with cutoff
# WHY: Shows the discontinuity at the cutoff. A visible jump suggests
# a treatment effect at the threshold.

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

# Adapt: df with running_var, outcome_var; cutoff value

fig, ax = plt.subplots(figsize=(8, 5))

ax.scatter(df["running_var"], df["outcome_var"], alpha=0.3, color="gray", s=15)

# Separate smoothed lines for each side of cutoff
for side, color in [("left", "#2166AC"), ("right", "#B2182B")]:
    mask = df["running_var"] < cutoff if side == "left" else df["running_var"] >= cutoff
    subset = df[mask].sort_values("running_var")
    if len(subset) > 10:
        z = np.polyfit(subset["running_var"], subset["outcome_var"], 2)
        p = np.poly1d(z)
        x_smooth = np.linspace(subset["running_var"].min(), subset["running_var"].max(), 100)
        ax.plot(x_smooth, p(x_smooth), color=color, linewidth=2)

ax.axvline(x=cutoff, linestyle="--", color="black", linewidth=0.8)
ax.text(cutoff, ax.get_ylim()[1], " Cutoff", va="top")
ax.set_xlabel("Running Variable")
ax.set_ylabel("Outcome")
ax.set_title("Regression Discontinuity")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_01_rdd_scatter.png", dpi=300, bbox_inches="tight")
plt.close()
```

## Synthetic Control: Treated vs Synthetic

```python
# Treated vs synthetic control time series
# WHY: Shows how the treated unit diverges from its counterfactual
# after intervention. The gap IS the estimated treatment effect.

import matplotlib.pyplot as plt

# Adapt: df_plot with columns: time_var, treated_outcome, synthetic_outcome
# intervention_time: when treatment began

fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(df_plot["time_var"], df_plot["treated_outcome"],
        color="#B2182B", linewidth=1.5, label="Treated")
ax.plot(df_plot["time_var"], df_plot["synthetic_outcome"],
        color="#2166AC", linewidth=1.5, linestyle="--", label="Synthetic Control")
ax.axvline(x=intervention_time, linestyle="--", color="gray", alpha=0.7)
ax.text(intervention_time, ax.get_ylim()[1], " Intervention", va="top", color="gray")
ax.set_xlabel("Time")
ax.set_ylabel("Outcome")
ax.set_title("Treated Unit vs Synthetic Control")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_01_sc_time_series.png", dpi=300, bbox_inches="tight")
plt.close()
```

## Matching: Love Plot (Balance)

```python
# Love plot — standardized mean differences before and after matching
# WHY: Shows whether matching successfully reduced covariate imbalance.
# Good balance (SMD < 0.1) supports the selection-on-observables assumption.

import matplotlib.pyplot as plt
import numpy as np

# Adapt: variables (list), smd_before (list), smd_after (list)

fig, ax = plt.subplots(figsize=(8, 6))

y_pos = np.arange(len(variables))
ax.scatter(np.abs(smd_before), y_pos, color="#B2182B", s=60, label="Before", zorder=3)
ax.scatter(np.abs(smd_after), y_pos, color="#2166AC", s=60, label="After", zorder=3)

# Connect before/after with lines
for i in range(len(variables)):
    ax.plot([abs(smd_before[i]), abs(smd_after[i])], [y_pos[i], y_pos[i]],
            color="gray", linewidth=0.5, alpha=0.5)

ax.axvline(x=0.1, linestyle="--", color="gray", alpha=0.7)
ax.text(0.1, len(variables), " SMD = 0.1", va="top", color="gray", fontsize=9)
ax.set_yticks(y_pos)
ax.set_yticklabels(variables)
ax.set_xlabel("|Standardized Mean Difference|")
ax.set_title("Covariate Balance: Before vs After Matching")
ax.legend()
ax.grid(True, alpha=0.3, axis="x")
plt.tight_layout()
plt.savefig("fig_01_love_plot.png", dpi=300, bbox_inches="tight")
plt.close()
```

## Experiments: Effect Plot with CIs

```python
# Effect plot — treatment effect with confidence interval
# WHY: Clear visual of the estimated effect and its uncertainty.
# Helps stakeholders see both the magnitude and precision of the result.

import matplotlib.pyplot as plt
import numpy as np

# Adapt: terms (list), estimates (list), ci_lower (list), ci_upper (list)

fig, ax = plt.subplots(figsize=(8, 4))

y_pos = np.arange(len(terms))
xerr_lower = [est - ci_l for est, ci_l in zip(estimates, ci_lower)]
xerr_upper = [ci_u - est for est, ci_u in zip(estimates, ci_upper)]

ax.errorbar(estimates, y_pos, xerr=[xerr_lower, xerr_upper],
            fmt="o", color="#B2182B", capsize=4, markersize=6)
ax.axvline(x=0, linestyle="--", color="gray", alpha=0.7)
ax.set_yticks(y_pos)
ax.set_yticklabels(terms)
ax.set_xlabel("Estimated Effect")
ax.set_title("Treatment Effect Estimate")
ax.grid(True, alpha=0.3, axis="x")
plt.tight_layout()
plt.savefig("fig_01_effect_plot.png", dpi=300, bbox_inches="tight")
plt.close()
```

## Time Series: Pre/Post with Intervention Line

```python
# Interrupted time series — outcome over time with intervention marker
# WHY: Shows the pre-treatment trend, the intervention moment, and
# the post-treatment trajectory. Visual comparison to the counterfactual.

import matplotlib.pyplot as plt

# Adapt: df with time_var, outcome_var; intervention_time

fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(df["time_var"], df["outcome_var"], color="#2166AC", linewidth=1.5)
ax.axvline(x=intervention_time, linestyle="--", color="#B2182B", linewidth=0.8)
ax.text(intervention_time, ax.get_ylim()[1], " Intervention",
        va="top", color="#B2182B")
ax.set_xlabel("Time")
ax.set_ylabel("Outcome")
ax.set_title("Interrupted Time Series")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_01_its_timeseries.png", dpi=300, bbox_inches="tight")
plt.close()
```

## HTE: CATE Distribution

```python
# CATE distribution — histogram of individual treatment effects
# WHY: Shows treatment effect heterogeneity. A wide distribution means
# the effect varies substantially across units — personalization may be valuable.

import matplotlib.pyplot as plt
import numpy as np

# Adapt: cate_values is a numpy array of estimated CATEs

fig, ax = plt.subplots(figsize=(8, 5))

ax.hist(cate_values, bins=40, color="#2166AC", edgecolor="white", alpha=0.8)
ax.axvline(x=np.mean(cate_values), linestyle="--", color="#B2182B", linewidth=1.5)
ax.text(np.mean(cate_values), ax.get_ylim()[1],
        f" ATE = {np.mean(cate_values):.3f}", va="top", color="#B2182B")
ax.set_xlabel("Conditional Average Treatment Effect (CATE)")
ax.set_ylabel("Count")
ax.set_title("Distribution of Heterogeneous Treatment Effects")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("fig_01_cate_distribution.png", dpi=300, bbox_inches="tight")
plt.close()
```
