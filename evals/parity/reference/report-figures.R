# report-figures parity reference (R).
# report-figures is a COMPILATION method (plots, not estimators). This probe
# computes the figure-DATA quantities the R template derives before drawing,
# using the SAME operations the template's plotting blocks use:
#   - Parallel-Trends: per-group mean outcome by period (template stat_summary fun=mean)
#   - First-Stage scatter: OLS slope via lm()  (template geom_smooth(method="lm"))
#   - CATE distribution: ATE = mean(cate_values)  (template mean(cate_values))
# `df` is preloaded by the parity runner from fixtures/report_figures_parity.csv.

TREATMENT_TIME <- 4

# Parallel-trends group means at the treatment time (matches stat_summary mean).
t0 <- df[df$time_var == TREATMENT_TIME, ]
pt_treated <- mean(t0$outcome_var[t0$group_var == 1])
pt_control <- mean(t0$outcome_var[t0$group_var == 0])

# First-stage OLS slope: lm(treatment ~ instrument) — geom_smooth(method="lm")
# draws exactly this fit line in the R first-stage-scatter block.
fs_slope <- coef(lm(treatment_var ~ instrument_var, data = df))[["instrument_var"]]

# CATE-distribution ATE annotation: mean of the CATE vector.
cate_ate <- mean(df$cate)

cat(sprintf("PT_TREATED_T0:%f\n", pt_treated))  # treated-group mean at treatment time
cat(sprintf("PT_CONTROL_T0:%f\n", pt_control))  # control-group mean at treatment time
cat(sprintf("FS_SLOPE:%f\n", fs_slope))         # first-stage OLS slope (instrument -> treatment)
cat(sprintf("CATE_ATE:%f\n", cate_ate))         # ATE = mean(CATE) annotated on the histogram
