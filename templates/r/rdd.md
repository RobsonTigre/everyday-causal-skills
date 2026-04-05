# Regression Discontinuity Design — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("rdrobust", "rddensity", "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(rdrobust)
library(rddensity)
library(modelsummary)
```

## Data Preparation
```r
# df: your data frame
# outcome:     dependent variable (Y)
# running_var: running/forcing variable (X) that determines treatment assignment
# cutoff:      threshold value of the running variable

cutoff <- 0  # Set your cutoff value

# Center the running variable at the cutoff
df <- df %>%
  mutate(
    running_centered = running_var - cutoff,
    treated = as.integer(running_var >= cutoff)
  )

# Quick look at the data around the cutoff
df %>%
  summarise(
    n_below  = sum(running_var < cutoff),
    n_above  = sum(running_var >= cutoff),
    mean_y_below = mean(outcome[running_var < cutoff], na.rm = TRUE),
    mean_y_above = mean(outcome[running_var >= cutoff], na.rm = TRUE)
  )
```

## Estimation
```r
# Local polynomial RD estimation with robust bias-corrected inference
# rdrobust automatically selects MSE-optimal bandwidth
rd_est <- rdrobust(
  y = df$outcome,
  x = df$running_var,
  c = cutoff
)

summary(rd_est)

# Extract key results
cat("RD Estimate (robust):", rd_est$coef["Robust", ], "\n")
cat("Bandwidth (h):", rd_est$bws["h", ], "\n")
cat("Effective N (left/right):", rd_est$N_h, "\n")
```

## Bandwidth Sensitivity
```r
# Check sensitivity to bandwidth choice
bandwidths <- seq(0.5 * rd_est$bws["h", 1], 2 * rd_est$bws["h", 1], length.out = 10)

bw_results <- map_dfr(bandwidths, function(h) {
  fit <- rdrobust(y = df$outcome, x = df$running_var, c = cutoff, h = h)
  tibble(
    bandwidth = h,
    estimate  = fit$coef["Conventional", 1],
    ci_lower  = fit$ci["Robust", 1],
    ci_upper  = fit$ci["Robust", 2]
  )
})

# Plot bandwidth sensitivity
ggplot(bw_results, aes(x = bandwidth, y = estimate)) +
  geom_point() +
  geom_errorbar(aes(ymin = ci_lower, ymax = ci_upper), width = 0.02) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "grey50") +
  labs(
    title = "Bandwidth Sensitivity Analysis",
    x = "Bandwidth", y = "RD Estimate"
  ) +
  theme_minimal()
```

## Diagnostics
```r
# Manipulation check: can units game the running variable to land on the preferred side?
# --- Density test for manipulation (Cattaneo, Jansson, and Ma 2020) ---
# H0: density is continuous at the cutoff (no sorting)
density_test <- rddensity(X = df$running_var, c = cutoff)
summary(density_test)

# Density plot
rdplotdensity(density_test, df$running_var,
              title = "Density Test at Cutoff",
              xlabel = "Running Variable",
              ylabel = "Density")

# Covariates should be smooth through the cutoff — a jump means something else is changing too
# --- Covariate smoothness (placebo outcomes) ---
# Covariates should NOT jump at the cutoff
# Replace covariate1, covariate2 with actual covariate names
covariates_to_test <- c("covariate1", "covariate2")

cov_tests <- map_dfr(covariates_to_test, function(cov) {
  fit <- rdrobust(y = df[[cov]], x = df$running_var, c = cutoff)
  tibble(
    covariate = cov,
    estimate  = fit$coef["Robust", 1],
    pvalue    = fit$pv["Robust", 1]
  )
})

print(cov_tests)
```

## Results Table
```r
# Manual summary table (rdrobust objects are not lm-class)
rd_table <- tibble(
  Term          = "RD Estimate",
  Conventional  = rd_est$coef["Conventional", 1],
  `Bias-Corrected` = rd_est$coef["Bias-Corrected", 1],
  Robust        = rd_est$coef["Robust", 1],
  `SE (Robust)` = rd_est$se["Robust", 1],
  `p-value`     = rd_est$pv["Robust", 1],
  `CI Lower`    = rd_est$ci["Robust", 1],
  `CI Upper`    = rd_est$ci["Robust", 2],
  `BW (h)`      = rd_est$bws["h", 1],
  `N Left`      = rd_est$N_h[1],
  `N Right`     = rd_est$N_h[2]
)

knitr::kable(rd_table, digits = 3, caption = "RD Estimates")
```

## Visualization
```r
# --- RD plot with local polynomial fits ---
rdplot(
  y = df$outcome,
  x = df$running_var,
  c = cutoff,
  title  = "Regression Discontinuity Plot",
  x.label = "Running Variable",
  y.label = "Outcome"
)

# --- Custom ggplot RD visualization ---
ggplot(df, aes(x = running_var, y = outcome)) +
  geom_point(aes(color = factor(treated)), alpha = 0.3, size = 1) +
  geom_smooth(
    data = filter(df, running_var < cutoff),
    method = "loess", se = TRUE, color = "#E41A1C"
  ) +
  geom_smooth(
    data = filter(df, running_var >= cutoff),
    method = "loess", se = TRUE, color = "#377EB8"
  ) +
  geom_vline(xintercept = cutoff, linetype = "dashed", color = "grey40") +
  labs(
    title = "RD Design: Outcome vs Running Variable",
    x = "Running Variable", y = "Outcome", color = "Treated"
  ) +
  theme_minimal()
```
