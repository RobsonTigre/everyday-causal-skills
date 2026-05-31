# Experiments parity reference recipe (R). `df` is preloaded by the runner.
# Canonical best-practice estimator: Lin (2013) interacted regression
# adjustment with HC2 robust SEs via estimatr::lm_lin / lm_robust.
suppressMessages({
  library(estimatr)
})

# 1. Difference in means (unadjusted ATE), HC2 SE via lm_robust.
dim_fit <- lm_robust(outcome ~ treatment, data = df, se_type = "HC2")
cat(sprintf("ATE:%f\n", coef(dim_fit)[["treatment"]]))
cat(sprintf("SE:%f\n", dim_fit$std.error[["treatment"]]))

# 2. Lin (2013) covariate-adjusted ATE: covariates centered and interacted
#    with treatment, HC2 SE. lm_lin is the dedicated implementation.
lin_fit <- lm_lin(outcome ~ treatment, covariates = ~ X1 + X2 + X3,
                  data = df, se_type = "HC2")
cat(sprintf("ATE_ADJ:%f\n", coef(lin_fit)[["treatment"]]))
cat(sprintf("SE_ADJ:%f\n", lin_fit$std.error[["treatment"]]))
