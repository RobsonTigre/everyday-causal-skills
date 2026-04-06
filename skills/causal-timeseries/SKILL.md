---
name: causal-timeseries
description: Implements interrupted time series and CausalImpact in R or Python with pre-period fit checks, stationarity testing, and placebo validation. Use when user mentions ITS, CausalImpact, time series intervention, or pre/post with no control group. Not for panel data with multiple units.
metadata:
  author: Robson Tigre
  version: 0.3.2
  compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal Time Series

You guide users through a complete interrupted time series / CausalImpact analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/timeseries.md` — the assumption checklist for time series causal methods.
3. Read `references/method-registry.md` → "Interrupted Time Series / CausalImpact" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, intervention, time series, control series, language, data structure. Confirm: "I've read your analysis plan. You're estimating the effect of [intervention] on [outcome series] using an interrupted time series approach. Does that sound right?"

**If no plan**: Ask:
1. "How many pre-treatment time points do you have? (Need at least 30-50 for reliable modeling.)"
2. "How many post-treatment time points?"
3. "What's the exact intervention date?"
4. "Do you have any control time series — series that were NOT affected by the intervention but follow similar trends? (This greatly strengthens the analysis.)"
5. "What's the outcome metric and its time granularity (daily, weekly, monthly)?"
6. "Is there known seasonality in the data?"
7. "R or Python?"

**Determine variant**:
- Control series available → CausalImpact (Bayesian structural time series) — preferred
- No control series → CausalArima (ARIMA-based counterfactual)
- Multiple interventions → Stepped-wedge or multi-intervention ITS

**Method selection logic**:

```
Control series available?
├── YES → CausalImpact (BSTS with regression on controls) ✓ PREFERRED
└── NO  → CausalArima (ARIMA-based counterfactual)

Either method: pre-period model fit diagnostic (MAPE) determines
whether the data supports reliable counterfactual projection.
If MAPE is poor or diagnostics fail → WARN user that the data
may not support causal modeling. User decides whether to proceed.
```

When in doubt, prefer CausalImpact (if controls exist) or CausalArima (if no controls). Segmented regression is available as a descriptive supplement within either analysis to show level/slope changes, but is NOT a standalone causal method.

**Pre-flight data check (before proceeding to Stage 2):** If the user has provided a dataset, check the pre-treatment period for structural breaks before proceeding. Run the structural break detection code from `references/assumptions/timeseries.md` → "No Structural Breaks in Pre-Period" section (CUSUM in R via `strucchange::efp()`, PELT in Python via `ruptures`). If a structural break exists, flag it immediately with a FATAL verdict — the counterfactual projection will be unreliable because the model will be fit on data from two different regimes. Discuss whether to truncate the pre-period to after the break, model the break with a level-shift dummy, or abandon the time series method. Do not proceed to full estimation without resolving the structural break.

## Stage 2: Assumptions

Read `references/assumptions/timeseries.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Pre-period model fit**: "Does the model accurately capture the pre-intervention pattern — trend, seasonality, autocorrelation? If the model can't explain the pre-period, it can't construct a reliable counterfactual."
   - Testable: inspect pre-period residuals, MAPE, one-step-ahead prediction quality.
   - Offer model fit diagnostic code.

2. **No concurrent events**: "Did anything else happen at the same time as the intervention that could explain the change in the outcome? This is the single biggest threat."
   - Ask: "Were there any other changes, events, or shocks around [intervention date] that might have affected [outcome]?"
   - This is NOT testable. Must be argued substantively.

3. **Stationarity (or proper differencing)**: "Is the pre-intervention series stationary, or does it need differencing/detrending? Non-stationarity can produce spurious effects."
   - Testable: ADF test, KPSS test, visual inspection.
   - Offer stationarity test code.

4. **Control series validity** (if using CausalImpact): "Are the control series truly unaffected by the intervention? If the control was also affected, the counterfactual is contaminated."
   - Ask: "Could the intervention have indirectly affected your control series?"

5. **Stable relationship**: "Is the relationship between the outcome and control series (or the time series pattern) stable across the pre-period? Structural breaks would invalidate the counterfactual projection."

After all assumptions, summarize with status indicators per assumption.

If fatal violations exist (especially very short pre-period or concurrent events), warn clearly and suggest alternatives.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/timeseries.md` or `templates/python/timeseries.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/timeseries.md` or `templates/python/timeseries.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**Always include**:
- Pre-period model fit assessment
- Counterfactual projection plot
- Point effect and cumulative effect estimates
- Confidence/credible intervals
- Residual diagnostics

**CausalImpact (R)**:
```r
library(CausalImpact)

# Prepare data: first column is outcome, remaining are controls
data <- cbind(outcome_ts, control1_ts, control2_ts)

pre.period <- c(start_date, intervention_date - 1)
post.period <- c(intervention_date, end_date)

impact <- CausalImpact(data, pre.period, post.period)
summary(impact)
summary(impact, "report")
plot(impact)

# Extract key numbers
cat("Average causal effect:", impact$summary$AbsEffect[1], "\n")
cat("Cumulative effect:", impact$summary$AbsEffect[2], "\n")
cat("Posterior probability of effect:", impact$summary$p[1], "\n")
```

**CausalArima (R)** — when no control series available:
```r
library(CausalArima)

result <- CausalArima(
  y = outcome_ts,
  dates = date_vector,
  int.date = intervention_date,
  nboot = 1000
)
summary(result)
plot(result)
```

**CausalArima (Python)** — when no control series available:
```python
from pycausalarima import CausalArima
import pandas as pd

dates = pd.to_datetime(df['date'])
intervention_date = pd.Timestamp('YYYY-MM-DD')  # adapt to user's data

ca = CausalArima(
    y=df['outcome'].values,
    dates=dates,
    intervention_date=intervention_date,
    auto=True,           # auto-select ARIMA order
    ic='aic',            # information criterion
    alpha=0.05
)
result = ca.fit()

# Summary: point, cumulative, and temporal average causal effects
print(ca.summary())

# Extract key numbers from summary DataFrame
summary = ca.summary()
point_effect = summary.loc['Point causal effect', summary.columns[0]]
cumulative_effect = summary.loc['Cumulative causal effect', summary.columns[0]]
avg_effect = summary.loc['Temporal average causal effect', summary.columns[0]]
p_value = summary.loc['Bidirectional p-value', summary.columns[0]]
print(f"Point causal effect: {point_effect:.3f}")
print(f"Cumulative effect: {cumulative_effect:.3f}")
print(f"Temporal average effect: {avg_effect:.3f}")
print(f"p-value (two-sided): {p_value:.4f}")

# Visualizations
ca.plot(type='forecast')   # observed vs counterfactual
ca.plot(type='impact')     # point and cumulative effects
ca.plot(type='residuals')  # residual diagnostics
```

**CausalImpact (Python)**:
```python
from causalimpact import CausalImpact
import pandas as pd

# Prepare data: columns = [outcome, control1, control2, ...]
data = pd.DataFrame({
    'y': outcome_series,
    'x1': control1_series,
    'x2': control2_series
}, index=date_index)

pre_period = [pre_start, pre_end]
post_period = [post_start, post_end]

ci = CausalImpact(data, pre_period, post_period)
print(ci.summary())
print(ci.summary(output='report'))
ci.plot()
```

**Segmented regression (R, descriptive supplement)**:
```r
# Descriptive supplement: level shift and slope change estimates.
# Use alongside CausalImpact or CausalArima — not as a standalone causal method.
library(sandwich)
library(lmtest)

df$time <- seq_len(nrow(df))
df$post <- as.integer(df$time >= intervention_time)
df$time_since <- pmax(0, df$time - intervention_time)

# OLS with Newey-West HAC standard errors
fit_ols <- lm(outcome ~ time + post + time_since, data = df)
coeftest(fit_ols, vcov = NeweyWest(fit_ols, lag = 4))

# Alternative: Prais-Winsten GLS (better coverage for autocorrelated errors;
# see Bottomley et al., 2023)
library(prais)
fit_pw <- prais_winsten(outcome ~ time + post + time_since, data = df)
summary(fit_pw)
```

**Segmented regression (descriptive supplement)** — not a standalone causal method. Use alongside CausalImpact or CausalArima to show level/slope changes as interpretive aids:
```python
import statsmodels.formula.api as smf
import numpy as np

# Create ITS variables
df['time'] = range(len(df))
df['post'] = (df['date'] >= intervention_date).astype(int)
df['time_since'] = np.maximum(0, df['time'] - intervention_time)

# Segmented regression
model = smf.ols('outcome ~ time + post + time_since', data=df).fit(
    cov_type='HAC', cov_kwds={'maxlags': 4})
print(model.summary())
print(f"Level change at intervention: {model.params['post']:.3f}")
print(f"Slope change after intervention: {model.params['time_since']:.3f}")

# Alternative: GLS with AR(1) errors (preferred for autocorrelated series)
from statsmodels.regression.linear_model import GLSAR
import statsmodels.api as sm

X = sm.add_constant(df[['time', 'post', 'time_since']])
model_gls = GLSAR(df['outcome'], X, rho=1)  # rho=1 = AR(1)
result_gls = model_gls.iterative_fit(maxiter=50)
print(result_gls.summary())
# GLSAR iteratively estimates the AR(1) coefficient — Python equivalent of Prais-Winsten.
```

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **Placebo intervention date**: Run the analysis with a fake intervention date in the pre-period (e.g., midway through). Finding a "significant effect" at a placebo date suggests model misspecification or structural instability.
2. **Placebo series**: Apply the analysis to a time series that should NOT have been affected by the intervention. Finding an effect suggests the model is picking up a concurrent event, not the intervention.
3. **Different model specifications**: Vary the number of control series, the seasonality specification, or the ARIMA order. Results should be qualitatively stable.
4. **Pre-period prediction accuracy**: Use the first half of the pre-period to predict the second half. If predictions are poor, the model is unreliable for counterfactual projection.
5. **Different pre-period lengths**: Shorten or extend the pre-period. If the estimated effect changes substantially, the result may be driven by model fit to specific pre-period features.

## Verification Gate

Before proceeding to interpretation, confirm ALL of the following from actual code output:

- [ ] Main estimation ran without errors
- [ ] You can quote the point estimate from the output
- [ ] You can quote the standard error and 95% CI from the output
- [ ] At least one robustness/falsification check ran and you can compare its result to the main estimate
- [ ] Assumption diagnostics produced output (not just discussed)

**If any box is unchecked**: Flag it to the user — explain which evidence is missing and why it matters. Offer to run the missing step before interpreting. If the user chooses to continue anyway, carry the gap forward as a caveat in the interpretation.

**Watch for premature conclusions** — phrases like "The results suggest..." or "Based on the analysis..." before the gate passes. These imply conclusions without evidence. Quote actual output instead.

**Severity verdicts must appear BEFORE this gate.** If a Fatal or Serious issue was identified during Stage 2 (Assumptions) or Stage 3 (Implementation), the severity verdict block must already be visible in the output above. Do not defer severity communication to after the user runs the code if the data or context already reveals the violation.

## Red Flags

### Data Diagnostic Signals

| Signal | Severity | Action |
|--------|----------|--------|
| Structural break in pre-period | 🚨 Fatal | Counterfactual model is built on broken data. Warn user; recommend fixing or truncating pre-period. |
| Known concurrent event at intervention date | 🚨 Fatal | Effect is confounded. Warn user that results cannot be attributed to intervention alone. |
| Pre-period MAPE > 10% | ⚠️ Serious | Model fit is weak. Report as strong caveat. |
| Fewer than 12 pre-period observations | ⚠️ Serious | Insufficient data to learn seasonal/trend pattern. Flag limitation. |

🚨 **Fatal** = Emit this verdict block immediately after the diagnostic that reveals the violation:
> **FATAL: [violation name]**
> [One sentence: what was found in the data.]
> This analysis should not proceed without addressing this issue. Results produced under this violation are not trustworthy.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use **CONDITIONAL FATAL: [violation name]** with the same format but replace the consequence line with: "If [specific diagnostic condition], this analysis should not proceed. Run the diagnostic above and report the result before continuing."
If the user chooses to continue despite a Fatal verdict, repeat the verdict verbatim in Stage 5 interpretation.

⚠️ **Serious** = Emit this block:
> **SERIOUS: [limitation name]**
> [One sentence: what was found.]
> Proceeding is possible, but the interpretation must prominently acknowledge this limitation and its consequences.

Use only **FATAL** and **SERIOUS** severity labels. Do not invent additional tiers (Critical, Yellow, Minor, etc.). When in doubt, round UP to the next severity level.

### Rationalization Shortcuts

| Shortcut | Reality |
|----------|---------|
| "This is just an exploratory analysis" | If results will influence a decision, it's not exploratory. Apply full rigor. |
| "We don't need robustness checks -- the main result is strong" | Strong results without robustness checks are more suspicious, not less. |
| "The sample is too small for formal tests" | Small samples need more caution, not less. Flag the limitation explicitly. |
| "The pre-period model fits well" | Report MAPE. Visual fit is deceptive with noisy series. |
| "No other events happened around the intervention" | This is the biggest threat to ITS. Actively search for concurrent events. Don't just assume. |
| "CausalImpact handles everything automatically" | CausalImpact assumes stationarity and no structural breaks. Verify both. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the interrupted time series analysis:
- The estimated average per-period effect is [point effect] (95% CI: [lower, upper]).
- The estimated cumulative effect over the full post-period is [cumulative effect] (95% CI: [lower, upper]).
- The posterior probability that the intervention had a causal effect is [p / 1-p].

Effect decomposition:
- [If using CausalImpact: 'The pre-intervention counterfactual was constructed using [N] control series.']
- [If using CausalArima: 'The counterfactual was projected from the pre-intervention ARIMA model.']
- [If using ITS: 'The level shift at intervention was [X] and the slope change was [Y] per period.']

Model fit:
- Pre-period MAPE: [value] — [good/acceptable/poor] fit.

Caveats:
- [Concurrent events — the biggest threat]
- [Quality of control series if used]
- [Pre-period length adequacy]
- [Stationarity concerns]"

### Reading Your Results

**Posterior probability**: "A posterior probability of [p] means the model estimates a [p*100]% chance the intervention caused a real effect. Above 0.95 is strong. Between 0.80-0.95, the signal is suggestive but not conclusive. Below 0.80, the effect is hard to distinguish from normal fluctuation."

**Pre-period MAPE**: If MAPE < 3%: "Excellent model fit — the counterfactual projection is reliable." If 3-5%: "Acceptable fit. The counterfactual is reasonable but not precise — interpret the point estimate with some caution." If > 5%: "Poor fit. The model couldn't predict the pre-period well, so the post-period counterfactual is unreliable. Consider adding control series, extending the pre-period, or checking for structural breaks."

**Counterfactual interpretation**: "The counterfactual line shows what would have happened without the intervention, projected from pre-period patterns. The gap between actual and counterfactual is the estimated effect. If the counterfactual looks implausible — wild swings, obvious drift, divergence from controls — the model needs re-specification."

**Cumulative vs per-period effect**: "The per-period effect of [X] is the average impact in each time unit. The cumulative effect of [Y] is the total accumulated impact across all post-intervention periods. For one-time decisions, the cumulative number usually matters more. For ongoing programs, the per-period number tells you the sustained benefit."

## Saving Output

Save alongside the plan (or create a new directory if standalone):

```
docs/causal-plans/YYYY-MM-DD-<project>/
├── plan.md              # From planner (or created here if standalone)
├── implementation.md    # This skill's stage-by-stage summary
└── analysis.[R|py]      # Generated code
```

Use the Write tool. Tell the user where files are saved.

## Handoff

"Your time series causal analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Refine**: If concurrent events or pre-period fit were concerning, we can explore mitigations.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Non-stationary series**: CausalImpact assumes a stationary relationship. Check with ADF test; difference if needed.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-sc` -- If donor units are available for counterfactual construction
- `/causal-did` -- If a control group exists

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### Time Series: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
