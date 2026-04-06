# Report Figure Templates (R)

Plotting code for `/causal-report` figure generation. Each block is standalone — adapt variable names from the analysis script, save to PNG.

---

## DiD: Parallel Trends

```r
# Parallel trends plot — shows pre-treatment outcome trends for treated vs control
# WHY: Visual evidence for the parallel trends assumption. If trends diverge
# before treatment, the DiD estimate may be biased.

library(ggplot2)

# Adapt these variable names from the analysis
# df: data frame with columns: time_var, outcome_var, group_var
# treatment_time: when treatment began

p <- ggplot(df, aes(x = time_var, y = outcome_var, color = factor(group_var))) +
  stat_summary(fun = mean, geom = "line", linewidth = 1) +
  stat_summary(fun = mean, geom = "point", size = 2) +
  geom_vline(xintercept = treatment_time, linetype = "dashed", color = "gray40") +
  annotate("text", x = treatment_time, y = Inf, label = "Treatment",
           vjust = 2, hjust = -0.1, color = "gray40") +
  labs(x = "Time", y = "Outcome", color = "Group",
       title = "Parallel Trends Check") +
  theme_minimal(base_size = 13) +
  scale_color_manual(values = c("0" = "#2166AC", "1" = "#B2182B"),
                     labels = c("Control", "Treated"))

ggsave("fig_01_parallel_trends.png", p, width = 8, height = 5, dpi = 300)
```

## DiD: Event Study

```r
# Event study plot — dynamic treatment effects relative to treatment onset
# WHY: Shows whether the effect appears at treatment time (not before),
# supporting causal interpretation.

library(fixest)
library(ggplot2)

# Adapt: model should be estimated with i(rel_time, ref = -1)
# es_model: fixest model with event-time coefficients

p <- iplot(es_model,
           main = "Event Study: Treatment Effect Over Time",
           xlab = "Periods Relative to Treatment",
           ylab = "Estimated Effect")

# For custom ggplot version:
coefs <- as.data.frame(coeftable(es_model))
coefs$rel_time <- as.numeric(gsub(".*::(.*)", "\\1", rownames(coefs)))
coefs <- coefs[grep("rel_time", rownames(coefs)), ]

p <- ggplot(coefs, aes(x = rel_time, y = Estimate)) +
  geom_point(size = 2) +
  geom_errorbar(aes(ymin = Estimate - 1.96 * `Std. Error`,
                     ymax = Estimate + 1.96 * `Std. Error`), width = 0.2) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray50") +
  geom_vline(xintercept = -0.5, linetype = "dashed", color = "red") +
  labs(x = "Periods Relative to Treatment", y = "Estimated Effect",
       title = "Event Study") +
  theme_minimal(base_size = 13)

ggsave("fig_02_event_study.png", p, width = 8, height = 5, dpi = 300)
```

## IV: First-Stage Scatter

```r
# First-stage scatter — relationship between instrument and endogenous variable
# WHY: Visual evidence of instrument relevance. A strong first stage
# means the instrument meaningfully shifts the treatment variable.

library(ggplot2)

# Adapt: df with instrument_var and treatment_var columns

p <- ggplot(df, aes(x = instrument_var, y = treatment_var)) +
  geom_point(alpha = 0.4, color = "#2166AC") +
  geom_smooth(method = "lm", color = "#B2182B", se = TRUE) +
  labs(x = "Instrument", y = "Treatment (Endogenous Variable)",
       title = "First Stage: Instrument vs Treatment") +
  theme_minimal(base_size = 13)

ggsave("fig_01_first_stage.png", p, width = 8, height = 5, dpi = 300)
```

## RDD: Running Variable Scatter

```r
# RDD scatter — outcome vs running variable with cutoff
# WHY: Shows the discontinuity at the cutoff. A visible jump suggests
# a treatment effect at the threshold.

library(ggplot2)

# Adapt: df with running_var, outcome_var; cutoff value

p <- ggplot(df, aes(x = running_var, y = outcome_var)) +
  geom_point(alpha = 0.3, color = "gray50") +
  geom_smooth(data = subset(df, running_var < cutoff),
              method = "loess", color = "#2166AC", se = TRUE) +
  geom_smooth(data = subset(df, running_var >= cutoff),
              method = "loess", color = "#B2182B", se = TRUE) +
  geom_vline(xintercept = cutoff, linetype = "dashed", linewidth = 0.8) +
  annotate("text", x = cutoff, y = Inf, label = "Cutoff",
           vjust = 2, hjust = -0.1) +
  labs(x = "Running Variable", y = "Outcome",
       title = "Regression Discontinuity") +
  theme_minimal(base_size = 13)

ggsave("fig_01_rdd_scatter.png", p, width = 8, height = 5, dpi = 300)
```

## Synthetic Control: Treated vs Synthetic

```r
# Treated vs synthetic control time series
# WHY: Shows how the treated unit diverges from its counterfactual
# after intervention. The gap IS the estimated treatment effect.

library(ggplot2)

# Adapt: df_plot with columns: time_var, treated_outcome, synthetic_outcome
# intervention_time: when treatment began

p <- ggplot(df_plot, aes(x = time_var)) +
  geom_line(aes(y = treated_outcome, color = "Treated"), linewidth = 1) +
  geom_line(aes(y = synthetic_outcome, color = "Synthetic Control"),
            linewidth = 1, linetype = "dashed") +
  geom_vline(xintercept = intervention_time, linetype = "dashed", color = "gray40") +
  annotate("text", x = intervention_time, y = Inf, label = "Intervention",
           vjust = 2, hjust = -0.1, color = "gray40") +
  labs(x = "Time", y = "Outcome", color = "",
       title = "Treated Unit vs Synthetic Control") +
  scale_color_manual(values = c("Treated" = "#B2182B", "Synthetic Control" = "#2166AC")) +
  theme_minimal(base_size = 13)

ggsave("fig_01_sc_time_series.png", p, width = 8, height = 5, dpi = 300)
```

## Matching: Love Plot (Balance)

```r
# Love plot — standardized mean differences before and after matching
# WHY: Shows whether matching successfully reduced covariate imbalance.
# Good balance (SMD < 0.1) supports the selection-on-observables assumption.

library(ggplot2)

# Adapt: balance_df with columns: variable, smd_before, smd_after

balance_long <- tidyr::pivot_longer(balance_df, cols = c(smd_before, smd_after),
                                     names_to = "stage", values_to = "smd")
balance_long$stage <- ifelse(balance_long$stage == "smd_before", "Before", "After")

p <- ggplot(balance_long, aes(x = abs(smd), y = reorder(variable, abs(smd)), color = stage)) +
  geom_point(size = 3) +
  geom_vline(xintercept = 0.1, linetype = "dashed", color = "gray50") +
  annotate("text", x = 0.1, y = Inf, label = "SMD = 0.1 threshold",
           vjust = 2, hjust = -0.1, color = "gray50", size = 3) +
  labs(x = "|Standardized Mean Difference|", y = "", color = "",
       title = "Covariate Balance: Before vs After Matching") +
  scale_color_manual(values = c("Before" = "#B2182B", "After" = "#2166AC")) +
  theme_minimal(base_size = 13)

ggsave("fig_01_love_plot.png", p, width = 8, height = 6, dpi = 300)
```

## Experiments: Effect Plot with CIs

```r
# Effect plot — treatment effect with confidence interval
# WHY: Clear visual of the estimated effect and its uncertainty.
# Helps stakeholders see both the magnitude and precision of the result.

library(ggplot2)

# Adapt: effect_df with columns: term, estimate, ci_lower, ci_upper

p <- ggplot(effect_df, aes(x = term, y = estimate)) +
  geom_point(size = 3, color = "#B2182B") +
  geom_errorbar(aes(ymin = ci_lower, ymax = ci_upper), width = 0.2, color = "#B2182B") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray50") +
  labs(x = "", y = "Estimated Effect",
       title = "Treatment Effect Estimate") +
  coord_flip() +
  theme_minimal(base_size = 13)

ggsave("fig_01_effect_plot.png", p, width = 8, height = 4, dpi = 300)
```

## Time Series: Pre/Post with Intervention Line

```r
# Interrupted time series — outcome over time with intervention marker
# WHY: Shows the pre-treatment trend, the intervention moment, and
# the post-treatment trajectory. Visual comparison to the counterfactual.

library(ggplot2)

# Adapt: df with time_var, outcome_var; intervention_time

p <- ggplot(df, aes(x = time_var, y = outcome_var)) +
  geom_line(color = "#2166AC", linewidth = 1) +
  geom_vline(xintercept = intervention_time, linetype = "dashed",
             color = "#B2182B", linewidth = 0.8) +
  annotate("text", x = intervention_time, y = Inf, label = "Intervention",
           vjust = 2, hjust = -0.1, color = "#B2182B") +
  labs(x = "Time", y = "Outcome",
       title = "Interrupted Time Series") +
  theme_minimal(base_size = 13)

ggsave("fig_01_its_timeseries.png", p, width = 8, height = 5, dpi = 300)
```

## HTE: CATE Distribution

```r
# CATE distribution — histogram of individual treatment effects
# WHY: Shows treatment effect heterogeneity. A wide distribution means
# the effect varies substantially across units — personalization may be valuable.

library(ggplot2)

# Adapt: cate_values is a numeric vector of estimated CATEs

p <- ggplot(data.frame(cate = cate_values), aes(x = cate)) +
  geom_histogram(fill = "#2166AC", color = "white", bins = 40, alpha = 0.8) +
  geom_vline(xintercept = mean(cate_values), linetype = "dashed",
             color = "#B2182B", linewidth = 0.8) +
  annotate("text", x = mean(cate_values), y = Inf,
           label = paste0("ATE = ", round(mean(cate_values), 3)),
           vjust = 2, hjust = -0.1, color = "#B2182B") +
  labs(x = "Conditional Average Treatment Effect (CATE)", y = "Count",
       title = "Distribution of Heterogeneous Treatment Effects") +
  theme_minimal(base_size = 13)

ggsave("fig_01_cate_distribution.png", p, width = 8, height = 5, dpi = 300)
```
