---
name: causal-iv
description: Implements instrumental variables and 2SLS in R or Python with first-stage diagnostics, weak instrument detection, and overidentification tests. Use when user mentions IV, instrument, 2SLS, non-compliance, or endogeneity. Not for cases without a plausible instrument.
metadata:
  author: Robson Tigre
  version: 0.3.2
compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal IV

You guide users through a complete instrumental variables analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/iv.md` — the assumption checklist for IV.
3. Read `references/method-registry.md` → "Instrumental Variables (IV)" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, instrument, endogenous treatment, outcome, language, data structure. Confirm: "I've read your analysis plan. You're using [instrument] as an instrument for [treatment] on [outcome]. Does that sound right?"

**If no plan**: Ask:
1. "What's the endogenous treatment variable — the variable whose causal effect you want to estimate?"
2. "What's the proposed instrument — the variable that shifts the treatment but (arguably) doesn't directly affect the outcome?"
3. "What's the outcome?"
4. "Is this a case of non-compliance (e.g., randomized encouragement but voluntary take-up)? One-sided (only treated group can deviate) or two-sided (both groups can deviate)?"
5. "Do you have more than one instrument? If so, list them."
6. "Any covariates you want to control for?"
7. "R or Python?"

**Determine variant**:
- Single instrument, single endogenous variable → Standard 2SLS
- Multiple instruments, single endogenous variable → 2SLS with overidentification test
- Fuzzy RDD framing → Fuzzy RDD (suggest `causal-rdd` instead)
- Weak instrument suspected → Flag for careful diagnostics

## Stage 2: Assumptions

Read `references/assumptions/iv.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Relevance (first-stage strength)**: "Does the instrument actually predict the treatment? We need a strong first stage — an F-statistic well above 10 (ideally above 100 for modern standards)."
   - This IS testable. Offer first-stage regression code.

2. **Exclusion restriction**: "Does the instrument affect the outcome ONLY through its effect on the treatment? There must be no direct path from instrument to outcome."
   - This is NOT directly testable. Must be argued on substantive grounds.
   - Ask: "Can you think of any way [instrument] could affect [outcome] other than through [treatment]?"

3. **Independence (as-if random)**: "Is the instrument independent of the potential outcomes and unobserved confounders? It should be as good as randomly assigned."
   - Partially testable: check balance of instrument with observables.

4. **Monotonicity**: "Does the instrument push everyone in the same direction? No 'defiers' — units who do the opposite of what the instrument encourages."
   - Needed for LATE interpretation. Discuss plausibility.

After all assumptions, summarize with status indicators per assumption.

**Pedagogy checkpoint (especially for first-time IV users)**:
- Explain the **ITT vs LATE distinction**: The intent-to-treat (ITT) estimate — the reduced-form effect of the instrument on the outcome — answers "what is the effect of being *assigned* to treatment?" The LATE answers "what is the effect of actually *taking* the treatment, among those who comply?" Both are useful, for different questions.
- Explain **who the compliers are**: LATE applies only to compliers — units whose treatment status was changed by the instrument. Always describe who these are in the user's specific context (e.g., "people who would use the savings product when encouraged but would not use it otherwise").
- Explain **what the first-stage F tells you**: A high F (>10, ideally >100) means the instrument strongly predicts treatment. A low F means 2SLS is unreliable — estimates are biased toward OLS and confidence intervals are wrong. This is the single most important diagnostic in IV.

If fatal violations exist (especially weak instrument or clearly violated exclusion restriction), warn clearly and suggest alternatives.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/iv.md` or `templates/python/iv.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/iv.md` or `templates/python/iv.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**Always include**:
- First-stage regression with F-statistic
- 2SLS / IV estimation
- Comparison with naive OLS (to show bias direction)
- Proper standard errors
- Confidence interval for the IV estimate

**IV estimation (R — fixest)**:
```r
library(fixest)
library(modelsummary)

# First stage: check instrument relevance
first_stage <- feols(treatment ~ instrument + X1 + X2, data = df)
summary(first_stage)
cat("First-stage F-statistic:", fitstat(first_stage, "ivf")$ivf$stat, "\n")

# 2SLS estimation
iv_model <- feols(outcome ~ X1 + X2 | treatment ~ instrument, data = df)
summary(iv_model)

# Naive OLS for comparison
ols_model <- feols(outcome ~ treatment + X1 + X2, data = df)

modelsummary(list("OLS" = ols_model, "IV/2SLS" = iv_model),
             stars = TRUE)
```

**IV estimation (R — AER)**:
```r
library(AER)

iv_model <- ivreg(outcome ~ treatment + X1 + X2 |
                   instrument + X1 + X2, data = df)
summary(iv_model, diagnostics = TRUE)
```

**IV estimation (Python)**:
```python
from linearmodels.iv import IV2SLS
import statsmodels.formula.api as smf

# First stage
first_stage = smf.ols('treatment ~ instrument + X1 + X2', data=df).fit()
print("First-stage F-statistic:", first_stage.fvalue)
print(first_stage.summary())

# 2SLS estimation
iv_model = IV2SLS.from_formula(
    'outcome ~ 1 + X1 + X2 + [treatment ~ instrument]', data=df
).fit(cov_type='robust')
print(iv_model.summary)

# Naive OLS for comparison
ols_model = smf.ols('outcome ~ treatment + X1 + X2', data=df).fit()
print(ols_model.summary())
```

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **Reduced form**: Regress outcome directly on instrument (skipping treatment). If the instrument is valid and relevant, this should show a significant effect in the same direction. The reduced form is often more robust than 2SLS.
2. **Placebo instrument**: Use a variable that should NOT be a valid instrument. If it produces similar IV estimates, something is wrong.
3. **Overidentification test** (if >1 instrument): Sargan/Hansen J-test. A rejection suggests at least one instrument is invalid.
4. **Sensitivity to controls**: Add or remove covariates. A stable IV estimate is reassuring.
5. **Balance on observables**: Check if the instrument is balanced on pre-treatment covariates (supports the independence assumption).

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
| First-stage F < 10 | 🚨 Fatal | Weak instrument. 2SLS estimates are unreliable. Warn user before continuing. |
| No substantive argument for exclusion restriction | 🚨 Fatal | Without an economic argument, IV is not identified. Warn user before continuing. |
| Hausman test fails to reject (OLS ~ IV) | ⚠️ Serious | Endogeneity may not be a problem. Report both estimates, discuss. |
| Overidentification test rejects (Hansen J) | ⚠️ Serious | At least one instrument may be invalid. Investigate which. |

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
| "The instrument is probably valid" | Exclusion restriction is untestable. You need an economic argument, not a feeling. |
| "First-stage F is close to 10" | Stock-Yogo critical values exist for a reason. Report the exact F and compare. |
| "IV gives us the ATE" | IV gives the LATE (complier effect). State who the compliers are. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the IV analysis:
- The IV estimate of the effect of [treatment] on [outcome] is [coefficient] (95% CI: [lower, upper]).
- For comparison, the naive OLS estimate was [OLS coefficient] — the difference suggests [direction of bias].
- The first-stage F-statistic is [F] ([strong/weak] instrument).

**LATE interpretation**: This estimate applies to compliers — units whose treatment status was changed by the instrument. It does NOT estimate the average treatment effect for the full population.
- Compliers are units who [specific description in context — e.g., 'would enroll in the program when encouraged but would not enroll otherwise'].
- If the treatment effect is heterogeneous, the LATE may differ from the ATE.

Caveats:
- [Exclusion restriction plausibility — strongest or weakest argument]
- [Weak instrument concerns if F < 100]
- [Monotonicity plausibility]"

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

"Your IV analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Refine**: If the instrument is weak or the exclusion restriction is shaky, we can discuss mitigations.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Weak instruments**: First-stage F-statistic below 10 signals a weak instrument. Report the F-stat and consider weak-instrument-robust methods (Anderson-Rubin, LIML).
- **Exclusion restriction asserted without argument**: The instrument must affect the outcome only through the treatment. This is untestable — require the user to articulate the economic or theoretical argument.
- **Multiple endogenous variables with insufficient instruments**: The order condition requires at least as many instruments as endogenous regressors. Check before estimating.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-rdd` -- If the instrument is a threshold with a cutoff
- `/causal-matching` -- If instrument is invalid but covariates are available

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### IV: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
