# Difference-in-Differences — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("fixest", "did", "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(fixest)
library(did)
library(modelsummary)
```

## Data Preparation
```r
# Panel data should have: unit (id), time (period), treatment indicator, outcome
# df: your data frame with columns unit, time, treated, outcome

# Create post-treatment indicator (classic 2x2 design)
# treatment_time: the period when treatment begins
df <- df %>%
  mutate(
    post = as.integer(time >= treatment_time),
    treat_post = treated * post
  )

# For staggered designs, create group variable (first treatment period per unit)
# Units never treated should have group = 0
df <- df %>%
  group_by(unit) %>%
  mutate(
    first_treat = if_else(any(treated == 1), min(time[treated == 1]), 0L)
  ) %>%
  ungroup()

# Event-time variable (periods relative to treatment onset)
df <- df %>%
  mutate(
    time_to_treat = if_else(first_treat > 0, time - first_treat, NA_integer_)
  )
```

## Estimation — Classic 2x2 DiD
```r
# Two-way fixed effects (TWFE) estimator
# Cluster standard errors at the unit level
mod_twfe <- feols(
  outcome ~ treat_post | unit + time,
  data    = df,
  cluster = ~unit
)

summary(mod_twfe)
```

## Estimation — Staggered DiD (Callaway & Sant'Anna)
```r
# att_gt() estimates group-time average treatment effects
# Avoids negative-weight problems of TWFE with staggered adoption
cs_att <- att_gt(
  yname  = "outcome",       # outcome variable
  tname  = "time",          # time variable
  idname = "unit",          # unit identifier
  gname  = "first_treat",   # first treatment period (0 = never treated)
  data   = df,
  control_group = "nevertreated",
  base_period   = "universal"
)

# Aggregate to overall ATT
cs_agg <- aggte(cs_att, type = "simple")
summary(cs_agg)

# Dynamic / event-study aggregation
cs_es <- aggte(cs_att, type = "dynamic")
summary(cs_es)
```

## Estimation — Event Study (fixest)
```r
# Event-study specification using fixest interaction operator i()
# Reference period is -1 (one period before treatment)
mod_es <- feols(
  outcome ~ i(time_to_treat, treated, ref = -1) | unit + time,
  data    = df,
  cluster = ~unit
)

summary(mod_es)
```

## Diagnostics
```r
# --- Pre-trends test (joint F-test on pre-treatment event-study coefficients) ---
# Extract pre-treatment coefficients from the event-study model
pre_coefs <- coef(mod_es)[grepl("time_to_treat::-[2-9]|time_to_treat::-[1-9][0-9]", names(coef(mod_es)))]
cat("Pre-treatment coefficients:\n")
print(pre_coefs)

# Joint test: were treated and control groups already diverging before treatment?
wald(mod_es, "time_to_treat::-")

# --- Parallel trends visualization ---
df %>%
  group_by(time, treated) %>%
  summarise(mean_outcome = mean(outcome, na.rm = TRUE), .groups = "drop") %>%
  ggplot(aes(x = time, y = mean_outcome, color = factor(treated))) +
  geom_line(linewidth = 1) +
  geom_vline(xintercept = treatment_time - 0.5, linetype = "dashed", color = "grey40") +
  labs(
    title = "Parallel Trends Check",
    x = "Time", y = "Mean Outcome", color = "Treated"
  ) +
  theme_minimal()
```

## Results Table
```r
# Side-by-side table: TWFE and event-study models
modelsummary(
  list("TWFE" = mod_twfe, "Event Study" = mod_es),
  stars    = c("*" = 0.10, "**" = 0.05, "***" = 0.01),
  gof_map  = c("nobs", "r.squared", "adj.r.squared"),
  coef_omit = "unit|time",
  title    = "Difference-in-Differences Estimates"
)
```

## Visualization
```r
# Visual check — pre-treatment coefficients should hover around zero
iplot(
  mod_es,
  main = "Event Study — DiD",
  xlab = "Periods Relative to Treatment",
  ylab = "Estimated Effect"
)

# --- Callaway & Sant'Anna event-study plot ---
ggdid(cs_es, title = "Event Study — Callaway & Sant'Anna")
```
