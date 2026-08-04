# Eval harness — environment setup

The harness executes the code the skills generate. That means results depend on the
Python interpreter and the exact package versions installed, so the environment is
part of what a verdict measures. This file is tracked precisely because that
information cannot live in `docs/` (gitignored) or `evals/config.yaml` (gitignored).

## Interpreter

**Python 3.12.13**, verified as the version under which every declared eval
dependency resolves and imports — including `econml`, `dowhy`, `mcf`, `scpi-pkg`,
`pycausalimpact` and `pycausalarima`. 3.13 and 3.14 are the documented fallbacks if a
future dependency loses 3.12 wheels; `pycausalarima` requires ≥ 3.10 in any case.

## What a measurement needs

Every case is answered by `claude -p`, so **a sweep requires an authenticated Claude
CLI account on this machine** and bills to that account. There is no offline path to a
real measurement, and the harness will never start an interactive login for you.

Being logged out is not a quality result. Preflight refuses to dispatch, exits **3**,
and says so: *0 cases were measured. This is NOT a FAIL and NOT a PASS.* The ledger is
still written, so once you log in you resume with `--resume` instead of starting over.

This dependency is recorded in every ledger and verdict as `backend: cli`. That field
exists because the harness previously relied on the login without naming it anywhere,
which is why a credential problem used to surface as an unexplained `claude -p exited
1`. A ledger written before the field existed stays readable and can still be
recompiled, but cannot be resumed.

`backend: cli` is the only implemented value; a config asking for anything else is
refused rather than quietly served by the CLI. An Anthropic-API backend was
deliberately not built — it would have to reimplement the tool sandbox the CLI gives
`run_case_cli` (Read/Glob/Grep over a workspace with `templates/` and `references/`
linked in), and a version that skipped that would silently measure a different
environment: the model reports the template missing and improvises code instead, with
no error anywhere in its response.

## Setup

```bash
python3.12 -m venv .venv          # .venv/ is gitignored
.venv/bin/pip install -e ".[evals,dev]"
```

The `evals` extra pulls in the `parity` extra, so one install covers both the parity
recipes and everything the shipped templates import. It is anchored on the book's
`requirements.txt` (`Desktop/everyday-ci/requirements.txt`), because the templates
ship code the book runs and the two must not drift.

## Running

```bash
.venv/bin/python -m pytest evals              # offline harness tests
.venv/bin/python evals/validate_cases.py      # case schema
.venv/bin/python evals/parity/run_parity.py --all
```

Point the harness at this interpreter with `EVAL_PYTHON`, which `scorer.py` already
honours:

```bash
EVAL_PYTHON="$PWD/.venv/bin/python" .venv/bin/python -u evals/sweep.py ...
```

For a release sweep, preserve the complete release command and let failures
propagate:

```bash
EVAL_PYTHON="$PWD/.venv/bin/python" .venv/bin/python -u evals/sweep.py \
  --runs 5 --workers 3 --config evals/config.release.yaml \
  --release-verdict vX.Y.Z
```

Avoid piping this command through `tee`, because a default shell pipeline can
hide the sweep's nonzero exit status. If a transcript is required, enable
`set -o pipefail` in the shell before piping to `tee`.

## The `causalimpact` trap

Two different PyPI distributions install a module named `causalimpact`:

| | `causalimpact` (Senouci) | `pycausalimpact` (Fuks) — **ours** |
|---|---|---|
| needs explicit `.run()` | yes | no, constructor runs |
| `summary_data` | absent | present (no `p` row; use `ci.p_value`) |
| effect bound labels | inverted at source | correct |
| `plot()` | — | `(panels, figsize)`, accepts no `ax` |

Because `from causalimpact import CausalImpact` works under both, installing the wrong
one fails only when an accessor is touched — and reads like a template bug. Install
**`pycausalimpact`**. `evals/test_env_deps.py` locks this down: it checks that every
template's declared pip-name really provides the import-name beside it, and asserts
specifically that `causalimpact` resolves to `pycausalimpact`.

R's `CausalImpact` (Google/Brodersen) is a separate, correct implementation and is
unaffected by any of the above.
