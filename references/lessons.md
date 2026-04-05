# Lessons

Known mistakes and corrections. All skills read this file before responding. Do NOT repeat these mistakes.

<!-- Lessons are added from five sources:
  1. User corrections ("that's wrong", "you missed X")
  2. L1-L3 eval failures (wrong method, missed violation, broken code)
  3. L4 eval failures (poor pedagogy, unsafe guidance, not actionable)
  4. L5 eval failures (broken handoffs between skills, inconsistent vocabulary)
  5. Auditor findings (gaps caught by causal-auditor that method skills missed)

Format:
### [Method]: [Short description]
**Layer**: [L1|L2|L3|L4|L5|User|Auditor]
**Trigger**: When this mistake tends to happen
**Mistake**: What went wrong
**Rule**: What to do instead
**Source**: [User correction | Eval failure | Auditor finding], [date]
-->

### Time Series: Structural breaks in pre-period not flagged
**Trigger**: User provides time series data for ITS/CausalImpact analysis
**Mistake**: Skill proceeded with analysis without checking for structural breaks or level shifts in the pre-treatment period
**Rule**: Before modeling, always inspect the pre-treatment period for structural breaks. Recommend a visual inspection and suggest a Chow test or CUSUM test. A structural break invalidates the counterfactual projection.
**Source**: Eval failure (timeseries_structural_break), 2026-04-01

### Matching: Code timeout on large datasets
**Trigger**: Propensity score matching on datasets with >1000 observations
**Mistake**: Generated matching code that was too computationally heavy, causing execution timeout
**Rule**: For large datasets (n > 1000), prefer efficient matching implementations (nearest-neighbor with caliper) over exhaustive optimal matching. Consider recommending IPW or doubly-robust estimators as faster alternatives.
**Source**: Eval failure (matching_ate), 2026-04-01

### Synthetic Control: Wrong R package used
**Trigger**: Generating R code for synthetic control
**Mistake**: Used `tidysynth` package which may not be installed, instead of the standard `Synth` package
**Rule**: Use the `Synth` package for R synthetic control implementations unless the user explicitly requests `tidysynth`. The `Synth` package is the canonical implementation and more widely available.
**Source**: Eval failure (sc_basic), 2026-04-01

### DAG: Controlling for colliders reverses sign
**Layer**: L2
**Trigger**: User proposes controlling for a variable caused by both treatment and an unobserved confounder
**Mistake**: Failing to detect the collider structure and allowing the bad control
**Rule**: Before accepting any control variable, check if it's a common effect (collider) of treatment and outcome (or treatment and an unobserved cause of outcome). If it is, conditioning on it opens a spurious path and can reverse the sign of the estimate. Reference Cunningham Ch. 3 gender discrimination example.
**Source**: Design decision (seeded from literature), 2026-04-05

### DAG: M-bias severity depends on relative path strengths
**Layer**: L4
**Trigger**: Skill encounters a pre-treatment collider of two unobserved causes (M-bias structure)
**Mistake**: Declaring M-bias as always FATAL, when in many realistic settings the bias from conditioning is smaller than the bias from omitted confounders
**Rule**: Flag M-bias as SERIOUS, not FATAL. Present both options (condition vs. don't condition) and note the Ding & Miratrix (2015) vs. Pearl (2015) debate. The decision depends on the relative strengths of the competing paths.
**Source**: Design decision (CausalML Ch. 11), 2026-04-05

### DAG: Instruments must not be used as controls
**Layer**: L2
**Trigger**: User includes a treatment-only cause (instrument) as a control variable alongside unobserved confounding
**Mistake**: Allowing the instrument in the adjustment set, which amplifies bias by removing exogenous variation while leaving confounded variation
**Rule**: If a variable affects only the treatment (not the outcome directly), it's an instrument. With unobserved confounding, including it as a control makes bias worse. Either use it as an instrument via 2SLS or exclude it from the adjustment set.
**Source**: Design decision (CausalML Ch. 11, Figure 11.6), 2026-04-05
