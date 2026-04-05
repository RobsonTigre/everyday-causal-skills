# Assumption Checklist: Heterogeneous Treatment Effects (HTE) / CATE Estimation

Reference: `references/method-registry.md` → Heterogeneous Treatment Effects (HTE) / CATE Estimation

---

## Conditional Independence (Unconfoundedness)

**Plain language**: After you account for all the measured covariates, treatment assignment is as good as random. HTE estimation does NOT relax this assumption — it inherits whatever identification strategy produced the ATE. If the ATE is biased by unmeasured confounders, the CATEs are biased too. Machine learning does not overcome confounding.

**Formal statement**: (Y(0), Y(1)) ⊥ D | Z, where Y(0) and Y(1) are potential outcomes, D is treatment status, and Z is the vector of all confounders. This is identical to matching/PSM — the causal forest adds no new identification power.

**Testable?**: No. This assumption is fundamentally untestable because it concerns unobserved variables.

**How to test**:

While untestable, you can assess plausibility using the same tools as matching:

R:
```r
# 1. Sensitivity analysis: how strong would an unmeasured confounder
#    need to be to overturn the result?
library(EValue)
# For a risk ratio of RR with CI lower bound RR_lo:
# evalues.RR(est = RR, lo = RR_lo, hi = RR_hi)

# 2. Coefficient stability test (Oster 2019)
# If adding more controls barely changes the ATE, it's less likely that
# unobserved confounders would change it
library(grf)
cf_sparse <- causal_forest(X[, 1:2], Y, W, num.trees = 2000, seed = 42)
cf_full   <- causal_forest(X, Y, W, num.trees = 2000, seed = 42)
cat("ATE (sparse covariates):", average_treatment_effect(cf_sparse)[1], "\n")
cat("ATE (full covariates):",   average_treatment_effect(cf_full)[1], "\n")
# Large change = adding controls matters = likely more unobserved confounders
```

Python:
```python
import numpy as np
from econml.dml import CausalForestDML
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

# Coefficient stability: compare ATE with sparse vs full covariates
est_sparse = CausalForestDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3),
    model_t=GradientBoostingClassifier(n_estimators=200, max_depth=3),
    n_estimators=2000, cv=5, random_state=42
)
est_sparse.fit(Y, T, X=X[:, :2], W=W[:, :2])

est_full = CausalForestDML(
    model_y=GradientBoostingRegressor(n_estimators=200, max_depth=3),
    model_t=GradientBoostingClassifier(n_estimators=200, max_depth=3),
    n_estimators=2000, cv=5, random_state=42
)
est_full.fit(Y, T, X=X, W=W)

print(f"ATE (sparse): {est_sparse.ate(X[:, :2]):.4f}")
print(f"ATE (full):   {est_full.ate(X):.4f}")
# Large change suggests sensitivity to covariate set
```

**What violation looks like**: The ATE estimate changes substantially when you add or remove covariates. Domain experts can identify plausible unmeasured confounders. The E-value is small. Treatment was assigned based on criteria you don't fully observe.

**Severity if violated**: Fatal. If important confounders are unmeasured, both the ATE and all CATEs are biased. The bias can be in either direction and there is no upper bound on its magnitude.

**Mitigation**: (1) Measure and include more covariates, especially those related to the treatment assignment mechanism. (2) Use the DML framework (which `grf` and `econml` implement internally) for robustness to partial misspecification of nuisance models. (3) Report sensitivity analysis (E-value, coefficient stability) to show how robust findings are. (4) If unconfoundedness is doubtful, use an alternative identification strategy (DiD, IV, RDD) as the upstream method, then apply HTE to those estimates. (5) Be transparent: heterogeneity estimates inherit all the limitations of the underlying identification strategy.

---

## Overlap / Positivity (Including Subgroup-Level)

**Plain language**: Every type of individual must have a real chance of being either treated or untreated, given their characteristics. For HTE specifically, overlap must hold *within* each CATE subgroup, not just overall. If the highest-CATE group has propensity scores near 1 (almost everyone treated), the GATE for that group is extrapolation, not estimation.

**Formal statement**: 0 < P(D = 1 | X = x) < 1 for all x in the support of X, including within each CATE quantile group. The propensity score e(x) must be bounded away from 0 and 1 in every region where you want to estimate heterogeneous effects.

**Testable?**: Yes. Check propensity score distributions both overall and within CATE quintiles.

**How to test**:

R:
```r
library(grf)

# After fitting causal forest cf:
# Overall overlap
hist(cf$W.hat, breaks = 50, main = "Propensity Score Distribution")

# Subgroup overlap: check within CATE quintiles
tau_hat <- predict(cf)$predictions
quintile <- cut(tau_hat, quantile(tau_hat, 0:5/5),
                include.lowest = TRUE, labels = 1:5)
tapply(cf$W.hat, quintile, summary)  # Look for min < 0.05 or max > 0.95

# Flag problematic quintiles
for (q in 1:5) {
  ps_q <- cf$W.hat[quintile == q]
  if (min(ps_q) < 0.05 | max(ps_q) > 0.95) {
    cat("WARNING: Quintile", q, "has extreme propensity scores:",
        "range [", min(ps_q), ",", max(ps_q), "]\n")
  }
}
```

Python:
```python
from econml.dml import CausalForestDML
import numpy as np
import pandas as pd

# After fitting est:
cate = est.effect(X)
quintile = pd.qcut(cate, 5, labels=[1, 2, 3, 4, 5])

# Check propensity within each quintile
for q in range(1, 6):
    mask = quintile == q
    ps_q = est.models_t[0][0].predict_proba(W[mask])[:, 1]  # approximate
    print(f"Q{q}: PS range [{ps_q.min():.3f}, {ps_q.max():.3f}]")
    if ps_q.min() < 0.05 or ps_q.max() > 0.95:
        print(f"  WARNING: Extreme propensity scores in quintile {q}")
```

**What violation looks like**: The highest-CATE quintile has propensity scores clustered near 1 (almost everyone treated), or the lowest-CATE quintile has propensity scores near 0 (almost no one treated). The GATE estimates for these quintiles have enormous confidence intervals. Variable importance is dominated by a variable that also drives treatment selection.

**Severity if violated**: Fatal (propensity < 0.05 or > 0.95 in any CATE quintile). The GATE estimate for that quintile is extrapolation, not estimation, and policy recommendations based on it are unreliable.

**Mitigation**: (1) Trim units with extreme propensity scores before estimating CATEs. (2) Report GATES only for quintiles with adequate overlap. (3) Use `grf`'s built-in overlap-aware inference (it uses AIPW scores that partially address limited overlap). (4) If overlap is very poor in the highest-CATE group, flag that the "who benefits most" conclusion is unreliable. (5) Consider changing the estimand — if overlap is only poor in one direction, estimate the CATT (conditional ATT) instead of the full CATE.

---

## SUTVA (No Interference)

**Plain language**: One person's treatment doesn't affect another person's outcome. This is the same assumption as in all other causal methods. If treating some customers changes the behavior of untreated customers (e.g., word of mouth, marketplace effects), the estimated CATEs mix direct effects with spillovers.

**Formal statement**: Y_i(D_1, ..., D_N) = Y_i(D_i) for all units i. Each unit's potential outcome depends only on its own treatment status, not on the treatment assignment of any other unit.

**Testable?**: No. SUTVA is generally untestable because we cannot observe the counterfactual of no treatment being assigned to anyone.

**How to test**:

While formally untestable, you can check for suggestive evidence:

R:
```r
library(fixest)

# Among control units, check if proximity to treated units predicts outcomes
# Requires distance or network data
control_df <- df[df$treatment == 0, ]

# If you have a "fraction treated nearby" variable
spillover_test <- feols(outcome ~ fraction_treated_nearby + X1 + X2,
                        data = control_df)
summary(spillover_test)
# Significant coefficient suggests spillover from treated to control units
```

Python:
```python
import statsmodels.formula.api as smf

# Among control units, does proximity to treated units predict outcomes?
control_df = df[df['treatment'] == 0].copy()

model = smf.ols('outcome ~ fraction_treated_nearby + X1 + X2',
                data=control_df).fit()
print(model.summary())
```

**What violation looks like**: Control units near treated units have different outcomes than control units far from treated units. Marketplace effects where treated sellers' discounts affect control sellers' revenues. Social network effects where treated individuals share information with control individuals.

**Severity if violated**: Fatal. If interference exists, the estimated treatment effects conflate direct effects with indirect spillover effects. The CATE estimates are meaningless because the "control" condition varies depending on how many nearby units are treated.

**Mitigation**: (1) Choose control units that are geographically or socially distant from treated units. (2) Use cluster-level treatment assignment. (3) Model interference explicitly if you have network data. (4) Acknowledge the threat and interpret results with the caveat that spillovers may bias both the ATE and the CATEs.

---

## Effect Modifiers Must Be Pre-Treatment

**Plain language**: Variables used to explore heterogeneity (the X matrix in your causal forest) must be measured before treatment exposure begins. Variables measured after treatment that could have been affected by treatment are post-treatment colliders — including them in X creates spurious heterogeneity. The forest will "discover" that the treatment effect varies with these post-treatment variables, but this variation is mechanical, not real.

**Formal statement**: For each effect modifier X_j, X_j must be fixed at the time of treatment assignment. Formally: X_j ⊥ D | Z (X_j is not caused by D). Equivalently, X_j is a pre-treatment covariate.

**Testable?**: No. This is a design issue, not a statistical one. It requires domain knowledge about the timing and causal ordering of variables.

**How to test**:

Not statistically testable. The skill must ask the user to confirm each effect modifier is pre-treatment.

R:
```r
# No statistical test — domain knowledge required.
# Create a timeline for each variable:
cat("Pre-treatment variable checklist:\n")
cat("  age:         Measured at enrollment (pre-treatment) ✓\n")
cat("  income:      Measured at enrollment (pre-treatment) ✓\n")
cat("  engagement:  Measured after treatment started (POST-TREATMENT) ✗\n")
# Any variable marked ✗ must be REMOVED from X before estimation.
```

Python:
```python
# No statistical test — domain knowledge required.
# Create a timeline for each variable:
print("Pre-treatment variable checklist:")
print("  age:         Measured at enrollment (pre-treatment) ✓")
print("  income:      Measured at enrollment (pre-treatment) ✓")
print("  engagement:  Measured after treatment started (POST-TREATMENT) ✗")
# Any variable marked ✗ must be REMOVED from X before estimation.
```

**Examples of violations**: "Engagement score after receiving the intervention," "customer satisfaction measured post-treatment," "BMI measured 6 months into the drug trial," "number of follow-up visits after starting treatment," "revenue in the month after the marketing campaign."

**What violation looks like**: A post-treatment variable appears to strongly moderate the treatment effect (high variable importance), but this is because the treatment itself changed the variable. For example, "patients who had more follow-up visits benefited more" — but more follow-up visits are a *consequence* of treatment, not a pre-existing characteristic.

**Severity if violated**: Fatal. Post-treatment colliders create spurious heterogeneity that cannot be distinguished from real heterogeneity. The entire CATE analysis is invalid. This is the HTE-specific analogue of the "bad controls" problem in regression.

**Mitigation**: (1) Remove the post-treatment variable from X. (2) If you want to study how the treatment effect varies with a post-treatment mediator, use causal mediation analysis instead — this requires different assumptions and methods. (3) Ask for each variable: "Could the treatment have affected this variable?" If yes, it cannot be an effect modifier.

---

## Sufficient Sample Size for Heterogeneity Detection

**Plain language**: Detecting treatment effect heterogeneity requires substantially more data than estimating an average treatment effect. A causal forest that finds "no heterogeneity" in a small sample may simply lack power. Rule of thumb: n ≥ 2,000 total (≥ 500 per treatment arm) for meaningful heterogeneity detection with causal forests. With smaller samples, LinearDML with pre-specified interactions is more appropriate. You also need ~100+ observations per CATE quintile for reliable GATES estimates.

**Formal statement**: The convergence rate of CATE estimation is slower than ATE estimation. For causal forests, the minimax rate for CATE estimation is n^(-2/(2+d)) where d is the effective dimension. In practice, this means heterogeneity detection requires sample sizes several times larger than ATE estimation.

**Testable?**: Yes. Check total n and n per CATE quintile.

**How to test**:

R:
```r
# Check total sample size
cat("Total n:", nrow(df), "\n")
cat("Treated:", sum(df$treatment == 1), "\n")
cat("Control:", sum(df$treatment == 0), "\n")

if (nrow(df) < 2000) {
  cat("WARNING: n < 2,000. Causal forest may lack power for heterogeneity detection.\n")
  cat("Consider LinearDML with pre-specified interactions instead.\n")
}

# Check n per CATE quintile (after fitting forest)
tau_hat <- predict(cf)$predictions
quintile <- cut(tau_hat, quantile(tau_hat, 0:5/5),
                include.lowest = TRUE, labels = 1:5)
cat("\nSample size per CATE quintile:\n")
print(table(quintile))
# Need ~100+ per quintile for reliable GATES
```

Python:
```python
import pandas as pd
import numpy as np

# Check total sample size
print(f"Total n: {len(df)}")
print(f"Treated: {(df['treatment'] == 1).sum()}")
print(f"Control: {(df['treatment'] == 0).sum()}")

if len(df) < 2000:
    print("WARNING: n < 2,000. Causal forest may lack power.")
    print("Consider LinearDML with pre-specified interactions instead.")

# Check n per CATE quintile (after fitting)
cate = est.effect(X)
quintile = pd.qcut(cate, 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
print("\nSample size per CATE quintile:")
print(quintile.value_counts().sort_index())
# Need ~100+ per quintile for reliable GATES
```

**What violation looks like**: The BLP test is not significant, but this may reflect low power rather than absence of heterogeneity. GATES confidence intervals are very wide and all overlap. The calibration test shows "mean.forest.prediction" is significant (the forest captures some signal) but "differential.forest.prediction" is not (heterogeneity not detectable at this sample size).

**Severity if violated**: Serious (n < 2,000 total or < 100 per CATE quintile). The analysis may fail to detect real heterogeneity, and any heterogeneity it does find may be unreliable.

**Mitigation**: (1) Use LinearDML as the primary estimator — it is more efficient with smaller samples because it imposes linearity. (2) Focus on pre-specified subgroup hypotheses rather than data-driven discovery. (3) Report that "no heterogeneity detected" should be interpreted as "insufficient power to detect heterogeneity," not "effects are homogeneous." (4) If possible, collect more data. (5) Reduce the number of effect modifiers to increase effective sample size per split.

---

## Honest Estimation / Sample Splitting

**Plain language**: The same data cannot be used to both discover heterogeneity patterns and confirm them. This is analogous to the problem of testing hypotheses on the same data used to generate them — it leads to overfitting and invalid confidence intervals. `grf` handles this via honest splitting (`honesty = TRUE`, the default): one subsample builds the tree structure, another estimates leaf effects. `econml` handles this via cross-fitting (`cv > 1`). Never turn these off.

**Formal statement**: Honest estimation requires that the subsample used to determine the tree partition (the "splitting" sample) is independent of the subsample used to estimate treatment effects within leaves (the "estimation" sample). Cross-fitting extends this to the nuisance model estimation stage.

**Testable?**: Yes — you can check the settings.

**How to test**:

R:
```r
# Check that honesty is enabled (it is by default)
# If you see honesty = FALSE in the causal_forest() call, this is FATAL.
cf <- causal_forest(X, Y, W, num.trees = 2000, honesty = TRUE, seed = 42)
# honesty = TRUE is the default — just make sure nobody turned it off.

# Verify:
cat("Honesty fraction:", cf$honesty.fraction, "\n")
# Should be > 0 (default is 0.5)
```

Python:
```python
from econml.dml import CausalForestDML

# Check that cross-fitting is enabled (cv > 1)
est = CausalForestDML(
    model_y=GradientBoostingRegressor(),
    model_t=GradientBoostingClassifier(),
    cv=5,  # 5-fold cross-fitting — do NOT set cv=1
    random_state=42
)
# cv=1 means no cross-fitting — this is dangerous.
# cv >= 3 (ideally 5) is recommended.
```

**What violation looks like**: Setting `honesty = FALSE` in `grf` or `cv = 1` in `econml`. The resulting confidence intervals are too narrow (anti-conservative), and the CATE estimates overfit to the training data. Variable importance is inflated. The BLP test shows "significant heterogeneity" that does not replicate on held-out data.

**Severity if violated**: Fatal. Confidence intervals become invalid. The forest reports heterogeneity that is an artifact of overfitting. Policy recommendations based on these estimates may harm units they claim to help.

**Mitigation**: (1) Keep `honesty = TRUE` in `grf` (the default). (2) Keep `cv >= 3` in `econml` (default is 3, but 5 is better). (3) If you suspect overfitting, hold out 20% of data and check whether CATE predictions from the training set correlate with actual outcomes in the held-out set. (4) Never turn off honesty or cross-fitting to "improve" results — the improvement is an illusion.
