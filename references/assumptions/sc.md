# Assumption Checklist: Synthetic Control

Reference: `references/method-registry.md` → Synthetic Control

---

## No Interference Between Units

**Plain language**: The control units (donors) are not affected by the treatment that was given to the treated unit. If California passes a policy, the states used to construct its synthetic version shouldn't be affected by California's policy (e.g., through economic spillovers, migration, or competitive responses).

**Formal statement**: The potential outcome for control unit j does not depend on the treatment status of the treated unit: Y_jt(D_1 = 1) = Y_jt(D_1 = 0) for all control units j and all post-treatment periods t, where D_1 is the treatment indicator for the treated unit.

**Testable?**: No. We cannot observe what would have happened to donor units in a world where the treated unit was not treated. This assumption must be argued on substantive grounds.

**How to test**:

While formally untestable, you can look for suggestive evidence:

R:
```r
library(tidysynth)

# Check if donor units show unusual behavior after the treatment date
# Idea: plot outcomes for each donor unit and look for breaks
# at the treatment date that might indicate spillovers

donor_data <- df |>
  dplyr::filter(unit != treated_unit_name) |>
  dplyr::group_by(unit)

library(ggplot2)
ggplot(donor_data, aes(x = time, y = outcome, color = unit)) +
  geom_line(alpha = 0.5) +
  geom_vline(xintercept = treatment_date, linetype = "dashed", color = "red") +
  labs(title = "Donor Unit Outcomes Around Treatment Date",
       x = "Time", y = "Outcome") +
  theme_minimal() +
  theme(legend.position = "none")

# Formal: run a placebo synthetic control for each donor unit
# using the treated unit's treatment date.
# If many donors show "effects," spillover (or model failure) is likely.
```

Python:
```python
import matplotlib.pyplot as plt

# Visual check: plot donor unit outcomes for breaks at treatment date
donor_data = df[df['unit'] != treated_unit_name]

fig, ax = plt.subplots(figsize=(12, 6))
for unit_name, group in donor_data.groupby('unit'):
    ax.plot(group['time'], group['outcome'], alpha=0.3, color='gray')
ax.axvline(x=treatment_date, color='red', linestyle='--', label='Treatment')
ax.set_xlabel('Time')
ax.set_ylabel('Outcome')
ax.set_title('Donor Unit Outcomes Around Treatment Date')
ax.legend()
plt.tight_layout()
plt.show()
```

**What violation looks like**: Donor units show a concurrent shift in outcomes at the treatment date. For example, if the policy in the treated state causes businesses to relocate to donor states, those donor states' outcomes improve at exactly the time the treatment occurred — making the synthetic control underestimate the treatment effect.

**Severity if violated**: Fatal. If donors are affected by the treatment, the synthetic control is constructed from contaminated outcomes. The estimated counterfactual is wrong, and the treatment effect estimate is biased. The direction of bias depends on whether spillovers help or hurt donor units.

**Mitigation**: (1) Choose donor units that are geographically, economically, or institutionally insulated from the treated unit. For example, use states in a different region or countries not connected by trade. (2) Remove donors most likely to be affected (e.g., neighboring states). (3) Use the leave-one-out test to check robustness to dropping specific donors. (4) If spillovers are substantial and unavoidable, synthetic control is not appropriate — consider a method that allows for interference.

---

## Convex Hull

**Plain language**: The treated unit's pre-treatment characteristics should lie within the range spanned by the donor units — not outside it. You can't build a good synthetic version of an extreme unit from donors that are all very different from it.

**Formal statement**: The treated unit's vector of pre-treatment outcomes and covariates X_1 lies within the convex hull of the donor units' vectors {X_2, ..., X_{J+1}}. That is, there exist non-negative weights w_j >= 0 with sum(w_j) = 1 such that X_1 = sum(w_j * X_j). If X_1 is outside this convex hull, exact matching is impossible and the synthetic control relies on extrapolation.

**Testable?**: Yes. Check whether the optimization produces weights that achieve a good fit (which implies X_1 is inside the hull) or whether the fit is poor despite large weights on a few donors.

**How to test**:

R:
```r
library(tidysynth)

# After fitting a synthetic control, check the donor weights
# and pre-treatment fit

# Example with tidysynth
synth_out <- df |>
  synthetic_control(
    outcome = outcome,
    unit = unit,
    time = time,
    i_unit = treated_unit_name,
    i_time = treatment_date,
    generate_placebos = TRUE
  ) |>
  generate_predictor(time_window = pre_start:pre_end,
                     outcome_avg = mean(outcome)) |>
  generate_weights(optimization_window = pre_start:pre_end) |>
  generate_control()

# Check weights — are they concentrated on just 1-2 donors?
# Ideally weights are spread across several donors.
synth_out |> grab_unit_weights() |>
  dplyr::filter(weight > 0.01) |>
  print()

# Check predictor balance
synth_out |> grab_predictor_balance() |> print()

# If the treated unit is extreme on any predictor compared to all
# donors, extrapolation is required — convex hull is violated.
```

Python:
```python
# After fitting a synthetic control, check the weights and predictor balance
# Using SparseSC or scpi

# Example with scpi
from scpi_pkg.scdata import scdata
from scpi_pkg.scest import scest

scd = scdata(
    df=df,
    id_var='unit',
    time_var='time',
    outcome_var='outcome',
    period_pre=list(range(pre_start, treatment_date)),
    period_post=list(range(treatment_date, post_end)),
    unit_tr=treated_unit_name,
    unit_co=donor_unit_list
)

result = scest(scd, e_method='all')

# Check donor weights
print("Donor weights:")
print(result.w)

# Check if weights are non-negative and whether fit is achieved
# Large residuals in predictor balance suggest convex hull issues
```

**What violation looks like**: The synthetic control cannot closely match the treated unit's pre-treatment outcomes or covariates. Donor weights are concentrated on one or two units (meaning the synthetic control is basically just one other unit, reducing the method to a simple comparison). Pre-treatment predictor balance shows large discrepancies between the treated unit and its synthetic version.

**Severity if violated**: Serious. If the treated unit is outside the convex hull, the synthetic control relies on extrapolation, which can produce a poor counterfactual. The pre-treatment fit will be poor, and the post-treatment gap (treatment effect) may reflect the inability to match rather than a genuine effect. However, some recent methods (augmented synthetic control, `augsynth`) address this by combining SCM with ridge regression to handle partial extrapolation.

**Mitigation**: (1) Expand the donor pool to include more diverse units. (2) Use the augmented synthetic control method (`augsynth` in R), which allows extrapolation by combining SCM with an outcome model. (3) Remove predictors on which the treated unit is extreme. (4) If the treated unit is genuinely unique (e.g., the largest state by far), synthetic control may not be suitable — consider interrupted time series or CausalImpact instead.

---

## Adequate Pre-Treatment Fit

**Plain language**: The synthetic control should closely track the treated unit's outcome during the pre-treatment period. If the synthetic version can't reproduce the treated unit's past, there's no reason to trust its prediction of the treated unit's future (counterfactual).

**Formal statement**: The pre-treatment root mean squared prediction error (RMSPE) should be small: RMSPE_pre = sqrt(1/T_0 * sum_{t=1}^{T_0} (Y_{1t} - sum_j w_j Y_{jt})^2) should be small relative to the scale of the outcome and relative to the post-treatment gap.

**Testable?**: Yes. Compute the pre-treatment RMSPE and compare it to the post-treatment gap and to the pre-treatment RMSPE of placebo units.

**How to test**:

R:
```r
library(tidysynth)

# Compute pre-treatment RMSPE and post/pre RMSPE ratio
synth_out <- df |>
  synthetic_control(
    outcome = outcome,
    unit = unit,
    time = time,
    i_unit = treated_unit_name,
    i_time = treatment_date,
    generate_placebos = TRUE
  ) |>
  generate_predictor(time_window = pre_start:pre_end,
                     outcome_avg = mean(outcome)) |>
  generate_weights(optimization_window = pre_start:pre_end) |>
  generate_control()

# Visual: treated vs synthetic
synth_out |> plot_trends()

# MSPE ratio for inference
synth_out |> plot_mspe_ratio()

# Grab MSPE values
mspe <- synth_out |> grab_signficance()
print(mspe)

# Rule of thumb: pre-treatment RMSPE should be <10% of the outcome's
# standard deviation. The post/pre RMSPE ratio for the treated unit
# should be an outlier compared to placebo units.
```

Python:
```python
import numpy as np

# After fitting synthetic control, compute pre-treatment RMSPE
# Assume you have treated_outcomes and synthetic_outcomes arrays
pre_treatment_mask = df['time'] < treatment_date

treated_pre = treated_outcomes[pre_treatment_mask]
synthetic_pre = synthetic_outcomes[pre_treatment_mask]

rmspe_pre = np.sqrt(np.mean((treated_pre - synthetic_pre) ** 2))
print(f"Pre-treatment RMSPE: {rmspe_pre:.4f}")
print(f"Outcome std dev: {treated_pre.std():.4f}")
print(f"RMSPE / SD ratio: {rmspe_pre / treated_pre.std():.4f}")

# Post-treatment gap
treated_post = treated_outcomes[~pre_treatment_mask]
synthetic_post = synthetic_outcomes[~pre_treatment_mask]
rmspe_post = np.sqrt(np.mean((treated_post - synthetic_post) ** 2))
print(f"Post/Pre RMSPE ratio: {rmspe_post / rmspe_pre:.2f}")

# Visual
import matplotlib.pyplot as plt
times = sorted(df['time'].unique())
plt.figure(figsize=(12, 6))
plt.plot(times, treated_outcomes, label='Treated', color='black')
plt.plot(times, synthetic_outcomes, label='Synthetic', color='blue',
         linestyle='--')
plt.axvline(x=treatment_date, color='red', linestyle=':', label='Treatment')
plt.xlabel('Time')
plt.ylabel('Outcome')
plt.title('Treated vs. Synthetic Control')
plt.legend()
plt.tight_layout()
plt.show()
```

**What violation looks like**: The synthetic control line diverges from the treated unit's line even before the treatment date. Large pre-treatment RMSPE relative to the outcome's scale. The treated vs. synthetic plot shows gaps in the pre-period.

**Severity if violated**: Serious. Poor pre-treatment fit means the synthetic control is a bad approximation of the treated unit's trajectory, and the post-treatment gap conflates the treatment effect with the model's inability to match the pre-treatment pattern. Inference based on RMSPE ratios (permutation tests) also becomes unreliable, because the placebo distribution is contaminated by genuinely poor-fitting units.

**Mitigation**: (1) Add more predictors or more pre-treatment periods to the optimization. (2) Expand the donor pool. (3) Use the augmented synthetic control method (`augsynth`) to improve fit via bias correction. (4) Remove placebo units with poor pre-treatment fit (e.g., >2x or >5x the treated unit's pre-RMSPE) from the permutation distribution. This is standard practice — Abadie et al. (2010) recommend this. (5) If pre-treatment fit cannot be achieved, the synthetic control is not credible for this treated unit.

---

## No Structural Breaks

**Plain language**: The relationship between the treated unit and the donor units stays the same after treatment, except for the treatment itself. There are no external shocks (recessions, natural disasters, other policy changes) that differentially affect the treated unit and its synthetic control.

**Formal statement**: The factor model Y_it = delta_t + theta_t * mu_i + epsilon_it that relates unit outcomes to common factors has stable factor loadings mu_i throughout the sample period. The relationship between the treated unit and donors in the pre-treatment period continues to hold in the post-treatment period, absent the treatment.

**Testable?**: Partially. An "in-time" placebo test (backdating the treatment to an earlier period) can detect instability. If the synthetic control shows a "treatment effect" at a placebo date, the relationship between units may not be stable.

**How to test**:

R:
```r
library(tidysynth)

# In-time placebo: backdate treatment to midpoint of pre-treatment period
placebo_date <- pre_start + floor((treatment_date - pre_start) / 2)

synth_placebo <- df |>
  dplyr::filter(time < treatment_date) |>  # use only pre-treatment data
  synthetic_control(
    outcome = outcome,
    unit = unit,
    time = time,
    i_unit = treated_unit_name,
    i_time = placebo_date,
    generate_placebos = FALSE
  ) |>
  generate_predictor(time_window = pre_start:(placebo_date - 1),
                     outcome_avg = mean(outcome)) |>
  generate_weights(optimization_window = pre_start:(placebo_date - 1)) |>
  generate_control()

# Plot: there should be NO gap after the placebo treatment date
synth_placebo |> plot_trends()

# If a gap appears at the placebo date, the model relationship is unstable
```

Python:
```python
import numpy as np
import matplotlib.pyplot as plt

# In-time placebo: use only pre-treatment data and pretend treatment
# happened at the midpoint
placebo_date = pre_start + (treatment_date - pre_start) // 2

pre_placebo_data = df[df['time'] < treatment_date].copy()

# Fit synthetic control on data before placebo_date,
# then check if a gap appears between placebo_date and treatment_date
# (Implementation depends on your SC package)

# Conceptual check: after fitting SC on pre-placebo data,
# compute gap in the "post-placebo, pre-actual-treatment" window
gap = treated_outcomes_placebo_post - synthetic_outcomes_placebo_post
print(f"Placebo gap mean: {np.mean(gap):.4f}")
print(f"Placebo gap std: {np.std(gap):.4f}")

# Plot
# [Plot treated vs synthetic with placebo treatment date marked]
# The gap after the placebo date (but before actual treatment)
# should be approximately zero.
```

**What violation looks like**: The in-time placebo test shows a significant gap between the treated unit and its synthetic control at a fake treatment date in the pre-treatment period. This indicates that the pre-treatment relationship between the treated unit and its donors is not stable — it shifts even without treatment.

**Severity if violated**: Serious. If the relationship between units shifts over time for reasons unrelated to treatment, the post-treatment gap may reflect structural instability rather than a treatment effect. The estimated effect is biased by the amount of structural drift.

**Mitigation**: (1) Add more predictors that capture the structural change (e.g., economic indicators that differ across the break). (2) Use the generalized synthetic control method (`gsynth` in R), which explicitly models time-varying factors. (3) Restrict the analysis window to a period of stable relationships. (4) Use multiple placebo dates to assess the typical "noise" level and compare it to the actual treatment effect. (5) If structural breaks are pervasive, the synthetic control method may not be reliable — consider interrupted time series or DiD with an appropriate control group.
