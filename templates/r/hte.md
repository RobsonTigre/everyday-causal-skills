# HTE Analysis — R Template (grf + policytree)

## Prerequisites

```r
# Install if needed: install.packages(c("grf", "policytree"))
library(grf)
library(policytree)
```

## Data Preparation

```r
# Load data
df <- read.csv("data.csv")

# Define variables:
# Y = outcome vector
# W = treatment vector (binary: 0/1)
# X = matrix of effect modifiers (variables you think drive heterogeneity)
#     In grf, ALL covariates go in X — there is no separate W argument.
#     grf handles confounding control internally via its honest AIPW scoring.
#     Include confounders AND effect modifiers in X.
Y <- df$outcome
W <- df$treatment
X <- as.matrix(df[, c("age", "income", "gender")])  # Adapt to your variables
```

## Step 1: LinearDML-equivalent first pass (interpretable coefficients)

```r
# Use best_linear_projection to get interpretable coefficients BEFORE
# running the full forest. This is faster and tells you which variables
# have a linear relationship with the treatment effect.
#
# First, fit a quick causal forest for the projection:
cf_quick <- causal_forest(X, Y, W, num.trees = 500, seed = 42)

# Project forest CATEs onto a linear model of your effect modifiers
# This gives "for each unit increase in age, the treatment effect changes by beta"
blp <- best_linear_projection(cf_quick, X)
print(blp)
# Look at coefficients and p-values.
# Significant coefficients = evidence of linear heterogeneity along that variable.
```

## Step 2: Causal Forest (nonparametric CATE estimation)

### For RCT data (known propensity):
```r
# If treatment was randomly assigned, supply the known propensity.
# This avoids unnecessary estimation noise.
cf <- causal_forest(
  X, Y, W,
  W.hat = rep(0.5, length(Y)),  # Known propensity from randomization
  num.trees = 2000,
  honesty = TRUE,               # NEVER set to FALSE — required for valid CIs
  seed = 42
)
```

### For observational data:
```r
# grf estimates the propensity score and outcome model internally.
# It uses Robinson/DML-style orthogonalization automatically.
cf <- causal_forest(
  X, Y, W,
  num.trees = 2000,
  honesty = TRUE,    # NEVER set to FALSE — required for valid CIs
  seed = 42
)
```

### Extract individual-level CATEs:
```r
tau_hat <- predict(cf)$predictions
summary(tau_hat)
hist(tau_hat, breaks = 50, main = "Distribution of Estimated CATEs",
     xlab = "Conditional Average Treatment Effect")
abline(v = mean(tau_hat), col = "red", lwd = 2)
```

### Variable importance:
```r
# Which covariates drive heterogeneity?
# Higher values = more important for splitting
varimp <- variable_importance(cf)
names(varimp) <- colnames(X)
barplot(sort(varimp, decreasing = TRUE),
        main = "Variable Importance for Treatment Effect Heterogeneity",
        ylab = "Importance", las = 2)
```

## Step 3: Validation — Calibration, BLP, GATES, CLAN, TOC

### Step 3a: Calibration test (fast screen)
```r
# Does the forest capture real signal?
# "mean.forest.prediction" significant = forest predicts real variation
# "differential.forest.prediction" significant = heterogeneity detected
cal <- test_calibration(cf)
print(cal)
# If neither is significant, the forest is likely fitting noise.
```

### Step 3b: BLP (Best Linear Predictor)
```r
# Formal test: does the CATE model explain real treatment effect variation?
# beta on tau_hat: should be significantly different from 0.
# Ideal value is 1 (CATE predictions linearly track true effects).
blp_test <- best_linear_projection(cf, X)
print(blp_test)
# NOTE: Non-significant beta does NOT mean "no heterogeneity."
# It means "we cannot detect heterogeneity at this sample size."
# The ATE may still be significant — check average_treatment_effect(cf).
```

### Step 3c: GATES (Sorted Group Average Treatment Effects)
```r
# Sort units by predicted CATE into quintiles.
# Estimate the actual ATE within each group.
# If GATES increase monotonically: model is ranking correctly.
# If GATES are flat: no detectable heterogeneity.
tau_hat <- predict(cf)$predictions
quintile <- cut(tau_hat, quantile(tau_hat, probs = 0:5/5),
                include.lowest = TRUE, labels = paste0("Q", 1:5))

gates <- data.frame(quintile = levels(quintile), gate = NA, se = NA)
for (i in 1:5) {
  idx <- quintile == paste0("Q", i)
  ate_q <- average_treatment_effect(cf, subset = idx)
  gates$gate[i] <- ate_q[1]
  gates$se[i] <- ate_q[2]
}
gates$ci_lower <- gates$gate - 1.96 * gates$se
gates$ci_upper <- gates$gate + 1.96 * gates$se
print(gates)

# Plot GATES
plot(1:5, gates$gate, ylim = range(c(gates$ci_lower, gates$ci_upper)),
     pch = 19, xlab = "CATE Quintile (lowest to highest)",
     ylab = "Group Average Treatment Effect", main = "GATES")
arrows(1:5, gates$ci_lower, 1:5, gates$ci_upper,
       angle = 90, code = 3, length = 0.1)
abline(h = average_treatment_effect(cf)[1], col = "red", lty = 2)
legend("topleft", "ATE", col = "red", lty = 2)
```

### Step 3d: CLAN (Classification Analysis)
```r
# What characterizes high vs low CATE groups?
# Compare average covariate values between top and bottom quintiles.
df$quintile <- quintile
high <- df[df$quintile == "Q5", ]
low  <- df[df$quintile == "Q1", ]

clan <- data.frame(
  variable = colnames(X),
  mean_high = colMeans(high[, colnames(X)]),
  mean_low  = colMeans(low[, colnames(X)]),
  difference = colMeans(high[, colnames(X)]) - colMeans(low[, colnames(X)])
)
print(clan)
```

### Step 3e: TOC / RATE (Targeting Operator Characteristic)
```r
# If I treat only the top k% by predicted CATE, how much do I gain?
# This measures the practical value of targeting.
rate <- rank_average_treatment_effect(cf)
print(rate)
plot(rate, main = "TOC: Targeting Operator Characteristic")
# AUTOC > 0 with confidence means targeting adds value over treating everyone.
```

### Step 3f: Stability check
```r
# Re-run with a different seed. If top-3 important variables change,
# the heterogeneity signal is unstable.
cf_check <- causal_forest(X, Y, W, num.trees = 2000,
                          honesty = TRUE, seed = 999)
varimp_check <- variable_importance(cf_check)
names(varimp_check) <- colnames(X)
cat("Seed 42 top-3:", names(sort(varimp, decreasing = TRUE))[1:3], "\n")
cat("Seed 999 top-3:", names(sort(varimp_check, decreasing = TRUE))[1:3], "\n")
# If different: SERIOUS — heterogeneity signal is not robust.
```

## Step 4: Interpretation + Policy

### Step 4a: Threshold rule (default)
```r
# Default policy: treat if estimated CATE > cost of treatment
cost <- 0  # User specifies cost; default 0 if free/unknown
treat_rule <- tau_hat > cost

cat("Threshold rule (CATE >", cost, "):\n")
cat("  Fraction treated:", mean(treat_rule), "\n")
cat("  Expected welfare gain (treated):",
    sum(tau_hat[treat_rule] - cost), "\n")
cat("  Treat-all welfare:", sum(tau_hat) - cost * length(tau_hat), "\n")
cat("  Treat-none welfare: 0\n")
```

### Step 4b: Policy tree (opt-in)
```r
# Interpretable targeting rule — a shallow decision tree.
# Uses doubly-robust scores from the causal forest.
dr_scores <- get_scores(cf)  # Doubly-robust scores

# Cost-adjusted rewards (subtract cost from the treatment arm score)
# dr_scores has columns for control (col 1) and treatment (col 2)
dr_scores_adjusted <- dr_scores
dr_scores_adjusted[, 2] <- dr_scores[, 2] - cost

pt <- policy_tree(X, dr_scores_adjusted, depth = 2)
print(pt)
plot(pt)

# Policy assignment
policy <- predict(pt, X)
cat("Policy tree treats:", mean(policy == 2), "of units\n")

# Compare to threshold rule
cat("Threshold rule treats:", mean(treat_rule), "of units\n")
```

### Step 4c: Fairness check
```r
# Check if policy correlates with protected attributes
# even if they were not used in the tree.
if ("gender" %in% colnames(df)) {
  cat("\nFairness check — treatment by gender:\n")
  print(table(policy, df$gender))
  print(chisq.test(policy, df$gender))
}
# Repeat for other protected attributes (race, age group, etc.)
```
