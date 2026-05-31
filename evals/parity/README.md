# R↔Python parity machine

Model-free gate that fails when a method's R and Python implementations disagree.

## Run it
- `python3 evals/parity/run_parity.py --all`        # every method
- `python3 evals/parity/run_parity.py --changed`    # only methods touched vs HEAD
- `python3 evals/parity/run_parity.py --method iv`  # one method

Verdicts: `ok` (agree), `known` (a disparity already tracked in `baseline.yaml`), `FAIL` (a NEW disagreement — exit non-zero).

## MANDATORY after editing any `skills/*` or `templates/*`
Run `python3 evals/parity/run_parity.py --changed` and resolve every `FAIL` before committing/pushing.
A `FAIL` means the R and Python paths for that method now disagree. Either fix the disagreement,
or — if it is a newly-discovered, not-yet-fixed disparity — add it to `evals/parity/baseline.yaml`
with a backlog id. Install the enforcing git hook once with `bash evals/parity/install-hooks.sh`.
