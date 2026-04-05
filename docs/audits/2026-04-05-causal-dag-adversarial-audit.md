# Adversarial Audit: `/causal-dag` Skill

**Date**: 2026-04-05  
**Scope**: Core correctness, eval completeness, non-intrusiveness, literature alignment, infrastructure  
**Auditors**: 5 parallel agents  
**Checklist compliance**: 13/15 PASS, 2 FAIL  
**Literature alignment**: ~80-85% of key concepts from 4 reference sources  

**Resolution**: All CRITICAL (C2) and IMPORTANT (I2-I9) issues fixed 2026-04-05. MINOR items M2, M3, M12, M14 also fixed. I1 (planner integration) dropped by design — auditor backstop is sufficient. Remaining MINOR items M0a, M1, M5-M11, M13 and SUGGESTIONS S1-S6 deferred to next iteration.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| IMPORTANT | 9 unique |
| MINOR | 16 |
| SUGGESTION | 6 |

**Post-validation corrections** (2026-04-05):
- **C1 downgraded CRITICAL → MINOR**: Installed NetworkX 3.2.1 still has `d_separated()`; `is_d_separator()` does not exist yet. Code works today. Agent claim about removal in 3.5 unverified. Future-proofing note only.
- **C3 downgraded CRITICAL → MINOR**: 10 generic negative trigger cases (`no_trigger_*.yaml`) DO exist and apply to all skills. What's missing is DAG-specific negatives with adjacent keywords. Not a critical gap.

The core skill design is sound — 5-stage flow, severity contract, red flags, and self-correction loop are well-structured. The one CRITICAL bug (R template ggplot piping) will cause a runtime error. The IMPORTANT issues cluster around three themes: (1) planner/exercise integration gaps, (2) missing foundational concepts (CMC, d-separation rules), and (3) terminology/attribution errors.

---

## CRITICAL

### C2. R template pipes ggplot2 onto base R plot
- **File**: `templates/r/dag.md` lines 112-114
- **Agent**: correctness
- **Issue**: `plotLocalTestResults(tests) + labs(...)` fails — `plotLocalTestResults` returns a base R plot, not a ggplot2 object. Error: `non-numeric argument to binary operator`.
- **Fix**: Remove `+ labs(...)`. Use `title()` after the plot call, or add title via the function's own arguments.

---

## IMPORTANT

### I1. Planner never routes to `/causal-dag`
- **Files**: `skills/causal-planner/SKILL.md`, `references/decision-tree.md`
- **Agents**: intrusiveness, infrastructure
- **Issue**: The planner and decision tree have zero references to DAG. Users can only reach `/causal-dag` via direct invocation or post-hoc auditor nudge. The DAG skill is invisible in the structured interview workflow.
- **Fix**: Add DAG checkpoint after P2 (treatment/outcome defined) in planner: "If identification depends on variable selection, consider `/causal-dag` first." Add to decision tree terminal nodes. **(Checklist item #4 FAIL)**

### I2. No L1 planner-to-DAG eval case
- **File**: `evals/cases/layer1/` (missing)
- **Agent**: evals, infrastructure
- **Issue**: No L1 case tests whether the planner recommends DAG. **(Checklist item #9 FAIL)**
- **Fix**: Add L1 case: user has observational data, unclear confounders vs mediators, planner should recommend `/causal-dag` before estimation.

### I3. Exercise skill has no DAG integration
- **File**: `skills/causal-exercises/SKILL.md`
- **Agent**: infrastructure
- **Issue**: Exercise skill never mentions DAG despite 3 DAG DGPs existing in the library. No mechanism to generate DAG-specific exercises.
- **Fix**: Add "DAG reasoning" as method option in Step 1. Add DAG to integration section.

### I4. "Front-door path" terminology is non-standard
- **File**: `skills/causal-dag/SKILL.md` line 79
- **Agent**: correctness
- **Issue**: Skill says "Front-door (all arrows point away from D)" conflating directed/causal paths with the front-door criterion (Pearl). Will confuse users when the actual front-door criterion appears in Stage 3.
- **Fix**: Change to "**Causal/directed paths** (all arrows point from D toward Y) vs. **back-door paths** (at least one arrow points into D)."

### I5. D-separation rules never explicitly stated
- **File**: `skills/causal-dag/SKILL.md`, `references/assumptions/dag.md`
- **Agent**: literature
- **Issue**: The three fundamental rules (chain, fork, collider) plus descendant-of-collider extension are never taught. Users cannot verify path analysis without them.
- **Fix**: Add d-separation primer in Stage 3 or in assumptions file. State all three rules with conditioning effects.

### I6. Causal Markov Condition entirely missing
- **File**: `references/assumptions/dag.md`
- **Agent**: literature
- **Issue**: CMC is one of two foundational axioms (with faithfulness). CausalML Ch. 7 treats them as a pair. Faithfulness is covered; CMC is absent.
- **Fix**: Add CMC section: "Each variable is conditionally independent of its non-descendants given its parents."

### I7. 18-pattern taxonomy misattributed
- **File**: `skills/causal-dag/SKILL.md` line 83
- **Agent**: literature
- **Issue**: Attributed to "Chernozhukov et al. Ch. 11" but the taxonomy is from **Cinelli, Forney & Pearl (2020/2024)**.
- **Fix**: Change to "(Cinelli, Forney & Pearl 2024; discussed in Chernozhukov et al. Ch. 11)."

### I8. Wrong d-separation test in assumptions file
- **File**: `references/assumptions/dag.md` lines 117-130
- **Agent**: correctness
- **Issue**: Python code for Causal Sufficiency uses `nx.has_path()` (directed reachability) instead of d-separation. Two nodes with no directed path can still be d-connected via a common cause.
- **Fix**: Replace with `nx.is_d_separator()` checks for marginal independence.

### I9. Missing SUTVA and Consistency assumptions
- **File**: `references/assumptions/dag.md`
- **Agent**: correctness
- **Issue**: SUTVA (no interference, no hidden treatment versions) and Consistency (Y_observed = Y(d) when D=d) are required for DAG-based adjustment to produce valid causal estimates. Both omitted.
- **Fix**: Add sections for both. Note they are generally untestable but have diagnostic checks.

---

## MINOR (16 items)

| # | File | Issue | Fix |
|---|------|-------|-----|
| M0a | `templates/python/dag.md` 73, 106 | `nx.d_separated()` works on installed 3.2.1 but may be deprecated in future NetworkX. Agent claim of removal in 3.5 unverified. | Add version note; monitor NetworkX changelog |
| M0b | `evals/cases/layer0/` | 10 generic negatives exist but no DAG-specific negative triggers (prompts with DAG-adjacent keywords that should NOT trigger) | Add 1-2 DAG-specific negatives (e.g., "I already have my DAG, run matching") |
| M1 | `templates/python/dag.md` 119-132 | DoWhy code entirely commented out; SKILL.md promises it | Uncomment or update SKILL.md to match |
| M2 | `skills/causal-dag/SKILL.md` 89-91 | Instrument listed as "Neutral" AND "SERIOUS" (contradiction) | Add qualifier: "safe only if no unobserved confounding" |
| M3 | `references/assumptions/dag.md` 289 | Positivity rated FATAL; it's an estimation issue, not identification | Change to SERIOUS with note |
| M4 | `skills/causal-dag/SKILL.md` 83 | "18-pattern" label not findable in cited source | Use "control variable taxonomy" instead |
| M5 | `templates/python/dag.md` 54 | Comment says "valid adjustment set" but code implements backdoor criterion specifically | Update comment to say "backdoor criterion" |
| M6 | Evals L0 | Missing edge-case trigger prompts ("bad controls", "backdoor path") | Add 2+ positive trigger cases |
| M7 | `evals/cases/layer2/dag_clean_confounder.yaml` | Doesn't specify WHICH variables should be in adjustment set | Add `expected_adjustment_set` field |
| M8 | `evals/cases/layer2/` | Missing patterns: mediator overcontrol, bias amplification (both in skill red flags) | Add 2 new L2 cases |
| M9 | `evals/cases/layer3/` | Fragile `output_contains` strings won't match actual tool output | Fix to match real dagitty/DoWhy output |
| M10 | `evals/cases/layer3/` | Neither L3 case verifies computed adjustment set content | Add `expected_adjustment_set` and `must_not_include` |
| M11 | `evals/cases/layer5/` | Only 1 integration test (DAG→Matching); missing DAG→IV, Planner→DAG | Add at least `workflow_dag_to_iv.yaml` |
| M12 | Front-door criterion phrasing | "no unobserved confounder of M and Y" is more restrictive than formal condition | Change to "all backdoor paths from M to Y blocked by D" |
| M13 | `evals/data/` | Missing `dag_frontdoor.csv` despite DGP-DAG-03 existing | Add to `generate_l2_data.py` |
| M14 | `references/lessons.md` | Missing "post-treatment conditioning" lesson (general case beyond colliders) | Add 4th DAG lesson |

---

## SUGGESTION (6 items)

| # | Topic | Recommendation |
|---|-------|---------------|
| S1 | Method registry ordering | List networkx first (primary), dowhy second (optional) |
| S2 | Do-operator mention | Brief note in Stage 3 about P(Y|do(D)) as formal target |
| S3 | Causal discovery algorithms | Note in Stage 2 that PC/FCI/GES exist but are hypothesis generators |
| S4 | Instrument DAG structure | Show Z→D with no Z→Y visually when instrument identified |
| S5 | L3 automated checking | Add `ADJUSTMENT_SET:<vars>` extraction pattern for automated eval |
| S6 | Neutral post-treatment controls | Note that not ALL post-treatment variables are bad controls |

---

## Clean Bill of Health

These areas passed with no issues:

- **Trigger keyword separation**: DAG keywords are distinct from all method skills
- **Workflow boundary**: DAG does NOT estimate effects; clean handoff to method skills
- **Severity terminology**: FATAL/SERIOUS consistent across all skills
- **Estimand terminology**: ATE/ATT/LATE consistent with IV, matching, experiments
- **Auditor integration**: Advisory nudge is appropriately placed and worded
- **Plugin keywords**: No false-match risk in discovery
- **Template structure**: Follows same conventions as other methods
- **Collider bias treatment**: Excellent, literature-aligned
- **M-bias treatment**: Excellent, captures Ding/Miratrix vs Pearl debate
- **Faithfulness assumption**: Thorough and correct
- **Bad controls coverage**: Comprehensive (6 patterns with correct severities)
- **READMEs**: Both EN and PT-BR in sync

---

## Recommended Fix Order

1. **C2** — Runtime-breaking R template bug. Fix immediately.
2. **I1 + I2** — Planner integration + L1 eval (same root cause).
3. **I4 + I5 + I7** — Terminology and attribution fixes (text-only edits).
4. **I6 + I8 + I9** — Missing assumptions (CMC, SUTVA, fix d-sep test).
5. **I3** — Exercise integration.
6. **M0a-M14** �� Minor fixes in priority order.
7. **S1-S6** — Suggestions at leisure.
