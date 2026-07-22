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
EVAL_PYTHON="$PWD/.venv/bin/python" .venv/bin/python evals/sweep.py ...
```

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
