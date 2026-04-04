# Assumption Checklist: Interrupted Time Series / CausalImpact

Reference: `references/method-registry.md` → Interrupted Time Series / CausalImpact

---

## No Concurrent Confounding Events

**Plain language**: Nothing else happened at the same time as the treatment that could explain the change in the outcome. If you launched a new ad campaign during Black Friday, you can't tell whether the sales spike was from the campaign or from Black Friday.

**Formal statement**: There are no unobserved shocks or interventions at the treatment time that also affect the outcome. Formally, the only discontinuity in the data-generating process at the treatment date is the treatment itself: E[Y_t(0) | t >= T_0] follows the same model as E[Y_t(0) | t < T_0], where T_0 is the intervention date and Y(0) is the untreated potential outcome.

**Testable?**: No. You cannot rule out concurrent events from data alone. This must be argued through knowledge of the context — investigating what else happened around the treatment date.

**How to test**:

While untestable statistically, these checks help build the case:

R:
```r
library(CausalImpact)

# 1. Placebo intervention test: apply the analysis to a date where
#    no treatment occurred. If a "treatment effect" appears, the model
#    is picking up noise or confounders.
pre_period_placebo <- c(start_date, placebo_date - 1)
post_period_placebo <- c(placebo_date, treatment_date - 1)

impact_placebo <- CausalImpact(ts_data, pre_period_placebo,
                                post_period_placebo)
summary(impact_placebo)
plot(impact_placebo)
# A significant placebo effect suggests the model is unreliable
# or confounders are present.

# 2. Include control time series that were NOT affected by treatment
#    (CausalImpact does this automatically if provided)
# The more control series you include, the better you can absorb
# concurrent shocks that affect both treated and control series.
```

Python:
```python
from causalimpact import CausalImpact

# 1. Placebo test at a fake intervention date
data_placebo = df[df['date'] < treatment_date].copy()
placebo_date = data_placebo['date'].median()  # midpoint of pre-period

ci_placebo = CausalImpact(
    data_placebo[['outcome', 'control1', 'control2']],
    pre_period=[data_placebo['date'].min(), placebo_date],
    post_period=[placebo_date + 1, data_placebo['date'].max()]
)
print(ci_placebo.summary())
ci_placebo.plot()

# 2. Check: does the control series pick up the same concurrent
#    events? If yes, CausalImpact can partial them out.
```

**What violation looks like**: A major event (recession, competitor action, seasonality, holiday, regulation) coincides with the treatment date. The treatment effect disappears when you include a control series that captures the concurrent event. Placebo tests at other dates also show "significant" effects.

**Severity if violated**: Fatal. If a concurrent event explains the outcome change, the estimated treatment effect is confounded. There is no way to separate the treatment effect from the confounder effect using a single interrupted time series.

**Mitigation**: (1) Include control time series that are affected by the concurrent events but NOT by the treatment. CausalImpact's Bayesian structural time series model uses these controls to absorb confounding shocks. (2) Document all known events around the treatment date and assess their likely impact. (3) Run placebo tests at dates with known concurrent events to see if the model handles them. (4) If no good control series exists and concurrent events are plausible, acknowledge this as a major limitation.

---

## Pre-Treatment Model Fit

**Plain language**: The statistical model you're using captures the patterns in your data before the treatment happened. If the model can't predict the pre-treatment outcomes well, there's no reason to trust its counterfactual prediction after treatment.

**Formal statement**: The fitted model M closely approximates the true data-generating process in the pre-treatment period. For CausalImpact, the one-step-ahead prediction errors in the pre-treatment period are small and well-behaved (white noise). Formally: MAPE_pre = (1/T_0) * sum(|Y_t - Yhat_t| / |Y_t|) is small, and residuals are approximately iid normal.

**Testable?**: Yes. Check model fit statistics and residual diagnostics in the pre-treatment period.

**How to test**:

R:
```r
library(CausalImpact)

# Run CausalImpact
pre_period <- c(start_date, treatment_date - 1)
post_period <- c(treatment_date, end_date)

impact <- CausalImpact(ts_data, pre_period, post_period)

# 1. Check pre-period fit visually
plot(impact)
# The first panel shows observed vs predicted. In the pre-period,
# the predicted (blue) line should closely track the observed (black).

# 2. Extract pre-period prediction errors
pre_data <- impact$series[index(impact$series) < treatment_date, ]
pre_residuals <- pre_data$response - pre_data$point.pred

# MAPE
mape <- mean(abs(pre_residuals / pre_data$response), na.rm = TRUE) * 100
cat("Pre-period MAPE:", round(mape, 2), "%\n")
# Rule of thumb: MAPE < 5% is good, < 10% is acceptable

# 3. Residual diagnostics
# Autocorrelation
acf(pre_residuals, main = "ACF of Pre-Period Residuals")

# Ljung-Box test for autocorrelation
Box.test(pre_residuals, lag = 10, type = "Ljung-Box")
# p > 0.05: residuals are white noise (good)

# Normality
shapiro.test(pre_residuals)
```

Python:
```python
from causalimpact import CausalImpact
import numpy as np
from statsmodels.stats.diagnostic import acorr_ljungbox
from scipy.stats import shapiro

# Run CausalImpact
ci = CausalImpact(
    data[['outcome', 'control1', 'control2']],
    pre_period=[start_date, treatment_date - 1],
    post_period=[treatment_date, end_date]
)

# 1. Visual check
ci.plot()

# 2. Pre-period residuals
pre_mask = data.index < treatment_date
pre_observed = data.loc[pre_mask, 'outcome']
pre_predicted = ci.inferences.loc[pre_mask, 'point_pred']
pre_residuals = pre_observed - pre_predicted

# MAPE
mape = np.mean(np.abs(pre_residuals / pre_observed)) * 100
print(f"Pre-period MAPE: {mape:.2f}%")

# 3. Ljung-Box test for autocorrelation
lb_test = acorr_ljungbox(pre_residuals.dropna(), lags=10, return_df=True)
print(lb_test)

# 4. Normality test
stat, p = shapiro(pre_residuals.dropna())
print(f"Shapiro-Wilk test: stat = {stat:.4f}, p = {p:.4f}")
```

**What violation looks like**: The model's predicted values diverge from the actual pre-treatment outcomes. High MAPE (> 10%) in the pre-period. Residuals show strong autocorrelation (significant Ljung-Box test) or non-normality. The pre-period confidence bands are wide, indicating the model is uncertain even in the period it was trained on.

**Severity if violated**: Serious. Poor pre-treatment fit means the counterfactual prediction is unreliable. The model may over- or underestimate what would have happened without treatment, leading to biased effect estimates. Wide confidence bands may also mean you cannot detect any effect.

**Mitigation**: (1) Include more or better control time series (these are the most important predictors in CausalImpact). (2) Use a longer pre-treatment period to give the model more data to learn patterns. (3) Try different model specifications (e.g., add seasonal components, adjust the number of lags). (4) For ITS without controls, consider ARIMA-based methods (`CausalArima`) that can capture more complex temporal patterns. (5) If pre-treatment fit remains poor, the model is not reliable — acknowledge the uncertainty.

---

## Stationarity

**Plain language**: The statistical properties of the time series (its average level, variance, and autocorrelation structure) don't change over time — or if they do, you've handled it properly (e.g., by differencing). Non-stationary series (trending, random walks) can produce spurious "treatment effects."

**Formal statement**: The pre-treatment time series {Y_t : t < T_0} is weakly stationary (or has been transformed to be stationary): E[Y_t] = mu and Cov(Y_t, Y_{t+h}) = gamma(h) for all t. If the series has a unit root, it should be differenced before modeling. CausalImpact handles this internally with a local linear trend component, but explicit checking is still recommended.

**Testable?**: Yes. Unit root tests (ADF, KPSS, Phillips-Perron) directly test for stationarity.

**How to test**:

R:
```r
library(tseries)

# Augmented Dickey-Fuller test
# H0: series has a unit root (non-stationary)
# H1: series is stationary
adf_test <- adf.test(ts_data$outcome[1:pre_period_end])
cat("ADF test statistic:", adf_test$statistic, "\n")
cat("p-value:", adf_test$p.value, "\n")
# p < 0.05: reject H0 → series is stationary (good)
# p > 0.05: fail to reject → series may have a unit root

# KPSS test (complementary: H0 is stationarity)
kpss_test <- kpss.test(ts_data$outcome[1:pre_period_end])
cat("KPSS test statistic:", kpss_test$statistic, "\n")
cat("p-value:", kpss_test$p.value, "\n")
# p > 0.05: fail to reject → series is stationary (good)
# p < 0.05: reject → series is non-stationary

# Visual check
plot(ts_data$outcome, main = "Outcome Time Series",
     ylab = "Outcome", xlab = "Time")
acf(ts_data$outcome[1:pre_period_end], main = "ACF of Pre-Period")

# If non-stationary, first-difference
if (adf_test$p.value > 0.05) {
  diff_series <- diff(ts_data$outcome)
  adf_diff <- adf.test(diff_series[1:(pre_period_end - 1)])
  cat("ADF on differenced series p-value:", adf_diff$p.value, "\n")
}
```

Python:
```python
from statsmodels.tsa.stattools import adfuller, kpss
import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf

pre_series = df.loc[df['date'] < treatment_date, 'outcome'].values

# ADF test
adf_result = adfuller(pre_series, autolag='AIC')
print(f"ADF statistic: {adf_result[0]:.4f}")
print(f"ADF p-value: {adf_result[1]:.4f}")
# p < 0.05 → stationary

# KPSS test
kpss_result = kpss(pre_series, regression='c', nlags='auto')
print(f"KPSS statistic: {kpss_result[0]:.4f}")
print(f"KPSS p-value: {kpss_result[1]:.4f}")
# p > 0.05 → stationary

# Visual check
fig, axes = plt.subplots(2, 1, figsize=(12, 8))
axes[0].plot(pre_series)
axes[0].set_title('Pre-Treatment Outcome Series')
axes[0].set_ylabel('Outcome')
plot_acf(pre_series, ax=axes[1], title='ACF of Pre-Period')
plt.tight_layout()
plt.show()

# If non-stationary, difference the series
import numpy as np
if adf_result[1] > 0.05:
    diff_series = np.diff(pre_series)
    adf_diff = adfuller(diff_series, autolag='AIC')
    print(f"ADF on differenced series: p = {adf_diff[1]:.4f}")
```

**What violation looks like**: The time series has a clear upward or downward trend (not mean-reverting). The ADF test fails to reject the unit root null. The KPSS test rejects stationarity. The ACF decays very slowly (characteristic of non-stationary series). A random walk can produce apparent "breaks" that look like treatment effects but are just noise.

**Severity if violated**: Serious. Non-stationary series can produce spurious treatment effects. If the series is trending, any post-treatment observations will mechanically differ from pre-treatment observations, and the model may misattribute the trend to the treatment. CausalImpact partially handles this with its local linear trend component, but explicit checking is still important.

**Mitigation**: (1) Difference the series if it has a unit root. (2) CausalImpact's built-in structural time series model includes a local linear trend component that can accommodate some non-stationarity — but verify that it does so adequately via pre-period fit. (3) For ARIMA-based ITS, use the appropriate order of integration (d parameter). (4) Include control series that share the same non-stationary behavior (trends, common shocks) — CausalImpact can model cointegrated series. (5) Consider log-transforming if the series shows increasing variance over time.

---

## Adequate Pre-Period Length

**Plain language**: You need enough pre-treatment data for the model to learn the patterns in your time series — seasonality, trends, and the relationship with control series. Too few observations, and the model is guessing rather than learning.

**Formal statement**: The pre-treatment period length T_0 is sufficient for reliable estimation of the model parameters. For CausalImpact: T_0 >= 3 * season_length (e.g., 3 years of monthly data for annual seasonality). As a general guideline: T_0 >= 30-50 observations for basic models, more for seasonal patterns.

**Testable?**: Yes. Count observations and compare to the minimum needed for your model.

**How to test**:

R:
```r
# Count pre-treatment observations
n_pre <- sum(index(ts_data) < treatment_date)
cat("Pre-treatment observations:", n_pre, "\n")

# Assess relative to model needs
frequency <- frequency(ts_data)  # e.g., 12 for monthly, 52 for weekly
cat("Data frequency:", frequency, "\n")
cat("Seasons of data:", n_pre / frequency, "\n")

# Guidelines:
# - Minimum: 30 observations (for basic models)
# - Recommended: 50+ observations
# - For seasonal data: at least 3 full seasonal cycles
#   (e.g., 36 months for monthly data with annual seasonality)
# - For CausalImpact with controls: at least 50 observations

if (n_pre < 30) {
  cat("WARNING: Pre-period is very short (< 30). Model may be unreliable.\n")
} else if (n_pre < 50) {
  cat("CAUTION: Pre-period is short (30-50). Results may be imprecise.\n")
} else {
  cat("OK: Pre-period length appears adequate.\n")
}

# Additional check: is the pre-period long enough to capture seasonality?
if (frequency > 1 && n_pre < 3 * frequency) {
  cat("WARNING: Pre-period does not cover 3 full seasonal cycles.\n")
  cat("Seasonal patterns may not be properly estimated.\n")
}
```

Python:
```python
import pandas as pd

# Count pre-treatment observations
pre_data = df[df['date'] < treatment_date]
n_pre = len(pre_data)
print(f"Pre-treatment observations: {n_pre}")

# Assess frequency (infer from data)
if hasattr(df['date'], 'dt'):
    date_diffs = df['date'].diff().dropna()
    median_diff = date_diffs.median()
    if median_diff <= pd.Timedelta(days=1):
        freq = 'daily'
        season_length = 365
    elif median_diff <= pd.Timedelta(days=7):
        freq = 'weekly'
        season_length = 52
    elif median_diff <= pd.Timedelta(days=31):
        freq = 'monthly'
        season_length = 12
    else:
        freq = 'other'
        season_length = None

    print(f"Data frequency: {freq}")
    if season_length:
        print(f"Seasonal cycles covered: {n_pre / season_length:.1f}")

# Guidelines
if n_pre < 30:
    print("WARNING: Pre-period is very short (< 30). Model may be unreliable.")
elif n_pre < 50:
    print("CAUTION: Pre-period is short (30-50). Results may be imprecise.")
else:
    print("OK: Pre-period length appears adequate.")

if season_length and n_pre < 3 * season_length:
    print("WARNING: Pre-period does not cover 3 full seasonal cycles.")
```

**What violation looks like**: Fewer than 30 pre-treatment observations. Wide confidence intervals on the treatment effect (the model is too uncertain). Pre-treatment model fit is poor because the model didn't have enough data to learn the patterns. Seasonal patterns are not captured because the pre-period doesn't cover full seasonal cycles.

**Severity if violated**: Serious. With too few pre-treatment observations, the model parameters are imprecise, the counterfactual is unreliable, and the confidence intervals are so wide that you may not detect a genuine effect. The analysis lacks statistical power.

**Mitigation**: (1) Use higher-frequency data if available (daily instead of weekly, weekly instead of monthly) to increase the number of observations. (2) Extend the pre-treatment window further back in time if data exists. (3) Use simpler models with fewer parameters (fewer control series, simpler trend components) to reduce the data demands. (4) If the pre-period is truly too short, acknowledge that the analysis is underpowered and interpret results as suggestive rather than definitive. (5) Consider complementary methods (DiD, before-after comparison with controls) that may require fewer time periods.
