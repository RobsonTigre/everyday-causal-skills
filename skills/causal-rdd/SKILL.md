---
name: causal-rdd
description: Implements sharp and fuzzy regression discontinuity designs in R or Python with bandwidth selection, manipulation testing, and sensitivity analysis. Use when user mentions RDD, cutoff, threshold, running variable, or discontinuity. Not for arbitrary subgroup comparisons.
metadata:
  author: Robson Tigre
  version: 0.3.2
  compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal RDD

You guide users through a complete regression discontinuity design analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/rdd.md` — the assumption checklist for RDD.
3. Read `references/method-registry.md` → "Regression Discontinuity Design (RDD)" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, running variable, cutoff, outcome, language, data structure. Confirm: "I've read your analysis plan. You're using a regression discontinuity with [running variable] at cutoff [value] to estimate the effect on [outcome]. Does that sound right?"

**If no plan**: Ask:
1. "What's the running variable (the continuous score that determines treatment)?"
2. "What's the cutoff value?"
3. "Is this a sharp RDD (treatment is deterministic at the cutoff — everyone above/below gets treated) or a fuzzy RDD (treatment probability jumps at the cutoff but isn't 100%)?"
4. "What's the outcome?"
5. "Approximately how many observations do you have, and how many are near the cutoff?"
6. "Are there any other known discontinuities at the same cutoff (e.g., other policies that kick in at the same threshold)?"
7. "R or Python?"

**Determine variant**:
- Treatment is deterministic at cutoff → Sharp RDD
- Treatment probability jumps but isn't 100% → Fuzzy RDD (IV with cutoff as instrument)
- Multiple cutoffs → Multi-cutoff RDD (normalize running variables)
- Geographic boundary → Geographic RDD (discuss spatial considerations)

## Stage 2: Assumptions

Read `references/assumptions/rdd.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **No manipulation of the running variable**: "Can units precisely control their score to sort around the cutoff? If so, units just above and below differ systematically."
   - Testable: Cattaneo, Jansson, and Ma (2020) density test (`rddensity`) — check for a jump in the density of the running variable at the cutoff.
   - Offer density test code.

2. **Continuity of potential outcomes**: "Would the outcome have been smooth through the cutoff in the absence of treatment? No other jump at the cutoff."
   - Partially testable: check if pre-determined covariates are smooth through the cutoff.
   - Offer covariate discontinuity test code.

3. **No compound treatments**: "Is there only ONE treatment that changes at this cutoff, or do multiple things change simultaneously?"
   - Ask: "Are there other programs, rules, or policies that use this same cutoff?"

4. **Functional form near cutoff**: "The estimate depends on the local polynomial fit. Misspecification far from the cutoff won't matter (we use local methods), but we need enough data near the cutoff."
   - rdrobust handles this with data-driven bandwidth selection.

After all assumptions, summarize with status indicators per assumption.

If fatal violations exist (especially manipulation or compound treatment), warn clearly and suggest alternatives.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/rdd.md` or `templates/python/rdd.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/rdd.md` or `templates/python/rdd.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**Always include**:
- RD plot (visual inspection of the discontinuity)
- Density test for manipulation (Cattaneo, Jansson, and Ma 2020)
- Main RD estimate with robust confidence interval
- Bandwidth selection details
- Covariate smoothness checks

**Sharp RDD (R)**:
```r
library(rdrobust)
library(rddensity)

# RD plot — visual inspection
rdplot(Y, X, c = cutoff,
       title = "RD Plot",
       x.label = "Running Variable",
       y.label = "Outcome")

# Density test for manipulation (Cattaneo, Jansson, and Ma 2020)
density_test <- rddensity(X, c = cutoff)
summary(density_test)

# Main RD estimate with robust bias-corrected inference
rd_est <- rdrobust(Y, X, c = cutoff)
summary(rd_est)

# With covariates for precision
rd_cov <- rdrobust(Y, X, c = cutoff, covs = cbind(Z1, Z2))
summary(rd_cov)
```

**Fuzzy RDD (R)**:
```r
library(rdrobust)

# Fuzzy RDD — treatment is endogenous, cutoff is instrument
rd_fuzzy <- rdrobust(Y, X, c = cutoff, fuzzy = treatment)
summary(rd_fuzzy)
```

**Sharp RDD (Python)**:
```python
from rdrobust import rdrobust, rdplot, rdbwselect
from rddensity import rddensity

# RD plot
rdplot(Y, X, c=cutoff,
       title="RD Plot",
       x_label="Running Variable",
       y_label="Outcome")

# Density test for manipulation (Cattaneo, Jansson, and Ma 2020)
density_test = rddensity(X, c=cutoff)
print(density_test)

# Main RD estimate
rd_est = rdrobust(Y, X, c=cutoff)
print(rd_est)
```

**Fuzzy RDD (Python)**:
```python
from rdrobust import rdrobust

# Fuzzy RDD
rd_fuzzy = rdrobust(Y, X, c=cutoff, fuzzy=treatment)
print(rd_fuzzy)
```

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **Bandwidth sensitivity**: Re-estimate at 50%, 75%, 125%, and 150% of the optimal bandwidth. Results should be qualitatively stable.
2. **Donut hole test**: Exclude units within a small window right at the cutoff (e.g., +/- 1 unit of the running variable). If manipulation is mild, the effect should survive.
3. **Placebo cutoffs**: Run the RD analysis at cutoff values where there is NO treatment. Finding an "effect" at a placebo cutoff suggests model misspecification.
4. **Covariate discontinuity tests**: Run rdrobust on pre-determined covariates as outcomes. They should NOT show a discontinuity at the cutoff.
5. **Polynomial order sensitivity**: Try local linear (p=1) and local quadratic (p=2). Results should be consistent.

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
| Density test rejects (rddensity) | 🚨 Fatal | Running variable is manipulated. RDD is likely invalid. Warn user before continuing. |
| Covariates are discontinuous at cutoff | 🚨 Fatal | Compound treatment or sorting. Warn user before continuing. |
| Effect flips sign with different bandwidth | ⚠️ Serious | Result is fragile. Report sensitivity plot. |
| Very few observations near cutoff | ⚠️ Serious | Estimates imprecise. Report effective sample size and CI width. |

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
| "There's no manipulation -- it's a natural cutoff" | Run the density test (`rddensity`). Natural cutoffs can still be gamed. |
| "We can extrapolate the RDD effect to the full population" | RDD estimates are local to the cutoff. Say so. |
| "Default bandwidth is fine" | Report sensitivity to bandwidth choice. One bandwidth = one fragile result. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the regression discontinuity analysis:
- The estimated treatment effect at the cutoff is [coefficient] (95% robust CI: [lower, upper]).
- The bandwidth used was [h], including observations within [h] units of the cutoff.
- This means [plain-language interpretation in their specific context].

**Local interpretation**: This effect applies to units near the cutoff ([running variable] close to [cutoff value]), not the full population. Units far from the cutoff may experience different effects.

Density test (Cattaneo, Jansson, and Ma 2020):
- [Result of density test — 'No evidence of manipulation' or 'Warning: density discontinuity detected']

Caveats:
- [Manipulation concerns from Stage 2]
- [Compound treatment concerns]
- [Limited external validity — this is a local estimate]
- [Sample size near cutoff]"

### Reading Your Results

**Density test (Cattaneo, Jansson, and Ma 2020)**: If the test rejects: "There are suspiciously more (or fewer) units just above or below the cutoff. This suggests people can manipulate their score to land on the preferred side, which breaks the 'as-if random' logic of RDD. The estimate is not credible without addressing this." If it passes: "No evidence of manipulation at the cutoff. Units on either side appear comparable."

**Bandwidth choice**: "The bandwidth of [h] means you're using units within [h] of the cutoff. Narrower = less bias (tighter local comparison) but more variance (fewer observations). The robust confidence interval accounts for this tradeoff. If results change dramatically across bandwidths, the estimate is fragile."

**Local interpretation**: "This effect applies only to units near the cutoff — not the entire population. If you're deciding whether to change a policy that affects everyone, consider whether the effect at the margin generalizes to units far from the cutoff."

**Covariate smoothness**: If any covariate shows a discontinuity at the cutoff: "This covariate jumps at the cutoff, which shouldn't happen if assignment near the cutoff is as-if random. Either there's manipulation, or there's a compound treatment — something else changes at the same cutoff."

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

"Your RDD analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Refine**: If manipulation or compound treatments were concerning, we can discuss mitigations.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Manipulation of the running variable**: If units can precisely control their position relative to the cutoff, RDD is invalid. Run the density test (`rddensity`) before proceeding.
- **Bandwidth too wide**: Large bandwidths increase bias. Always report results across multiple bandwidths and use MSE-optimal selection from rdrobust.
- **Covariate discontinuities**: If covariates jump at the cutoff, there may be compound treatments. Check covariate balance at the threshold.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-iv` -- If cutoff is fuzzy and instrument framing works
- `/causal-did` -- If pre/post data and a control group exist

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### RDD: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
