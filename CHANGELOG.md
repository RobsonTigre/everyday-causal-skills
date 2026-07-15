# Changelog

All notable changes to this plugin are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

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
