# Time Series Causal Inference — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("CausalImpact", "CausalArima", "zoo", "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(CausalImpact)
library(CausalArima)
library(zoo)
library(modelsummary)
```

## Data Preparation
```r
# df: time series data frame with columns: date, outcome, (optional) covariates
# intervention_date: date when the intervention/treatment occurred

intervention_date <- as.Date("2020-01-01")  # Set your intervention date

# Define pre and post periods
pre.period  <- as.Date(c("2018-01-01", "2019-12-31"))
post.period <- as.Date(c("2020-01-01", "2021-12-31"))

# Convert to zoo object (required by CausalImpact)
# Column 1 = outcome, remaining columns = covariates (controls)
ts_data <- df %>%
  arrange(date) %>%
  select(date, outcome, covariate1, covariate2) %>%
  read.zoo(index.column = "date")

# Quick visualization of the time series
autoplot(ts_data[, "outcome"]) +
  geom_vline(xintercept = as.numeric(intervention_date),
             linetype = "dashed", color = "red") +
  labs(title = "Outcome Time Series", x = "Date", y = "Outcome") +
  theme_minimal()
```

## Estimation — CausalImpact (Bayesian Structural Time Series)
```r
# CausalImpact builds a counterfactual using pre-period data and covariates
# The covariates should NOT be affected by the intervention
impact <- CausalImpact(
  data        = ts_data,
  pre.period  = pre.period,
  post.period = post.period,
  model.args  = list(
    niter       = 1000,   # MCMC iterations
    nseasons    = 52,     # seasonal component (e.g., 52 for weekly)
    season.duration = 1
  )
)

# Summary of causal effect
summary(impact)

# Detailed report with posterior inference
summary(impact, "report")
```

## Estimation — Without Covariates
```r
# If no control series available, CausalImpact uses a local level model
ts_outcome <- df %>%
  arrange(date) %>%
  select(date, outcome) %>%
  read.zoo(index.column = "date")

impact_nocov <- CausalImpact(
  data        = ts_outcome,
  pre.period  = pre.period,
  post.period = post.period
)

summary(impact_nocov)
```

## Estimation — CausalArima (Alternative)
```r
# CausalArima uses ARIMA models for the counterfactual
# Useful when you want explicit ARIMA order control

# Prepare numeric vectors
y_pre  <- df %>% filter(date < intervention_date) %>% pull(outcome)
y_post <- df %>% filter(date >= intervention_date) %>% pull(outcome)

# Fit CausalArima
ca_fit <- CausalArima(
  y       = c(y_pre, y_post),
  auto    = TRUE,                    # auto-select ARIMA order
  dates   = df$date,
  int.date = intervention_date,
  nboot   = 1000                     # bootstrap iterations for inference
)

# Summary
summary(ca_fit)
```

## Diagnostics
```r
# --- CausalImpact: residual diagnostics ---
# Plot shows: original, pointwise effect, cumulative effect
plot(impact)

# --- Extract posterior predictive checks ---
# Compare predicted vs actual in pre-period
impact_data <- as_tibble(impact$series) %>%
  mutate(date = index(ts_data))

# Pre-period fit check: if MAPE > 5%, the counterfactual projection is unreliable
pre_data <- impact_data %>%
  filter(date <= pre.period[2])

cat("Pre-period MAE:", mean(abs(pre_data$response - pre_data$point.pred), na.rm = TRUE), "\n")
cat("Pre-period MAPE:", mean(abs((pre_data$response - pre_data$point.pred) / pre_data$response), na.rm = TRUE) * 100, "%\n")

# --- CausalArima: model diagnostics ---
# Residual autocorrelation inflates confidence — CIs may be too narrow
if (exists("ca_fit")) {
  plot(ca_fit)
}

# --- Posterior tail-area probability ---
# p-value: probability of observing the effect under the null
cat("Posterior tail-area probability:", impact$summary$p[1], "\n")
cat("Probability of causal effect:", 1 - impact$summary$p[1], "\n")
```

## Results Table
```r
# Extract key results into a summary table
ci_summary <- tibble(
  Metric = c(
    "Average causal effect (pointwise)",
    "Cumulative causal effect",
    "Relative effect (%)",
    "Posterior tail-area p-value"
  ),
  Estimate = c(
    impact$summary$AbsEffect[1],
    impact$summary$AbsEffect[2],
    impact$summary$RelEffect[1] * 100,
    impact$summary$p[1]
  ),
  CI_Lower = c(
    impact$summary$AbsEffect.lower[1],
    impact$summary$AbsEffect.lower[2],
    impact$summary$RelEffect.lower[1] * 100,
    NA
  ),
  CI_Upper = c(
    impact$summary$AbsEffect.upper[1],
    impact$summary$AbsEffect.upper[2],
    impact$summary$RelEffect.upper[1] * 100,
    NA
  )
)

knitr::kable(ci_summary, digits = 3, caption = "Causal Impact Summary")
```

## Visualization
```r
# --- Full CausalImpact plot (3 panels) ---
plot(impact) +
  theme_minimal()
```
