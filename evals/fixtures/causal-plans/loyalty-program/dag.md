# Causal DAG — Loyalty Program → Repeat Purchases

**Treatment (D)**: Loyalty program enrollment (store-level, all-or-nothing).
**Outcome (Y)**: Repeat purchase rate.

## Variables

- **Store size** (pre-treatment, observed): Affects both which stores were
  selected for the pilot (larger stores were prioritized) and the baseline
  repeat-purchase rate. **Confounder.**
- **Store region** (pre-treatment, observed): Correlated with store size and
  with regional promotional calendars that also affect repeat purchases.
  **Confounder.**
- **Post-launch email campaign** (post-treatment): Sent only to enrolled
  customers, driven by enrollment itself. **Mediator, not a confounder — do
  not adjust for it if the total effect of the program is of interest.**

## Backdoor paths and adjustment set

`Program ← Store size → Repeat purchases` and `Program ← Store region →
Repeat purchases` are the only backdoor paths identified. Both are blocked by
adjusting for **{store size, store region}** — implemented as store fixed
effects in the DiD specification, which absorb any time-invariant store
characteristic including both of these.

## Testable implication

If store and month fixed effects fully account for the assignment mechanism,
pre-treatment trends in repeat purchases should not differ systematically
between treated and control stores. This is tested directly in
`/causal-did`'s parallel-trends check.

## Unobserved confounders

Store manager quality is not measured and could plausibly affect both
program adoption effort and repeat purchases independent of the program
itself. Flagged as a residual threat to validity, carried into the audit.
