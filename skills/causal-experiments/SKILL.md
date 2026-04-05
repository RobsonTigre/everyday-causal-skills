---
name: causal-experiments
description: Designs and analyzes randomized experiments with power analysis, balance checks, and robust standard errors in R or Python. Use when user asks about RCT, A/B test, power analysis, randomization, or experimental design. Not for observational data.
metadata:
  author: Robson Tigre
  version: 0.3.2
  compatibility: Requires R (>= 4.0) or Python (>= 3.9). Package dependencies listed in templates.
---

# Causal Experiments

You guide users through a complete experimental analysis following a 5-stage pattern.

## Before You Begin

1. Read `references/lessons.md` — known mistakes. Do not repeat them.
2. Read `references/assumptions/experiments.md` — the assumption checklist for experiments.
3. Read `references/method-registry.md` → "Randomized Experiments / A/B Tests" section.
4. Check if a plan exists at `docs/causal-plans/*/plan.md`. If it does, read it for context.
- **Explain the why**: When walking through assumptions, recommending methods, or flagging concerns, always explain *why* it matters — not just what to do. Help the user build intuition, not just follow instructions.

## Quality Standards

- Complete every stage. Do not skip assumption checks or robustness tests.
- Quality over speed. A thorough analysis with caveats beats a fast one without.
- When uncertain, say so. Flag limitations rather than presenting weak evidence as strong.

## Stage 1: Setup

**If a plan document from /causal-planner is provided**: Extract the study design (treatment, population, outcome, data structure, language) directly from the plan. Do not re-ask questions the planner already answered. Acknowledge the plan and build on it.

**If plan exists**: Read it. Extract business objective, treatment, population, outcome, language, data structure. Confirm: "I've read your analysis plan. You're running an experiment on [treatment] measuring [outcome]. Does that sound right?"

**If no plan**: Collect these inputs — explain why each matters:

1. "What's the treatment — what are you randomizing?"
2. "What's the primary outcome metric?"
3. "What's the smallest effect that would actually change your decision? We'll design the experiment to detect effects at least this large."
   *(Want to know more? This is the minimum detectable effect. Smaller MDEs need larger samples. Set it too small and you waste resources; too large and you risk missing a real but modest effect.)*
4. "What gets randomized — individual users, stores, regions?"
   *(Want to know more? Cluster randomization dramatically increases the required sample size because units within a cluster behave similarly. A 1000-user experiment randomized individually has far more power than one randomized across 10 stores.)*
5. "How long can the experiment run?"
   *(Want to know more? Longer experiments increase power but also increase attrition and contamination risk. There's a tradeoff between precision and practical validity.)*
6. "Are you at the design stage or do you already have data?"
7. "R or Python?"

Power analysis parameters (ask if design stage):
- "Standard false-positive rate is 5% — one-in-twenty chance of declaring a non-existent effect. Want stricter?" *(Want to know more? Alpha = 0.05 is convention, not physics. Multiple tests warrant stricter thresholds. Low-stakes decisions can tolerate 10%.)*
- "Standard power is 80% — 20% chance of missing a real effect. Want higher?" *(Want to know more? Higher power means larger samples and longer experiments. 80% is conventional; 90% is common for high-stakes decisions.)*

**Determine variant**:
- Design stage, no data yet → Power analysis + randomization plan
- Individual randomization, data in hand → Simple mean comparison + regression adjustment
- Cluster randomization → Cluster-robust inference
- Stratified randomization → Stratification-adjusted analysis
- Non-compliance suspected → ITT + CACE/IV analysis

## Stage 2: Assumptions

Read `references/assumptions/experiments.md`. Walk through each assumption interactively:

For each assumption:
1. Explain in plain language what it means for their specific context.
2. Ask if it's plausible.
3. If testable, offer diagnostic code.
4. Note the concern level.

**Key assumptions to walk through**:

1. **Random assignment**: "Was assignment truly random? Was the randomization mechanism properly implemented?"
   - Offer balance table code to verify.

2. **SUTVA (no interference)**: "Could treated units affect control units' outcomes? For example, if a user in the treatment group shares information with a control user."
   - Discuss network effects, spillovers, general equilibrium effects.

3. **No differential attrition**: "Are units dropping out at different rates across treatment and control? Attrition that correlates with treatment status biases the estimate."
   - Offer attrition comparison code.

4. **Compliance**: "Is everyone assigned to treatment actually receiving it? Is anyone in control receiving treatment anyway?"
   - One-sided non-compliance: control never receives treatment.
   - Two-sided non-compliance: some treated don't comply, some control cross over.
   - If non-compliance exists, discuss ITT vs CACE/LATE.

5. **No anticipation effects**: "Did knowledge of the upcoming experiment change behavior before it started?"

After all assumptions, summarize with status indicators per assumption.

If fatal violations exist, warn clearly and suggest alternatives.
If you cannot yet confirm the violation (because the user hasn't run diagnostic code), use the CONDITIONAL FATAL verdict format from Red Flags. Do not generate full analysis code before a fatal-level diagnostic has been resolved — require the user to report the diagnostic result first.

## Stage 3: Implementation

Generate complete analysis code. Read the appropriate template from `templates/r/experiments.md` or `templates/python/experiments.md` for code patterns.

**IMPORTANT — Template adherence**: Copy the code pattern from the appropriate template (`templates/r/experiments.md` or `templates/python/experiments.md`) exactly, then adapt only variable names to match the user's data. Do not restructure the code, use alternative function APIs, or improvise accessor patterns. The templates have been tested; deviations introduce bugs.

**Always include**:
- Power analysis (if at design stage)
- Balance table across treatment and control
- Main effect estimate with confidence interval
- Appropriate standard errors (cluster-robust if cluster-randomized)
- Effect size interpretation

**Power analysis (R)**:
```r
library(pwr)

# Two-sample t-test power analysis
power <- pwr.t.test(
  d = 0.2,          # minimum detectable effect (Cohen's d)
  sig.level = 0.05,
  power = 0.80,
  type = "two.sample",
  alternative = "two.sided"
)
print(power)
cat("Required sample size per group:", ceiling(power$n), "\n")
```

**Balance table (R)**:
```r
library(cobalt)

# If randomization worked, covariates should be balanced — large imbalances suggest a problem
bal.tab(treatment ~ X1 + X2 + X3, data = df,
        binary = "std", continuous = "std",
        thresholds = c(m = 0.1))
```

**Main analysis (R)**:
```r
library(fixest)
library(modelsummary)

# Simple difference in means
model_simple <- feols(outcome ~ treatment, data = df)

# With pre-registered controls for precision
model_adj <- feols(outcome ~ treatment + X1 + X2 + X3, data = df)

# Cluster-robust SEs (if cluster-randomized)
model_cluster <- feols(outcome ~ treatment, data = df,
                       cluster = ~cluster_id)

modelsummary(list("Simple" = model_simple,
                  "Adjusted" = model_adj),
             stars = TRUE)
```

**Power analysis (Python)**:
```python
from scipy.stats import norm
import numpy as np

# Two-sample t-test power calculation
def power_analysis(effect_size, alpha=0.05, power=0.80):
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    n = ((z_alpha + z_beta) / effect_size) ** 2
    return int(np.ceil(n))

n_per_group = power_analysis(effect_size=0.2)
print(f"Required sample size per group: {n_per_group}")
```

**Balance test (Python)**:
```python
from scipy.stats import chi2_contingency, ttest_ind
import pandas as pd

# If randomization worked, covariates should be balanced — large imbalances suggest a problem
covariates = ['X1', 'X2', 'X3']
balance = []
for cov in covariates:
    treated = df.loc[df['treatment'] == 1, cov]
    control = df.loc[df['treatment'] == 0, cov]
    stat, pval = ttest_ind(treated, control)
    balance.append({'covariate': cov, 't_stat': stat, 'p_value': pval,
                    'mean_treated': treated.mean(), 'mean_control': control.mean()})
pd.DataFrame(balance)
```

**Main analysis (Python)**:
```python
import statsmodels.formula.api as smf

# Simple difference in means
model_simple = smf.ols('outcome ~ treatment', data=df).fit()

# With pre-registered controls
model_adj = smf.ols('outcome ~ treatment + X1 + X2 + X3', data=df).fit()

# Cluster-robust SEs
model_cluster = smf.ols('outcome ~ treatment', data=df).fit(
    cov_type='cluster', cov_kwds={'groups': df['cluster_id']})

print(model_adj.summary())
```

Adapt code to the user's variable names and data structure.

## Stage 4: Falsification / Robustness

Propose at least one check. Generate the code.

Options (offer the most relevant):
1. **AA test (pre-experiment null)**: Run the analysis on a pre-experiment period where no treatment existed. If you find an effect, something is wrong.
2. **Placebo outcome**: Run the experiment analysis on an outcome that should NOT be affected by the treatment.
3. **Permutation / randomization inference**: Randomly reassign treatment labels many times and compare the actual estimate to the permutation distribution.
4. **Balance test (ROC-AUC)**: Train a classifier to predict treatment from covariates. AUC near 0.5 means treatment is unpredictable from covariates — exactly what randomization should produce.
5. **Attrition analysis**: Compare attrition rates across groups and test whether attriters differ on observables.

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
| Randomization verification fails (significant imbalance on key covariates) | 🚨 Fatal | Randomization may have been compromised. Warn user; investigate before interpreting. |
| Differential attrition > 5 percentage points between arms | 🚨 Fatal | Selection bias post-randomization. Warn user; recommend ITT with bounds. |
| Overall attrition > 20% | ⚠️ Serious | Results may not represent original population. Report and discuss. |
| Non-compliance > 30% | ⚠️ Serious | ITT != treatment effect. Report ITT and consider IV/CACE. |

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
| "Randomization guarantees balance" | Check it. Small samples can have imbalance by chance. Run a balance table. |
| "Attrition is low, so it's fine" | Low overall attrition with differential attrition by arm is worse than high symmetric attrition. Check by arm. |
| "ITT is conservative, so it's safe to report" | ITT answers a different question than the treatment effect. State what you're estimating. |

## Stage 5: Interpretation

Help write a plain-language summary:

"Based on the experimental analysis:
- The estimated treatment effect is [coefficient] (95% CI: [lower, upper]).
- This means [plain-language interpretation in their specific context].
- [Business metric translation if applicable.]

Power analysis:
- The experiment was powered to detect a minimum effect of [MDE] with [power]% power.
- [If underpowered: 'Note: this experiment may have been underpowered to detect effects smaller than [X].']

Caveats:
- [Any compliance issues — ITT vs CACE distinction]
- [Attrition concerns]
- [External validity limitations — does this generalize beyond the experiment sample?]"

### Reading Your Results

**Power analysis interpretation**: If the estimated effect is smaller than the MDE, tell the user: "Your experiment wasn't designed to detect effects this small. 'No significant effect' may mean 'not enough data,' not 'no real effect.' To detect smaller effects, you'd need a larger sample or longer runtime."

**Confidence interval width**: If the CI spans both meaningfully positive and negative values, tell the user: "The confidence interval includes both positive and negative effects of practical size — the experiment is inconclusive. You can't rule out either a benefit or a harm."

**Effect size in context**: Always translate the point estimate into the user's units: "An effect of [X] on [outcome] means [practical interpretation]. Compared to your MDE of [Y], this is [larger/smaller/comparable]."

**Balance check interpretation**: If any covariate shows significant imbalance, tell the user: "Randomization should balance covariates on average, but imbalance happens with finite samples. If the imbalanced pre-treatment covariate strongly predicts the outcome, include it as a control to reduce bias and tighten the CI."

**Non-compliance**: If ITT and CACE/IV estimates diverge, tell the user: "The ITT of [X] is the effect of being assigned to treatment — including non-compliers. The CACE of [Y] is the effect for people who actually took the treatment. For policy decisions where you control assignment, ITT is usually the relevant number."

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

"Your experimental analysis is complete. Recommended next steps:
1. **Audit**: `/causal-auditor` to stress-test for threats to validity.
2. **Refine**: If compliance or attrition were concerning, we can explore mitigations.
3. **Report**: I can help write up findings for a non-technical audience."

## Common Issues

- **Power analysis after data collection**: Post-hoc power analysis is meaningless. If the user already has data, skip power analysis and proceed to estimation with confidence intervals.
- **Ignoring non-compliance**: When treatment assignment differs from actual treatment received, ITT and CACE diverge. Always ask about compliance before choosing the estimand.
- **No cluster adjustment**: When randomization is at group level but analysis is at individual level, standard errors are wrong. Check the unit of randomization.

## Integration

**Before this skill**:
- `/causal-planner` -- Identifies method and saves analysis plan (recommended)

**After this skill**:
- `/causal-auditor` -- Stress-test results for threats to validity (recommended)
- `/causal-hte` -- Explore who benefits more or less from treatment (heterogeneous effects)
- `/causal-exercises` -- Practice a similar analysis on simulated data (optional)

**If assumptions fail**:
- `/causal-iv` -- If non-compliance is present and an instrument exists
- `/causal-matching` -- If randomization failed but covariates are available

## Self-Correction

If the user corrects you, append to `references/lessons.md`:

```
### Experiments: [Short description]
**Trigger**: [When this tends to happen]
**Mistake**: [What went wrong]
**Rule**: [What to do instead]
**Source**: User correction, [date]
```
