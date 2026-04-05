# Instrumental Variables — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("fixest", "AER", "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(fixest)
library(AER)
library(modelsummary)
```

## Data Preparation
```r
# df: your data frame
# outcome:     dependent variable (Y)
# endogenous:  endogenous treatment/regressor (D)
# instrument:  excluded instrument(s) (Z)
# covariates:  exogenous controls (X1, X2, ...)

# Check the instrument has variation
df %>%
  summarise(
    mean_instrument  = mean(instrument, na.rm = TRUE),
    sd_instrument    = sd(instrument, na.rm = TRUE),
    mean_endogenous  = mean(endogenous, na.rm = TRUE),
    cor_z_d          = cor(instrument, endogenous, use = "complete.obs")
  )

# Verify no missing values in key variables
df <- df %>%
  drop_na(outcome, endogenous, instrument)
```

## Estimation — fixest (preferred for panel data)
```r
# 2SLS with fixest: pipe syntax endogenous ~ instrument
# Without fixed effects
mod_iv_fixest <- feols(
  outcome ~ 1 | endogenous ~ instrument,
  data = df
)

# With covariates and fixed effects
mod_iv_fe <- feols(
  outcome ~ covariates | fe_var | endogenous ~ instrument,
  data    = df,
  cluster = ~unit
)

summary(mod_iv_fixest, stage = 1:2)  # Show both stages
```

## Estimation — AER::ivreg (classic, cross-sectional)
```r
# ivreg formula: outcome ~ endogenous + covariates | instrument + covariates
# Exogenous regressors appear on both sides of |
mod_iv_aer <- ivreg(
  outcome ~ endogenous + X1 + X2 | instrument + X1 + X2,
  data = df
)

summary(mod_iv_aer)
```

## First Stage
```r
# Explicit first-stage regression
mod_first <- feols(
  endogenous ~ instrument,
  data = df
)

summary(mod_first)

# F < 10 = weak instrument — estimates biased toward OLS, standard errors misleading
# First-stage F-statistic (rule of thumb: F > 10)
fitstat(mod_iv_fixest, "ivf")
```

## Diagnostics
```r
# --- Wu-Hausman endogeneity test ---
# Does OLS give a significantly different answer? If so, the endogeneity problem is real
# H0: endogenous variable is exogenous (OLS is consistent)
summary(mod_iv_aer, diagnostics = TRUE)

# --- Reduced-form estimate ---
# Reduced form: instrument → outcome directly. Should be significant if the causal chain works
mod_rf <- feols(outcome ~ instrument, data = df)
summary(mod_rf)

# --- Instrument relevance: partial R-squared ---
mod_ols_full    <- lm(endogenous ~ instrument + X1 + X2, data = df)
mod_ols_partial <- lm(endogenous ~ X1 + X2, data = df)
cat("Partial R-squared of instrument:",
    summary(mod_ols_full)$r.squared - summary(mod_ols_partial)$r.squared, "\n")

# --- Compare OLS vs IV ---
mod_ols <- feols(outcome ~ endogenous, data = df)
modelsummary(
  list("OLS" = mod_ols, "First Stage" = mod_first,
       "Reduced Form" = mod_rf, "2SLS" = mod_iv_fixest),
  stars   = c("*" = 0.10, "**" = 0.05, "***" = 0.01),
  title   = "OLS vs IV Comparison"
)
```

## Results Table
```r
modelsummary(
  list("2SLS (fixest)" = mod_iv_fixest, "2SLS (AER)" = mod_iv_aer),
  stars    = c("*" = 0.10, "**" = 0.05, "***" = 0.01),
  gof_map  = c("nobs", "r.squared", "adj.r.squared"),
  title    = "Instrumental Variables Estimates"
)
```

## Visualization
```r
# --- First-stage relationship ---
ggplot(df, aes(x = instrument, y = endogenous)) +
  geom_point(alpha = 0.3) +
  geom_smooth(method = "lm", color = "steelblue", se = TRUE) +
  labs(
    title = "First Stage: Instrument vs Endogenous Variable",
    x = "Instrument (Z)", y = "Endogenous Variable (D)"
  ) +
  theme_minimal()

# --- Compare OLS and IV coefficient estimates ---
modelplot(
  list("OLS" = mod_ols, "2SLS" = mod_iv_fixest),
  coef_map = c("endogenous" = "Treatment Effect")
) +
  labs(title = "OLS vs IV Estimates") +
  theme_minimal()
```
