# ROI Translation Framework

Runtime reference for `/causal-roi`. The skill loads this file at Stage 2
(normalization gate) and follows it exactly. Source of truth for the input
schema, normalization rules, cost taxonomy, estimand scaling, formulas,
decision matrix, parameter validation, interval labeling, the six pipeline
assumptions, and the results artifact schema.

Book reference: *Everyday Causal Inference*, "Translating causal estimates
into metrics for decision making" (everydaycausal.com/business-translations.html).

---

## 1. Canonical input schema

Every calculation starts from this named-input set. Each input records its
**provenance**: `sourced` (artifact / finance / product / rollout data),
`range` (labeled sensitivity range supplied or approved by the user), or
`unknown` (explicitly unknown — may force a withheld verdict).

| Input | Definition | Validation |
|---|---|---|
| `effect` | Point estimate of the causal effect, in the units the study identified | required |
| `ci_lo`, `ci_hi` | Interval bounds from the upstream analysis | `ci_lo ≤ effect ≤ ci_hi` |
| `ci_level` | Confidence level of that interval | required with the CI; asked if absent; **never assumed or relabeled 95%** |
| `estimand`, `method` | ATE / ITT / LATE / ATT / cumulative impact / CATE, and the method that produced it | drives the scaling table (§4) |
| `unit_denominator` | Per-what the effect is identified: invited customer, complier, treated unit, store, market, segment | required — unidentified denominator is FATAL |
| `base_period` | The period the effect is measured over (e.g., per 30 days) | must be consistent with `T` and recurring costs, or converted at the gate |
| `currency` | Symbol used verbatim; inferred from artifacts, confirmed once | mixed currencies are FATAL |
| `T` | Projection horizon, in base periods | integer ≥ 1 |
| `N_t` | **Eligible population before rollout and survival**, per period (constant allowed) | ≥ 0 |
| `N_active_t` | *Alternative, mutually exclusive path*: active/surviving population per period | if used, the script MUST set `s = 1` — survival is never applied twice |
| `rollout_t` | Deployment/adoption ramp per period | ∈ [0, 1]; for ITT, deployment ramp ONLY (take-up already embedded) |
| `transport_factor` | Representativeness of the study population for the rollout population | ∈ [0, 1] — zero is valid |
| `net_incrementality_factor` | Survives cannibalization / SUTVA at scale | ∈ [0, 1] — zero is valid (total cannibalization) |
| `lambda` (λ) | Effect persistence per period | ∈ (0, 1]. **v1 rejects λ > 1 (growing effects) with a clear message — never silently accepted or clamped** |
| `s` | User/unit survival per period | ∈ [0, 1] |
| `r` | Discount rate per period (from finance) | ≥ 0; 0 only if the user says so |
| `investment_one_time` | Fixed build cost | ≥ 0 |
| `recurring_t` | Recurring cost per period (maintenance, licences) | ≥ 0 |
| `hurdle` (h) | Minimum acceptable ROI, user-confirmed | a *confirmed* 0 = breakeven is valid; unset → verdict degrades to "clears breakeven" language |
| `margin_buffer` (k) | Margin-of-safety multiple separating "comfortable" from "thin" | process choice; recommended default k = 2; if unapproved, conservative default verdict is "Ship, staged" |

---

## 2. Normalization rules

Goal: reduce the causal result to **ΔProfit₀ — incremental profit per
identified unit per base period**. Recipes split by effect scale. Percentage
points and percentage changes are **distinct inputs** — the gate records which
one the estimate is.

| Upstream construct | Recipe to ΔProfit₀ |
|---|---|
| Revenue effect | × margin, or − variable costs (state which costs) |
| **Absolute probability-point effect** (Δp, e.g., +2.3 p.p. conversion) | `Δp × value_per_event` — **never** also multiplied by the baseline rate |
| **Relative probability / percent lift** (e.g., +10% conversion) | `baseline_rate × relative_lift × value_per_event` |
| Count lift (e.g., +0.4 orders/user) | `Δcount × value_per_event` |
| % lift on a continuous outcome | `baseline_level × relative_lift` |
| Log-linear outcome (log(Y), OLS) | `exp(β) − 1` = relative lift, then × `baseline_level`; note any mean-level retransformation (smearing) requirement when predicting levels |
| **Logit/probit coefficient** | **Never `exp(β) − 1`.** Require an average marginal effect (AME) or a predicted-probability difference at a stated baseline/covariate profile. A raw coefficient alone blocks the gate until the AME is supplied |
| Already-net outcome (incremental profit) | Skip conversion; record which costs are already inside |

**Cost-inclusion audit** (asked at the gate): Which variable costs are already
netted inside the causal outcome? Which remain to subtract here? Every cost
must appear in exactly one place (§3).

**Normalization gate record** — recorded as soon as its own inputs (construct,
effect scale, denominator, base period, unit economics, horizon convention) are
known, before the projection inputs; written to `roi.md` when file-writing is
available, otherwise shown in the reply: outcome construct, effect scale (points
vs percent), unit denominator, **base period kept as measured — not annualized
here**, conversions applied with sources, cost-inclusion audit result, the
**projection horizon T as a count of base periods** (from the user's stated
horizon convention, not a calendar mapping), and the resulting ΔProfit₀ (value +
units) from the recipe above. The gate's single normalization result may be shown without an
executed script; no projection, ROI, breakeven, or verdict proceeds until the
remaining inputs are sourced or each gap is explicitly labeled `unknown`.

---

## 3. Cost taxonomy

| Cost type | Where it enters | Never |
|---|---|---|
| One-time build (development, infrastructure) | `PV_INVESTMENT` (undiscounted, paid at t = 0) | inside ΔProfit₀ |
| Recurring (maintenance, licences, monitoring) | `PV_INVESTMENT` as `Σ recurring_t / (1+r)^t` | inside ΔProfit₀ |
| Treatment-delivery variable cost (serving, fees, support per unit) | Inside ΔProfit₀ — either already netted in the causal outcome or subtracted at normalization | in `PV_INVESTMENT` |

**Double-counting check**: each cost line appears in exactly one place. If the
upstream outcome is profit (variable costs already netted), do not subtract
them again; if it is revenue, subtract them at normalization, not from the
investment.

The **cost denominator** must be defined (per what, over what period) — an
undefined cost denominator is a FATAL input error.

---

## 4. Estimand-scaling table

Route by the estimand actually estimated. Rows 1–7 follow the book's Appendix
13.A; rows 8–9 cover the additional method skills in this plugin.

| Estimand (method) | Scales to | Rule | Violation severity |
|---|---|---|---|
| ATE (experiment) | Population supported by study + transport assumptions | Scale to target N only with a stated transport factor or user-confirmed representativeness | SERIOUS if transport unexamined |
| ITT (experiment w/ partial take-up) | Assigned/eligible units | NO second adoption adjustment — take-up is already embedded in the ITT; `rollout_t` reflects deployment ramp only | FATAL if adoption is applied twice |
| LATE (IV / non-compliance) | Compliers only | Multiply by expected complier share in production only when the policy moves the same margin and monotonicity holds; **product adoption ≠ complier share** | FATAL if scaled to non-compliers |
| Local effect (RDD) | Marginal units near the cutoff | Rollout verdict limited to the identified region; extrapolating beyond it requires a defensible transport model | FATAL for a rollout verdict outside the region without one |
| ATT over time (DiD / staggered) | Treated group/cohorts | Sum event-study effects only when they are per-period flows — not cumulative, not improperly weighted across cohorts | FATAL if cumulative coefficients are summed again |
| Cumulative impact (time series / CausalImpact) | Aggregate market/region | Detect whether the upstream result is already cumulative before summing periods | FATAL if a cumulative total is multiplied by periods |
| CATE (HTE) | Named segments | Aggregate with target-population segment weights, or report segment-specific ROI per named segment | FATAL if one segment's CATE is scaled to the full population |
| ATE/ATT (matching / IPW / doubly robust) | The population the estimand covers: ATT → treated-like units; ATE → the overlap/covered population | Route by the estimand actually estimated, not by analogy to experiments; scaling beyond the covered population needs a stated transport factor | FATAL if an ATT is scaled to units unlike the treated without a transport model; SERIOUS if transport unexamined |
| Per-period / cumulative gap (synthetic control) | The treated unit only | Distinguish per-period gaps from the cumulative gap before summing; monetization is limited to the treated unit — other units require a separate transport argument | FATAL if a cumulative gap is summed again or the result is scaled to other units without a transport model |

---

## 5. Formulas — the canonical calculation contract

One pipeline; every published number derives from it.

**Per-unit value:**

```
EFFECTIVE_PERIODS              = Σ_{t=0}^{T-1} λ^t · s^t / (1+r)^t
PV_INCREMENTAL_PROFIT_PER_UNIT = ΔProfit₀ × EFFECTIVE_PERIODS
```

Label `PV_INCREMENTAL_PROFIT_PER_UNIT` as ΔCLV **only when the unit is a
customer**.

**Population value (pipeline multiplier M):**

```
M = Σ_{t=0}^{T-1} [ N_t · rollout_t · λ^t · s^t / (1+r)^t ]
      × transport_factor × net_incrementality_factor

PV_INCREMENTAL_PROFIT = ΔProfit₀ × M
```

If the active-population path (`N_active_t`) was used, `s = 1` inside M.

**Investment, net profit, ROI:**

```
PV_INVESTMENT = investment_one_time + Σ_{t=0}^{T-1} recurring_t / (1+r)^t
NET_PROFIT    = PV_INCREMENTAL_PROFIT − PV_INVESTMENT
ROI           = NET_PROFIT / PV_INVESTMENT
```

**Breakeven — from the SAME pipeline** (never the simplified book formula when
any other pipeline term is active):

```
BREAKEVEN_EFFECT = PV_INVESTMENT / M          # ΔProfit₀* such that ROI = 0
Hurdle line (h)  = (1 + h) · PV_INVESTMENT / M
```

**Reduction to the book's formulas** (consistency check): with r = 0, s = 1,
rollout_t = 1, transport = net_incrementality = 1, constant N:
`EFFECTIVE_PERIODS = Σ λ^t`, `M = N · Σ λ^t`, and
`BREAKEVEN_EFFECT = Investment / (N × Σ λ^t)` — exactly the chapter's
`Investment / (Users × Effective periods)`.

**Uncertainty (plug-in):**

```
ROI_LO, ROI_HI = ROI evaluated at ci_lo, ci_hi
```

Valid only under the conditions in §8.

**Edge cases (script-enforced, never divide by zero):**

- `PV_INVESTMENT = 0` → ROI and breakeven are **undefined**: report
  `PV_INCREMENTAL_PROFIT` and say so (status `undefined` in the results
  artifact).
- `M = 0` (zero rollout, zero transport, or total cannibalization) → report
  "no monetizable exposure" and an undefined breakeven.
- Time bases inconsistent (effect period ≠ pipeline period ≠ recurring-cost
  period) and not convertible → FATAL input error.

---

## 6. Decision matrix

The decision line is the hurdle-adjusted breakeven
`ΔProfit₀ᴴ = (1 + h) · PV_INVESTMENT / M`. Compare the effect CI **at its
recorded confidence level** against the line.

| Where the effect CI sits vs the line | Margin of safety | Verdict |
|---|---|---|
| Lower bound ≥ k × line | Comfortable | **Ship** — full rollout |
| Lower bound between the line and k × line | Thin | **Ship, staged** — keep a holdout, monitor |
| CI straddles the line | Negative — downside real | **Size the bet** — limited rollout; extend the test only when new information could flip the verdict and the wait is affordable. Never plain "ship" |
| Upper bound below the line | None | **Kill** — no plausible scenario clears the hurdle |

**Deterministic rules:**

- Interval level comes from the upstream analysis; asked for if absent; never
  relabeled as 95%.
- A *confirmed* hurdle h (including a confirmed 0) activates the matrix
  verdict. If the user declines to set one, h = 0 is a mathematical breakeven
  comparison only: report "clears breakeven by X×" and withhold ship/kill
  language.
- Comfortable vs thin uses the user-approved margin buffer k (recommended
  default 2). No approved buffer → conservative default for any clearing
  margin is "Ship, staged".
- **Value of information is qualitative**: more data has no decision value
  when no value inside the interval flips the verdict; positive value when the
  interval straddles the line. Never report a numeric EVPI (that requires a
  probability distribution over the effect plus an explicit payoff function).
- Scenario-range parameters → verdict stated per scenario or withheld — never
  averaged across scenarios.

**Kill memo checklist** (when the verdict is Kill): the threshold used, the
bound that violates it, sample size, period covered — in language a
non-technical executive can quote without translation.

---

## 7. Parameter validation — no invented parameters

"Lead with a recommendation" applies ONLY to process choices: currency
inferred from artifacts, horizon convention, plug-in vs scenario method,
margin buffer k. For **financial and pipeline parameters** — λ, r, s,
rollout, transport, net incrementality, margins, baselines, costs — exactly
three routes:

1. **Sourced**: from artifacts, finance, product, or rollout data (record the
   source).
2. **Labeled range**: explicitly unknown; run a sensitivity range supplied or
   approved by the user, with each scenario named.
3. **Withheld verdict**: when the missing input is material to the decision,
   say so and withhold the ship/kill verdict.

The book's illustrative values (λ = 0.9, r = 0.01, the waterfall haircuts) are
**never** silently adopted. Upstream `audit.md` findings are **never**
converted into numeric haircuts — they appear as named risks and may motivate
scenario analysis.

Range checks (§1) are enforced in the generated script, with clear error
messages, before any pipeline arithmetic runs.

---

## 8. Interval-labeling rules

- **Plug-in CI** (`ROI_LO`/`ROI_HI` from `ci_lo`/`ci_hi`) is valid only when
  (a) the calculation is monotone in the effect and (b) all financial
  parameters are fixed point values. Label it with the recorded confidence
  level ("ROI interval at the effect's X% CI").
- **Several uncertain inputs** → labeled scenario ranges: named scenarios
  (e.g., "pessimistic: λ = 0.8, transport = 0.9"), one ROI per scenario.
  **Never** label a scenario grid as a CI, and never present the joint worst
  case as an interval bound.
- The output must state which method was used.
- Escalations beyond plug-in (delta method, Monte Carlo — book Appendix 13.C)
  are out of scope for this skill; name them as options when a finance team
  demands formal bands under joint uncertainty.

---

## 9. The six pipeline assumptions

Listed in every one-pager, each marked **checked / assumed / unknown** for the
analysis at hand:

1. **The upstream causal estimate is unbiased.** The pipeline cannot rescue a
   flawed estimate; bias carries straight through.
2. **The effect fades at a predictable rate.** λ (and its functional form) is
   itself a causal parameter — estimate it from holdout/event-study data when
   possible.
3. **The per-user effect holds up as you reach more users.** Diminishing
   returns, later adopters, saturation, market interference.
4. **The investment cost is known and stable.** Overruns move ROI directly.
5. **The measured lift is genuinely new — not borrowed** from another surface
   or period (cannibalization, pull-forward, SUTVA at scale).
6. **Metric definitions are stable** between the study window and the
   projection window (same MAU, same revenue construct, same denominators).

---

## 10. Results artifact schema

Two machine-readable outputs, written by the generated script:

**(a) `KEY: value` stdout lines** — the parity contract. One line per scalar:
`EFFECTIVE_PERIODS`, `PV_INCREMENTAL_PROFIT_PER_UNIT`,
`PV_INCREMENTAL_PROFIT`, `NET_PROFIT`, `ROI`, `ROI_LO`, `ROI_HI`,
`BREAKEVEN_EFFECT`, `VERDICT_CODE` (−1 kill / 0 size the bet / 1 ship
staged / 2 ship — full rollout).

**(b) `roi-results.csv`** — the inter-skill data contract consumed by
`/causal-report`. Long format, one row per metric × scenario:

| Column | Meaning |
|---|---|
| `metric` | e.g., `ROI`, `BREAKEVEN_EFFECT`, `PV_INCREMENTAL_PROFIT` |
| `scenario` | `base`, a named scenario, or empty |
| `value` | numeric; **empty when status is `withheld`/`undefined`** — never fabricated |
| `currency` | verbatim symbol (empty for unitless metrics) |
| `unit` | e.g., `per user per month`, `ratio` |
| `interval_level` | recorded CI level for `lo`/`hi` rows; empty otherwise |
| `status` | `point`, `lo`, `hi`, `scenario`, `withheld`, `undefined` |
| `notes` | why withheld/undefined; source labels |

Written with base R `write.csv` / pandas `to_csv` — no new dependencies.
