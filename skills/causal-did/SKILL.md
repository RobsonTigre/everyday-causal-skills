---
name: causal-did
description: Implements difference-in-differences in R or Python with parallel trends testing, robustness checks, and plain-language interpretation. Use when user asks about DiD, staggered rollout, TWFE, event study, or parallel trends. Not for simple pre/post without a control group.
metadata:
  author: Robson Tigre
  version: 0.3.2
  compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal DiD

You guide users through a complete difference-in-differences analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/did.md` — the assumption checklist for DiD.
3. Read `references/method-registry.md` → "Difference-in-Differences" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, treatment, population, outcome, language, data structure. Confirm: "I've read your analysis plan. You're looking at [treatment] on [outcome] using DiD. Does that sound right?"

**If no plan**: Ask:
1. "What's the treatment and when did it start?"
2. "What's the outcome metric?"
3. "Do you have panel data (same units observed over time)?"
4. "Is this a staggered rollout (units treated at different times) or a single treatment date?"
5. "How many units and time periods?"
6. "R or Python?"

**Determine variant**:
- Single treatment date, 2 groups → Classic 2x2 DiD
- Single date, panel → TWFE with unit + time FE
- Staggered dates → Staggered DiD (Callaway-Sant'Anna or Sun-Abraham)
- Want dynamics → Event study

## Stage 2: Assumptions

Read `references/assumptions/did.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Parallel trends**: "Without the treatment, would the treated and control groups have followed similar trends? Let's check with a pre-trends test."
   - Offer event study plot code.

2. **No anticipation**: "Did treated units change behavior before treatment actually started?"

3. **Stable composition**: "Did units enter or leave the sample because of treatment?"

4. **No spillovers (SUTVA)**: "Could treated units affect control units' outcomes?"

5. **Functional form** (for staggered): "Standard TWFE can be biased with heterogeneous treatment effects across cohorts. I'll use a robust estimator."

After all assumptions, summarize with status indicators per assumption.

If fatal violations exist, warn clearly and suggest alternatives.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/did.md` or `templates/python/did.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/did.md` or `templates/python/did.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**Common pitfall — entity fixed effects and time-invariant variables**:
When using entity (unit) fixed effects, do NOT include time-invariant variables as regressors (e.g., a `treated` dummy that never changes within a unit). Entity FE already absorb all time-invariant unit characteristics. Including them causes perfect multicollinearity and will crash PanelOLS / `feols` or silently drop the variable. The interaction term `treated * post` (or `treated:post` in formula syntax) is fine because it varies over time.

**Always include**:
- Data preparation / reshaping
- Main estimation with proper specification
- Clustered standard errors (at unit level)
- Effect size with 95% confidence interval
- Event study plot (for visual dynamics)
- Results summary table

**For classic 2x2 DiD (R)**:
```r
library(fixest)
library(modelsummary)

model <- feols(outcome ~ treated:post | unit + time, data = df,
               cluster = ~unit)
summary(model)
modelsummary(model, stars = TRUE)
```

**For staggered DiD (R)**:
```r
library(did)
att_gt <- att_gt(yname = "outcome", tname = "time", idname = "unit",
                  gname = "first_treat", data = df)
summary(att_gt)
ggdid(att_gt)
agg <- aggte(att_gt, type = "simple")
summary(agg)
```

**For classic DiD (Python)**:
```python
from linearmodels.panel import PanelOLS
import statsmodels.formula.api as smf

# PanelOLS approach
mod = PanelOLS.from_formula('outcome ~ treated_post + EntityEffects + TimeEffects',
                             data=df.set_index(['unit', 'time']))
res = mod.fit(cov_type='clustered', cluster_entity=True)
print(res)
```

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **Placebo test (pre-treatment)**: Run DiD on pre-treatment data with a fake treatment date midway through.
2. **Placebo outcome**: Run DiD on an outcome that should NOT be affected.
3. **Pre-trends test**: Test if event study pre-treatment coefficients are jointly zero.
4. **Specification robustness**: Different controls, different clustering, different sample windows.

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
| Pre-treatment coefficients show a clear trend | 🚨 Fatal | Parallel trends assumption is violated. Warn user before continuing. |
| Treatment timing correlates with outcome shocks | 🚨 Fatal | Selection into treatment invalidates DiD. Warn user before continuing. |
| Large compositional change around treatment | ⚠️ Serious | Flag survivorship/attrition bias. Report bounds if possible. |
| Only 1-2 pre-periods available | ⚠️ Serious | Parallel trends untestable. State as strong caveat. |

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
| "Parallel trends look close enough" | "Close" isn't a statistical concept. Run the formal pre-test and report the result. |
| "We only have 2 pre-periods, so we can't test trends" | Then parallel trends is an untestable assumption. Say so clearly -- don't skip it. |
| "TWFE is fine for staggered rollout" | TWFE with heterogeneous effects and staggered timing is biased. Use Callaway-Sant'Anna or Sun-Abraham. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the DiD analysis:
- The estimated treatment effect is [coefficient] (95% CI: [lower, upper]).
- This means [plain-language interpretation in their specific context].
- [Business metric translation if applicable.]

Caveats:
- [Weakest assumptions from Stage 2]
- [What the estimate does NOT tell us]"

### Reading Your Results

**Pre-treatment coefficients (event study)**: If any pre-treatment coefficient is individually significant, tell the user: "This period shows a significant effect before treatment — which shouldn't happen. Small blips may be noise, but a clear upward or downward trend suggests the groups were already diverging, which undermines parallel trends."

**Parallel trends test**: If the joint test rejects (p < 0.05): "The formal test rejects parallel trends — the core assumption for DiD. If treated and control groups were on different trajectories, the estimated effect absorbs that pre-existing difference." If p > 0.05: "The test doesn't reject parallel trends, but this test has low power with few pre-treatment periods. The event study plot matters as much as the p-value — look for visual patterns."

**ATT interpretation**: "The ATT of [X] means treated units changed by [X] more than control units after treatment. This is the effect on those who were actually treated — it doesn't tell you what would happen if you treated a different group."

**Confounding time trends**: "If something else changed at the same time as treatment (a policy, a season, a market shift), DiD can't separate the treatment effect from that event. Look for concurrent changes and consider whether they affect treated and control groups differently."

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

"Your DiD analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats.
2. **Refine**: If assumptions were concerning, we can explore mitigations.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Post-treatment controls included**: Controlling for variables affected by treatment biases the estimate. Audit covariates against treatment timing.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-hte` -- Explore who benefits more or less from treatment (heterogeneous effects)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-sc` -- Few treated units with long pre-period
- `/causal-matching` -- Cross-sectional data with rich covariates

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### DiD: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
