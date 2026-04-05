# Method Registry

Single source of truth for all causal inference methods supported by this plugin. Skills reference this file for method details, package recommendations, and diagnostics.

---

## Randomized Experiments / A/B Tests

**When to use**: Treatment was randomly assigned (RCT, A/B test). User asks about power analysis, randomization, or experimental design. Large sample available.

**Key assumptions**: Random assignment, SUTVA (no interference), no differential attrition, compliance.

**Data needs**: Cross-sectional or panel. Treatment and control groups with outcome metric.

**R packages**: `pwr` (power analysis), `RCT` (balance checks), `fixest` (regression adjustment)

**Python packages**: `scipy.stats` (t-tests), `statsmodels` (regression adjustment)

**Key diagnostics**: Balance test (ROC-AUC of propensity score), attrition analysis, compliance rate check.

**Assumption checklist**: `assumptions/experiments.md`

**Book refs**: Everyday CI Ch. 4-5; The Effect Ch. 14; Mixtape Ch. 4

---

## Difference-in-Differences (DiD)

**When to use**: Treatment affects some units but not others (staggered rollout, policy change). User asks about DiD, TWFE, event study, or parallel trends. Panel or repeated cross-section data available.

**Key assumptions**: Parallel trends (pre-treatment), no anticipation, stable composition, no spillovers (SUTVA), correct functional form.

**Data needs**: Panel data (units x time periods). Need multiple pre-treatment periods for pre-trends testing. For staggered: need treatment timing variable.

**Variants**:
- Classic 2x2 DiD: Single treatment date, two groups
- TWFE: Panel data with unit + time fixed effects
- Staggered DiD: Different units treated at different times (use Callaway-Sant'Anna or Sun-Abraham, NOT naive TWFE)
- Event study: Dynamic treatment effect visualization

**R packages**: `fixest` (feols, sunab for staggered), `did` (Callaway-Sant'Anna att_gt), `etwfe` (extended TWFE)

**Python packages**: `linearmodels` (PanelOLS), `differences` (att_gt), `csdid`

**Key diagnostics**: Pre-trends test / event study plot, parallel trends visualization, balance checks.

**Assumption checklist**: `assumptions/did.md`

**Book refs**: Everyday CI Ch. 10-11; The Effect Ch. 18; Mixtape Ch. 9

---

## Instrumental Variables (IV)

**When to use**: Treatment is endogenous (non-compliance, omitted variables) but a valid instrument is available. User asks about IV, 2SLS, or endogeneity.

**Key assumptions**: Relevance (instrument predicts treatment), exclusion restriction (instrument affects outcome only via treatment), independence (instrument is as-if random), monotonicity (for LATE interpretation).

**Data needs**: Instrument variable, treatment variable, outcome variable. Cross-sectional or panel. Need sufficient variation in instrument.

**R packages**: `AER` (ivreg), `fixest` (feols with `| instrument` syntax)

**Python packages**: `linearmodels` (IV2SLS, IVGMM)

**Key diagnostics**: First-stage F-statistic (>10, ideally >100), Sargan/Hansen overidentification test (if >1 instrument), Wu-Hausman endogeneity test.

**Assumption checklist**: `assumptions/iv.md`

**Book refs**: Everyday CI Ch. 14; The Effect Ch. 19; Mixtape Ch. 7

---

## Regression Discontinuity Design (RDD)

**When to use**: Treatment is assigned by a cutoff on a running variable. User asks about RDD, threshold, discontinuity, or cutoff-based assignment.

**Key assumptions**: Continuity of potential outcomes at cutoff, no manipulation of running variable, no other discontinuities at cutoff, local identification (effect only at cutoff).

**Variants**:
- Sharp RDD: Treatment is deterministic at cutoff (everyone above gets it)
- Fuzzy RDD: Treatment probability jumps at cutoff (like IV with the cutoff as instrument)

**Data needs**: Running variable (continuous), cutoff value, outcome. Need sufficient observations near the cutoff.

**R packages**: `rdrobust` (rdrobust, rdplot), `rddensity` (manipulation test)

**Python packages**: `rdrobust` (rdrobust, rdplot), `rddensity`

**Key diagnostics**: McCrary density test (manipulation), covariate smoothness at cutoff, bandwidth sensitivity analysis, donut hole test.

**Assumption checklist**: `assumptions/rdd.md`

**Book refs**: Everyday CI Ch. 13; The Effect Ch. 20; Mixtape Ch. 6

---

## Synthetic Control

**When to use**: Single treated unit (or small number), many potential control units, long pre-treatment period. User asks about synthetic control, comparative case study, or donor pool.

**Key assumptions**: No interference between units, treated unit lies within convex hull of donors, adequate pre-treatment fit, no structural breaks in the relationship between treated and donor units.

**Data needs**: Panel data. Few treated units (1-5), larger donor pool of control units, many pre-treatment time periods (at least 10-20).

**R packages**: `Synth` (classic), `tidysynth` (tidy interface), `gsynth` (generalized)

**Python packages**: `scpi` (prediction intervals)

**Key diagnostics**: Pre-treatment RMSPE, donor weight distribution, in-space placebo (apply method to each control unit), in-time placebo (fake earlier treatment date), leave-one-out (remove each donor).

**Assumption checklist**: `assumptions/sc.md`

**Book refs**: Everyday CI Ch. 12; The Effect Ch. 18; Mixtape Ch. 10

---

## Matching / PSM / PSW / Doubly-Robust

**When to use**: Treatment is not randomly assigned but rich covariates are available. User asks about matching, propensity score, observational study, confounders, or selection bias. Selection on observables is plausible.

**Key assumptions**: Conditional independence / unconfoundedness (all confounders measured), overlap / positivity (all units have nonzero probability of treatment), SUTVA (no interference), correct specification (of propensity score or outcome model).

**Variants**:
- Propensity Score Matching (PSM): Match treated to control on propensity score
- Propensity Score Weighting (PSW/IPW): Reweight sample by inverse propensity scores
- Doubly-Robust (DR): Combine outcome modeling with propensity weighting — consistent if either model is correct
- Coarsened Exact Matching (CEM): Coarsen covariates and exact-match within bins

**R packages**: `MatchIt` (matching algorithms), `cobalt` (balance diagnostics)

**Python packages**: `dowhy` (causal framework), `econml` (DR learners, meta-learners)

**Key diagnostics**: Propensity score overlap (histogram), covariate balance (SMD < 0.1), love plot, sensitivity analysis (Rosenbaum bounds).

**Always warn**: Effects estimated under conditional independence may not reproduce. Unobserved confounders can bias results. This should be framed as the weakest available strategy.

**Assumption checklist**: `assumptions/matching.md`

**Book refs**: Everyday CI Ch. 8-9; The Effect Ch. 14; Mixtape Ch. 5

---

## Interrupted Time Series / CausalImpact

**When to use**: Single unit (or aggregate), long time series, clear intervention point. User asks about ITS, CausalImpact, or time series intervention. No control group available.

**Key assumptions**: No confounding events concurrent with treatment, pre-treatment model fits well (captures seasonal/trend patterns), stationarity (or proper differencing), adequate pre-treatment period length.

**Data needs**: Time series with many pre-treatment observations (at least 30-50). For CausalImpact: additional control series that were NOT affected by the treatment.

**R packages**: `CausalImpact` (Bayesian structural time series), `CausalArima` (ARIMA-based)

**Python packages**: `causalimpact` (Python port of CausalImpact), `pycausalarima`

**Key diagnostics**: Pre-period fit (MAPE), residual diagnostics (autocorrelation, normality), Ljung-Box test, comparison with placebo intervention dates, comparison with control series.

**Assumption checklist**: `assumptions/timeseries.md`

**Book refs**: Everyday CI Ch. 15; The Effect Ch. 17

---

## Regression / Adjustment

**When to use**: As a complement to randomized experiments for variance reduction, or as a baseline estimator when controlling for observed confounders.

**Key assumptions**: Linearity (or correct functional form), no omitted variable bias (in observational settings), exogeneity of regressors.

**Data needs**: Cross-sectional or panel. Treatment variable and outcome, plus covariates.

**R packages**: `fixest` (feols with cluster-robust SEs)

**Python packages**: `statsmodels` (OLS, WLS)

**Key diagnostics**: Residual plots, multicollinearity check, specification tests.

**Book refs**: Everyday CI Ch. 6-7; The Effect Ch. 13

---

## Event Studies

**When to use**: To visualize dynamic treatment effects over time — how effects evolve before and after treatment onset. Often paired with DiD to test pre-trends and show effect trajectories.

**Key assumptions**: Same as DiD (parallel trends, no anticipation). Additionally: reference period choice matters.

**Data needs**: Panel data with unit and time identifiers, treatment timing variable.

**R packages**: `fixest` (feols with `i()` syntax, `iplot()`)

**Python packages**: `statsmodels` (manual dummy construction), `linearmodels`

**Key diagnostics**: Joint significance test of pre-treatment coefficients, visual inspection of pre-trends.

**Book refs**: Everyday CI Ch. 11; The Effect Ch. 18; Mixtape Ch. 9

---

## Shared Infrastructure

These packages are used across all methods and should be loaded by default.

**R**: `tidyverse` (data manipulation + ggplot2), `modelsummary` (results tables), `fixest` (fixed effects backbone)

**Python**: `pandas` (data manipulation), `numpy` (computation), `matplotlib` + `seaborn` (visualization), `statsmodels` (statistical backbone)

---

## Directed Acyclic Graphs (DAGs)

**When to use**: User wants to reason about causal structure before choosing an estimation method. User asks about DAGs, causal graphs, confounders, backdoor paths, colliders, adjustment sets, "what should I control for", or bad controls. Also use when the identification strategy for another method is unclear.

**Key assumptions**: Acyclicity, causal sufficiency (all common causes represented), correct edge direction, faithfulness (for testable implications), positivity (for adjustment).

**Data needs**: Domain knowledge is the primary input. Data is optional (used for testing implications and checking positivity). No specific panel/cross-section requirement.

**R packages**: `dagitty` (adjustment sets, testable implications, d-separation), `ggdag` (visualization)

**Python packages**: `dowhy` (identification, estimation pipeline), `networkx` (graph operations, d-separation)

**Key diagnostics**: Testable implication checks (conditional independence tests), positivity / overlap checks for proposed adjustment sets, collider detection.

**Assumption checklist**: `assumptions/dag.md`

**Book refs**: The Effect Ch. 6-8; Mixtape Ch. 3; CausalML Ch. 7, 11; Pearl (2009) Causality; Cinelli, Forney & Pearl (2024) A Crash Course in Good and Bad Controls
