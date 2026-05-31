# Synthetic-control parity reference (Python).
# Canonical modern Python SC: scpi_pkg (Cattaneo, Feng, Palomba, Titiunik) — the
# package the Python template already uses. Classic simplex-constrained SCM
# (Abadie). `df` is preloaded by the parity runner from fixtures/sc_parity.csv.
#
# Prints, for cross-language comparison:
#   ATT     : mean post-treatment gap (actual treated - synthetic)
#   RMSPE_PRE : pre-treatment root mean squared prediction error (fit quality)
#   W_DONOR1  : synthetic-control weight on donor_1
import numpy as np
from scpi_pkg.scdata import scdata
from scpi_pkg.scest import scest

TREAT_TIME = 13
TREATED = "treated"

time_min = int(df["time"].min())
time_max = int(df["time"].max())
donors = sorted(u for u in df["unit"].unique() if u != TREATED)

sc_data = scdata(
    df=df, id_var="unit", time_var="time", outcome_var="outcome",
    period_pre=np.arange(time_min, TREAT_TIME),
    period_post=np.arange(TREAT_TIME, time_max + 1),
    unit_tr=TREATED, unit_co=donors, constant=False, cointegrated_data=False,
)

# Default w_constr is the canonical Abadie simplex (weights >= 0, sum to 1).
est = scest(sc_data, w_constr={"name": "simplex"})

# est.w preserves the unit_co order; align weights positionally to `donors`.
# (scpi relabels "donor_1" -> "donor 1" for display, so don't match on labels.)
weights = dict(zip(donors, est.w.iloc[:, 0].to_numpy()))
w_donor1 = float(weights["donor_1"])

# Reconstruct synthetic outcome over the full horizon from donor panel x weights.
donor_panel = df[df["unit"].isin(donors)].pivot(index="time", columns="unit",
                                                values="outcome")
weight_vec = np.array([float(weights[d]) for d in donor_panel.columns])
synthetic = donor_panel.to_numpy() @ weight_vec
actual = (df[df["unit"] == TREATED].sort_values("time")["outcome"].to_numpy())
times = donor_panel.index.to_numpy()

gap = actual - synthetic
pre_mask = times < TREAT_TIME
post_mask = times >= TREAT_TIME

att = float(gap[post_mask].mean())
rmspe_pre = float(np.sqrt(np.mean(gap[pre_mask] ** 2)))

print(f"ATT:{att}")
print(f"RMSPE_PRE:{rmspe_pre}")
print(f"W_DONOR1:{w_donor1}")
