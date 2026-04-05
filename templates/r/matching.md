# Matching & Inverse Probability Weighting — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("MatchIt", "cobalt", "marginaleffects", "fixest",
                   "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(MatchIt)
library(cobalt)
library(marginaleffects)
library(fixest)
library(modelsummary)
```

## Data Preparation
```r
# df: cross-sectional data frame
# treatment:  binary treatment indicator (0/1)
# outcome:    dependent variable (Y)
# X1, X2, X3: pre-treatment covariates for matching

# Check treatment distribution
df %>%
  count(treatment) %>%
  mutate(pct = n / sum(n))

# Inspect covariate distributions by treatment group
df %>%
  group_by(treatment) %>%
  summarise(across(c(X1, X2, X3), list(mean = mean, sd = sd), .names = "{.col}_{.fn}"))
```

## Estimation — Nearest-Neighbor Matching
```r
# Propensity-score nearest-neighbor matching (1:1, no replacement)
m_nn <- matchit(
  treatment ~ X1 + X2 + X3,
  data     = df,
  method   = "nearest",
  distance = "glm",        # logistic propensity score
  replace  = FALSE,
  ratio    = 1
)

summary(m_nn)

# Extract matched data
df_matched <- match.data(m_nn)

# Estimate treatment effect on matched sample (with matched weights)
mod_matched <- feols(
  outcome ~ treatment + X1 + X2 + X3,
  data    = df_matched,
  weights = ~weights
)

summary(mod_matched)
```

## Estimation — Inverse Probability Weighting (IPW)
```r
# Estimate propensity score
ps_model <- glm(treatment ~ X1 + X2 + X3, data = df, family = binomial)
df$pscore <- predict(ps_model, type = "response")

# Compute IPW weights (ATE weights)
df <- df %>%
  mutate(
    ipw = if_else(treatment == 1, 1 / pscore, 1 / (1 - pscore))
  )

# Trim extreme weights to reduce variance (optional)
q99 <- quantile(df$ipw, 0.99)
df <- df %>%
  mutate(ipw_trimmed = pmin(ipw, q99))

# IPW-weighted regression
mod_ipw <- feols(
  outcome ~ treatment,
  data    = df,
  weights = ~ipw_trimmed
)

summary(mod_ipw)
```

## Estimation — Doubly Robust (AIPW via marginaleffects)
```r
# Doubly robust: combine outcome model and propensity score
# Uses MatchIt's subclassification + regression adjustment
m_sub <- matchit(
  treatment ~ X1 + X2 + X3,
  data   = df,
  method = "subclass",
  subclass = 6
)

df_sub <- match.data(m_sub)

# Outcome model on matched/subclassified data
mod_dr <- lm(
  outcome ~ treatment * (X1 + X2 + X3),
  data    = df_sub,
  weights = weights
)

# Average treatment effect using marginaleffects
ate_dr <- avg_comparisons(
  mod_dr,
  variables  = "treatment",
  vcov       = "HC2",
  newdata    = df_sub,
  wts        = "weights"
)

print(ate_dr)
```

## Diagnostics
```r
# Balance check: did matching make treated and control groups comparable?
bal.tab(
  m_nn,
  stats   = c("m", "v", "ks"),   # mean diff, variance ratio, KS statistic
  un      = TRUE,                  # show unmatched balance too
  thresholds = c(m = 0.1)         # flag SMDs > 0.1
)

# --- Love plot (visual balance) ---
love.plot(
  m_nn,
  stats     = "mean.diffs",
  abs       = TRUE,
  thresholds = c(m = 0.1),
  var.order  = "unadjusted",
  title      = "Covariate Balance: Before vs After Matching"
)

# Overlap: are there treated units with no comparable controls? If so, we're extrapolating
ggplot(df, aes(x = pscore, fill = factor(treatment))) +
  geom_histogram(alpha = 0.5, position = "identity", bins = 50) +
  labs(
    title = "Propensity Score Overlap",
    x = "Propensity Score", fill = "Treatment"
  ) +
  theme_minimal()

# How much data did matching actually use? Low ESS means high variance
ess_treated <- sum(df$ipw_trimmed[df$treatment == 1])^2 /
               sum(df$ipw_trimmed[df$treatment == 1]^2)
ess_control <- sum(df$ipw_trimmed[df$treatment == 0])^2 /
               sum(df$ipw_trimmed[df$treatment == 0]^2)
cat("Effective sample size — Treated:", round(ess_treated),
    "Control:", round(ess_control), "\n")
```

## Results Table
```r
modelsummary(
  list(
    "Naive OLS"    = feols(outcome ~ treatment, data = df),
    "NN Matching"  = mod_matched,
    "IPW"          = mod_ipw
  ),
  stars    = c("*" = 0.10, "**" = 0.05, "***" = 0.01),
  coef_map = c("treatment" = "Treatment Effect"),
  gof_map  = c("nobs", "r.squared"),
  title    = "Treatment Effect Estimates: Matching & Weighting"
)
```

## Visualization
```r
# --- Compare estimates across methods ---
estimates <- tibble(
  Method   = c("Naive OLS", "NN Matching", "IPW", "Doubly Robust"),
  Estimate = c(
    coef(feols(outcome ~ treatment, data = df))["treatment"],
    coef(mod_matched)["treatment"],
    coef(mod_ipw)["treatment"],
    ate_dr$estimate
  ),
  CI_Lower = c(
    confint(feols(outcome ~ treatment, data = df))["treatment", 1],
    confint(mod_matched)["treatment", 1],
    confint(mod_ipw)["treatment", 1],
    ate_dr$conf.low
  ),
  CI_Upper = c(
    confint(feols(outcome ~ treatment, data = df))["treatment", 2],
    confint(mod_matched)["treatment", 2],
    confint(mod_ipw)["treatment", 2],
    ate_dr$conf.high
  )
)

ggplot(estimates, aes(x = Method, y = Estimate)) +
  geom_point(size = 3) +
  geom_errorbar(aes(ymin = CI_Lower, ymax = CI_Upper), width = 0.2) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "grey50") +
  coord_flip() +
  labs(
    title = "Treatment Effect Estimates Across Methods",
    x = NULL, y = "Estimated Treatment Effect"
  ) +
  theme_minimal()
```
