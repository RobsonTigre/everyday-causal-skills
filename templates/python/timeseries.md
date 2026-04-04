# Time Series Causal Inference — Python Template

## Prerequisites

```python
# Install (if needed)
# pip install pandas numpy matplotlib seaborn causalimpact statsmodels

# Import
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
```

## Data Preparation

```python
# --- Load your data ---
# df should have columns: date, outcome
# For CausalImpact: also include control time series (covariates not affected by treatment)
# date: datetime index
# outcome: the response variable (e.g., sales, visits, metric of interest)

# Ensure date is datetime and set as index
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date").sort_index()

# Define pre- and post-intervention periods
pre_start = "2020-01-01"
pre_end = "2020-06-30"
post_start = "2020-07-01"
post_end = "2020-12-31"

pre_period = [pre_start, pre_end]
post_period = [post_start, post_end]

print(f"Pre-treatment:  {pre_start} to {pre_end} ({len(df[pre_start:pre_end])} obs)")
print(f"Post-treatment: {post_start} to {post_end} ({len(df[post_start:post_end])} obs)")
```

## Estimation — CausalImpact

```python
# CausalImpact uses a Bayesian structural time series model
# Columns: outcome (first column), control series (remaining columns)
from causalimpact import CausalImpact

# data should be a DataFrame with outcome as first column, controls as additional columns
# Example: data = df[["outcome", "control1", "control2"]]
data = df[["outcome", "control1", "control2"]]

ci = CausalImpact(data, pre_period, post_period)

# Print the summary report
print(ci.summary())
print(ci.summary(output="report"))

# Extract numerical results
point_effect = ci.summary_data["average"]["abs_effect"]
ci_lower = ci.summary_data["average"]["abs_effect_lower"]
ci_upper = ci.summary_data["average"]["abs_effect_upper"]
cum_effect = ci.summary_data["cumulative"]["abs_effect"]
p_value = ci.summary_data["average"]["p"]

print(f"\n=== Key Results ===")
print(f"Average causal effect: {point_effect:.4f}")
print(f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"Cumulative effect: {cum_effect:.4f}")
print(f"Posterior tail-area prob (p): {p_value:.4f}")
```

## Estimation — Segmented Regression (Interrupted Time Series)

```python
# Alternative: segmented regression / interrupted time series analysis
# Useful when no control series is available

df_its = df[["outcome"]].copy()
df_its = df_its.reset_index()
df_its["time"] = range(len(df_its))  # Linear time trend

# Intervention indicators
intervention_date = pd.Timestamp(post_start)
df_its["post"] = (df_its["date"] >= intervention_date).astype(int)
df_its["time_since"] = np.where(
    df_its["post"] == 1,
    (df_its["date"] - intervention_date).dt.days,
    0
)

# Segmented regression: outcome ~ time + post + time_since
its_model = smf.ols("outcome ~ time + post + time_since", data=df_its).fit(
    cov_type="HAC", cov_kwds={"maxlags": 4}  # Newey-West HAC standard errors
)
print("=== Segmented Regression (ITS) ===")
print(its_model.summary())

# Key coefficients:
# post = immediate level shift at intervention
# time_since = change in trend after intervention
level_shift = its_model.params["post"]
trend_change = its_model.params["time_since"]
print(f"\nImmediate level shift: {level_shift:.4f} (p = {its_model.pvalues['post']:.4f})")
print(f"Trend change: {trend_change:.4f} (p = {its_model.pvalues['time_since']:.4f})")
```

## Diagnostics — Residual Analysis

```python
# Check ITS model residuals for autocorrelation
residuals = its_model.resid

# Durbin-Watson test (2.0 = no autocorrelation)
from statsmodels.stats.stattools import durbin_watson
dw = durbin_watson(residuals)
print(f"Durbin-Watson statistic: {dw:.4f} (values near 2.0 suggest no autocorrelation)")

# Ljung-Box test for autocorrelation at multiple lags
from statsmodels.stats.diagnostic import acorr_ljungbox
lb_test = acorr_ljungbox(residuals, lags=[4, 8, 12], return_df=True)
print("\n=== Ljung-Box Test ===")
print(lb_test)

# ACF/PACF of residuals
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sm.graphics.tsa.plot_acf(residuals, ax=axes[0], lags=20, title="ACF of Residuals")
sm.graphics.tsa.plot_pacf(residuals, ax=axes[1], lags=20, title="PACF of Residuals")
plt.tight_layout()
plt.savefig("its_residual_diagnostics.png", dpi=150)
plt.show()
```

## Diagnostics — Pre-Intervention Fit

```python
# Check model fit in the pre-period
pre_mask = df_its["date"] < intervention_date
pre_residuals = residuals[pre_mask]

print(f"Pre-intervention residual std: {pre_residuals.std():.4f}")
print(f"Pre-intervention residual mean: {pre_residuals.mean():.4f}")

# Normality test on pre-period residuals
shapiro_stat, shapiro_p = stats.shapiro(pre_residuals[:min(len(pre_residuals), 5000)])
print(f"Shapiro-Wilk normality test: W = {shapiro_stat:.4f}, p = {shapiro_p:.4f}")
```

## Results Table

```python
results_table = pd.DataFrame({
    "Method": ["CausalImpact (avg)", "CausalImpact (cum)", "ITS level shift", "ITS trend change"],
    "Estimate": [point_effect, cum_effect, level_shift, trend_change],
    "CI Lower": [ci_lower, np.nan, its_model.conf_int().loc["post", 0], its_model.conf_int().loc["time_since", 0]],
    "CI Upper": [ci_upper, np.nan, its_model.conf_int().loc["post", 1], its_model.conf_int().loc["time_since", 1]],
    "p-value": [p_value, np.nan, its_model.pvalues["post"], its_model.pvalues["time_since"]],
})
print("=== Results Summary ===")
print(results_table.to_string(index=False, float_format="%.4f"))
```

## Visualization

```python
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# --- Panel 1: CausalImpact plot (manual reconstruction) ---
ax = axes[0, 0]
ci.plot(panels=["original"], ax=ax)
ax.set_title("CausalImpact: Observed vs. Predicted")

# --- Panel 2: CausalImpact point effects ---
ax = axes[0, 1]
ci.plot(panels=["pointwise"], ax=ax)
ax.set_title("CausalImpact: Pointwise Effect")

# --- Panel 3: ITS segmented regression ---
ax = axes[1, 0]
ax.scatter(df_its["date"], df_its["outcome"], s=8, alpha=0.5, color="gray", label="Observed")

# Fitted values
df_its["fitted"] = its_model.fittedvalues
pre_fit = df_its[df_its["post"] == 0]
post_fit = df_its[df_its["post"] == 1]
ax.plot(pre_fit["date"], pre_fit["fitted"], color="steelblue", linewidth=2, label="Pre-trend")
ax.plot(post_fit["date"], post_fit["fitted"], color="coral", linewidth=2, label="Post-trend")

# Counterfactual: extend pre-trend into post-period
df_its["counterfactual"] = its_model.params["Intercept"] + its_model.params["time"] * df_its["time"]
ax.plot(post_fit["date"], df_its.loc[df_its["post"] == 1, "counterfactual"],
        color="steelblue", linewidth=1.5, linestyle="--", label="Counterfactual")

ax.axvline(intervention_date, color="red", linestyle=":", linewidth=1, label="Intervention")
ax.set_xlabel("Date")
ax.set_ylabel("Outcome")
ax.set_title("Interrupted Time Series")
ax.legend(fontsize=8)
sns.despine(ax=ax)

# --- Panel 4: Pre/post distributions ---
ax = axes[1, 1]
pre_outcomes = df.loc[:pre_end, "outcome"]
post_outcomes = df.loc[post_start:, "outcome"]
ax.hist(pre_outcomes, bins=25, alpha=0.5, color="steelblue", density=True, label="Pre")
ax.hist(post_outcomes, bins=25, alpha=0.5, color="coral", density=True, label="Post")
ax.set_xlabel("Outcome")
ax.set_ylabel("Density")
ax.set_title("Outcome Distribution: Pre vs. Post")
ax.legend()
sns.despine(ax=ax)

plt.tight_layout()
plt.savefig("timeseries_causal.png", dpi=150)
plt.show()
```
