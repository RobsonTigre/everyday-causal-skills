# Experiments (RCT) — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("pwr", "fixest", "cobalt", "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(pwr)
library(fixest)
library(cobalt)
library(modelsummary)
```

## Data Preparation
```r
# df: cross-sectional data from a randomized experiment
# treatment:   binary treatment indicator (0/1)
# outcome:     dependent variable (Y)
# covariates:  pre-treatment covariates (X1, X2, X3)
# cluster_var: cluster identifier (for cluster-randomized designs)

# Check treatment assignment
df %>%
  count(treatment) %>%
  mutate(pct = n / sum(n))

# Summary statistics by treatment arm
df %>%
  group_by(treatment) %>%
  summarise(
    n         = n(),
    mean_y    = mean(outcome, na.rm = TRUE),
    sd_y      = sd(outcome, na.rm = TRUE),
    across(c(X1, X2, X3), mean, .names = "mean_{.col}")
  )
```

## Power Analysis (Pre-Experiment)
```r
# --- Two-sample t-test power calculation ---
# mde: minimum detectable effect size (in original units)
# sd_outcome: expected standard deviation of the outcome
mde <- 0.5
sd_outcome <- 1.0

# Required sample size per arm
power_result <- pwr.t.test(
  d         = mde / sd_outcome,  # Cohen's d
  sig.level = 0.05,
  power     = 0.80,
  type      = "two.sample",
  alternative = "two.sided"
)

cat("Required n per arm:", ceiling(power_result$n), "\n")
cat("Total sample size:", 2 * ceiling(power_result$n), "\n")

# --- Power curve ---
effect_sizes <- seq(0.1, 1.0, by = 0.05)
power_curve <- map_dfr(effect_sizes, function(d) {
  pw <- pwr.t.test(d = d, sig.level = 0.05, power = 0.80, type = "two.sample")
  tibble(effect_size = d, n_per_arm = ceiling(pw$n))
})

ggplot(power_curve, aes(x = effect_size, y = n_per_arm)) +
  geom_line(linewidth = 1, color = "steelblue") +
  geom_point(size = 2, color = "steelblue") +
  labs(
    title = "Power Analysis: Sample Size vs Effect Size",
    x = "Effect Size (Cohen's d)", y = "Required n per Arm"
  ) +
  theme_minimal()

# --- Cluster-randomized design power ---
# icc: intra-cluster correlation
# m: average cluster size
# icc <- 0.05; m <- 20
# deff <- 1 + (m - 1) * icc   # design effect
# n_cluster_arm <- ceiling(power_result$n * deff / m)
# cat("Clusters per arm:", n_cluster_arm, "\n")
```

## Estimation — Simple Difference in Means
```r
# --- t-test ---
t_result <- t.test(outcome ~ treatment, data = df, var.equal = FALSE)
print(t_result)

cat("Difference in means:", diff(t_result$estimate), "\n")
cat("95% CI:", t_result$conf.int, "\n")
```

## Estimation — Regression Adjustment
```r
# OLS without covariates
mod_simple <- feols(outcome ~ treatment, data = df)

# OLS with covariate adjustment (Lin 2013: interact covariates with treatment)
mod_adj <- feols(
  outcome ~ treatment * (X1 + X2 + X3),
  data = df
)

# With cluster-robust standard errors (for cluster-randomized designs)
mod_cluster <- feols(
  outcome ~ treatment + X1 + X2 + X3,
  data    = df,
  cluster = ~cluster_var
)

summary(mod_adj)
```

## Diagnostics
```r
# --- Balance table: verify randomization succeeded ---
bal.tab(
  treatment ~ X1 + X2 + X3,
  data       = df,
  stats      = c("m", "v"),     # standardized mean diff, variance ratio
  thresholds = c(m = 0.1)
)

# --- Love plot for covariate balance ---
love.plot(
  treatment ~ X1 + X2 + X3,
  data       = df,
  stats      = "mean.diffs",
  abs        = TRUE,
  thresholds = c(m = 0.1),
  title      = "Randomization Balance Check"
)

# --- Attrition check ---
# If there is an attrition indicator
# df %>%
#   group_by(treatment) %>%
#   summarise(
#     n_assigned  = n(),
#     n_observed  = sum(!is.na(outcome)),
#     attrition   = 1 - n_observed / n_assigned
#   )

# --- Propensity score model to check randomization ---
# A good randomization should produce AUC near 0.5
ps_check <- glm(treatment ~ X1 + X2 + X3, data = df, family = binomial)
ps_pred <- predict(ps_check, type = "response")

# Simple discrimination measure
cat("Propensity score SD:", sd(ps_pred), "\n")
cat("If SD is near 0, randomization is well-balanced.\n")
```

## Results Table
```r
modelsummary(
  list(
    "Difference in Means" = mod_simple,
    "Covariate-Adjusted"  = mod_adj,
    "Cluster-Robust"      = mod_cluster
  ),
  stars    = c("*" = 0.10, "**" = 0.05, "***" = 0.01),
  coef_map = c("treatment" = "Treatment Effect"),
  gof_map  = c("nobs", "r.squared", "adj.r.squared"),
  title    = "Experimental Treatment Effect Estimates"
)
```

## Visualization
```r
# --- Outcome distribution by treatment arm ---
ggplot(df, aes(x = outcome, fill = factor(treatment))) +
  geom_histogram(alpha = 0.5, position = "identity", bins = 40) +
  labs(
    title = "Outcome Distribution by Treatment Arm",
    x = "Outcome", fill = "Treatment"
  ) +
  theme_minimal()

# --- Treatment effect comparison (native modelsummary function) ---
modelplot(
  list(
    "Unadjusted"        = mod_simple,
    "Covariate-Adjusted" = mod_adj,
    "Cluster-Robust"     = mod_cluster
  ),
  coef_map = c("treatment" = "Treatment Effect"),
  title    = "Treatment Effect Estimates"
) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey50") +
  theme_minimal()
```
