# Decision Tree: P1-P10 Causal Problem Identification

Translated from `identificacao-problemas-causais.md`. The causal planner follows this tree.

---

## P1: What is the business objective?

**Ask**: "What are you trying to accomplish with this analysis?"

**Classify into one of**:
1. **Evaluation** (measurement after the fact): A decision was already made; you want to know its effect.
2. **Optimization** (measurement before the fact): A decision hasn't been made yet (or was only piloted); you want to know if you should proceed.
3. **Personalization**: You want to know which units respond better or worse to an intervention, to optimize allocation.

**If unclear**: The user may describe a technical goal instead of a business goal. Probe: "But what's the ultimate business question?" Example: "I want to attribute customers to affiliate links" → probe → "I want the effect of influencer campaigns" → classify as Evaluation.

**Output**: Objective type stored for the plan.

---

## P2: Treatment entity, population, outcome

**Ask**: "Tell me about your setup: Who or what is being treated? What's the population? What was done (or will be done) to them? What's the outcome metric you care about?"

Also ask: "Will you be implementing in R or Python?"

**Extract**:
- Treatment entity and description (observable or not?)
- Population and approximate size (tens, hundreds, thousands+)
- Outcome metric
- Language preference

**Post-treatment conditioning trap** (CRITICAL — MUST CHECK EVERY TIME): Check if the population is conditioned on a post-treatment variable.

Examples:
- "Customers who clicked Buy Insurance and saw different suggested prices" — but the price was shown on the icon before clicking, influencing who clicked. Using only clickers underestimates the effect.
- "Active customers (spent > X) with different credit limits" — the credit limit was exposed to all customers and likely influenced who became active. Conditioning on activity = conditioning on a post-treatment variable.
- "Customers who opened the marketing email" — opening is influenced by subject line/sender, which may correlate with treatment. Comparing openers vs non-openers conflates email opening behavior with treatment effect.

If detected: Explain how this conditioning can create selection bias or misalign the business objective (from P1) with the causal estimand. Suggest expanding the population.

**Prior exposure check** (ask on every case): "Has this population already been exposed to this intervention, or is this the first time?"

Classify:
1. **No prior exposure**: Clean baseline. Measuring first-time effect.
2. **Partial exposure**: Some units were exposed before. Risk of contamination between exposed and unexposed. Possible novelty effect inflating results for newly-exposed units.
3. **Full prior exposure**: Everyone has already seen the intervention. The estimand is the incremental/ongoing effect, NOT the first-time effect. Must reframe the causal question accordingly — e.g., "what is the marginal effect of continuing X" rather than "what is the effect of X."

Example: "We've been showing personalized recommendations for 6 months. Now we want to know if they increase purchases." → Full prior exposure. The relevant estimand is the ongoing lift from recommendations, not the initial surprise effect. Consider a removal experiment (turn it OFF for a random group) rather than trying to estimate the original effect.

**External events check** (ask on every case): "Is anything else happening around the same time that could affect your outcome — seasonality, competing campaigns, policy changes, market shifts?"

If yes: Document the events. They affect:
- **Study window selection**: Avoid periods confounded by the external event, or at minimum note it as a limitation.
- **Method vulnerability**: ITS and synthetic control are especially sensitive to concurrent events (they have no within-period control group). DiD is somewhat protected if the event affects treatment and control equally.
- **Robustness checks needed**: Plan placebo dates, control series comparisons, or event-exclusion sensitivity tests.

Example: "We launched the loyalty program in November." → Probe: "Was this during a holiday sales period? Were there other promotions running simultaneously?" If yes, document as a known threat and plan robustness checks that address it.

---

## P3: Randomization?

**Ask**: "Was the treatment randomly assigned? Do you have an A/B test?"

**Classify**:
1. **Random**: A/B test or explicit randomized assignment.
2. **Conditionally random**: Random within known strata. Probe: "Is it possible your data combines multiple experiments with different randomization rates?" Example: a company ran separate A/B tests in different regions — 50/50 split in São Paulo, 70/30 in Rio — then merged the datasets. The merged data is NOT unconditionally random, but it IS random conditional on region. Treatment: stratify the analysis by the grouping variable, or weight by the known assignment probability. Do not analyze the merged data as if it were a single randomized experiment.
3. **Not random**: No randomization.

### If random (1 or 2) + large sample:

**For Evaluation / Optimization objective**:
→ Recommend: Simple comparison of means, or regression / PSW / DR for variance reduction.

**For Personalization objective**:
→ Recommend: Heterogeneous treatment effect analysis — Causal Forest with DML validation.
→ Handoff to `causal-hte`.

**Note**: Even with randomization, verify balance. Test with ROC-AUC of a propensity score model on a holdout set.

**EARLY EXIT**: State recommendation. Ask: "Would you like to optimize this further (e.g., variance reduction, CUPED), or is this plan ready?"
- If optimize → continue to P5-P7
- If ready → save plan, offer handoff to method skill

### If not random (3) or small sample:
→ Continue to P4.

---

## P4: Can you collect more data?

**Ask**: "Are you willing and able to run an experiment to collect new data?"

### If yes:

Determine experiment design based on control level:
- **Individual control** over who gets treatment → Traditional A/B test
- **Group-level control** (by region, store, time period) → Synthetic control design, switchback experiment, or hybrid
- **No direct control** but can manipulate a variable that influences treatment (instrument) → Encouragement design

→ Recommend experiment design. Offer handoff to `causal-experiments`.

### If no:
→ Continue to P5.

---

## P5: Treatment strength

**Ask**: "How large do you expect the effect to be? Is this a subtle or dramatic change?"

**Strong treatment**:
- Simple mean comparison works for A/B tests
- Prediction metrics (R2, MSE) can proxy CATE quality for personalization
- Precise inference even with small samples

**Weak treatment**:
- Needs variance reduction (regression, DiD, SC) even if randomized
- Makes experiments longer to reach significance
- Harder to distinguish from noise

---

## P6: Effect lag

**Ask**: "How quickly does the treatment affect the outcome? Immediately, days, weeks, months?"

Also: "Does the effect build over time, or appear all at once?"

**Long lag**:
- Increases time for data collection
- Complicates panel methods — DiD needs robust-to-heterogeneous-timing variant
- Makes switchback experiments impractical

**Short lag**:
- Facilitates data collection
- Enables panel methods and switchback experiments

---

## P7: Panel data available?

**Ask**: "Do you have data on how these units behaved before and after treatment?"

**If yes**, ask: "How many time periods? How many units?"

**Use panel methods when**:
- Small sample → panel reduces variance
- Weak treatment → panel reduces variance
- Level differences between groups → panel controls for time-invariant unobservables

**Panel method selection**:
- Many units + few periods → DiD / TWFE
- Few units + many periods → Synthetic control

**Avoid panel methods when**:
- Non-parallel growth trends (for DiD)
- Computational constraints
- Effect heterogeneity over time not handled by chosen estimator

---

## P8: Non-compliance?

**Ask**: "Did everyone who was supposed to receive the treatment actually receive it?"

### If significant non-compliance + valid instrument exists:
→ IV path. Estimate LATE (Local Average Treatment Effect).

**Cautions**:
- Non-compliance > 50%: variance may be too large for useful estimates
- Exclusion restriction: instrument must affect outcome ONLY via treatment
- Common misidentification: what looks like non-compliance may be a population definition issue

**Population definition trap**: Examples from the questionnaire:
- 50% get pre-approved credit but only 10% enter the product to check → pre-approval may affect entry, so either model entry separately or verify that pre-approval doesn't affect entry behavior.
- 50% get a discount but only 5% visit the site → the discount may affect site visits.

If the "non-compliance" is actually a conversion funnel issue, redefine the population rather than using IV.

---

## P9: Discontinuity?

**Ask**: "Is there a cutoff, threshold, or rule that determines who gets treated?"

### If yes:
→ RDD path. Need: running variable, clear cutoff, sufficient data near cutoff.

Ask for details: "What's the running variable? What's the cutoff value? Is the cutoff strict (sharp) or does it just change the probability of treatment (fuzzy)?"

---

## P10: Selection on observables (last resort)

**Ask**: "What determines who gets the treatment? What variables influence assignment?"

This is the **weakest identification strategy**. Must explicitly warn the user.

**Classification**:
- Treatment is deterministic in some regions (positivity violation) → Regression, DML, DR methods
- Good overlap (non-deterministic assignment) → PSM, PSW, DR methods

**Always warn**: "I should be transparent: this approach relies on the assumption that all important confounders have been measured. If there are unmeasured factors that affect both treatment and outcome, the estimates could be biased. This is the least reliable identification strategy available."

---

## Terminal Nodes Summary

| Path | Recommended Method | Skill Handoff |
|---|---|---|
| P3=random + large + eval/optim | Experiments (mean comparison / regression) | `causal-experiments` |
| P3=random + large + personalization | Causal Forest / HTE | `causal-hte` |
| P4=yes + individual control | A/B test design | `causal-experiments` |
| P4=yes + group control | SC design / switchback | `causal-experiments` or `causal-sc` |
| P4=yes + instrument available | Encouragement design | `causal-experiments` |
| P7=yes + many units, few periods | DiD / TWFE | `causal-did` |
| P7=yes + few units, many periods | Synthetic control | `causal-sc` |
| P8=non-compliance + valid IV | Instrumental variables | `causal-iv` |
| P9=cutoff exists | RDD | `causal-rdd` |
| P10=good overlap | Matching / PSW / DR | `causal-matching` |
| P10=good overlap + personalization | Causal Forest / HTE (observational) | `causal-hte` |
| P10=deterministic regions | Regression / DML / DR | `causal-matching` |
| P7=yes + weak treatment + random | DiD for variance reduction | `causal-did` |

---

## After Analysis: Report Generation

After completing any analysis path above and optionally running `/causal-auditor`, the user can compile their findings:

→ **`/causal-report`** — Compiles all artifacts (plan, implementation, audit) into a structured report with tables, figures, and method summaries. Three modes: business, academic, hybrid.

This is the terminal step in the full workflow:

```
/causal-planner → /causal-[method] → /causal-auditor → /causal-report
```
