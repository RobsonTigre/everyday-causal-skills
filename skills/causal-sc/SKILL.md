---
name: causal-sc
description: Builds synthetic control counterfactuals in R or Python with donor weighting, pre-treatment fit diagnostics, and placebo tests. Use when user mentions synthetic control, single treated unit, comparative case study, or donor pool. Not for settings with many treated units.
metadata:
  author: Robson Tigre
  version: 0.3.2
compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal SC

You guide users through a complete synthetic control analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/sc.md` — the assumption checklist for synthetic control.
3. Read `references/method-registry.md` → "Synthetic Control" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, treated unit, donor pool, outcome, language, data structure. Confirm: "I've read your analysis plan. You're constructing a synthetic control for [treated unit] to estimate the effect of [treatment] on [outcome]. Does that sound right?"

**If no plan**: Ask:
1. "How many treated units are there? (Synthetic control is designed for 1 or very few.)"
2. "How many potential control (donor) units are available?"
3. "How many pre-treatment time periods do you have? (Need at least 10-20 for a good pre-treatment fit.)"
4. "How many post-treatment time periods?"
5. "What outcome variable are you tracking?"
6. "What predictor variables do you have for matching (e.g., pre-treatment outcomes, economic indicators)?"
7. "R or Python?"

**Determine variant**:
- 1 treated unit, many donors, good pre-fit expected → Classic synthetic control (Abadie et al.)
- 1 treated unit, treated unit is outlier or pre-fit is poor → **Augmented synthetic control** (Ben-Michael et al., `augsynth`)
- Few treated units (2-5) → Iterate SC for each, or use generalized SC (`gsynth`)
- Many treated units → Consider DiD instead (suggest `causal-did`)
- Want prediction intervals → Use `scpi` (Python) or `gsynth` (R)

## Stage 2: Assumptions

Read `references/assumptions/sc.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Pre-treatment fit quality**: "Can a weighted combination of donor units reproduce the treated unit's pre-treatment trajectory? Poor fit means the synthetic control is unreliable."
   - Testable: inspect pre-treatment RMSPE (root mean squared prediction error).
   - Offer fit visualization code.

2. **Convex hull**: "Does the treated unit's pre-treatment characteristics lie within the range spanned by the donor units? If the treated unit is an extreme outlier, no convex combination of donors can match it."
   - Partially testable: check if the treated unit's values fall within the min-max range of the donor pool.
   - If convex hull is violated: **recommend augmented synthetic control** (`augsynth` in R) which handles extrapolation by adding a ridge-regularized outcome model. This is the modern default for cases where the treated unit is an outlier relative to donors.

3. **No interference between units**: "Could the treatment of [treated unit] have affected the donor units' outcomes? If donors are affected by the treatment, the synthetic counterfactual is contaminated."
   - Must be argued substantively.

4. **Donor pool composition**: "Are all donor units plausible counterfactuals? Including donors affected by their own shocks can bias the synthetic control."
   - Ask: "Did any donor unit experience its own large shock during the study period?"

5. **No anticipation**: "Did the treated unit's behavior change before the treatment actually started?"

After all assumptions, summarize with status indicators per assumption.

If fatal violations exist (especially poor pre-treatment fit or contaminated donor pool), warn clearly and suggest alternatives.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/sc.md` or `templates/python/sc.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/sc.md` or `templates/python/sc.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**R package preference**: Use the `Synth` package (not `tidysynth`) for R implementations unless the user specifically requests `tidysynth`. The `Synth` package is more widely installed.

**Always include**:
- Synthetic control construction with explicit donor weights
- Pre-treatment fit plot (treated vs synthetic)
- Post-treatment gap plot (treated minus synthetic)
- Donor weight table
- Pre-treatment RMSPE

**Synthetic control (R — tidysynth)**:
```r
library(tidysynth)

sc <- df %>%
  synthetic_control(
    outcome = outcome,
    unit = unit_id,
    time = time,
    i_unit = "treated_unit_name",
    i_time = treatment_time,
    generate_placebos = TRUE
  ) %>%
  generate_predictor(
    time_window = pre_start:pre_end,
    predictor1 = mean(predictor1),
    predictor2 = mean(predictor2),
    outcome_avg = mean(outcome)
  ) %>%
  generate_weights(optimization_window = pre_start:pre_end) %>%
  generate_control()

# Plot: treated vs synthetic
sc %>% plot_trends()

# Plot: treatment effect (gap)
sc %>% plot_differences()

# Donor weights
sc %>% grab_unit_weights() %>% arrange(desc(weight))

# Pre-treatment fit
sc %>% grab_significance() %>% filter(unit_name == "treated_unit_name")
```

**Synthetic control (R — Synth)**:
```r
library(Synth)

dataprep_out <- dataprep(
  foo = df,
  predictors = c("predictor1", "predictor2"),
  predictors.op = "mean",
  dependent = "outcome",
  unit.variable = "unit_id",
  time.variable = "time",
  treatment.identifier = treated_id,
  controls.identifier = donor_ids,
  time.predictors.prior = pre_start:pre_end,
  time.optimize.ssr = pre_start:pre_end,
  time.plot = full_start:full_end
)

synth_out <- synth(dataprep_out)
path.plot(synth.res = synth_out, dataprep.res = dataprep_out)
gaps.plot(synth.res = synth_out, dataprep.res = dataprep_out)
```

**Synthetic control (Python — scpi)**:
```python
from scpi_pkg.scdata import scdata
from scpi_pkg.scest import scest
from scpi_pkg.scpi import scpi
from scpi_pkg.scplot import scplot

# Prepare data
scd = scdata(
    df=df,
    id_var="unit_id",
    time_var="time",
    outcome_var="outcome",
    period_pre=list(range(pre_start, treatment_time)),
    period_post=list(range(treatment_time, post_end + 1)),
    unit_tr="treated_unit_name",
    unit_co=donor_list
)

# Estimate
sc_est = scest(scd, w_constr={"name": "simplex"})
print(sc_est)

# Prediction intervals
sc_pred = scpi(scd, w_constr={"name": "simplex"})
print(sc_pred)

# Plot
scplot(sc_pred)
```

**Augmented synthetic control (R — augsynth)**:

Use when pre-treatment fit is poor or the treated unit falls outside the donor pool's convex hull. ASCM adds a ridge-regularized outcome model on top of SCM weights, allowing controlled extrapolation.

```r
library(augsynth)

# Augmented synthetic control
asyn <- augsynth(
  outcome ~ treatment,
  unit = unit_id,
  time = time,
  data = df,
  progfunc = "Ridge",    # bias correction via ridge regression
  scm = TRUE             # combine with SCM weights
)

summary(asyn)
plot(asyn)

# Compare with standard SCM
syn_only <- augsynth(
  outcome ~ treatment,
  unit = unit_id,
  time = time,
  data = df,
  progfunc = "None",     # no augmentation = standard SCM
  scm = TRUE
)

# If augmented and standard diverge substantially,
# the treated unit was likely outside the convex hull
cat("Standard SCM ATT:", summary(syn_only)$att$Estimate, "\n")
cat("Augmented SCM ATT:", summary(asyn)$att$Estimate, "\n")
```

**When to upgrade from SCM to ASCM**:
1. Pre-treatment RMSPE is large (poor fit)
2. Donor weights are concentrated on 1-2 units
3. The treated unit's pre-treatment values fall outside the range of donor values on key predictors
4. Standard SCM and ASCM estimates diverge substantially (suggesting extrapolation bias in standard SCM)

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **In-space placebo (permutation)**: Apply the synthetic control method to each donor unit as if it were the treated unit. If the actual treated unit's effect is large relative to the donor "effects," that supports a genuine treatment effect. Calculate a p-value: rank the treated unit's post/pre RMSPE ratio among all placebos.
2. **In-time placebo**: Pretend treatment happened at an earlier date (e.g., halfway through the pre-treatment period). If you find a "gap" opening before the true treatment, the pre-treatment fit was unreliable.
3. **Leave-one-out donor analysis**: Re-estimate removing one donor at a time. If results are driven by a single donor, the finding is fragile.
4. **Different predictor specifications**: Vary which pre-treatment variables are used as predictors. Results should be robust.
5. **Standard vs. augmented comparison**: Run both standard SCM and augmented SCM. If estimates diverge, the standard SCM may be biased by convex hull violations. Report both.

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
| Pre-treatment RMSPE is large (poor fit) | 🚨 Fatal | Synthetic control is unreliable. Warn user; consider augmented SC or switching methods. |
| Treated unit outside donor convex hull | 🚨 Fatal | Extrapolation — weights cannot construct a valid counterfactual. Warn user before continuing. |
| One donor weight > 80% | ⚠️ Serious | Effectively a pairwise comparison. Flag and test robustness to removing that donor. |
| Fewer than 5 donors | ⚠️ Serious | Placebo inference has almost no power. State explicitly. |

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
| "The pre-fit looks reasonable" | Report RMSPE. "Reasonable" needs a number. |
| "We have enough donors" | With fewer than ~10 donors, placebo inference has almost no power. Report it. |
| "The weights make sense" | If one donor dominates (>80%), the synthetic control is basically a comparison to one unit. Flag it. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the synthetic control analysis:
- The estimated effect for [treated unit] is [gap value] in the post-treatment period.
- This is based on comparison with a synthetic version of [treated unit] constructed from [list key donors with largest weights].
- The synthetic control closely matched the treated unit in the pre-treatment period (RMSPE = [value]).

Placebo inference:
- When the same method is applied to [N] donor units, the treated unit's effect ranks [rank/N] — implying a pseudo p-value of [p].

Cumulative vs period effects:
- The average per-period effect is [X].
- The cumulative effect over the full post-period is [Y].

Caveats:
- [Pre-treatment fit quality]
- [Donor pool composition concerns]
- [Whether the effect applies only to this specific unit]
- [Any donors with large weights that may be problematic]"

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

"Your synthetic control analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Refine**: If pre-treatment fit was poor or the donor pool was questionable, we can explore alternatives.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Wrong R package**: Use the `Synth` package (Abadie et al.), not `tidysynth`, for the canonical implementation. tidysynth has API differences that break standard diagnostics.
- **Poor pre-treatment fit**: If RMSPE is large relative to the outcome scale, the synthetic control is unreliable. Report pre-treatment RMSPE and consider whether the donor pool is adequate.
- **Too few donor units**: Placebo tests require enough donors to construct a meaningful distribution. Fewer than 10 donors limits inference.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-did` -- If more treated units are available
- `/causal-timeseries` -- Single unit with no suitable donors

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### SC: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
