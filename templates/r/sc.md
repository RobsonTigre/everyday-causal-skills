# Synthetic Control — R Template

## Prerequisites
```r
# Install (if needed)
install.packages(c("tidysynth", "Synth", "modelsummary", "tidyverse"))

# Load
library(tidyverse)
library(tidysynth)
library(modelsummary)
```

## Data Preparation
```r
# df: balanced panel data frame
# unit:      unit identifier (e.g., state name or ID)
# time:      time period variable
# outcome:   dependent variable (Y)
# treated_unit: name/ID of the treated unit
# treatment_time: period when treatment begins

# Verify panel is balanced
df %>%
  count(unit) %>%
  summarise(
    n_units   = n(),
    min_periods = min(n),
    max_periods = max(n)
  )

# Inspect pre-treatment outcome trends
df %>%
  mutate(is_treated = if_else(unit == treated_unit, "Treated", "Donor Pool")) %>%
  group_by(time, is_treated) %>%
  summarise(mean_outcome = mean(outcome, na.rm = TRUE), .groups = "drop") %>%
  ggplot(aes(x = time, y = mean_outcome, color = is_treated)) +
  geom_line(linewidth = 1) +
  geom_vline(xintercept = treatment_time, linetype = "dashed") +
  labs(title = "Pre-treatment Trends", x = "Time", y = "Outcome") +
  theme_minimal()
```

## Estimation — tidysynth Pipeline
```r
# Full tidysynth pipeline: build synthetic control step by step
sc_out <- df %>%
  synthetic_control(
    outcome   = outcome,        # outcome variable
    unit      = unit,           # unit identifier
    time      = time,           # time variable
    i_unit    = treated_unit,   # treated unit name
    i_time    = treatment_time, # treatment onset
    generate_placebos = TRUE    # needed for inference
  ) %>%
  # Add predictors: pre-treatment outcome averages
  generate_predictor(
    time_window = min(df$time):(treatment_time - 1),
    mean_outcome = mean(outcome, na.rm = TRUE)
  ) %>%
  # Add additional predictors (covariates)
  # generate_predictor(
  #   time_window = min(df$time):(treatment_time - 1),
  #   mean_covariate1 = mean(covariate1, na.rm = TRUE)
  # ) %>%
  # Specific lagged outcomes as predictors
  generate_predictor(
    time_window = treatment_time - 1,
    lag1_outcome = outcome
  ) %>%
  generate_predictor(
    time_window = treatment_time - 3,
    lag3_outcome = outcome
  ) %>%
  # Compute optimal donor weights

  generate_weights(
    optimization_window = min(df$time):(treatment_time - 1)
  ) %>%
  # Generate the synthetic control unit
  generate_control()

# Print the synthetic control object
sc_out
```

## Diagnostics
```r
# --- Pre-treatment fit: RMSPE ---
# Lower RMSPE = better pre-treatment fit
pre_rmspe <- sc_out %>%
  grab_signficance() %>%
  filter(unit_name == treated_unit) %>%
  pull(pre_mspe) %>%
  sqrt()

cat("Pre-treatment RMSPE:", round(pre_rmspe, 4), "\n")

# --- Donor unit weights ---
# Check which units contribute to the synthetic control
sc_out %>%
  grab_unit_weights() %>%
  arrange(desc(weight)) %>%
  filter(weight > 0.001)

# --- Predictor balance table ---
# Compare treated unit vs synthetic control on predictors
sc_out %>%
  grab_predictor_balance()

# --- Pre/post RMSPE ratio ---
# Large ratio = treatment effect unlikely due to chance
sc_out %>%
  grab_signficance() %>%
  select(unit_name, pre_mspe, post_mspe) %>%
  mutate(
    ratio = post_mspe / pre_mspe
  ) %>%
  arrange(desc(ratio))
```

## Placebo Tests
```r
# --- In-space placebo: apply SC to every donor unit ---
# Iteratively treats each donor as if it were the treated unit
sc_out %>%
  plot_placebos(prune = TRUE) +
  labs(
    title = "In-Space Placebo Test",
    x = "Time", y = "Gap (Treated - Synthetic)"
  )

# --- Significance: rank of treated unit's post/pre RMSPE ratio ---
sig_table <- sc_out %>%
  grab_signficance() %>%
  arrange(desc(fishers_exact_pvalue))

cat("Fisher's exact p-value:", sig_table %>%
      filter(unit_name == treated_unit) %>%
      pull(fishers_exact_pvalue), "\n")

print(sig_table)
```

## Results Table
```r
# Summary of synthetic control outcome
sc_summary <- sc_out %>%
  grab_synthetic_control() %>%
  mutate(gap = real_y - synth_y) %>%
  summarise(
    pre_treatment_gap  = mean(gap[time_unit < treatment_time]),
    post_treatment_gap = mean(gap[time_unit >= treatment_time]),
    pre_rmspe  = sqrt(mean(gap[time_unit < treatment_time]^2)),
    post_rmspe = sqrt(mean(gap[time_unit >= treatment_time]^2))
  )

knitr::kable(sc_summary, digits = 3, caption = "Synthetic Control Summary")
```

## Visualization
```r
# --- Treated vs Synthetic Control trajectory ---
sc_out %>%
  plot_trends() +
  labs(
    title = "Treated vs Synthetic Control",
    x = "Time", y = "Outcome"
  )

# --- Gaps plot (treatment effect over time) ---
sc_out %>%
  plot_differences() +
  labs(
    title = "Treatment Effect (Gap = Treated - Synthetic)",
    x = "Time", y = "Gap"
  )

# --- Unit weight distribution ---
sc_out %>%
  grab_unit_weights() %>%
  filter(weight > 0.001) %>%
  ggplot(aes(x = reorder(unit, weight), y = weight)) +
  geom_col(fill = "steelblue") +
  coord_flip() +
  labs(
    title = "Synthetic Control Donor Weights",
    x = "Donor Unit", y = "Weight"
  ) +
  theme_minimal()
```
