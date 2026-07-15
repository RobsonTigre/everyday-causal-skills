# ROI translation pipeline -- Python reference.
# `df` is preloaded by the parity runner from the shared fixture (one row per
# period; scalar inputs are constant columns read from the first row).
# Mirrors templates/python/roi.md: validation -> normalization -> estimand
# scaling -> pipeline multiplier M -> ROI (point + plug-in bounds) -> breakeven
# from the SAME pipeline -> verdict code.
import numpy as np


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


s = df.iloc[0]  # scalar inputs
n_eligible = df["n_eligible"].to_numpy(dtype=float)
rollout = df["rollout"].to_numpy(dtype=float)
recurring = df["recurring"].to_numpy(dtype=float)
horizon = len(df)
t_idx = np.arange(horizon)

# Validation: bad inputs are blocking errors, not warnings.
require(s["ci_lo_raw"] <= s["effect_raw"] <= s["ci_hi_raw"],
        "interval must satisfy ci_lo <= effect <= ci_hi")
require(0 < s["persistence"] <= 1, "persistence must be in (0,1]")
require(0 <= s["survival"] <= 1, "survival must be in [0,1]")
require(s["discount"] >= 0, "discount rate must be >= 0")
require(bool(np.all((rollout >= 0) & (rollout <= 1))), "rollout must be in [0,1]")
require(0 <= s["transport"] <= 1, "transport must be in [0,1]")
require(0 <= s["net_incrementality"] <= 1, "net incrementality must be in [0,1]")
require(0 <= s["scaling_factor"] <= 1, "scaling factor must be in [0,1]")
require(s["margin"] >= 0, "margin must be >= 0")

# Normalization: reduce to incremental profit per unit per period.
delta_profit0 = s["effect_raw"] * s["margin"]
ci_lo_n = s["ci_lo_raw"] * s["margin"]
ci_hi_n = s["ci_hi_raw"] * s["margin"]

# Pipeline multiplier M (estimand scaling enters exactly once).
unit_weight = s["persistence"]**t_idx * s["survival"]**t_idx / (1 + s["discount"])**t_idx
effective_periods = float(unit_weight.sum())
M = float((n_eligible * s["scaling_factor"] * rollout * unit_weight).sum()) \
    * s["transport"] * s["net_incrementality"]

pv_per_unit = delta_profit0 * effective_periods
pv = delta_profit0 * M
pv_investment = s["one_time"] + float((recurring / (1 + s["discount"])**t_idx).sum())
require(pv_investment > 0, "investment must be positive: ROI and breakeven undefined at zero")
require(M > 0, "pipeline multiplier M is zero: no monetizable exposure")

net_profit = pv - pv_investment
roi = net_profit / pv_investment
roi_lo = (ci_lo_n * M - pv_investment) / pv_investment
roi_hi = (ci_hi_n * M - pv_investment) / pv_investment
breakeven_effect = pv_investment / M

# Verdict code from the hurdle-adjusted line and the margin buffer:
# 2 ship / 1 ship-staged / 0 size-the-bet / -1 kill.
line = (1 + s["hurdle"]) * pv_investment / M
if ci_hi_n < line:
    verdict_code = -1
elif ci_lo_n >= s["margin_buffer"] * line:
    verdict_code = 2
elif ci_lo_n >= line:
    verdict_code = 1
else:
    verdict_code = 0

print(f"EFFECTIVE_PERIODS:{effective_periods:.10f}")
print(f"PV_INCREMENTAL_PROFIT_PER_UNIT:{pv_per_unit:.10f}")
print(f"PV_INCREMENTAL_PROFIT:{pv:.10f}")
print(f"NET_PROFIT:{net_profit:.10f}")
print(f"ROI:{roi:.10f}")
print(f"ROI_LO:{roi_lo:.10f}")
print(f"ROI_HI:{roi_hi:.10f}")
print(f"BREAKEVEN_EFFECT:{breakeven_effect:.10f}")
print(f"VERDICT_CODE:{verdict_code}")
