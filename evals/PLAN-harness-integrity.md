# Harness integrity — TDD plan

Test-first specification for the work described in `tasks/todo.md`
("Unblock v0.6.0 — repair the instrument's memory", 2026-08-04).

**The premise that makes this TDD and not ceremony:** every defect below has already
happened, and the artifact that proves it is still on disk. No scenario needs inventing.
Each test names the real file it runs against and the reason it must fail *today*.

Per `superpowers:test-driven-development`: write the test, **watch it fail for the right
reason**, then write the minimal code. A test that passes on first run is testing existing
behavior — fix the test, not the code.

## Scope

| Phase | TDD? | Why |
|---|---|---|
| 0 — re-measure L4 at HEAD | **No** | A measurement, not a code change. There is nothing to assert until it runs. |
| 1 — drift detection | Yes | Deterministic, offline, reproduces from stored artifacts. |
| 2 — per-question L4 gate | Yes | Same, plus a frozen decision rule that must be proven to move. |
| 3 — offline reachability | Yes | Pure static analysis over tracked files. |
| 4 — exemplar calibration | Partly | Machinery is testable; blessing an exemplar is human judgment. |
| 5 — release topology | **No** | Robson's decision. |

## Standing rules for every test here

1. **Real artifacts over fixtures** wherever one exists. `evals/results/sweep-2026-08-03_161835_pid42331/ledger.json`
   and the tracked case files are the corpus. Synthetic dicts only for shapes that cannot
   occur naturally (forged counts).
2. **Name the production change that would make it fail** before writing it. If you can't,
   the test is decorative.
3. **Never assert on a mean when the defect is per-question.** That is the failure this whole
   plan exists to fix (`tasks/lessons.md`, 2026-08-03).
4. **Validators land in `warn_case` first, `validate_case` later.** `validate_tree` is blocking
   at `sweep.py:671`; `warn_tree` is advisory at `:682`. Promoting a new rule to a hard build
   error mid-investigation is what `tasks/lessons.md:58-74` exists to prevent. Promote at a
   version boundary.
5. **Anything touching the gate must move `_gate_digest`.** A rule that changes the verdict
   while the digest stays byte-identical is the Package F finding #5 failure, repeated.

---

## Phase 1 — Make drift impossible to miss

### T1.1 `test_validator_rejects_an_l4_rubric_entry_without_an_id`

- **File:** `evals/test_validate_cases.py`
- **Fails today because:** `_check_l4_rubric` does not exist. `validate_cases.py:370-388`
  accepts any dict of known dimension keys holding non-empty lists of bare strings.
- **Green:** `_check_l4_rubric` requiring `{id, question, required}` per entry, mirroring
  `_check_l2_rubric` — reject duplicate ids, unknown fields, and declaration in both
  `expected.rubric` and top-level `rubric`.
- **Ordering hazard:** this invalidates all 37 L4 cases until they are migrated. Land the
  function and its unit tests against synthetic case dicts first; migrate the 37 files as a
  separate commit; only then wire it into `warn_case`, and into `validate_case` at a version
  boundary.

### T1.2 `test_aggregate_refuses_a_ledger_whose_question_text_disagrees_with_the_case` ★ — **DONE 2026-08-05**

**The keystone test.** This is the bug that invalidated a month of diagnosis.

Landed as `runner._l4_question_drift`, wired into `aggregate()`'s L4 branch, plus
`scorer._judge_l4` recording `questions_asked` and `sweep._unmeasured_reason` naming the
drift. 7 tests in `test_runner.py`, 1 in `test_sweep.py`, all red first.

**Correction to this plan: the text could not come from the aggregate.** This section said
"store the question text alongside the counts in the aggregate", and T2.1 had already done
that — but the text an aggregate stores is read out of *today's* case file, so comparing it
to today's case file compares a value with itself. Only the run can say what it was graded
on, so the record had to be pushed down into `_judge_l4`. That is why T1.2 changes the
scorer, which this plan did not anticipate.

Consequently there are two checks, not one, and only one of them works on ledgers that
already exist:

- **Shape**, on any ledger. `_call_judge` raises unless it yields exactly one answer per
  question, so a valid run always carries the count its case declared at measurement time.
  A stored count that disagrees with the case file today is proof the rubric moved.
- **Text**, only on runs written since `questions_asked`. A reword keeps the count.

**The limit this leaves, stated because it bounds every claim made off the 08-03 ledger:**
12 of 37 L4 cases moved question text between `3bf5738` and HEAD; 3 changed shape and are
caught, **9 were reworded at the same length and are permanently undetectable there**.
Retroactive drift detection is partial by construction. Forward detection is complete.

One consequence for Phase 2: `_l4_questions`' `partial` status is now unreachable through
`aggregate` — a run holding fewer answers than the case declares is drift, refused a step
earlier. `test_l4_question_denominator_is_every_valid_run` therefore calls `_l4_questions`
directly. T2.4 must be written against that boundary, not against a short answer array.

- **File:** `evals/test_runner.py`
- **Real artifact:** the 08-03 ledger's `report_figures_success` slots (3 stored `actionable`
  answers) against today's `evals/cases/layer4/report_figures_success.yaml` (1 safety +
  2 actionable, entirely different text, plus 2 `deferred_rubric` entries that did not exist
  at `3bf5738`).
- **Fails today because:** `question_answers` is positional (`{dim: [bool, ...]}`) with no ids,
  so stored answers silently re-point onto whatever questions now occupy those indices. Only a
  length change is detectable, and rewording keeps the length.
- **Green:** store the question text alongside the counts in the aggregate; return
  `UNMEASURED` when the stored text disagrees with the case file — the same
  ledger-and-case-must-agree discipline `_load_ledger_case` already enforces on paths and
  layers (`sweep.py:778-795`).
- **Also assert:** one of the 13 *unchanged* L4 cases still aggregates cleanly, so the check
  discriminates rather than refusing everything.

### T1.3 `test_stale_ledger_names_which_measurement_keys_moved` — **DONE 2026-08-04**

Landed as `sweep.staleness_report(stored, current)`, 5 tests in `evals/test_sweep.py`.

**Correction to this plan:** the intended real artifact — the 2026-08-03 ledger — is under
`evals/results/sweep-*/`, which is **gitignored**. It cannot be a hermetic fixture; the tests
use synthetic fingerprints instead. The same constraint applies to any future test that wanted
a stored ledger as its corpus. Tracked case files (T1.2, T3.x) are unaffected.

- **File:** `evals/test_sweep.py`
- **Real artifact:** the 08-03 ledger (`fingerprint.commit = 3bf5738`) against a fingerprint
  built from HEAD.
- **Fails today because:** `fingerprint_mismatch()` (`sweep.py:433`) computes exactly this and
  is wired only to guard **resume** (`sweep.py:1348`). Nothing surfaces it to a human — or an
  agent — reading a ledger or `verdict.md`.
- **Green:** a staleness report on every human-facing read, naming the moved keys (`commit`,
  `cases_sha256`, `harness_sha256`) and the count of case files changed since.
- **Assert specifically:** the report names `cases_sha256`, not just "stale".

### T1.4 `test_repo_doctor_notes_a_ledger_whose_fingerprint_predates_head` — **DONE 2026-08-04**

Landed as `repo_doctor.stale_results()` + `stale_results_note()` + `check_stale_results()`,
11 tests in `evals/test_repo_doctor.py`. Pure functions stay git-free, per that file's
hermetic convention; the IO wrapper does the shelling.

**A defect the first green introduced, caught by running it:** "a note per stale ledger"
emitted **21 lines** on the real repo, burying every other finding — every stored sweep
predates HEAD the moment anything is committed. Fixed test-first with `stale_results_note`,
which collapses to one line carrying the count, the total, and the newest stale sweep (the one
someone is about to cite). **Any future check here must be scale-aware for the same reason.**

Deliberately a note, never a blocker: an expired result is a correct record of a tree that has
since moved. The plan's original "cited in `tasks/` as current evidence is a blocker" was
dropped — inferring citation intent from prose is guesswork, and a false blocker before a
release is worse than a note.

---

## Phase 2 — Per-question L4 gate

Strictly tightening throughout: no threshold moves, no criterion is demoted. C15.1-legal.

### T2.1 `test_l4_questions_aggregates_per_question_counts_from_stored_answers` — **DONE 2026-08-04**

Landed as `runner._l4_questions()`, surfaced as `question_stats` in `aggregate()`'s L4 branch.
6 tests. **Reported, not gated** — the gate change is step 4 and moves the digest.

Verified by replaying the real 2026-08-03 ledger (37 cases, 185 valid runs) through the new
`aggregate`: **0 dimension means moved, worst delta exactly 0.00e+00** — not merely inside
`_GATE_EPS`. `question_stats` produced for all 37 cases; 230 question slots accounted for.

That replay also produced the first mechanical evidence of rubric drift: three questions
declared in today's case files were never answered by the stored runs —
`exercise_iv_quality.pedagogy[3]`, `report_figures_success.safety[0]`,
`report_tone_academic.safety[2]` — each classified `partial` with `rate: None`, never a silent
zero. That is Package F's never-shrink-the-denominator rule now holding on L4, and it is
precisely the signal T1.2 will turn into a refusal.

- **File:** `evals/test_runner.py`
- **Real artifact:** slots from one of the **13 unchanged** L4 cases in the 08-03 ledger, so
  text-pinning (T1.2) holds and the test does not depend on drifted data.
- **Fails today because:** `_l4_questions` does not exist. `aggregate()`'s L4 branch
  (`runner.py:733-766`) collapses `question_answers` to three dimension means and drops the
  rest, so `case_gate` — which only ever sees `agg` — is structurally blind to it.
- **Green:** `_l4_questions(valid, case)` beside `_rubric_criteria` (`runner.py:614`), keyed by
  rubric **id** (T1.1), emitting `{question, passed, answered, valid}`. Return `None` when no
  valid run carries `question_answers` — the pre-`8e9420e` ledger marker, mirroring
  `runner.py:630`.
- **Regression guard:** assert the existing dimension means still reproduce **within
  `_GATE_EPS`**, never with `==`. They reproduce to ~2.2e-16, not byte-identically.

### T2.2 `test_l4_question_status_rejects_forged_counts` — **DONE 2026-08-04, as reuse not a clone**

**Correction to this plan: there is no `question_status`.** This section specified "a clone of
`criterion_status`". That function's own docstring argues against exactly that — *"One helper,
not three: the gate, the UNMEASURED reason and the verdict table all have to agree on what
'complete' means. Three copies would drift."* L4 question blocks have the identical shape
(`passed`/`answered`/`valid`), so `criterion_status` is **reused verbatim** and `_l4_questions`
carries no validation of its own.

Pinned by `test_l4_question_blocks_are_validated_by_the_same_helper_as_l2_criteria`, which
asserts both Package F forged shapes (`{passed: 999}`, `{passed: True}`) and the partial shape
are rejected, and that a real `_l4_questions` block validates clean through the same call.

### T2.3 `test_l4_gate_fails_a_case_whose_dimension_passes_but_one_question_is_dead` ★ — **DONE 2026-08-05**

Landed with T2.4, T2.5 and T2.6 in one cycle, in the order this plan prescribes: digest
coverage first, then the rule.

**Measured effect on the 2026-08-04 baseline: 32 PASS / 5 FAIL becomes 23 PASS / 14 FAIL.**
Nine cases were clearing a dimension mean while a question inside it ran at 20–60%. That is
the defect this test describes, nine times over, in the only valid measurement of HEAD.

The `tasks/lessons.md` 2026-08-03 scenario, made executable.

- **File:** `evals/test_runner.py`
- **Fails today because:** `case_gate`'s L4 branch is three dimension means ≥ 0.7. A two-question
  `actionable` at `(1.0 + 0.4)/2 = 0.7` **passes** — a behavior appearing 40% of the time, read
  as green. Nearly cost ~15 hours of calibration on top of it.
- **Green:** a per-question floor added **after** the untouched dimension loop, with
  `DEFAULT_THRESHOLDS["layer4"]["question_rate"] = 0.8`.
- **Assert the existing thresholds are untouched** in the same test, so the change is provably
  additive.

### T2.4 `test_l4_gate_is_unmeasured_when_a_question_is_answered_in_only_some_runs` — **DONE 2026-08-05**

- Package F's "never shrink the denominator" rule, ported to L4. A question answered in 4 of 5
  valid runs must read as **UNMEASURED**, never as 4/4 = 100%.
- Written against a **stored** aggregate, per T1.2's note: aggregation now refuses a short
  answer array before this rule can see it, so the state survives only in a ledger already on
  disk — which is exactly where `compile_verdict` meets it.

### T2.5 `test_gate_digest_moves_when_an_l4_rubric_question_changes` ★ — **DONE 2026-08-05**

Landed as `_l4_gate_contract`, hashing sorted `(dimension, id, required)` per L4 case.
**Correction: there is no `question_status` to add** — T2.2 already established that
`criterion_status` is reused rather than cloned, and Package F hashed it. The digest moved
from `7aac29ec…` to `a001661d…` across this cycle, which is the point.

- **File:** `evals/test_sweep.py`, beside
  `test_gate_digest_covers_the_rubric_accessor_and_the_ledger_case_loader`
- **Fails today because:** `_gate_digest` (`sweep.py:168-209`) hashes `case_gate`, `_meets`,
  `_threshold`, `compile_verdict` and `_l2_gate_contract` — but nothing about L4 rubrics. Once
  the gate depends on per-question ids, editing a question would move the verdict while leaving
  the digest byte-identical. Exactly Package F finding #5.
- **Green:** add `question_status` and an `_l4_gate_contract(case_paths)` hashing each L4 case's
  normalized `(id, required)` contract.
- **Assert the inverse too:** rewording a question's *text* is measurement, not gate, and must
  **not** move the digest — mirroring the L2 rule.

### T2.6 `test_save_history_l4_column_is_a_pass_fraction` — **DONE 2026-08-05**

`layer_stats[4]` gained its `"pass"` key, `case_gate` now covers layer 4, and `HISTORY.md`'s
demarcation note says the column changed units so no one reads a fraction against a
percentage as a fall.

- **Fails today because:** `save_history` calls `case_gate` only for layers 0–3
  (`runner.py:891`) and renders L4 as `avg_pct` of each case's `rate` (`runner.py:916-917, 938`)
  — a mean of means of means, the exact averaging this phase exists to stop. Tightening the gate
  would not move the trend column by a single point.
- **Green:** PASS/total, like L0–L3. Watch `layer_stats[4]` — it has no `"pass"` key today, so
  a naive edit KeyErrors at `runner.py:902`.

---

## Phase 3 — Catch unsatisfiable cases before spending a sweep

All offline. Zero model calls. Target: the 15-hour sweep becomes the last step, not the
diagnostic tool.

### T3.1 `test_skill_stage_profile_finds_the_one_turn_escape_clause`

- **Real artifacts, both pinned by value:** `skills/causal-sc/SKILL.md:48` declares
  `**Fully specified direct mode**` → escape present. `skills/causal-hte/SKILL.md:40` marks its
  Stage 1 questions `**(always ask)**` with no escape → absent.
- **Fails today because:** no such parser exists.
- **Green:** `_skill_stage_profile(skill)` in `validate_cases.py`, parsing `^## Stage \d` /
  `^### Step \d` headings plus the escape-clause forms actually in use: the literal
  `**Fully specified direct mode**` block (`causal-sc:48`, `matching:54`, `rdd:56`,
  `timeseries:48`), prose variants (`causal-iv`, `causal-report`, `did:42`, `experiments:48`),
  and `causal-roi`'s `## Response contract — pick exactly one mode` (`SKILL.md:60-107`).

### T3.2 `test_final_output_is_rejected_for_a_skill_with_no_one_turn_escape` ★

- **Real artifact:** `evals/cases/layer4/hte_pedagogy_clean.yaml` and `hte_pedagogy_messy.yaml`
  — both declare `response_contract: final_output` against a skill whose Stage 1 questions are
  `**(always ask)**`.
- **Fails today because:** nothing cross-checks a case's contract against its skill's structure.
  The contract is a hand-typed assumption, and these two are structurally unsatisfiable.
- **Green:** `_check_stage_reachability` beside `_check_grading_contract`
  (`validate_cases.py:138`). `final_output` is legal only when the skill exposes an escape whose
  terminal mode is reachable in the runner's real envelope — one `claude -p` with
  `--tools Read,Glob,Grep` (`runner.py:432`), so **nothing executes**.
- **Wire into `warn_case` (`:457`), not `validate_case` (`:299`)** — see standing rule 4.

### T3.3 `test_criterion_demanding_a_computed_value_is_flagged_under_a_read_only_grant`

- **Real artifact:** `roi_pedagogy_clean.actionable[0]` demanded *"report breakeven
  1.4626027139 and VERDICT_CODE 1"* under a grant with no execution. The only way to pass is to
  hand-compute, which the skill forbids — the same unsatisfiable shape as the
  `roi_full_artifacts` latent false pass that `e8d825c` already had to fix once.
- **Green:** flag any criterion demanding a specific computed value where the layer's tool grant
  cannot produce one.

### T3.4 `test_twin_pair_with_divergent_contracts_requires_a_rationale`

- **Real artifact:** 9 `*_pedagogy_clean` / `*_pedagogy_messy` pairs in `evals/cases/layer4/`;
  **6 currently disagree** on `response_contract`.
- **Green:** require an explicit `contract_rationale:` string on any disagreeing pair, registered
  in `_COMMON_TOP` (`validate_cases.py:430`) so it is not reported as dead metadata. The lint
  demands justification, **not** sameness — a twin pair may legitimately differ.

---

## Phase 4 — Let a case be found guilty

Adds a **validity** precondition orthogonal to the pass/fail rule. No threshold moves, no
criterion is demoted.

### T4.1 `test_exemplar_must_be_pinned_to_a_recorded_slot_sha256` ★

**Write this one first.** It is the entire safety property.

- **Fails today because:** `evals/exemplars.py` does not exist.
- **Green:** reject any exemplar not sha256-matched to an actual recorded slot in a named sweep
  ledger, verified at calibration time.
- **Why it leads:** this mechanism opens a side door the freeze rule does not cover. Instead of
  lowering a threshold, you shrink the measured set — and the audit trail reads like diligence.
  A threshold is one number `_gate_digest` screams about; a hand-written exemplar is prose that
  looks like evidence. Without T4.1, Phase 4 is a liability, not a control.

### T4.2 `test_case_failing_a_blessed_known_good_exemplar_is_unmeasured_not_fail`
### T4.3 `test_case_passing_a_known_bad_exemplar_is_unmeasured`

- **Green:** `calibrate_case(case, config, k=3)` scores the exemplar through
  `scorer.score_response`, wraps it in a one-run pseudo-aggregate, and feeds it to the
  **unmodified** `runner.case_gate` — so no second copy of the decision rule exists.
  Judge calls only; no `claude -p` generation.

### T4.4 `test_quarantine_cannot_turn_a_red_release_green` ★

- **Green (already true structurally, must be pinned):** `compile_verdict` sets
  `overall = "FAIL"` before it considers UNMEASURED (`sweep.py:1021-1026`). Assert it, so a
  future refactor cannot quietly make quarantine a release laundering path.

### T4.5 `test_single_dissenting_judge_call_marks_calibration_inconclusive_not_defective`

- `k=3` with majority agreement. One dissent ⇒ `inconclusive` (warn), not `defective`
  (quarantine). The judge has a confirmed false positive on record (`tasks/lessons.md:38-41`);
  a fallible instrument must not be able to delete a case on its own.

### T4.6 `test_save_history_skips_a_quarantined_l4_case`

- `save_history` consults `case_gate` only for layers 0–3 and `layer_stats[4]` has no `"pass"`
  key (`runner.py:891-902`). A quarantined L4 case must `continue` before line 900 or line 902
  KeyErrors.

---

## Suggested commit sequence

Each line is one red-green-refactor cycle, offline, verifiable in seconds.

1. T1.3, T1.4 — staleness reporting. Smallest blast radius, immediately useful, unblocks honest
   reasoning about every existing artifact.
2. T2.2, T2.1 — `question_status` then `_l4_questions`. Aggregator only; **do not touch the gate
   yet.** Prove it reproduces the stored means within `_GATE_EPS`.
3. T1.1 + the 37-case migration + T1.2 — rubric ids, then text-pinning. T1.2 is not
   implementable before ids exist.
4. T2.5, T2.3, T2.4 — digest coverage **before** the gate change, so the digest is proven to
   move when the rule does.
5. T2.6 — HISTORY column.
6. T3.1 → T3.4 — static lints, all as warnings.
7. T4.1 first, then the rest of Phase 4.

The six tests in `evals/test_runner.py` (lines 577, 584, 599, 613, 624, 635) that call
`case_gate({"layer": 4}, agg)` with a stripped case dict break as soon as the L4 **gate** needs
the rubric — exactly as `case_gate`'s D9 docstring predicts.

**Correction to this plan, twice over:** they were first listed as "before step 2", then moved
to "before step 4". Neither is right — **they never break at all.** Each pairs
`case_gate({"layer": 4}, agg)` with an aggregate built from that same stripped dict, so it
carries no `question_stats`, no required question resolves, and the guard has nothing to fire
on. That pairing cannot occur in production, where `_load_ledger_case` always loads the real
case. The D9 shape that *can* occur is a real aggregate against a stripped case, and that is
now pinned by `test_l4_gate_refuses_a_stripped_case_dict_carrying_question_stats`, which
raises. Predicting a test will fail is not the same as watching it fail.

## Definition of done

- Every test above written, **watched failing for the stated reason**, then made green.
- Full suite green (399 at last count, plus the new ones), 187/187 cases valid, ruff clean on
  changed files only, `git diff --check` clean.
- `_gate_digest` **moves** when the gate moves, and **does not** when only wording moves — both
  directions asserted.
- A stale ledger cannot be read anywhere in this repo without saying so.
