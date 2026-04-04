# Assumption Checklist: Randomized Experiments / A/B Tests

Reference: `references/method-registry.md` → Randomized Experiments / A/B Tests

---

## Random Assignment

**Plain language**: Treatment was truly randomly assigned — each unit had a known, non-zero probability of being in either group, and no one could influence their assignment. The randomization mechanism was properly implemented and not compromised.

**Formal statement**: D ⊥ (Y(0), Y(1)), where D is the treatment indicator and Y(0), Y(1) are potential outcomes. Treatment assignment is independent of all potential outcomes (and therefore of all observed and unobserved covariates). For stratified randomization: D ⊥ (Y(0), Y(1)) | S, where S is the stratification variable.

**Testable?**: Yes. While you can't directly test independence from unobservables, you can verify that observed covariates are balanced across groups — which is what randomization should produce.

**How to test**:

R:
```r
library(cobalt)
library(fixest)

# 1. Balance table: standardized mean differences across covariates
bal <- bal.tab(treatment ~ X1 + X2 + X3 + X4 + X5,
               data = df,
               binary = "std", continuous = "std",
               thresholds = c(m = 0.1))
print(bal)

# Love plot: visual balance check
love.plot(bal, threshold = 0.1,
          title = "Covariate Balance: Treatment vs Control")

# 2. ROC-AUC test: train a classifier to predict treatment from
#    covariates. AUC should be near 0.5 (can't distinguish groups).
library(pROC)

# Fit propensity score model
ps_model <- glm(treatment ~ X1 + X2 + X3 + X4 + X5,
                data = df, family = binomial)
ps <- predict(ps_model, type = "response")

# Out-of-sample AUC (using holdout or cross-validation)
set.seed(42)
train_idx <- sample(nrow(df), 0.7 * nrow(df))
ps_train <- glm(treatment ~ X1 + X2 + X3 + X4 + X5,
                data = df[train_idx, ], family = binomial)
ps_test <- predict(ps_train, newdata = df[-train_idx, ], type = "response")
roc_result <- roc(df$treatment[-train_idx], ps_test)
cat("Holdout AUC:", auc(roc_result), "\n")
# AUC near 0.5 → cannot predict treatment → good balance
# AUC > 0.6 → covariates predict treatment → possible imbalance

# 3. Joint F-test: regress treatment on all covariates
f_test <- feols(treatment ~ X1 + X2 + X3 + X4 + X5, data = df)
wald(f_test, keep = c("X1", "X2", "X3", "X4", "X5"))
# p > 0.05 → covariates don't jointly predict treatment (good)
```

Python:
```python
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import roc_auc_score
from scipy.stats import ttest_ind

# 1. Balance table: standardized mean differences
covariates = ['X1', 'X2', 'X3', 'X4', 'X5']
balance = []
for cov in covariates:
    treated = df.loc[df['treatment'] == 1, cov]
    control = df.loc[df['treatment'] == 0, cov]
    pooled_std = np.sqrt((treated.var() + control.var()) / 2)
    smd = (treated.mean() - control.mean()) / pooled_std
    stat, pval = ttest_ind(treated, control)
    balance.append({
        'covariate': cov,
        'mean_treated': treated.mean(),
        'mean_control': control.mean(),
        'SMD': smd,
        'p_value': pval,
        'balanced': abs(smd) < 0.1
    })
print(pd.DataFrame(balance))

# 2. ROC-AUC test: can covariates predict treatment?
X = df[covariates].values
D = df['treatment'].values

model = LogisticRegression(max_iter=1000)
# Cross-validated predictions to avoid overfitting
cv_probs = cross_val_predict(model, X, D, cv=5, method='predict_proba')[:, 1]
auc = roc_auc_score(D, cv_probs)
print(f"\nCross-validated AUC: {auc:.4f}")
print("AUC near 0.5 → good balance (can't predict treatment)")
print("AUC > 0.6 → possible imbalance")

# 3. Joint F-test via OLS
import statsmodels.formula.api as smf
f_model = smf.ols('treatment ~ X1 + X2 + X3 + X4 + X5', data=df).fit()
print(f"\nJoint F-test: F = {f_model.fvalue:.4f}, p = {f_model.f_pvalue:.4f}")
```

**What violation looks like**: Large standardized mean differences (> 0.1) on key covariates. ROC-AUC substantially above 0.5 (e.g., > 0.6). Joint F-test rejects (p < 0.05). These can occur from: (1) a bug in the randomization code, (2) manual overrides of random assignment, (3) sample contamination (units switching groups), or (4) bad luck with small samples (which should happen ~5% of the time for any single covariate test).

**Severity if violated**: Fatal. If assignment was not random, the fundamental basis of the experiment collapses. The treatment and control groups differ systematically, and any difference in outcomes may be due to the baseline differences rather than the treatment.

**Mitigation**: (1) Investigate the randomization mechanism — check the code, verify no manual overrides occurred. (2) If imbalance is minor and plausibly due to chance (especially in small samples), use regression adjustment to control for the imbalanced covariates. (3) Re-randomize if the experiment hasn't started yet and the assignment protocol was flawed. (4) If the randomization was clearly compromised (e.g., manual overrides, self-selection), treat the data as observational and use appropriate methods (matching, DiD).

---

## SUTVA (No Interference)

**Plain language**: One person's treatment assignment doesn't affect another person's outcomes. If you give a 20% discount to some users, that shouldn't change the behavior of users who didn't get the discount — for example, through word-of-mouth, shared accounts, or marketplace competition effects.

**Formal statement**: Y_i(D_1, ..., D_N) = Y_i(D_i) for all units i. Each unit's potential outcome depends only on its own treatment status, not on the treatment assignment of any other unit. Additionally, there is only one version of treatment (no hidden variations).

**Testable?**: No. SUTVA is fundamentally untestable because we cannot observe what would have happened to control units in a world where no one was treated.

**How to test**:

While formally untestable, you can check for suggestive evidence:

R:
```r
library(fixest)

# Suggestive test 1: Check if control group outcomes vary by exposure
# to treated units (requires geographic or network proximity data)
control_df <- df[df$treatment == 0, ]

spillover_model <- feols(outcome ~ pct_treated_in_cluster,
                         data = control_df)
summary(spillover_model)
# Significant coefficient → control outcomes vary with treatment intensity

# Suggestive test 2: Compare treatment effects across clusters with
# different treatment assignment fractions
df$treatment_intensity <- ave(df$treatment, df$cluster_id, FUN = mean)
model_intensity <- feols(outcome ~ treatment * treatment_intensity,
                         data = df, cluster = ~cluster_id)
summary(model_intensity)
# Significant interaction → effect depends on how many others are treated
```

Python:
```python
import statsmodels.formula.api as smf

# Suggestive test: among control units, does exposure to treated
# units predict outcomes?
control_df = df[df['treatment'] == 0].copy()

model = smf.ols('outcome ~ pct_treated_in_cluster', data=control_df).fit()
print(model.summary())

# Test for treatment intensity effects
model_intensity = smf.ols('outcome ~ treatment * treatment_intensity',
                          data=df).fit(
    cov_type='cluster', cov_kwds={'groups': df['cluster_id']})
print(model_intensity.summary())
```

**What violation looks like**: Control group outcomes change systematically depending on how many treated units are nearby. The estimated treatment effect varies with the fraction of units treated in a cluster. Users in the control group show awareness of or response to the treatment (e.g., mentioning a promotion they heard about from treated users).

**Severity if violated**: Fatal. If treated units affect control units, the control group no longer represents the untreated potential outcome. The difference in means no longer estimates the ATE. Spillovers can bias the estimate in either direction: positive spillovers (treated helping control) attenuate the estimated effect; negative spillovers (treated harming control via competition) inflate it.

**Mitigation**: (1) Use cluster-randomized designs where entire clusters (stores, regions, friend groups) are assigned to treatment or control, reducing within-cluster contamination. (2) Create buffer zones — exclude units that are geographically close to the opposite group. (3) Measure and model spillovers explicitly if network data is available. (4) Use switchback designs (alternating treatment and control over time) for marketplace experiments. (5) If spillovers are inherent (e.g., marketplace experiments), estimate the total effect (direct + indirect) rather than the individual-level effect.

---

## Compliance

**Plain language**: Everyone who was assigned to receive the treatment actually received it, and no one in the control group received the treatment. If people switch groups or don't comply, the simple comparison of assigned groups is diluted.

**Formal statement**: D_i = Z_i for all i, where Z_i is the treatment assignment and D_i is the actual treatment received. Perfect compliance means the assignment IS the treatment. When compliance is imperfect, the comparison of assigned groups estimates the intention-to-treat (ITT) effect rather than the treatment effect on the treated.

**Testable?**: Yes. Check the compliance rate directly by comparing treatment assignment to actual treatment receipt.

**How to test**:

R:
```r
# Compliance rates
compliance <- table(assigned = df$assignment, received = df$actual_treatment)
print(compliance)

# Compliance rate among assigned-to-treatment
comply_treat <- mean(df$actual_treatment[df$assignment == 1])
cat("Compliance rate (treatment group):", comply_treat, "\n")

# Contamination rate among assigned-to-control
contam_control <- mean(df$actual_treatment[df$assignment == 0])
cat("Contamination rate (control group):", contam_control, "\n")

# Overall compliance
overall <- mean(df$assignment == df$actual_treatment)
cat("Overall compliance:", overall, "\n")

# If non-compliance exists: estimate both ITT and CACE/LATE
library(fixest)

# ITT: effect of assignment (always valid)
itt <- feols(outcome ~ assignment, data = df)
summary(itt)

# CACE/LATE via IV: instrument is assignment, treatment is actual receipt
cace <- feols(outcome ~ 1 | actual_treatment ~ assignment, data = df)
summary(cace)
cat("First-stage F:", fitstat(cace, "ivf")$ivf$stat, "\n")
```

Python:
```python
import pandas as pd
import numpy as np
from linearmodels.iv import IV2SLS

# Compliance rates
compliance_table = pd.crosstab(df['assignment'], df['actual_treatment'],
                                margins=True)
print(compliance_table)

comply_treat = df.loc[df['assignment'] == 1, 'actual_treatment'].mean()
contam_control = df.loc[df['assignment'] == 0, 'actual_treatment'].mean()
print(f"Compliance rate (treatment group): {comply_treat:.4f}")
print(f"Contamination rate (control group): {contam_control:.4f}")

# ITT: effect of assignment
import statsmodels.formula.api as smf
itt = smf.ols('outcome ~ assignment', data=df).fit()
print("\n--- ITT ---")
print(f"ITT estimate: {itt.params['assignment']:.4f}")

# CACE/LATE via IV
iv = IV2SLS.from_formula(
    'outcome ~ 1 + [actual_treatment ~ assignment]',
    data=df)
iv_res = iv.fit(cov_type='robust')
print("\n--- CACE/LATE ---")
print(iv_res)
```

**What violation looks like**: Compliance rate below 100%. Some units assigned to treatment never received it (one-sided non-compliance). Some units assigned to control received the treatment anyway (two-sided non-compliance / contamination). The ITT effect is attenuated compared to the treatment-on-treated effect.

**Severity if violated**: Serious. Non-compliance doesn't invalidate the experiment entirely — the ITT is always a valid causal effect (of assignment, not treatment). But if your question is about the effect of actually receiving treatment, you need to adjust. Low compliance (< 50%) makes the CACE/LATE estimate noisy and imprecise. Very low compliance means the experiment is effectively not testing the treatment.

**Mitigation**: (1) Always report the ITT estimate — it is valid under any level of non-compliance. (2) Use IV (assignment instruments for actual treatment) to estimate the CACE/LATE for compliers. (3) Ensure the first-stage F-statistic is strong (F > 10) for the IV estimate to be reliable. (4) At the design stage: improve compliance by making treatment assignment harder to avoid (automatic enrollment, etc.). (5) If non-compliance is severe, bound the treatment effect using the ITT and compliance rate: CACE = ITT / compliance_rate.

---

## No Differential Attrition

**Plain language**: People don't drop out of the study at different rates depending on which group they're in. If 20% of the treatment group drops out but only 5% of the control group does, the remaining samples are no longer comparable — the treatment group is now a selected (possibly healthier, more engaged) subset.

**Formal statement**: P(observed at endline | D = 1) = P(observed at endline | D = 0). Attrition is independent of treatment assignment, and attriters are not systematically different from non-attriters within each group.

**Testable?**: Yes. Compare attrition rates across groups and test whether attriters differ from non-attriters on baseline characteristics.

**How to test**:

R:
```r
library(fixest)
library(cobalt)

# 1. Attrition rates by group
attrition_rate <- df |>
  dplyr::group_by(treatment) |>
  dplyr::summarize(
    n_initial = dplyr::n(),
    n_observed = sum(!is.na(outcome)),
    attrition_rate = 1 - n_observed / n_initial
  )
print(attrition_rate)

# Test for differential attrition
df$attrited <- as.integer(is.na(df$outcome))
attrition_test <- feols(attrited ~ treatment, data = df)
summary(attrition_test)
# p < 0.05 → differential attrition exists

# 2. Are attriters different on baseline characteristics?
attriters <- df[df$attrited == 1, ]
non_attriters <- df[df$attrited == 0, ]

bal_attrit <- bal.tab(attrited ~ X1 + X2 + X3,
                      data = df, binary = "std", continuous = "std",
                      thresholds = c(m = 0.1))
print(bal_attrit)

# 3. Lee bounds: worst-case bounds on the treatment effect
#    accounting for differential attrition
# (Requires trimming the group with less attrition to equalize rates)
# Simple implementation:
treat_outcomes <- sort(df$outcome[df$treatment == 1 & !df$attrited])
control_outcomes <- df$outcome[df$treatment == 0 & !df$attrited]
n_trim <- sum(df$attrited & df$treatment == 0) -
          sum(df$attrited & df$treatment == 1)
if (n_trim > 0) {
  # Trim from top and bottom of the less-attrited group
  upper_bound <- mean(treat_outcomes[1:(length(treat_outcomes) - n_trim)]) -
                 mean(control_outcomes)
  lower_bound <- mean(treat_outcomes[(n_trim + 1):length(treat_outcomes)]) -
                 mean(control_outcomes)
  cat("Lee bounds: [", lower_bound, ",", upper_bound, "]\n")
}
```

Python:
```python
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency, ttest_ind

# 1. Attrition rates by group
df['attrited'] = df['outcome'].isna().astype(int)

attrition = df.groupby('treatment').agg(
    n_initial=('treatment', 'count'),
    n_attrited=('attrited', 'sum')
).assign(attrition_rate=lambda x: x['n_attrited'] / x['n_initial'])
print(attrition)

# Test for differential attrition
table = pd.crosstab(df['treatment'], df['attrited'])
chi2, p, _, _ = chi2_contingency(table)
print(f"\nDifferential attrition test: chi2 = {chi2:.4f}, p = {p:.4f}")

# 2. Compare attriters vs non-attriters on baseline covariates
covariates = ['X1', 'X2', 'X3']
for cov in covariates:
    attriters = df.loc[df['attrited'] == 1, cov]
    stayers = df.loc[df['attrited'] == 0, cov]
    stat, pval = ttest_ind(attriters.dropna(), stayers.dropna())
    print(f"{cov}: attriters mean = {attriters.mean():.3f}, "
          f"stayers mean = {stayers.mean():.3f}, p = {pval:.4f}")

# 3. Lee bounds (simplified)
observed = df[df['attrited'] == 0].copy()
treat_outcomes = np.sort(observed.loc[observed['treatment'] == 1, 'outcome'].values)
control_mean = observed.loc[observed['treatment'] == 0, 'outcome'].mean()

n_excess = (df.loc[df['treatment'] == 0, 'attrited'].sum() -
            df.loc[df['treatment'] == 1, 'attrited'].sum())

if n_excess > 0:
    # Trim from less-attrited group
    lower = np.mean(treat_outcomes[n_excess:]) - control_mean
    upper = np.mean(treat_outcomes[:len(treat_outcomes) - n_excess]) - control_mean
    print(f"\nLee bounds: [{min(lower, upper):.4f}, {max(lower, upper):.4f}]")
```

**What violation looks like**: Attrition rates differ significantly between treatment and control (e.g., 15% vs 5%). Attriters differ from non-attriters on baseline covariates. The treatment group that remains after attrition looks systematically different from the control group on baseline characteristics, even though randomization was correct at baseline.

**Severity if violated**: Serious. Differential attrition creates post-randomization selection bias. Even if the initial randomization was perfect, unequal dropout makes the remaining samples non-comparable. The direction of bias depends on who drops out: if the treatment causes the weakest to leave, the effect is overstated (survivorship bias); if the treatment causes the strongest to leave (e.g., they no longer need the service), the effect is understated.

**Mitigation**: (1) Report Lee bounds to show the range of possible effects under worst-case attrition assumptions. (2) Compare attriters vs non-attriters on baseline characteristics within each group. (3) Use inverse probability of attrition weighting (IPAW) to reweight the remaining sample. (4) At the design stage: minimize attrition through incentives, follow-up protocols, and reducing participant burden. (5) If attrition is severe and differential, acknowledge that the experimental estimates are no longer protected by randomization and interpret results cautiously.
