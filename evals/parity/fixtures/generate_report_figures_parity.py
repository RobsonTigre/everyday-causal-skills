import numpy as np, pandas as pd
# Deterministic fixture for the report-figures R<->Python parity probe.
#
# report-figures is a COMPILATION method: the templates ship plotting code, not
# estimators. The cross-language numerical probe therefore targets the *figure-
# data computations* that BOTH language templates perform before drawing — the
# numbers that must agree or the two reports would show different figures:
#
#   PT_TREATED_T0 : treated-group mean outcome at the treatment time
#                   (Parallel-Trends figure: per-group means by period)
#   PT_CONTROL_T0 : control-group mean outcome at the treatment time
#   FS_SLOPE      : OLS slope of treatment on instrument
#                   (First-Stage scatter: R geom_smooth(lm) / Py np.polyfit deg 1)
#   CATE_ATE      : mean of the CATE vector (CATE-distribution figure: ATE annotation)
#
# All columns live in one tidy frame so a single fixture drives every probe.
rng = np.random.default_rng(20260531)

# --- DiD-style panel for the Parallel-Trends figure -------------------------
# 60 units (30 treated, 30 control) x 8 periods; treatment_time = 4.
n_units, n_periods, treatment_time = 60, 8, 4
units = np.arange(n_units)
group = (units >= 30).astype(int)          # 1 = treated, 0 = control
unit_fe = rng.normal(0.0, 1.0, size=n_units)
rows = []
for u in units:
    for t in range(n_periods):
        # common time trend; treated units get a post-treatment level shift
        post = int(t >= treatment_time)
        y = (2.0 + unit_fe[u] + 0.3 * t
             + 1.5 * group[u] * post
             + rng.normal(0.0, 0.5))
        rows.append((u, t, int(group[u]), y))
panel = pd.DataFrame(rows, columns=["unit", "time_var", "group_var", "outcome_var"])

# --- IV-style columns for the First-Stage scatter ---------------------------
# Strong first stage: treatment_var = a + b*instrument_var + noise (b ~ 0.8).
N = len(panel)
instrument = rng.normal(0.0, 1.0, size=N)
treatment = 0.5 + 0.8 * instrument + rng.normal(0.0, 0.4, size=N)
panel["instrument_var"] = np.round(instrument, 6)
panel["treatment_var"] = np.round(treatment, 6)

# --- CATE vector for the CATE-distribution figure ---------------------------
# Heterogeneous effects centered near 1.2; both templates annotate the mean.
cate = rng.normal(1.2, 0.6, size=N)
panel["cate"] = np.round(cate, 6)

panel["outcome_var"] = np.round(panel["outcome_var"], 6)
panel.to_csv("evals/parity/fixtures/report_figures_parity.csv", index=False)

# Echo the ground-truth probe targets for sanity.
t0 = panel[panel["time_var"] == treatment_time]
print("wrote", len(panel), "rows; treatment_time =", treatment_time)
print("PT_TREATED_T0", round(t0[t0.group_var == 1]["outcome_var"].mean(), 6))
print("PT_CONTROL_T0", round(t0[t0.group_var == 0]["outcome_var"].mean(), 6))
b = np.polyfit(panel["instrument_var"], panel["treatment_var"], 1)[0]
print("FS_SLOPE", round(b, 6))
print("CATE_ATE", round(panel["cate"].mean(), 6))
