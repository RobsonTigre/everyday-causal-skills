---
name: causal-sc
description: Builds synthetic control counterfactuals in R or Python with donor weighting, pre-treatment fit diagnostics, and placebo tests. Use when user mentions synthetic control, single treated unit, comparative case study, or donor pool. Not for settings with many treated units.
metadata:
  author: Robson Tigre
  compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal SC

You guide users through a complete synthetic control analysis following a 5-stage pattern.

**Canonical runnable block**: When emitting executable code, put the exact line
`# EVAL_EXECUTABLE` as the first nonblank program line inside exactly one
correct-language code fence. Do not indent it or add other text on that line.
That fence must contain the complete program to run. Keep preflight snippets and
illustrative alternatives outside it; do not mark more than one block.

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

**Fully specified direct mode**: If the user or attached fixture already identifies
the treated unit, intervention date, outcome, donor units, pre/post periods,
language, and either predictors or enough pre-treatment outcomes to construct
outcome-based predictors, and asks for the complete response now, do not repeat the
intake or stop for confirmation. Direct mode overrides only interactive pauses; it
does not override diagnostic stop rules. A known fatal violation takes precedence
over direct mode: issue the verdict and do not provide an effect estimate. When no
separate predictors are named, use stated pre-treatment outcome periods as
predictors and disclose that choice.

Within direct mode, the guarded runnable block replaces the later instruction to
wait for the user to report an unresolved testable diagnostic: the guard itself
prevents the effect stage from running on failure. This direct-mode subsection also
takes precedence over Stage 3's template-adherence rule and missing-package pause.
Use the fixture-specific `Synth` path below instead of copying the generic template.
Those later wait and template rules still apply outside direct mode. If the supplied
facts already establish a fatal violation, the fatal verdict wins over direct mode:
do not calculate or interpret an effect.

Start the runnable code with donor eligibility and data-coverage checks, followed by
the convex-hull assessment. Fit the synthetic weights next, but calculate and check
pre-treatment RMSPE and weight concentration before calculating any post-treatment
effect or placebo rank. Only if those gates pass may the code calculate the
post-treatment gap and interpret the placebo distribution. Implement an explicit
guard: on poor pre-fit, convex-hull failure, or another fatal diagnostic, emit the
verdict and stop before effect estimation; on a serious concentration warning,
report it and run the specified donor-dependence check before any interpretation.
Supplying the whole guarded program now satisfies direct mode; it does not mean any
diagnostic has run. Do not claim that the code ran, diagnostics passed, files were
saved, or results exist unless execution or user-supplied output establishes that.

Keep no-interference, no-anticipation, and donor-pool plausibility explicit as
substantive assumptions. The code cannot prove them, and passing the testable gates
does not establish them. Provide the method explanation, assumptions, complete
runnable implementation, diagnostics, placebo inference, and result-reading
instructions in one response. The direct response must:

- explain that the synthetic control is a weighted combination of untreated donors
  chosen to reproduce the treated unit before intervention;
- include code to calculate pre-treatment RMSPE and explain what the measure means,
  because a post-treatment gap is not credible if the synthetic unit could not track
  the treated unit beforehand;
- print donor weights and explain both what the largest weights mean and why a result
  concentrated on one or two donors is dependent on those donors;
- state that donor-pool inclusion is a substantive researcher decision and test that
  dependence with leave-one-out or alternative-pool analyses; and
- include in-space placebo code and explain rank/post-to-pre-RMSPE inference rather
  than treating it as an ordinary regression p-value.

Use the supplied treated unit, date, outcome, and donor list literally in the code;
do not leave generic placeholders when those values are available. Do not state
numerical weights, RMSPE, gaps, or placebo ranks unless they come from executed or
user-supplied output.

**Outcome-only `Synth` fixture path**: For the supplied panel with columns
`unit,time,outcome,treated,post`, treated unit 1, intervention period 21, and donors
2 through 10, use these values literally. The panel has no separate covariates, so
use pre-treatment outcome history through `special.predictors`; never invent
`predictor1` or `predictor2`. Give the following as the one guarded runnable block,
adapt only the data path if the attachment is mounted elsewhere, and explain that
the screening threshold must be prespecified and justified for the outcome scale:

```r
# EVAL_EXECUTABLE
required <- "Synth"
if (!requireNamespace(required, quietly = TRUE)) {
  stop("Missing R package Synth. Install it explicitly, then rerun this script.")
}

df <- read.csv("evals/data/sc_basic_l3.csv")
treated_id <- 1L
intervention <- 21L
donor_ids <- 2:10
pre_periods <- 1:(intervention - 1L)
all_periods <- sort(unique(df$time))
max_pre_rmspe_share <- 0.10 # prespecify and justify for this outcome scale

required_columns <- c("unit", "time", "outcome", "treated", "post")
stopifnot(all(required_columns %in% names(df)))
study <- df[df$unit %in% c(treated_id, donor_ids), required_columns]
coverage <- table(study$unit, study$time)
if (!setequal(unique(study$unit), c(treated_id, donor_ids)) ||
    any(coverage != 1L) || anyNA(study[, c("unit", "time", "outcome")])) {
  stop("FATAL: donor eligibility or panel coverage failed; no effect was estimated.")
}

pre <- study[study$time %in% pre_periods, ]
treated_pre <- pre$outcome[match(pre_periods, pre$time[pre$unit == treated_id])]
donor_pre <- vapply(donor_ids, function(id) {
  x <- pre[pre$unit == id, ]
  x$outcome[match(pre_periods, x$time)]
}, numeric(length(pre_periods)))
outside_hull <- treated_pre < apply(donor_pre, 1, min) |
  treated_pre > apply(donor_pre, 1, max)
if (any(outside_hull)) {
  stop("FATAL: treated outcomes leave the donor range before treatment; no effect was estimated.")
}

outcome_history <- lapply(c(1L, 5L, 10L, 15L, 20L), function(t) {
  list("outcome", t, "mean")
})
fit_sc <- function(target, controls) {
  dp <- Synth::dataprep(
    foo = as.data.frame(study),
    predictors = "outcome", predictors.op = "mean",
    special.predictors = outcome_history,
    dependent = "outcome", unit.variable = "unit", time.variable = "time",
    treatment.identifier = target, controls.identifier = controls,
    time.predictors.prior = pre_periods, time.optimize.ssr = pre_periods,
    time.plot = all_periods
  )
  syn <- Synth::synth(dp)
  gap <- drop(dp$Y1plot - dp$Y0plot %*% syn$solution.w)
  list(dp = dp, syn = syn, gap = gap,
       pre_rmspe = sqrt(mean(gap[all_periods < intervention]^2)))
}

main <- fit_sc(treated_id, donor_ids)
weights <- data.frame(unit = donor_ids, weight = drop(main$syn$solution.w))
weights <- weights[order(weights$weight, decreasing = TRUE), ]
print(weights)
cat("Pre-treatment RMSPE:", main$pre_rmspe, "\n")
pre_scale <- mean(abs(treated_pre))
fit_ok <- is.finite(main$pre_rmspe) && is.finite(pre_scale) && pre_scale > 0 &&
  main$pre_rmspe / pre_scale <= max_pre_rmspe_share
if (!fit_ok) {
  stop("FATAL: prespecified pre-fit gate failed; no effect or placebo rank was estimated.")
}

positive_donors <- weights$unit[weights$weight > 0.001]
if (max(weights$weight) > 0.80) {
  message("SERIOUS: one donor exceeds 80%; inspect leave-one-out results before interpretation.")
}
loo <- lapply(positive_donors, function(drop_id) {
  fit_sc(treated_id, setdiff(donor_ids, drop_id))$gap
})
names(loo) <- positive_donors
if (max(weights$weight) > 0.80 && length(loo) == 0L) {
  stop("SERIOUS: concentrated weights require a leave-one-out result before interpretation.")
}

effect <- mean(main$gap[all_periods >= intervention])
loo_effects <- vapply(loo, function(gap) {
  mean(gap[all_periods >= intervention])
}, numeric(1))
ratio <- function(gap) {
  sqrt(mean(gap[all_periods >= intervention]^2)) /
    sqrt(mean(gap[all_periods < intervention]^2))
}
placebos <- lapply(donor_ids, function(fake_id) {
  fit_sc(fake_id, setdiff(donor_ids, fake_id))
})
placebo_pre <- vapply(placebos, `[[`, numeric(1), "pre_rmspe")
eligible <- is.finite(placebo_pre) & placebo_pre <= 5 * main$pre_rmspe
placebo_ratios <- vapply(placebos[eligible], function(x) ratio(x$gap), numeric(1))
treated_ratio <- ratio(main$gap)
pseudo_p <- mean(c(treated_ratio, placebo_ratios) >= treated_ratio)

cat("Average post-treatment gap:", effect, "\n")
cat("Leave-one-out effect range:", range(loo_effects), "\n")
cat("Treated post/pre RMSPE ratio:", treated_ratio, "\n")
cat("Placebo rank fraction (pseudo p-value):", pseudo_p, "\n")
cat("Leave-one-out specifications completed:", length(loo), "\n")
Synth::path.plot(synth.res = main$syn, dataprep.res = main$dp)
Synth::gaps.plot(synth.res = main$syn, dataprep.res = main$dp)
```

Explain the output in this order: pre-RMSPE and the treated-versus-synthetic path;
weight concentration and the leave-one-out range; then the post-treatment gap and
its rank among eligible in-space placebos. Call the rank fraction a permutation or
pseudo p-value, not an ordinary regression p-value. The code has not been executed;
do not claim diagnostics passed or interpret the effect until actual output clears
the pre-fit and donor-dependence checks. No-interference, no-anticipation, and donor
validity still require substantive arguments even when the code gates pass.

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
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Outside fully specified direct mode, do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first. In direct mode, provide the guarded program now; its diagnostic gates must stop before effect estimation on failure. A fatal violation already established by supplied facts still wins.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/sc.md` or `templates/python/sc.md` for code patterns.

**Missing-package preflight**: Outside fully specified direct mode, the template's Prerequisites block detects (never installs) missing packages. Follow `references/preflight.md`: report what's missing, then ask the user whether they want you to install it for them or do it themselves — install only on an explicit yes. In direct mode, the guarded program detects the missing package and stops honestly without an installation pause or claim of execution.

**IMPORTANT — Template adherence**: Outside fully specified direct mode, copy the code pattern from the appropriate template (`templates/r/sc.md` or `templates/python/sc.md`) exactly, then adapt only variable names to match the user's data. In direct mode, the fixture-specific pathway in Stage 1 takes precedence and must be used instead. Do not copy generic predictor names into an outcome-only fixture.

**R package preference**: Use the `Synth` package (not `tidysynth`) for R implementations unless the user specifically requests `tidysynth`. The `Synth` package is more widely installed.

**Always include**:
- Synthetic control construction with explicit donor weights
- Pre-treatment fit plot (treated vs synthetic)
- Post-treatment gap plot (treated minus synthetic)
- Donor weight table
- Pre-treatment RMSPE

**Synthetic control (R — Synth)**:
```r
library(Synth)

dataprep_out <- dataprep(
  foo = df,
  predictors = "outcome",
  predictors.op = "mean",
  special.predictors = lapply(c(pre_start, pre_mid, pre_end), function(t) {
    list("outcome", t, "mean")
  }),
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

### Reading Your Results

**Donor weights**: "The synthetic control is a weighted mix of donor units. If one donor carries more than 60-70% of the weight, the analysis is essentially a comparison with that single unit — fragile and sensitive to anything idiosyncratic about that donor. A more balanced portfolio of donors is more credible."

**Pre-treatment RMSPE**: "RMSPE of [X] means the synthetic control's predictions were off by [X] on average in the pre-treatment period. Lower is better. If the synthetic version can't track the treated unit before treatment, its post-treatment projection is unreliable — like forecasting with a broken model."

**Post/pre RMSPE ratio**: "A ratio above 2 means the gap between the treated unit and its synthetic version roughly doubled after treatment — suggesting a real effect. A ratio near 1 means no detectable change. Compare this ratio to the placebo distribution."

**Placebo rank**: "The treated unit ranks [X] out of [N] in the placebo distribution. Only [X-1] donor units showed a larger effect when we pretended they were treated. Think of rank/N as a pseudo p-value: 1/20 = 0.05, 2/20 = 0.10. Ranks above 0.10 are not clearly distinguishable from noise."

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
