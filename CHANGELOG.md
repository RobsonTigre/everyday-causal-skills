# Changelog

All notable changes to this plugin are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`/causal-roi`** — business-translation skill: turns an estimated causal
  effect into money through one canonical pipeline (normalization gate →
  estimand-aware scaling → projection waterfall → incremental ROI with
  uncertainty → breakeven → ship/staged/size/kill verdict). All numbers come
  from a generated, executed R/Python script (base R / numpy+pandas only);
  financial parameters are never invented — sourced, run as a labeled
  sensitivity range, or the verdict is withheld. Outputs `roi.md`, the script,
  and a machine-readable `roi-results.csv`. Runtime rules live in
  `references/roi-framework.md`; workflow becomes planner → method → auditor →
  **roi** → report.
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
  attribution, method choice must NOT trigger the skill).

### Changed

- `/causal-report` now consumes `roi.md`/`roi-results.csv` for monetary
  figures. It quotes money numbers from the ROI artifact or explicit user
  input but never derives ROI, breakeven, financial ranges, or rollout
  verdicts itself — the ROI artifact is the single financial source of truth.
- The workflow flowchart (`assets/flowchart.png`) gained the **Translate**
  stage (`/causal-roi`) between Stress-test and Report.

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

[0.5.0]: https://github.com/RobsonTigre/everyday-causal-skills/releases/tag/v0.5.0
[0.4.1]: https://github.com/RobsonTigre/everyday-causal-skills/releases/tag/v0.4.1
