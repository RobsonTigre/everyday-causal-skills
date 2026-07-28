# Changelog

All notable changes to this plugin are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] - 2026-07-28

### Added

- **`/causal-roi`** — business-translation skill: turns an estimated causal
  effect into money through one canonical pipeline (normalization gate →
  estimand-aware scaling → projection waterfall → incremental ROI with
  uncertainty → breakeven → ship/staged/size/kill verdict). Every downstream
  number after the normalization gate comes from a generated R/Python script
  (base R / numpy+pandas only) whose output has actually been inspected;
  financial parameters are never invented — sourced, run as a labeled
  sensitivity range, or the verdict is withheld. Outputs `roi.md`, the script,
  and a machine-readable `roi-results.csv`. Runtime rules live in
  `references/roi-framework.md`; workflow becomes planner → method → auditor →
  **roi** → report.
- **Three-mode response contract for `/causal-roi`**, keyed on execution state
  rather than tool availability, so a financial number is never asserted ahead
  of the evidence for it:
  - **Mode A — any required input is missing.** Every missing normalization and
    projection input is asked for in that same response. Promising a follow-up
    interview or a second pass does not satisfy this: a deferred ask is a
    missing ask.
  - **Mode B — inputs complete, no successful output inspected.** Covers no
    execution tool, a missing dependency, a permission failure, a crash, a
    timeout, and unparsable output alike. The reply carries the normalization
    gate record, the provenance record, the complete runnable script, and the
    six pipeline assumptions each marked checked / assumed / unknown. Outside
    the script, no downstream value is stated — no waterfall figure, present
    value, ROI, ROI interval, breakeven, sensitivity result, machine-readable
    `KEY: value`, or verdict. The waterfall's shape is described; its numbers
    are not. No label rescues a hand-computed number: "hand-traced",
    "closed-form", and "please run to confirm" are all Mode B.
  - **Mode C — execution completed and output inspected.** Either the agent ran
    the generated script and read its output, or the user supplied that same
    script's raw output. Only here do the full one-pager and the verdict appear.
- Estimand-scaling safeguards with severity blocks: LATE never scaled to
  non-compliers, ITT never adoption-adjusted twice, already-cumulative DiD /
  time-series results never re-summed, RDD verdicts limited to the identified
  region, CATE aggregated with segment weights, matching routed by its actual
  estimand, synthetic control monetized for the treated unit only.
- Parity suite for the roi pipeline (fixture, R/Python reference recipes,
  spec) plus an independent hand-derived known-answer oracle suite
  (`evals/parity/test_roi_known_answers.py`).
- Eval-harness extensions (backwards-compatible, unit-tested): L2 judge now
  honors rubric questions (reviving the dormant `rubric:` fields in the
  `report_*` cases) and L3 scoring supports named `KEY: value` outputs with
  per-key tolerances. New L0/L2/L3/L4/L5 roi eval cases, including 5
  ROI-specific negative triggers (accounting ROI, real-estate, stock returns,
  attribution, method choice must NOT trigger the skill), and an L3 case that
  executes the full roi pipeline in R against a hand-derived oracle covering
  every reported key including `VERDICT_CODE`. The suite is now 187 cases.
- Declarative evaluation metadata now has validated schemas and evaluator
  support: `response_contract` records whether a case targets a final output or
  first turn; `input_mode` describes how inputs arrive and provisions artifact
  fixtures when applicable; `deferred_rubric` keeps unreachable questions
  visible in the verdict without judging, scoring, or counting them toward a
  pass.
- A tracked release-sweep configuration and a provenance fingerprint covering
  cases, skills, references, templates, fixtures, manifests, dependency
  versions, and the actual execution interpreter. Release verdict mode now
  rejects dirty or untracked measurement inputs and records measurement and
  gate digests separately.
- **Per-criterion L2 rubric gate.** L2 rubric entries are now
  `{id, question, required}` objects, the judge returns one answer per criterion
  instead of a single collapsed mean, and 34 criteria across eight cases are
  gated individually at ≥4/5 valid runs (`layer2.rubric_required_rate`).
  Detection, severity and every required criterion must pass independently. The
  verdict reports each criterion's rate and whether it gated.
- A green release sweep now writes one consolidated `HISTORY.md` row, keyed by an
  exact `[release:vX.Y.Z]` token: re-running a sweep for the same unpublished
  version replaces that row instead of appending a second one. Failed or
  unmeasured sweeps write no row.

### Changed

- `/causal-roi` emits the normalization gate record **before** the projection
  interview, not after it. Collection is split into normalization inputs
  (currency, outcome construct and cost inclusion, unit denominator, unit
  economics, horizon convention) and projection inputs (population, transport,
  investment, discount rate, persistence, cannibalization, hurdle), so the
  per-period effect in money is fixed and visible before anything is projected
  from it. `references/roi-framework.md` §2 mirrors the same ordering, and §10
  documents `VERDICT_CODE`, which the templates emit but the framework had not
  listed.
- `case_gate()` takes the whole case rather than a layer number, so every caller
  gates on the contract the case actually declares. Two consumers (the release
  verdict and the HISTORY pass column) previously derived verdicts from the
  aggregate alone, which is how a gate fix could apply to one and not the other.
- Rubric results that are incomplete are reported as UNMEASURED, never scored
  over the subset of runs that answered: a required criterion answered in four of
  five valid runs reads as a measurement gap, not as 4/4. Ledgers written before
  this gate existed are UNMEASURED for the same reason, with the verdict saying
  which of the two it was.
- `/causal-report` now consumes `roi.md`/`roi-results.csv` for monetary
  figures. It quotes money numbers from the ROI artifact or explicit user
  input but never derives ROI, breakeven, financial ranges, or rollout
  verdicts itself — the ROI artifact is the single financial source of truth.
  It also names the skill behind every missing artifact, including when it
  judges the gap non-blocking.
- `/causal-dag` saves `dag.md` when file-writing tools are available and
  otherwise says so and returns the full analysis and code inline. A missing
  Write tool no longer downgrades the answer to a Markdown-only artifact.
- The workflow flowchart (`assets/flowchart.png`) gained the **Translate**
  stage (`/causal-roi`) between Stress-test and Report.
- Plugin versioning now has one enforced policy: the six user-facing manifests
  carry version `0.6.0`, while per-skill `metadata.version` fields are removed.
  Git tags and this changelog provide skill provenance until skills are ever
  distributed independently.

### Fixed

- **`/causal-timeseries`, CausalArima in R.** The template passed the raw
  character `date` column straight into `CausalArima(dates = ...)`, which fails
  with "`dates` must be a vector of class Date"; dates are now converted before
  the call. Added the two accessors the template never documented — the point
  estimate and a confidence interval derived from the fitted object's own
  bootstrap forecast distribution (the packaged `impact()` accessor is broken in
  the installed version). `SKILL.md`'s shorter CausalArima example was missing
  both and now matches its neighbors.
- **`/causal-hte`.** The variable-importance caveat and the policy-tree
  deployment disclaimer were printed *after* a plotting call that can throw, so
  a plot crash silently suppressed the safety message the skill exists to emit.
  Both now immediately follow their anchor call, in the R and Python templates.
- **`/causal-dag`, DoWhy output.** Generated Python now runs unattended from a
  clean process: `matplotlib.use("Agg")` before importing `pyplot`, figures
  saved and closed rather than shown, and a small seeded placeholder dataframe
  containing every DAG variable when the user supplies none.
- **Eval fixture confinement.** `artifact_fixture.source` and `dest` are both
  confined to `evals/fixtures/` at the point of use, not only in a validator
  that a bare `--case` invocation skips, and symlinks anywhere inside an
  otherwise-confined fixture tree are rejected — `shutil.copytree` dereferences
  them by default, so a symlink could pull arbitrary file content into the
  model-readable sandbox.
- **Release sweeps are timeout-safe and slot-aware.** Configurable, terminal
  (never retried) skill and judge timeouts with typed invalid reasons; process
  group cleanup so a timeout leaves no orphaned `claude -p` grandchildren;
  per-run-slot checkpointing so one slow or failing run no longer discards a
  case's other four valid runs; coordinator-only ledger writes, eliminating a
  concurrent-mutation race; and release fail-fast checked before every dispatch
  rather than once up front.
- Sweep aggregation loads the full case contract rather than a bare layer
  number, so the L2 multi-flag gate and the L4 old-ledger fallback engage
  through the release sweep and not only through direct `--case` runs. A
  two-flag L2 case where every run caught one flag previously passed through the
  sweep and failed through the direct path.
- Eval gates now require successful process exit, apply floating-point
  tolerance consistently, use one shared gate implementation for verdicts and
  history, report empty executions explicitly, retry bounded rate-limit
  failures, and validate that case fields are actually consumed by each layer.
- Parity baselines now excuse only the named known disparities; execution
  failures always fail. Python DAG code works across NetworkX's
  `d_separated`/`is_d_separator` API change, and shipped API references are
  checked against installed libraries.
- Python template dependency and API mismatches were corrected for
  `pycausalimpact`, CausalImpact summaries and plots, ROI preflight mappings,
  and the current time-series parity contract.
- Eval fixtures and their prose: the loyalty-program parallel-trends test
  computes a genuine 5-degree-of-freedom joint F-test instead of silently
  pooling five month dummies into one, and "12% relative increase" is relabeled
  "12 percentage points" everywhere it appeared, including `/causal-report`'s
  own worked example. The clean-confounder DAG fixture was made causally
  complete, and the template-ordering regression test no longer passes
  vacuously when a safety message precedes its anchor.

## [0.5.0] - 2026-07-14

### Added

- **Missing-package preflight** for all method skills: templates now detect
  missing R/Python packages up front, report exactly what's missing with the
  install command, and the agent asks before installing — nothing is installed
  without an explicit yes. R templates no longer auto-run `install.packages()`;
  Python templates no longer fail with a deep `ModuleNotFoundError`
  mid-estimation. Canonical protocol in `references/preflight.md`.

### Changed

- Documented the `/plugin update` step in the Claude Code update instructions
  (README, English and Portuguese) — refreshing the marketplace catalog alone
  does not upgrade an installed plugin.

### Fixed

- **Parity gate (dev tooling)**: parity recipes now run under the launching
  Python interpreter, the pre-push hook auto-detects a real venv, and the
  recipes' Python dependencies are declared as an installable extra
  (`pip install -e ".[parity]"`) with a guard test — parity greens are genuine.

## [0.4.1] - 2026-06-14

### Fixed

- **`/causal-hte`**: corrected the RATE (Rank-Weighted Average Treatment Effect)
  self-grading logic in the R and Python templates, so the validation step grades
  the estimate against the correct reference instead of itself.

### Changed

- Added a workflow flowchart to the README (English and Portuguese).
- Documented `git pull`-based update paths for Codex CLI and Cursor installs.

[0.6.0]: https://github.com/RobsonTigre/everyday-causal-skills/releases/tag/v0.6.0
[0.5.0]: https://github.com/RobsonTigre/everyday-causal-skills/releases/tag/v0.5.0
[0.4.1]: https://github.com/RobsonTigre/everyday-causal-skills/releases/tag/v0.4.1
