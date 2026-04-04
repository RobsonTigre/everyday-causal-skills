# Assumption Checklist: Difference-in-Differences

Reference: `references/method-registry.md` → Difference-in-Differences

---

## Parallel Trends

**Plain language**: Without treatment, treated and control groups would have followed similar trends over time. The gap between groups might differ in level, but the trajectory would have been the same.

**Formal statement**: E[Y(0)_t - Y(0)_{t-1} | D=1] = E[Y(0)_t - Y(0)_{t-1} | D=0] for all post-treatment periods t, where Y(0) denotes the untreated potential outcome and D indicates treatment group membership.

**Testable?**: Partially. You can check whether trends were parallel in the pre-treatment period, but you cannot verify that they would have remained parallel after treatment. Pre-treatment parallel trends are necessary but not sufficient.

**How to test**:

R:
```r
library(fixest)

# Create time-to-treatment variable
# (for staggered: relative to each unit's treatment date)
# (for classic: relative to the single treatment date)
df$time_to_treat <- df$time - df$treatment_date

# Event study specification
es <- feols(outcome ~ i(time_to_treat, ref = -1) | unit + time,
            data = df, cluster = ~unit)

# Visual diagnostic: pre-treatment coefficients should be near zero
iplot(es, main = "Event Study: Pre-Trends Check",
      xlab = "Periods Relative to Treatment")

# Joint test of pre-treatment coefficients
# H0: all pre-treatment coefficients = 0
pre_coefs <- coef(es)[grep("time_to_treat::-", names(coef(es)))]
wald(es, keep = "time_to_treat::-")
```

Python:
```python
import pandas as pd
import numpy as np
from linearmodels.panel import PanelOLS
import matplotlib.pyplot as plt

# Create time-to-treatment dummies (exclude t = -1 as reference)
df['time_to_treat'] = df['time'] - df['treatment_date']
periods = sorted(df['time_to_treat'].unique())
periods = [p for p in periods if p != -1]  # drop reference period

for p in periods:
    df[f'ttp_{p}'] = (df['time_to_treat'] == p).astype(int)

# Event study regression with entity and time fixed effects
ttp_cols = [f'ttp_{p}' for p in periods]
formula = 'outcome ~ ' + ' + '.join(ttp_cols) + ' + EntityEffects + TimeEffects'
mod = PanelOLS.from_formula(formula, data=df.set_index(['unit', 'time']))
res = mod.fit(cov_type='clustered', cluster_entity=True)

# Plot coefficients
coefs = [res.params[f'ttp_{p}'] for p in periods]
ci_lower = [res.conf_int().loc[f'ttp_{p}', 'lower'] for p in periods]
ci_upper = [res.conf_int().loc[f'ttp_{p}', 'upper'] for p in periods]

plt.figure(figsize=(10, 6))
plt.errorbar(periods, coefs, yerr=[np.array(coefs) - np.array(ci_lower),
             np.array(ci_upper) - np.array(coefs)], fmt='o-', capsize=3)
plt.axhline(y=0, color='red', linestyle='--')
plt.axvline(x=-0.5, color='gray', linestyle=':')
plt.xlabel('Periods Relative to Treatment')
plt.ylabel('Coefficient')
plt.title('Event Study: Pre-Trends Check')
plt.tight_layout()
plt.show()
```

**What violation looks like**: Pre-treatment event study coefficients that are statistically different from zero, or that show a clear trend (increasing or decreasing) in the pre-period. A diverging pre-trend between treated and control groups visible in raw outcome plots.

**Severity if violated**: Fatal. If trends were not parallel before treatment, DiD attributes the pre-existing trend difference to the treatment effect, producing biased estimates.

**Mitigation**: (1) Use matching or reweighting to find a control group with more similar pre-trends. (2) Add group-specific linear time trends (though this is controversial and can absorb the treatment effect). (3) Use a triple-difference (DDD) design if a within-group control is available. (4) Consider synthetic control, which explicitly optimizes for pre-treatment fit. (5) If pre-trends are clearly diverging, acknowledge that DiD is not credible and choose a different method.

---

## No Anticipation

**Plain language**: Units don't change their behavior before the treatment actually starts. If a policy takes effect in January, people aren't already reacting to it in November or December.

**Formal statement**: E[Y_t(g) | G=g] = E[Y_t(0) | G=g] for all t < g, where g is the treatment adoption date and Y_t(g) is the potential outcome at time t under treatment at time g. In words: the potential outcome before treatment is the same whether or not the unit will eventually be treated.

**Testable?**: Partially. Check whether the event study coefficients at t = -2, -3, etc. are zero (same diagnostic as pre-trends). Anticipation often appears as a ramp-up in the event study just before treatment.

**How to test**:

R:
```r
library(fixest)

# Same event study as parallel trends — look specifically at
# coefficients just before treatment (t = -2, -3)
es <- feols(outcome ~ i(time_to_treat, ref = -1) | unit + time,
            data = df, cluster = ~unit)

# Check: are coefficients at t = -2, -3 significantly different from zero?
summary(es)
# Look at the pre-treatment coefficients — anticipation shows as
# significant positive/negative effects just before t = 0

# If anticipation is suspected, shift the reference period
es_alt <- feols(outcome ~ i(time_to_treat, ref = -3) | unit + time,
                data = df, cluster = ~unit)
iplot(es_alt)
```

Python:
```python
# Use the same event study from the parallel trends test above.
# Inspect the coefficients at t = -2, t = -3, etc.
# If they are significantly different from zero and trending toward
# the post-treatment direction, anticipation is likely.

for p in [-3, -2]:
    col = f'ttp_{p}'
    if col in res.params.index:
        print(f"t = {p}: coef = {res.params[col]:.4f}, "
              f"p-value = {res.pvalues[col]:.4f}")
```

**What violation looks like**: Event study coefficients at t = -2 or t = -3 that are significant and in the same direction as the post-treatment effect. A "ramp-up" pattern before the treatment date. For example, if a new regulation was announced months before implementation, firms may have adjusted early.

**Severity if violated**: Serious. Anticipation effects bias the DiD estimate (the treatment effect bleeds into the pre-period, making both the pre-trend test unreliable and the post-treatment estimate too small). In the Callaway-Sant'Anna framework, this also contaminates the group-time ATT estimates.

**Mitigation**: (1) Redefine the treatment date to when units first learned about the treatment (announcement date rather than implementation date). (2) In the `did` package, use the `anticipation` parameter: `att_gt(..., anticipation = k)` to allow k periods of anticipation. (3) Drop the periods immediately before treatment from the analysis. (4) If anticipation is inherent to the treatment (e.g., stock market reactions to policy announcements), acknowledge it and reinterpret the estimand.

---

## Stable Composition

**Plain language**: The units in your sample don't enter or leave because of the treatment. If a policy causes some businesses to shut down, those businesses disappear from the data, and your remaining sample is no longer comparable.

**Formal statement**: The composition of the treatment and control groups remains stable over time. Formally, P(Unit i observed at time t | D_i = d) does not depend on the treatment for any post-treatment time t.

**Testable?**: Yes. Check whether the panel is balanced and whether attrition/entry differs by treatment status.

**How to test**:

R:
```r
# Check panel balance
panel_balance <- df |>
  dplyr::group_by(unit) |>
  dplyr::summarize(n_periods = dplyr::n_distinct(time),
                   treated = max(treatment)) |>
  dplyr::group_by(treated) |>
  dplyr::summarize(
    n_units = dplyr::n(),
    mean_periods = mean(n_periods),
    min_periods = min(n_periods),
    max_periods = max(n_periods),
    fully_observed = sum(n_periods == max(df$time) - min(df$time) + 1)
  )
print(panel_balance)

# Check for differential attrition: do treated units drop out more?
total_periods <- length(unique(df$time))
attrition <- df |>
  dplyr::group_by(unit) |>
  dplyr::summarize(
    treated = max(treatment),
    observed_periods = dplyr::n_distinct(time),
    attrited = observed_periods < total_periods
  )

# Compare attrition rates
table(attrition$treated, attrition$attrited)
chisq.test(table(attrition$treated, attrition$attrited))
```

Python:
```python
import pandas as pd
from scipy.stats import chi2_contingency

# Check panel balance
total_periods = df['time'].nunique()

panel_balance = (df.groupby('unit')
    .agg(n_periods=('time', 'nunique'), treated=('treatment', 'max'))
    .reset_index())

panel_balance['attrited'] = panel_balance['n_periods'] < total_periods

# Compare attrition rates by treatment status
attrition_table = pd.crosstab(panel_balance['treated'],
                               panel_balance['attrited'])
print(attrition_table)

chi2, p, _, _ = chi2_contingency(attrition_table)
print(f"Chi-squared test: chi2 = {chi2:.3f}, p = {p:.4f}")
```

**What violation looks like**: Unbalanced panel where treated units have fewer observed periods. Attrition rates that differ significantly between treatment and control groups. A sudden drop in sample size after treatment onset for the treated group.

**Severity if violated**: Serious. Differential attrition creates survivorship bias. If the weakest treated units drop out, the estimated effect is biased upward (you only observe the "survivors"). If the treatment causes entry of new units, the composition of the treated group changes.

**Mitigation**: (1) Restrict analysis to a balanced panel (units observed in all periods). (2) Use Lee bounds to estimate the range of effects under worst-case attrition assumptions. (3) Test whether attriters differ from non-attriters on pre-treatment characteristics. (4) If attrition is severe and differential, acknowledge the threat and bound the estimates rather than point-estimating.

---

## No Spillovers (SUTVA)

**Plain language**: Treated units don't affect control units' outcomes. If your treatment group gets a discount, that shouldn't change the behavior of control group customers (e.g., through word-of-mouth, competition effects, or market-level price changes).

**Formal statement**: The Stable Unit Treatment Value Assumption (SUTVA) requires that the potential outcome for unit i depends only on its own treatment status, not on the treatment status of other units. Formally: Y_i(D_1, ..., D_N) = Y_i(D_i) for all i.

**Testable?**: No. SUTVA is generally untestable because we cannot observe the counterfactual of what would have happened to control units in the absence of any treated units.

**How to test**:

While SUTVA is untestable, you can look for suggestive evidence:

R:
```r
# Suggestive test: check if control units near treated units
# behave differently from control units far from treated units
# (requires geographic or network distance data)

# Example: compare control units by proximity to treated units
library(fixest)

# If you have a distance/proximity variable
model_spillover <- feols(outcome ~ post:distance_to_treated | unit + time,
                         data = df[df$treated == 0, ], cluster = ~unit)
summary(model_spillover)

# If spillover exists: control units closer to treated units
# show different post-treatment outcomes
```

Python:
```python
import statsmodels.formula.api as smf

# Suggestive test: among control units, check if those "close" to
# treated units behave differently after treatment
control_df = df[df['treated'] == 0].copy()

model = smf.ols('outcome ~ post * distance_to_treated', data=control_df).fit(
    cov_type='cluster', cov_kwds={'groups': control_df['unit']})
print(model.summary())
```

**What violation looks like**: Control group outcomes that shift after treatment onset, especially for control units geographically or socially proximate to treated units. Market-level effects that depress or inflate control group outcomes (e.g., treated firms stealing customers from control firms).

**Severity if violated**: Fatal. If treatment spills over to control units, the control group no longer represents the untreated counterfactual. This biases the DiD estimate — typically toward zero if spillovers make control units look more like treated units, or away from zero if they create competitive displacement.

**Mitigation**: None that fully solves the problem. (1) Use control units that are geographically or socially distant from treated units. (2) Model spillovers explicitly if you have distance/network data. (3) Use a different estimand that accounts for interference (e.g., partial identification under interference). (4) If spillovers are inherent to the treatment mechanism, DiD may not be the right method — consider synthetic control with donors from unaffected markets.

---

## Correct Functional Form

**Plain language**: For staggered adoption designs, the standard two-way fixed effects (TWFE) regression can give biased and even wrong-signed estimates when the treatment effect varies across groups or over time. This happens because TWFE uses already-treated units as implicit controls for later-treated units, creating "forbidden comparisons."

**Formal statement**: In the standard TWFE specification Y_it = alpha_i + gamma_t + beta * D_it + epsilon_it, the coefficient beta is a weighted average of group-time treatment effects where some weights can be negative. When treatment effects are heterogeneous across cohorts or dynamic over time, beta can be a biased estimate of the ATT, including being the wrong sign (Goodman-Bacon 2021, de Chaisemartin & D'Haultfoeuille 2020).

**Testable?**: Yes. Compare the TWFE estimate to a robust heterogeneity-aware estimator. If they differ substantially, TWFE is biased.

**How to test**:

R:
```r
library(fixest)
library(did)

# Standard TWFE (potentially biased under heterogeneity)
twfe <- feols(outcome ~ treatment | unit + time,
              data = df, cluster = ~unit)
cat("TWFE estimate:", coef(twfe)["treatment"], "\n")

# Robust estimator: Callaway & Sant'Anna (2021)
cs <- att_gt(yname = "outcome", tname = "time", idname = "unit",
             gname = "first_treat", data = df)
agg_cs <- aggte(cs, type = "simple")
cat("Callaway-Sant'Anna ATT:", agg_cs$overall.att, "\n")

# Robust estimator: Sun & Abraham (2021) via fixest
sa <- feols(outcome ~ sunab(first_treat, time) | unit + time,
            data = df, cluster = ~unit)
summary(sa)

# Compare: if TWFE and robust estimates differ, TWFE is biased
```

Python:
```python
from linearmodels.panel import PanelOLS
# Note: for robust staggered DiD in Python, use the `csdid` or
# `differences` package

# Standard TWFE
df_panel = df.set_index(['unit', 'time'])
twfe = PanelOLS.from_formula(
    'outcome ~ treatment + EntityEffects + TimeEffects',
    data=df_panel)
twfe_res = twfe.fit(cov_type='clustered', cluster_entity=True)
print(f"TWFE estimate: {twfe_res.params['treatment']:.4f}")

# Robust estimator (using differences package if available)
# pip install differences
try:
    from differences import ATTgt
    att = ATTgt(data=df, cohort_name='first_treat', time_name='time',
                unit_name='unit', outcome_name='outcome')
    att.fit()
    print(f"Callaway-Sant'Anna ATT: {att.aggregate('simple')}")
except ImportError:
    print("Install `differences` for robust staggered DiD: pip install differences")
```

**What violation looks like**: The TWFE estimate and the robust estimator give substantially different point estimates. In extreme cases, TWFE gives a positive estimate when the true effect is negative (or vice versa). The Goodman-Bacon decomposition shows large negative weights on some 2x2 comparisons.

**Severity if violated**: Serious (for staggered designs). For a single treatment date with only one treated cohort, TWFE is fine. But for staggered adoption with heterogeneous effects, TWFE is biased. The severity depends on how much treatment effect heterogeneity exists and how "bad" the implicit comparisons are.

**Mitigation**: (1) Use a robust estimator: Callaway & Sant'Anna (`did::att_gt`), Sun & Abraham (`fixest::sunab`), or extended TWFE (`etwfe`). (2) Run the Goodman-Bacon decomposition (`bacondecomp::bacon()`) to see which comparisons drive the TWFE estimate. (3) For a single treatment date, this is not a concern — standard TWFE is fine.
