---
name: causal-hte
description: Estimates heterogeneous treatment effects using Causal Forest and DML with validation (BLP/GATES/CLAN/TOC) and policy learning (policytree). Use when user asks about CATE, who benefits, subgroup effects, personalization, targeting, treatment effect heterogeneity, or causal forest.
metadata:
  author: Robson Tigre
  version: 0.1.0
  compatibility: "R (>= 4.0) with grf, policytree. Python (>= 3.9) with econml."
---

# Causal HTE

You guide users through a complete heterogeneous treatment effect analysis following a 5-stage pattern: Setup → Assumptions → Implementation → Validation → Interpretation + Policy.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/hte.md` — the assumption checklist for HTE methods.
3. Read `references/method-registry.md` → "Heterogeneous Treatment Effects (HTE) / CATE Estimation" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If coming from another ATE skill** (matching, experiments, DiD, IV): Inherit the treatment, outcome, covariates, and identification strategy. Ask only HTE-specific questions below.

**If plan exists**: Read it. Extract business objective, treatment, covariates, outcome, language, data structure. Confirm: "I've read your analysis plan. You're estimating the effect of [treatment] on [outcome] and now want to explore heterogeneity. Does that sound right?"

**If no plan / standalone**: Ask:
1. "What is the treatment and outcome?"
2. "What covariates are available?"
3. "R or Python?"

**HTE-specific questions (always ask)**:
1. "Which variables might *moderate* the treatment effect? (These are your effect modifiers — variables where you think the treatment works differently for different people.)"
2. "Is treatment randomized (RCT/A/B test) or observational?" → determines RCT vs observational path
3. "Is your outcome continuous or binary?" → if binary, add scale warnings
4. "Do you have pre-specified subgroup hypotheses, or are you exploring?" → labels the analysis

**X vs W decision aid (MUST present to user)**:

| Category | Goes in... | Meaning |
|----------|-----------|---------|
| **W (confounders)** | Nuisance models only | Affects both treatment AND outcome. Needed for identification. |
| **X (effect modifiers)** | CATE model | Might change the SIZE of the treatment effect. |
| **Both X and W** | Both stages | Variable is a confounder AND might moderate the effect. **When in doubt, include in both.** |

**Platform note**: In `grf`, all covariates go in one matrix X — there is no separate W argument. `grf` handles confounding control internally. In `econml`, X and W are separate arguments — putting a confounder only in X (not W) biases estimates.

**Pre-flight checks (before proceeding to Stage 2)**:
- **Sample size**: n < 2,000 → emit SERIOUS warning, recommend LinearDML with pre-specified interactions only
- **Binary outcome detection** → warn about boundary issues (predicted CATEs near 0 or 1 can be unreliable on the probability scale)
- **Overlap check**: If user provides data, check propensity score distribution before proceeding
- **Post-treatment modifier check**: For EACH proposed effect modifier, ask: "Was [variable] measured BEFORE treatment began? Could the treatment have affected it?" If yes → FATAL

## Stage 2: Assumptions

Read `references/assumptions/hte.md`. Walk through each assumption interactively:

**Critical framing (state this explicitly)**: "HTE estimation does NOT relax identification assumptions. If your ATE would be biased (e.g., unmeasured confounders), your CATEs are biased too. Machine learning does not overcome confounding."

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Conditional independence / unconfoundedness**: Same as matching — must believe all confounders are measured. If coming from an RCT, this is satisfied by design. If observational, discuss plausibility.

2. **Overlap / positivity (subgroup-level)**: "For HTE, overlap must hold *within* each CATE subgroup, not just overall. If the highest-effect group has propensity scores near 1, the effect estimate for that group is extrapolation."
   - Testable: check propensity within CATE quintiles (code in templates).

3. **SUTVA (no interference)**: Same as all methods.

4. **Effect modifiers must be pre-treatment**: "Variables in X must be measured before treatment. Post-treatment variables create spurious heterogeneity — the forest will 'discover' patterns that are mechanical, not real."
   - Not statistically testable — require user confirmation for each variable.

5. **Sufficient sample size**: n ≥ 2,000 for causal forests, n ≥ 100 per CATE quintile for reliable GATES.

6. **Honest estimation / sample splitting**: Verify `honesty = TRUE` in grf, `cv >= 3` in econml.

After all assumptions, summarize with status indicators per assumption.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/hte.md` or `templates/python/hte.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise. The templates have been tested; deviations introduce bugs.

**Two-pass approach (always follow this order)**:

1. **LinearDML first pass** (always run — fast, interpretable, screens for signal):
   - R: `best_linear_projection()` on a quick causal forest
   - Python: `LinearDML` with `summary()`
   - Report coefficients and significance. This tells you which variables have linear heterogeneity.

2. **Causal Forest** (primary estimator):
   - Only skip if LinearDML finds no signal AND n < 2,000
   - Branch on RCT vs observational for propensity handling:
     - RCT: supply known propensity (`W.hat = rep(0.5, n)` in R, `DummyClassifier` in Python)
     - Observational: let the forest estimate propensity internally

**Always include**:
- CATE distribution histogram
- Variable importance plot
- ATE estimate for comparison

## Stage 4: Validation

Generate validation code from templates. Full sequence:

0. **Calibration test** (gatekeeper — R only via `test_calibration()`):
   - If "mean.forest.prediction" not significant: forest may be fitting noise
   - If "differential.forest.prediction" not significant: heterogeneity not detected at this sample size

1. **BLP (Best Linear Predictor)**:
   - Significant beta = confirmed heterogeneity
   - Non-significant beta = "cannot detect heterogeneity at this sample size," NOT "no heterogeneity"
   - The ATE may still be significant — always check `average_treatment_effect()`

2. **GATES + overlap-within-quintile check**:
   - Sort units by predicted CATE into quintiles
   - Estimate actual ATE within each quintile
   - Check propensity score distribution within each quintile
   - Plot with confidence intervals

3. **CLAN (Classification Analysis)**:
   - Compare covariate means between top and bottom CATE quintiles
   - Identifies WHO the high/low effect groups are

4. **TOC/RATE** (R: `rank_average_treatment_effect()`):
   - Measures practical value of targeting vs treating everyone
   - AUTOC > 0 means targeting adds value

5. **Stability check**:
   - Re-run forest with different seed
   - Compare top-3 variable importance
   - If they change: SERIOUS — heterogeneity signal is unstable

## Verification Gate

Before proceeding to interpretation, confirm ALL of the following from actual code output:

- [ ] LinearDML ran and coefficients reported
- [ ] Causal Forest ran without errors
- [ ] Calibration test result reported (R) or ATE inference reported (Python)
- [ ] BLP result reported with interpretation
- [ ] GATES plotted with CIs
- [ ] At least one stability check ran
- [ ] Variable importance reported

**If any box is unchecked**: Flag it to the user — explain which evidence is missing and why it matters. Offer to run the missing step before interpreting. If the user chooses to continue anyway, carry the gap forward as a caveat in the interpretation.

**Watch for premature conclusions** — phrases like "The heterogeneity suggests..." before the gate passes. Quote actual output instead.

**Severity verdicts must appear BEFORE this gate.** If a Fatal or Serious issue was identified during Stage 2 or Stage 3, the severity verdict block must already be visible in the output above.

## Red Flags

### Data Diagnostic Signals

| Signal | Severity | Action |
|--------|----------|--------|
| Post-treatment variable in X | 🚨 Fatal | Spurious heterogeneity. Remove variable before estimation. |
| Propensity < 0.05 or > 0.95 in any CATE quintile | 🚨 Fatal | GATE for that quintile is extrapolation. Warn user. |
| Honest splitting turned off (honesty=FALSE / cv=1) | 🚨 Fatal | CIs invalid, CATEs overfit. Require re-estimation. |
| n < 2,000 total | ⚠️ Serious | Low power for heterogeneity detection. Recommend LinearDML only. |
| n < 100 per CATE quintile | ⚠️ Serious | GATES unreliable for small quintiles. |
| Calibration test fails (both terms non-significant) | ⚠️ Serious | Forest may be fitting noise. |
| BLP coefficient not significant | ⚠️ Serious | Cannot detect heterogeneity at this sample size. |
| GATES CIs all overlap | ⚠️ Serious | No detectable difference between CATE groups. |
| Single variable > 60% of importance | ⚠️ Serious | May indicate confounding with treatment, not moderation. Investigate. |
| Variable importance changes across seeds | ⚠️ Serious | Heterogeneity signal is not robust. |

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

Use only **FATAL** and **SERIOUS** severity labels. Do not invent additional tiers.

### Rationalization Shortcuts

| Shortcut | Reality |
|----------|---------|
| "The causal forest found the heterogeneity, so it must be real" | Causal forests discover patterns in data. Without validation (BLP, GATES), you don't know if the pattern is real or noise. |
| "Variable importance tells us what drives the treatment effect" | Variable importance measures splitting value, not causal moderation. A variable can be important for splitting without being a true effect modifier. |
| "We can skip LinearDML — the forest is more flexible" | LinearDML is a diagnostic, not a competitor. It screens for signal quickly and provides interpretable coefficients. Always run it first. |
| "No heterogeneity detected means effects are homogeneous" | It means you lack power to detect heterogeneity. The ATE applies broadly — which is a valid and useful finding. |
| "The policy tree tells us who to treat" | It's an exploratory rule, not a deployment-ready policy. Validate on held-out data and run a confirmatory experiment. |

## Stage 5: Interpretation + Policy

Three layers, presented in order:

### Layer 1: Heterogeneity summary (always)

"Based on the HTE analysis:
- The overall ATE is [estimate] (95% CI: [lower, upper]).
- LinearDML found [significant/no significant] linear heterogeneity along [variables].
- The causal forest identified [variable1] and [variable2] as the primary drivers of heterogeneity (variable importance: [values]).
- BLP test: [result and interpretation].
- GATES: [description — monotonically increasing? flat? one outlier quintile?]
- CLAN: High-effect individuals tend to be [profile]. Low-effect individuals tend to be [profile].

**Important caveat**: Variable importance measures splitting value, not causal moderation. A variable that is important for the forest's predictions is not necessarily a causal modifier — it could correlate with a true modifier."

### Layer 2: Threshold rule (default)

Ask: "What is the cost of treatment per unit? (If free or unknown, I'll use 0.)"

Present three benchmarks:
- Treat-none welfare: 0
- Treat-all welfare: [sum of CATEs minus total cost]
- Threshold rule (CATE > cost) welfare: [sum of CATEs for treated minus cost]
- Fraction treated under threshold rule: [percentage]

### Layer 3: Policy tree (opt-in)

Only offer if:
- No FATAL flags active
- BLP or GATES showed meaningful heterogeneity
- User wants a targeting rule

Default: depth = 2 (shallow, interpretable). Cost-adjusted rewards.

**Deployment disclaimer (ALWAYS shown with any policy output)**:
> **This is an exploratory targeting rule, not a deployment-ready policy.** Before operationalizing: (1) validate on held-out data, (2) run a confirmatory experiment, (3) review for fairness and equity, (4) get domain expert review.

**Fairness check (ALWAYS run with policy output)**: Check if the policy correlates with protected attributes (gender, race, age group) even if they were not used in the tree.

**Finding no heterogeneity is a valid result**: "Your ATE estimate from [upstream method] appears to apply broadly. This is useful — it means you don't need to segment or target."

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

"Your HTE analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Practice**: `/causal-exercises` to try HTE on simulated data with known ground truth.
3. If heterogeneity was not detected: Your ATE estimate from [upstream method] appears to apply broadly."

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)
- `/causal-matching`, `/causal-experiments`, `/causal-did`, `/causal-iv` -- Any ATE skill can hand off here

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-exercises` -- Practice HTE on simulated data (optional)

**If assumptions fail**:
- `/causal-matching` -- If overlap is the main issue (re-examine propensity model)
- `/causal-experiments` -- If you can run an RCT (strongest identification for HTE)

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### HTE: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
