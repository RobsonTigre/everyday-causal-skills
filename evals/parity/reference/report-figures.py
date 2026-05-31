# report-figures parity reference (Python).
# report-figures is a COMPILATION method (plots, not estimators). This probe
# computes the figure-DATA quantities the Python template derives before
# drawing, using the SAME operations the template's plotting blocks use:
#   - Parallel-Trends: per-group mean outcome by period (template groupby().mean())
#   - First-Stage scatter: OLS slope via np.polyfit(deg=1)  (template line 86)
#   - CATE distribution: ATE = np.mean(cate_values)         (template line 276)
# `df` is preloaded by the parity runner from fixtures/report_figures_parity.csv.
import numpy as np

TREATMENT_TIME = 4

# Parallel-trends group means at the treatment time (matches template groupby mean).
t0 = df[df["time_var"] == TREATMENT_TIME]
pt_treated = t0[t0["group_var"] == 1]["outcome_var"].mean()
pt_control = t0[t0["group_var"] == 0]["outcome_var"].mean()

# First-stage OLS slope: np.polyfit(instrument, treatment, 1)[0] — the exact
# call the Python first-stage-scatter block uses to draw its fit line.
fs_slope = np.polyfit(df["instrument_var"], df["treatment_var"], 1)[0]

# CATE-distribution ATE annotation: mean of the CATE vector.
cate_ate = np.mean(df["cate"].to_numpy())

print(f"PT_TREATED_T0:{pt_treated}")   # treated-group mean at treatment time
print(f"PT_CONTROL_T0:{pt_control}")   # control-group mean at treatment time
print(f"FS_SLOPE:{fs_slope}")          # first-stage OLS slope (instrument -> treatment)
print(f"CATE_ATE:{cate_ate}")          # ATE = mean(CATE) annotated on the histogram
