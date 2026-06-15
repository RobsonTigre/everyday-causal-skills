# R↔Python parity machine

Model-free gate that fails when a method's R and Python implementations disagree.

## Setup
Install the method packages into your project venv once (needs pip ≥ 21.3 for the
editable install — in a fresh venv run `python -m pip install --upgrade pip` first):

    /path/to/venv/bin/python -m pip install -e ".[parity]"

This installs the exact Python packages the recipes import (`rdrobust`, `scpi_pkg`, …).
`evals/parity/test_parity_deps.py` enforces that this list stays complete.

## Run it
Run the gate with the **interpreter that has the method packages** (e.g. `scpi_pkg`, `diff-diff`)
— usually your project venv, **not** system `python3`. The runner uses whatever Python launches it
for the Python recipes (override with `$EVAL_PYTHON`).

- `<venv>/bin/python evals/parity/run_parity.py --all`        # every method
- `<venv>/bin/python evals/parity/run_parity.py --changed`    # only methods touched vs HEAD
- `<venv>/bin/python evals/parity/run_parity.py --method iv`  # one method

Or point at any interpreter explicitly:
- `EVAL_PYTHON=/path/to/venv/bin/python python3 evals/parity/run_parity.py --all`
- `EVAL_RSCRIPT=/path/to/Rscript` overrides the R interpreter the same way.

> If you run it under bare system `python3`, methods whose packages live only in your venv
> (e.g. synthetic control / `scpi_pkg`) silently report `None` and pass as `known` — a hollow
> green, not a real comparison.

Verdicts: `ok` (agree), `known` (a disparity already tracked in `baseline.yaml`), `FAIL` (a NEW disagreement — exit non-zero).

## MANDATORY after editing any `skills/*` or `templates/*`
Run `<venv>/bin/python evals/parity/run_parity.py --changed` (see interpreter note above) and resolve every `FAIL` before committing/pushing.
A `FAIL` means the R and Python paths for that method now disagree. Either fix the disagreement,
or — if it is a newly-discovered, not-yet-fixed disparity — add it to `evals/parity/baseline.yaml`
with a backlog id. Install the enforcing git hook once with `bash evals/parity/install-hooks.sh`.
