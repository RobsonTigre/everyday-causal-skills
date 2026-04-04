---
name: causal-matching
description: Implements matching, propensity scores, IPW, and doubly-robust estimators in R or Python with balance diagnostics and sensitivity analysis. Use when user mentions matching, propensity score, observational study, confounders, selection bias, or covariate balance. Not for settings with unobserved confounding.
metadata:
  author: Robson Tigre
  version: 0.3.2
compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal Matching

You guide users through a complete matching / propensity score / doubly-robust analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/matching.md` — the assumption checklist for matching methods.
3. Read `references/method-registry.md` → "Matching / PSM / PSW / Doubly-Robust" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, treatment, covariates, outcome, language, data structure. Confirm: "I've read your analysis plan. You're estimating the effect of [treatment] on [outcome] using matching/weighting methods conditional on [covariates]. Does that sound right?"

**If no plan**: Ask:
1. "What covariates are available for matching? List all pre-treatment variables you have."
2. "How was treatment assigned? What do you know about the selection process — why did some units receive treatment and others didn't?"
3. "Any prior knowledge about potential confounders — variables that affect both treatment assignment and the outcome?"
4. "Are there covariates you believe are confounders but cannot measure?"
5. "What's the outcome?"
6. "Do you want an ATT (average treatment effect on the treated) or ATE (average treatment effect on everyone)?"
7. "R or Python?"

**Determine variant**:
- Good overlap, want transparency → Propensity Score Matching (PSM) with MatchIt
- Large sample, want efficiency → Inverse Probability Weighting (IPW/PSW)
- Worried about model misspecification → Doubly-Robust (DR) estimation
- Few categorical covariates → Coarsened Exact Matching (CEM)
- Want heterogeneous effects → DR Learner or meta-learners (econml)

**Always flag**: Matching relies on conditional independence (selection on observables). This is the WEAKEST identification strategy. If a stronger design is available (DiD, IV, RDD), use that instead.

**Pre-flight data check (before proceeding to Stage 2):** If the user has provided a dataset, examine it for overlap before proceeding. Plot or summarize propensity score distributions (or raw covariate distributions) for treated vs control groups. If there are regions with near-zero overlap — e.g., treated units have no comparable controls, or propensity scores are clustered near 0 or 1 — flag this immediately as a fundamental problem. Matching cannot produce reliable estimates in regions without overlap. Do not proceed to full estimation without acknowledging and discussing the overlap problem with the user.

## Stage 2: Assumptions

Read `references/assumptions/matching.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Conditional independence / unconfoundedness (CIA)**: "Given the covariates you're matching on, is treatment assignment independent of potential outcomes? In plain English: after accounting for [covariates], is there NO remaining reason why treated and control units would have different outcomes even without treatment?"
   - This is NOT directly testable. It's the hardest assumption to defend.
   - Ask: "Can you think of any unobserved variable that both drives treatment selection and affects the outcome?"
   - If there are plausible unobserved confounders, warn explicitly and recommend sensitivity analysis.

2. **Overlap / positivity**: "Does every unit have a nonzero probability of receiving treatment? If some units always/never get treated based on covariates, we can't estimate effects for them."
   - Testable: propensity score distribution and overlap histogram.
   - Offer overlap diagnostic code.

3. **SUTVA (no interference)**: "Could one unit's treatment affect another unit's outcome?"

4. **Correct specification**: "For propensity score methods: is the propensity score model correctly specified? For outcome models: is the outcome model correct? Doubly-robust gives you two chances — only one model needs to be right."

After all assumptions, summarize with status indicators per assumption.

If CIA is clearly violated (known unobserved confounders), warn clearly: "Matching cannot solve omitted variable bias. Consider IV, DiD, or RDD if possible."
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/matching.md` or `templates/python/matching.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/matching.md` or `templates/python/matching.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**Always include**:
- Propensity score estimation
- Overlap / common support check
- Matching or weighting
- Covariate balance diagnostics (SMD, love plot)
- Treatment effect estimate with confidence interval

**Matching (R — MatchIt + cobalt)**:
```r
library(MatchIt)
library(cobalt)
library(marginaleffects)

# Propensity score matching (nearest neighbor)
m_out <- matchit(treatment ~ X1 + X2 + X3, data = df,
                 method = "nearest", distance = "glm",
                 ratio = 1, replace = FALSE)
summary(m_out)

# Balance diagnostics
bal.tab(m_out, thresholds = c(m = 0.1))
love.plot(m_out, thresholds = c(m = 0.1))

# Extract matched data and estimate effect
m_data <- match.data(m_out)
model <- lm(outcome ~ treatment + X1 + X2 + X3,
            data = m_data, weights = weights)
avg_comparisons(model, variables = "treatment",
                vcov = ~subclass, newdata = m_data,
                wts = "weights")
```

**Inverse probability weighting (R)**:
```r
library(cobalt)

# Estimate propensity scores
ps_model <- glm(treatment ~ X1 + X2 + X3, data = df,
                family = binomial)
df$ps <- predict(ps_model, type = "response")

# IPW weights (for ATT)
df$ipw <- ifelse(df$treatment == 1, 1, df$ps / (1 - df$ps))

# Check overlap
hist(df$ps[df$treatment == 1], col = rgb(1, 0, 0, 0.5), main = "PS Overlap")
hist(df$ps[df$treatment == 0], col = rgb(0, 0, 1, 0.5), add = TRUE)

# Weighted regression
model_ipw <- lm(outcome ~ treatment, data = df, weights = ipw)
summary(model_ipw)
```

**Matching (Python — dowhy + econml)**:
```python
import dowhy
from dowhy import CausalModel

# Define causal model
model = CausalModel(
    data=df,
    treatment='treatment',
    outcome='outcome',
    common_causes=['X1', 'X2', 'X3']
)

# Identify causal effect
identified = model.identify_effect()

# Estimate using propensity score matching
estimate_psm = model.estimate_effect(
    identified,
    method_name="backdoor.propensity_score_matching"
)
print(estimate_psm)
```

**Doubly-robust (Python — econml)**:
```python
from econml.dr import DRLearner
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

dr = DRLearner(
    model_propensity=GradientBoostingClassifier(),
    model_regression=GradientBoostingRegressor(),
    model_final=GradientBoostingRegressor()
)
dr.fit(Y=df['outcome'].values, T=df['treatment'].values,
       X=df[['X1', 'X2', 'X3']].values)

ate = dr.ate(df[['X1', 'X2', 'X3']].values)
print(f"ATE estimate: {ate}")
ate_interval = dr.ate_interval(df[['X1', 'X2', 'X3']].values)
print(f"95% CI: {ate_interval}")
```

**Manual IPW (Python)**:
```python
import statsmodels.formula.api as smf
import numpy as np

# Estimate propensity scores
ps_model = smf.logit('treatment ~ X1 + X2 + X3', data=df).fit()
df['ps'] = ps_model.predict()

# IPW weights (for ATT)
df['ipw'] = np.where(df['treatment'] == 1, 1, df['ps'] / (1 - df['ps']))

# Weighted regression
model_ipw = smf.wls('outcome ~ treatment', data=df, weights=df['ipw']).fit()
print(model_ipw.summary())
```

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **Sensitivity analysis (Rosenbaum bounds)**: How strong would an unobserved confounder need to be to explain away the estimated effect? Use `sensemakr` (R) or manual Rosenbaum bounds.
2. **Placebo outcome**: Run the matching analysis on an outcome that should NOT be affected by the treatment. Finding an "effect" suggests residual confounding.
3. **Different matching specifications**: Vary the method (nearest neighbor, caliper, CEM, full matching), with/without replacement, different calipers. Results should be qualitatively stable.
4. **Propensity score trimming**: Exclude units with extreme propensity scores (e.g., outside [0.1, 0.9]). If results change dramatically, the overlap assumption is problematic.
5. **Different covariate sets**: Add or remove covariates. Sensitivity of the estimate to covariate choice indicates fragility.

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
| Zero or near-zero overlap in propensity scores | 🚨 Fatal | No comparable units exist. Warn user that matching results will be unreliable. |
| Post-treatment variable included as covariate | 🚨 Fatal | Biased estimate. Warn user; recommend removing the variable. |
| Any SMD > 0.25 after matching | ⚠️ Serious | Substantial residual imbalance. Report and consider re-specification. |
| Propensity model ROC-AUC > 0.9 | ⚠️ Serious | Near-deterministic treatment assignment. Overlap likely poor. Inspect. |

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
| "We controlled for the main confounders" | Conditional independence requires ALL confounders. If you can name one you're missing, matching is suspect. |
| "Balance improved after matching" | Improved isn't sufficient. Report SMDs. Any SMD > 0.1 means residual imbalance. |
| "Propensity scores are well estimated" | Check overlap. Good model fit with no overlap = useless matching. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the matching analysis:
- The estimated treatment effect ([ATT/ATE]) is [coefficient] (95% CI: [lower, upper]).
- This estimate was obtained using [method — e.g., nearest-neighbor propensity score matching].
- Covariate balance after matching: [summary — e.g., all SMDs below 0.1].

**Critical assumption warning**: This estimate is credible only if all important confounders are captured in the covariates ([list covariates]). Unmeasured confounders would bias these results.

Sensitivity analysis:
- An unobserved confounder would need to [description from Rosenbaum bounds or sensemakr] to fully explain away the estimated effect.

Caveats:
- [CIA plausibility assessment — how confident are we that all confounders are measured?]
- [Overlap quality — were there regions of poor common support?]
- [Sensitivity of results to specification choices]
- [This is the weakest identification strategy — interpret with appropriate caution]"

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

"Your matching analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Refine**: If unconfoundedness was concerning, consider sensitivity analysis or a stronger identification strategy.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Code timeout on large datasets**: PSM with nearest-neighbor matching on n > 1,000 can hang. Recommend IPW or CEM as faster alternatives and warn before attempting.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-did` -- If panel data and treatment timing exist
- `/causal-iv` -- If an instrument is available (stronger identification)

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### Matching: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
