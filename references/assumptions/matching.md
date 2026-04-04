# Assumption Checklist: Matching / PSM / PSW / Doubly-Robust

Reference: `references/method-registry.md` → Matching / PSM / PSW / Doubly-Robust

---

## Conditional Independence (Unconfoundedness)

**Plain language**: After you account for all the measured covariates, treatment assignment is as good as random. There are no unmeasured variables that affect both who gets treated and the outcome. This is the hardest assumption to believe — it requires that you've measured everything that matters.

**Formal statement**: (Y(0), Y(1)) ⊥ D | X, where Y(0) and Y(1) are potential outcomes, D is treatment status, and X is the vector of observed covariates. Conditional on X, treatment assignment is independent of potential outcomes. Also known as "selection on observables," "ignorability," or "no unmeasured confounders."

**Testable?**: No. This assumption is fundamentally untestable because it concerns unobserved variables. You can never rule out that an important confounder was missed.

**How to test**:

While untestable, you can assess plausibility:

R:
```r
# 1. Sensitivity analysis: how strong would an unmeasured confounder
#    need to be to overturn the result?
# Rosenbaum bounds (for matched data)
library(rbounds)
# After matching, extract matched outcomes
# psens(matched_outcome_treated, matched_outcome_control, Gamma = 2, GammaInc = 0.1)

# 2. E-value: minimum strength of confounding needed to explain away
#    the observed effect
library(EValue)
# For a risk ratio of RR with CI lower bound RR_lo:
evalues.RR(est = RR, lo = RR_lo, hi = RR_hi)

# 3. Coefficient stability test (Oster 2019)
# If adding more controls barely changes the treatment coefficient,
# it's less likely that unobserved confounders would change it
library(fixest)
model_sparse <- feols(outcome ~ treatment, data = df)
model_full <- feols(outcome ~ treatment + X1 + X2 + X3 + X4, data = df)
cat("Sparse estimate:", coef(model_sparse)["treatment"], "\n")
cat("Full estimate:", coef(model_full)["treatment"], "\n")
cat("Change:", abs(coef(model_sparse)["treatment"] - coef(model_full)["treatment"]), "\n")
# Large change = adding controls matters a lot = likely more unobserved confounders
```

Python:
```python
import statsmodels.formula.api as smf

# Coefficient stability test
model_sparse = smf.ols('outcome ~ treatment', data=df).fit()
model_full = smf.ols('outcome ~ treatment + X1 + X2 + X3 + X4', data=df).fit()

print(f"Sparse estimate: {model_sparse.params['treatment']:.4f}")
print(f"Full estimate: {model_full.params['treatment']:.4f}")
change = abs(model_sparse.params['treatment'] - model_full.params['treatment'])
print(f"Change when adding controls: {change:.4f}")

# Sensitivity analysis: E-value calculation
import numpy as np
def e_value(rr):
    """Minimum confounding strength to explain away observed RR."""
    return rr + np.sqrt(rr * (rr - 1))

# Convert your effect to a risk ratio and compute E-value
# e_val = e_value(your_risk_ratio)
# print(f"E-value: {e_val:.2f}")
```

**What violation looks like**: There is no single statistical test that detects this violation. Warning signs include: (1) the treatment coefficient changes substantially as you add controls (suggesting unobserved confounders could change it further), (2) domain experts identify plausible unmeasured confounders, (3) the E-value is small (a weak unobserved confounder could overturn the result), (4) the treatment was assigned based on criteria you don't fully observe.

**Severity if violated**: Fatal. If important confounders are unmeasured, the estimated treatment effect is biased. The bias can be in either direction and there is no upper bound on its magnitude. This is the fundamental limitation of all observational methods that rely on selection on observables.

**Mitigation**: None that fully resolves the problem. (1) Measure and include more covariates, especially those related to the treatment assignment mechanism. (2) Use doubly-robust estimation (combine propensity score with outcome model) for robustness to partial misspecification. (3) Report sensitivity analysis (E-value, Rosenbaum bounds, Oster bounds) to show how robust the finding is to unobserved confounding. (4) Use an alternative identification strategy if available (DiD, IV, RDD). (5) Be transparent: state explicitly that this is the weakest identification strategy and that unobserved confounders may bias results.

---

## Overlap / Positivity

**Plain language**: Every unit in the study must have a real chance of being either treated or untreated, given their characteristics. If some types of people always get the treatment (or never get it), you can't compare treated and untreated units with those characteristics — there's no overlap.

**Formal statement**: 0 < P(D = 1 | X = x) < 1 for all x in the support of X. Every covariate stratum must contain both treated and untreated units. Equivalently, the propensity score e(x) = P(D=1|X=x) must be bounded away from 0 and 1.

**Testable?**: Yes. Check the distribution of propensity scores in both groups. Violations appear as regions with no overlap.

**How to test**:

R:
```r
library(MatchIt)
library(cobalt)

# Estimate propensity scores
m_out <- matchit(treatment ~ X1 + X2 + X3 + X4, data = df,
                 method = NULL, estimand = "ATT")

# Propensity score overlap plot
library(ggplot2)
ps <- m_out$distance  # propensity scores
df$ps <- ps

ggplot(df, aes(x = ps, fill = factor(treatment))) +
  geom_histogram(alpha = 0.5, position = "identity", bins = 50) +
  labs(title = "Propensity Score Distribution by Treatment Group",
       x = "Propensity Score", y = "Count", fill = "Treatment") +
  theme_minimal()

# Check extremes
cat("Propensity score summary (treated):\n")
summary(df$ps[df$treatment == 1])
cat("\nPropensity score summary (control):\n")
summary(df$ps[df$treatment == 0])

# Fraction with extreme propensity scores
cat("\nFraction with PS < 0.05:", mean(df$ps < 0.05), "\n")
cat("Fraction with PS > 0.95:", mean(df$ps > 0.95), "\n")

# Overlap assessment from cobalt
bal.plot(m_out, var.name = "distance", which = "both",
         type = "histogram", mirror = TRUE)
```

Python:
```python
from sklearn.linear_model import LogisticRegression
import matplotlib.pyplot as plt
import numpy as np

# Estimate propensity scores
X = df[['X1', 'X2', 'X3', 'X4']].values
D = df['treatment'].values

ps_model = LogisticRegression(max_iter=1000)
ps_model.fit(X, D)
ps = ps_model.predict_proba(X)[:, 1]
df['ps'] = ps

# Overlap plot
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(ps[D == 1], bins=50, alpha=0.5, label='Treated', density=True)
ax.hist(ps[D == 0], bins=50, alpha=0.5, label='Control', density=True)
ax.set_xlabel('Propensity Score')
ax.set_ylabel('Density')
ax.set_title('Propensity Score Distribution by Treatment Group')
ax.legend()
plt.tight_layout()
plt.show()

# Check extremes
print(f"Treated PS range: [{ps[D==1].min():.4f}, {ps[D==1].max():.4f}]")
print(f"Control PS range: [{ps[D==0].min():.4f}, {ps[D==0].max():.4f}]")
print(f"Fraction with PS < 0.05: {np.mean(ps < 0.05):.4f}")
print(f"Fraction with PS > 0.95: {np.mean(ps > 0.95):.4f}")
```

**What violation looks like**: The propensity score distributions for treated and control groups have little overlap — treated units have very high propensity scores while control units have very low ones. Some covariate combinations exist only in the treated group (or only in the control). The propensity score histogram shows separation between groups.

**Severity if violated**: Fatal. Without overlap, matching/weighting methods must extrapolate into regions with no data, leading to extreme weights and unstable estimates. IPW estimates become dominated by a few units with extreme propensity scores, and the variance explodes.

**Mitigation**: (1) Trim the sample to the region of common support (drop units with propensity scores near 0 or 1). Common thresholds: drop PS < 0.05 or PS > 0.95. (2) Use weight trimming or stabilized IPW weights. (3) Use doubly-robust methods, which are more stable than pure IPW under limited overlap. (4) Use coarsened exact matching (CEM), which explicitly restricts to strata with both treated and control units. (5) Change the estimand — estimate the ATT (effect on the treated) rather than the ATE if only one direction has poor overlap. (6) If overlap is very poor, this is a sign that treated and control groups are too different — matching may not be credible.

---

## SUTVA (No Interference)

**Plain language**: One person's treatment doesn't affect another person's outcome. If you give a discount to one customer, that shouldn't change the behavior of other customers who didn't get the discount.

**Formal statement**: Y_i(D_1, ..., D_N) = Y_i(D_i) for all units i. Each unit's potential outcome depends only on its own treatment status, not on the treatment assignment of any other unit.

**Testable?**: No. SUTVA is generally untestable because we cannot observe the counterfactual of no treatment being assigned to anyone.

**How to test**:

While formally untestable, you can check for suggestive evidence:

R:
```r
library(fixest)

# Suggestive: among control units, check if proximity to treated
# units predicts outcomes (requires distance/network data)
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

# Suggestive test: among control units, does proximity to treated
# units predict outcomes?
control_df = df[df['treatment'] == 0].copy()

model = smf.ols('outcome ~ fraction_treated_nearby + X1 + X2',
                data=control_df).fit()
print(model.summary())
```

**What violation looks like**: Control units near treated units have different outcomes than control units far from treated units. Marketplace effects where treated sellers' discounts affect control sellers' revenues. Social network effects where treated individuals share information with control individuals.

**Severity if violated**: Fatal. If interference exists, the estimated treatment effect conflates the direct effect of treatment with indirect spillover effects. The control group is contaminated, and the comparison between treated and control is no longer valid.

**Mitigation**: (1) Choose control units that are geographically or socially distant from treated units. (2) Use cluster-level assignment (treat entire clusters, use other clusters as controls). (3) Model interference explicitly if you have network data (see interference-aware estimators). (4) Acknowledge the threat and interpret results with the caveat that spillovers may bias the estimate.

---

## Correct Model Specification

**Plain language**: The propensity score model (or outcome model, for doubly-robust methods) is correctly specified. If you use logistic regression for the propensity score but the true relationship is nonlinear, the estimated propensity scores are wrong, and matching/weighting will be off.

**Formal statement**: For PSM/PSW, the propensity score model e(x; beta) correctly specifies P(D=1|X=x). For outcome modeling, the conditional mean function m(x; gamma) = E[Y|X=x, D=d] is correctly specified. For doubly-robust methods: the estimate is consistent if EITHER the propensity score OR the outcome model is correct (but at least one must be).

**Testable?**: Partially. You can check the adequacy of the propensity score model via covariate balance after matching/weighting. If balance is achieved, the propensity score model was adequate for the purpose of removing confounding — even if misspecified in a statistical sense.

**How to test**:

R:
```r
library(MatchIt)
library(cobalt)

# Step 1: Match using MatchIt
m_out <- matchit(treatment ~ X1 + X2 + X3 + X4, data = df,
                 method = "nearest", estimand = "ATT",
                 distance = "glm")  # logistic propensity score

# Step 2: Check covariate balance
bal <- bal.tab(m_out, thresholds = c(m = 0.1))
print(bal)

# Step 3: Love plot — visual balance check
love.plot(bal, threshold = 0.1,
          title = "Covariate Balance: Before vs After Matching")

# Rule of thumb: standardized mean differences (SMD) should be < 0.1
# (or at least < 0.25) after matching

# Step 4: Variance ratios (should be between 0.5 and 2.0)
bal.tab(m_out, thresholds = c(m = 0.1, v = 2))

# Step 5: If balance is poor, try a more flexible specification
m_out_flex <- matchit(treatment ~ X1 + X2 + X3 + X4 +
                        I(X1^2) + I(X2^2) + X1:X2,
                      data = df, method = "nearest", estimand = "ATT")
bal.tab(m_out_flex, thresholds = c(m = 0.1))
```

Python:
```python
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

# Step 1: Estimate propensity scores
covariates = ['X1', 'X2', 'X3', 'X4']
X = df[covariates].values
D = df['treatment'].values

ps_model = LogisticRegression(max_iter=1000)
ps_model.fit(X, D)
df['ps'] = ps_model.predict_proba(X)[:, 1]

# Step 2: IPW weights (for ATT)
df['ipw_weight'] = np.where(
    df['treatment'] == 1, 1,
    df['ps'] / (1 - df['ps'])
)

# Step 3: Check weighted balance via standardized mean differences
def smd(treated, control, weights_control=None):
    """Compute standardized mean difference."""
    m_t = treated.mean()
    s_t = treated.std()
    if weights_control is not None:
        m_c = np.average(control, weights=weights_control)
    else:
        m_c = control.mean()
    return (m_t - m_c) / s_t

balance = []
for cov in covariates:
    treated_vals = df.loc[df['treatment'] == 1, cov]
    control_vals = df.loc[df['treatment'] == 0, cov]
    control_weights = df.loc[df['treatment'] == 0, 'ipw_weight']

    smd_raw = smd(treated_vals, control_vals)
    smd_weighted = smd(treated_vals, control_vals, control_weights)

    balance.append({
        'covariate': cov,
        'SMD_before': smd_raw,
        'SMD_after': smd_weighted,
        'balanced': abs(smd_weighted) < 0.1
    })

balance_df = pd.DataFrame(balance)
print(balance_df)

# Rule of thumb: SMD < 0.1 after weighting/matching
print(f"\nAll balanced: {balance_df['balanced'].all()}")
```

**What violation looks like**: Covariate balance (SMD) remains poor after matching or weighting. Standardized mean differences exceed 0.1 (or even 0.25) for important covariates. The love plot shows persistent imbalance. Variance ratios are far from 1.0.

**Severity if violated**: Serious. Misspecification of the propensity score model leads to incorrect weights/matches, which fails to remove confounding. However, doubly-robust methods provide a safety net: the estimate is consistent if either the propensity score or the outcome model is correct. Poor balance is the observable manifestation of misspecification — it is both the diagnostic and the warning.

**Mitigation**: (1) Use a more flexible propensity score model: add polynomials, interactions, or use machine learning (GBM, random forest) to estimate propensity scores. (2) Try different matching methods: full matching, CEM, or genetic matching may achieve better balance than nearest-neighbor PSM. (3) Use doubly-robust estimation (AIPW) as a safeguard. (4) Iterate: estimate propensity scores → check balance → re-specify until balance is achieved. In R, `MatchIt` makes this easy with `method = "full"` or `method = "cem"`. (5) Consider `cobalt::bal.tab()` with `love.plot()` as the primary diagnostic — balance, not model fit statistics, is what matters.
