"""Static schema check for eval cases.

A case whose shape the runner cannot consume fails identically to a skill that
answers badly — except it fails on every run, forever, and burns live model
calls proving it. Several such cases sat in the tree for months. This validator
catches that class before a sweep starts, not after.

Run: python3 evals/validate_cases.py   (from repo root)
Exits 0 when every case is well formed, 1 with a per-case list otherwise.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorer import FIXTURES_ROOT, SEVERITIES, must_include_alternates, reject_symlinks  # noqa: E402

DIMENSIONS = ("pedagogy", "safety", "actionable")


def _is_nonempty_list(v) -> bool:
    return isinstance(v, list) and len(v) > 0


def _check_common(case: dict, path: Path, errors: list[str]) -> int | None:
    stem = path.stem
    name = case.get("name")
    if name != stem:
        errors.append(f"name {name!r} does not match filename {stem!r}")
    if not case.get("description"):
        errors.append("missing description")

    layer = case.get("layer")
    dir_layer = None
    if path.parent.name.startswith("layer"):
        try:
            dir_layer = int(path.parent.name[len("layer"):])
        except ValueError:
            dir_layer = None
    if layer is None:
        errors.append("missing layer")
    elif dir_layer is not None and layer != dir_layer:
        errors.append(f"layer {layer} but lives in {path.parent.name}")
    return layer


_L2_RUBRIC_FIELDS = {"id", "question", "required"}
_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


def _check_l2_rubric(case: dict, expected: dict, errors: list[str]) -> None:
    """L2 rubric entries are `{id, question, required}` objects — Package F.

    Scoped to layer 2 on purpose. L1 and L5 rubrics are flat lists of question
    strings and L4's is a dict of dimension -> questions; a generic element check
    would reject 60+ valid cases.

    The `id` is what makes a criterion gateable: the judge's answers come back as
    a positional array, and without a stable key per question there is no way to
    say "this specific criterion passed in 4 of 5 runs". `required` is explicit
    rather than defaulted so promoting a criterion into the release gate is always
    a visible edit to the case file.
    """
    under_expected = expected.get("rubric")
    top_level = case.get("rubric")
    if under_expected is not None and top_level is not None:
        errors.append(
            "rubric declared in both expected.rubric and top-level rubric — "
            "scorer.py takes expected.rubric and silently drops the other")
        return

    rubric = under_expected if under_expected is not None else top_level
    if rubric is None:
        return
    if not isinstance(rubric, list):
        errors.append("L2 rubric must be a list")
        return

    seen: set[str] = set()
    for i, entry in enumerate(rubric):
        where = f"L2 rubric[{i}]"
        if not isinstance(entry, dict):
            errors.append(
                f"{where} must be a mapping with {sorted(_L2_RUBRIC_FIELDS)} "
                f"(a bare question string cannot be gated — it has no id)")
            continue

        unknown = set(entry) - _L2_RUBRIC_FIELDS
        if unknown:
            errors.append(f"{where} has unknown field(s): {sorted(unknown)}")
        missing = _L2_RUBRIC_FIELDS - set(entry)
        if missing:
            errors.append(f"{where} is missing {sorted(missing)}")

        cid = entry.get("id")
        if "id" in entry:
            if not isinstance(cid, str) or not _SNAKE_CASE.match(cid):
                errors.append(f"{where} id must be snake_case, got {cid!r}")
            elif cid in seen:
                errors.append(f"{where} duplicate id {cid!r}")
            else:
                seen.add(cid)

        question = entry.get("question")
        if "question" in entry and (not isinstance(question, str) or not question.strip()):
            errors.append(f"{where} question must be a non-empty string")

        if "required" in entry and not isinstance(entry["required"], bool):
            errors.append(
                f"{where} required must be true or false, got {entry['required']!r}")


def _check_paths(case: dict, errors: list[str]) -> None:
    for ref in case.get("references", []) or []:
        if not Path(ref).exists():
            errors.append(f"reference not found: {ref}")
    dataset = case.get("dataset")
    if dataset and not Path(dataset).exists():
        errors.append(f"dataset not found: {dataset}")


def _check_single_skill(case: dict, errors: list[str]) -> None:
    if not case.get("skill"):
        errors.append("missing skill")
    if not case.get("user_message"):
        errors.append("missing user_message")


_RESPONSE_CONTRACTS = {"final_output", "first_turn"}
_INPUT_MODES = {"inline", "dataset", "artifact", "withheld"}


def _check_grading_contract(case: dict, errors: list[str]) -> None:
    """`response_contract` / `input_mode` / `deferred_rubric` — optional at every
    layer; an absent field preserves current behaviour exactly. When present,
    each must be well-formed:

    - response_contract: final_output (grade the finished artifact) or
      first_turn (grade turn one only — read by scorer.py's _judge_l4).
    - input_mode: inline / dataset / artifact / withheld — read only by this
      validator, never by the scorer.
    - deferred_rubric: non-empty list of question strings moved out of the
      graded rubric because they cannot be reached in one turn. Reported in
      the verdict, never scored, never judged.
    """
    contract = case.get("response_contract")
    if contract is not None and contract not in _RESPONSE_CONTRACTS:
        errors.append(
            f"response_contract must be one of {sorted(_RESPONSE_CONTRACTS)}, got {contract!r}")

    mode = case.get("input_mode")
    if mode is not None and mode not in _INPUT_MODES:
        errors.append(f"input_mode must be one of {sorted(_INPUT_MODES)}, got {mode!r}")

    if "deferred_rubric" in case:
        deferred = case["deferred_rubric"]
        if not isinstance(deferred, list) or not deferred:
            errors.append("deferred_rubric, if present, must be a non-empty list")
        elif not all(isinstance(q, str) and q.strip() for q in deferred):
            errors.append("deferred_rubric entries must be non-empty strings")


def _check_dataset_contract(case: dict, errors: list[str]) -> None:
    """`dataset_contract: {columns: [...], n_rows: N}` (D4) — a declarative claim about
    the fixture named in `dataset:`, checked against the CSV itself. This is how a case's
    prose narrative is kept honest: runner.py's inject_schema() pastes the real df.head()
    into the prompt regardless of what the narrative claims, so a case whose story
    describes different columns or a different row count than the fixture puts a flat
    contradiction in front of the model on every run. Deliberately does not parse the
    prose narrative itself — regexing free text for claimed columns/counts is fragile
    and generates its own false failures; the author keeps the narrative and the
    contract in sync by hand, and this checks the contract against ground truth.
    """
    if "dataset_contract" not in case:
        return
    contract = case["dataset_contract"]
    if not isinstance(contract, dict):
        errors.append("dataset_contract must be a mapping")
        return

    dataset = case.get("dataset")
    if not dataset:
        errors.append("dataset_contract requires a dataset: field to check it against")
        return
    if not Path(dataset).exists():
        return  # _check_paths already reports the missing dataset

    columns = contract.get("columns")
    columns_ok = (isinstance(columns, list) and columns
                  and all(isinstance(c, str) for c in columns))
    if not columns_ok:
        errors.append("dataset_contract.columns must be a non-empty list of strings")

    n_rows = contract.get("n_rows")
    n_rows_ok = isinstance(n_rows, int) and not isinstance(n_rows, bool) and n_rows > 0
    if not n_rows_ok:
        errors.append("dataset_contract.n_rows must be a positive integer")

    if not (columns_ok and n_rows_ok):
        return

    with open(dataset, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        actual_rows = sum(1 for _ in reader)

    if columns != header:
        errors.append(
            f"dataset_contract.columns {columns} does not match {dataset}'s actual "
            f"header {header}")
    if n_rows != actual_rows:
        errors.append(
            f"dataset_contract.n_rows {n_rows} does not match {dataset}'s actual row "
            f"count {actual_rows}")


def _check_artifact_fixture(case: dict, errors: list[str]) -> None:
    """`input_mode: artifact` (D5) requires `artifact_fixture: {source, dest}` — the
    checked-in fixture tree under `evals/fixtures/` and the sandbox-relative path where
    runner.py's `_provision_artifact_fixture` copies it before invoking the skill.
    Without this, a case claiming a project folder exists would either fabricate-proof
    itself (if the runner trusted the claim) or fail every run against an empty sandbox
    (if it didn't) — this is what makes the folder real for the duration of one run.
    """
    mode = case.get("input_mode")
    fixture = case.get("artifact_fixture")

    if mode == "artifact" and fixture is None:
        errors.append("input_mode: artifact requires an artifact_fixture: {source, dest} block")
        return
    if fixture is None:
        return
    if mode != "artifact":
        errors.append("artifact_fixture is only meaningful with input_mode: artifact")

    if not isinstance(fixture, dict) or "source" not in fixture or "dest" not in fixture:
        errors.append("artifact_fixture must be a mapping with source and dest")
        return

    source, dest = fixture["source"], fixture["dest"]
    # Unlike `dest`, an absolute `source` is not itself unsafe -- there is no
    # Path(workdir)/source join for it to defeat. What matters is where it resolves to,
    # so containment is the authoritative check, not path style.
    if not isinstance(source, str) or ".." in Path(source).parts:
        errors.append(f"artifact_fixture.source must not contain '..': {source!r}")
    elif not Path(source).resolve().is_relative_to(FIXTURES_ROOT):
        errors.append(f"artifact_fixture.source must be under evals/fixtures/: {source!r}")
    elif not Path(source).is_dir():
        errors.append(f"artifact_fixture.source not found or not a directory: {source}")
    else:
        try:
            reject_symlinks(Path(source))
        except ValueError as e:
            errors.append(f"artifact_fixture.source {e}")
    if not isinstance(dest, str) or Path(dest).is_absolute() or ".." in Path(dest).parts:
        errors.append(f"artifact_fixture.dest must be a relative path with no '..': {dest!r}")


def _check_must_include(expected: dict, errors: list[str]) -> None:
    """`must_include` terms are strings or non-empty lists of alternate phrasings.

    Rejects the shapes that would either crash the scorer or silently collide: a term
    that is neither string nor list, an empty list, a list holding non-strings, and two
    terms resolving to the same canonical key (the later one would overwrite the
    earlier in the results dict, hiding a metric with no error).
    """
    terms = expected.get("must_include")
    if terms is None:
        return
    if not isinstance(terms, list):
        errors.append("expected.must_include must be a list")
        return

    seen: dict[str, int] = {}
    for i, term in enumerate(terms):
        try:
            canonical, _ = must_include_alternates(term)
        except ValueError as e:
            errors.append(f"expected.must_include[{i}]: {e}")
            continue
        if canonical in seen:
            errors.append(
                f"expected.must_include[{i}] repeats canonical key {canonical!r} "
                f"(also at [{seen[canonical]}]) — results would silently collide")
        else:
            seen[canonical] = i


def validate_case(path: Path) -> list[str]:
    """Return a list of problems with one case file (empty means valid)."""
    errors: list[str] = []
    try:
        case = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [f"unparseable YAML: {e}"]
    if not isinstance(case, dict):
        return ["file does not contain a YAML mapping"]

    layer = _check_common(case, path, errors)
    _check_paths(case, errors)
    _check_grading_contract(case, errors)
    _check_dataset_contract(case, errors)
    _check_artifact_fixture(case, errors)
    expected = case.get("expected") or {}

    if layer == 0:
        _check_single_skill(case, errors)
        if not isinstance(expected.get("should_trigger"), bool):
            errors.append("expected.should_trigger must be true or false")

    elif layer == 1:
        _check_single_skill(case, errors)
        if not _is_nonempty_list(expected.get("rubric")):
            errors.append("L1 needs a non-empty expected.rubric list")

    elif layer == 2:
        _check_single_skill(case, errors)
        _check_l2_rubric(case, expected, errors)
        rubric = expected.get("rubric") or case.get("rubric")
        if "must_flag" in expected:
            # An explicit [] is a deliberate clean case: it scores whether the
            # skill raises a false alarm on data with nothing wrong.
            if not isinstance(expected["must_flag"], list):
                errors.append("expected.must_flag must be a list")
        elif not _is_nonempty_list(rubric):
            errors.append("L2 needs expected.must_flag (use [] for a clean case) or a rubric")
        # D9: `_check_severity_patterns` treats any value outside SEVERITIES as "no
        # severity expected" and auto-passes -- a typo here would silently never be
        # checked, at any threshold, on any run, forever.
        severity = expected.get("severity")
        if severity not in (None, "") and severity not in SEVERITIES:
            errors.append(
                f"expected.severity must be one of {sorted(SEVERITIES)} or empty, "
                f"got {severity!r}")

    elif layer == 3:
        _check_single_skill(case, errors)
        # Explicit, not defaulted: the executor picks an interpreter from this, and a
        # case that silently inherits "python" is a case nobody decided the language of.
        if "language" not in case:
            errors.append("L3 needs an explicit language (python or r)")
        lang = case.get("language", "python")
        if lang not in ("python", "r", "R"):
            errors.append(f"unsupported language: {lang}")
        if not expected:
            errors.append("L3 needs an expected block")
        execution_mode = case.get("execution_mode", "standard")
        if execution_mode not in ("standard", "exercise"):
            errors.append("L3 execution_mode must be standard or exercise")
        required_output = case.get("required_output")
        if required_output not in (None, "estimate"):
            errors.append("L3 required_output must be estimate when present")
        if execution_mode == "exercise" and required_output != "estimate":
            errors.append("L3 exercise mode needs required_output: estimate")
        if required_output == "estimate" and execution_mode != "exercise":
            errors.append(
                "L3 required_output: estimate is only valid in exercise mode")
        _check_must_include(expected, errors)

    elif layer == 4:
        # _judge_l4 reads a TOP-LEVEL rubric keyed by dimension. A flat list
        # under expected.rubric yields zero questions and a silent 0.0 score.
        _check_single_skill(case, errors)
        rubric = case.get("rubric")
        if isinstance(expected.get("rubric"), list):
            errors.append(
                "L4 rubric is under expected.rubric as a flat list — the scorer reads a "
                "top-level rubric bucketed by pedagogy/safety/actionable and would score 0.0")
        if not isinstance(rubric, dict):
            errors.append("L4 needs a top-level rubric mapping of dimension -> questions")
        else:
            populated = [d for d in DIMENSIONS if _is_nonempty_list(rubric.get(d))]
            if not populated:
                errors.append(
                    f"L4 rubric has no questions under any of {', '.join(DIMENSIONS)}")
            for key in rubric:
                if key not in DIMENSIONS:
                    errors.append(f"L4 rubric has unknown dimension {key!r}")

    elif layer == 5:
        # run_case_l5_* indexes case["steps"][0] and [1]; score_l5 reads a
        # top-level rubric list. Anything else KeyErrors on every run.
        steps = case.get("steps")
        if not _is_nonempty_list(steps):
            errors.append("L5 needs a top-level steps list (the runner indexes case['steps'])")
        elif len(steps) < 2:
            errors.append(f"L5 needs at least 2 steps, found {len(steps)}")
        else:
            for i, step in enumerate(steps[:2], start=1):
                if not isinstance(step, dict):
                    errors.append(f"step {i} is not a mapping")
                    continue
                if not step.get("skill"):
                    errors.append(f"step {i} missing skill")
                if not step.get("scenario"):
                    errors.append(f"step {i} missing scenario")
        if isinstance(expected.get("rubric"), list):
            errors.append("L5 rubric must be top-level, not under expected")
        if not _is_nonempty_list(case.get("rubric")):
            errors.append("L5 needs a non-empty top-level rubric list")

    elif layer is not None:
        errors.append(f"unknown layer {layer}")

    return errors


# --- Consumed-key schema -------------------------------------------------------
# Every key the scorer and runner actually read, per layer. Anything a case declares
# that is NOT here is dead metadata: it looks like a graded assertion, reads like one
# in review, and is silently ignored at scoring time. Ten L2 cases carried a
# `must_not_miss` list that nothing had ever read.
#
# Keep this in sync with scorer.py by construction: if you add a key to a case, add it
# here only once something consumes it.

# `dataset` is common to every layer, not just L3: runner.py:131 injects the dataset's
# schema into the user_message so the skill can see the columns, regardless of whether
# anything later executes against the file.
_COMMON_TOP = {"name", "description", "layer", "skill", "references", "user_message",
               "expected", "dataset",
               # Grading contract (D1) — legal at every layer, consumed by
               # scorer.py's _judge_l4 (response_contract, deferred_rubric)
               # and by this validator only (input_mode).
               "response_contract", "input_mode", "deferred_rubric",
               # Dataset contract (D4) — consumed by this validator only, checked
               # against the dataset: fixture, never scored or read by the runner.
               "dataset_contract",
               # Artifact fixture (D5) — consumed by this validator and by
               # runner.py's _provision_artifact_fixture; never scored.
               "artifact_fixture"}

# layer -> (extra top-level keys, allowed expected.* keys)
_SCHEMA: dict[int, tuple[set[str], set[str]]] = {
    0: (set(), {"should_trigger"}),
    1: (set(), {"rubric", "method", "alternative_methods", "must_ask",
                "must_not_recommend", "must_warn"}),
    2: ({"rubric"}, {"must_flag", "severity", "rubric"}),
    3: ({"language", "requires", "execution_mode", "required_output"},
        {"true_effect", "tolerance", "values", "values_tolerance", "code_runs",
         "must_include", "must_not_include", "must_include_code"}),
    4: ({"rubric"}, set()),
    5: ({"rubric", "steps"}, set()),
}


def warn_case(path: Path) -> list[str]:
    """Non-fatal smells: keys that look meaningful but the scorer never reads."""
    warnings: list[str] = []
    try:
        case = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return warnings
    if not isinstance(case, dict):
        return warnings

    layer = case.get("layer")
    if layer not in _SCHEMA:
        return warnings
    extra_top, allowed_expected = _SCHEMA[layer]

    for key in sorted(set(case) - _COMMON_TOP - extra_top):
        warnings.append(
            f"top-level {key!r} is not read by the harness at L{layer} — dead metadata")

    expected = case.get("expected") or {}
    if isinstance(expected, dict):
        for key in sorted(set(expected) - allowed_expected):
            warnings.append(
                f"expected.{key} is not read by the harness at L{layer} — dead metadata")
    return warnings


def validate_tree(cases_dir: Path | None = None) -> dict[str, list[str]]:
    """Validate every case, plus cross-case uniqueness. Returns path -> problems."""
    cases_dir = Path(cases_dir) if cases_dir else Path("evals/cases")
    problems: dict[str, list[str]] = {}

    by_name: dict[str, list[str]] = {}
    for path in sorted(cases_dir.rglob("*.yaml")):
        by_name.setdefault(path.stem, []).append(str(path))
        errs = validate_case(path)
        if errs:
            problems[str(path)] = errs

    for name, paths in sorted(by_name.items()):
        if len(paths) > 1:
            # Case names key --case, ledgers and verdicts; a collision shadows one.
            for p in paths:
                problems.setdefault(p, []).append(
                    f"duplicate case name {name!r} also at {', '.join(x for x in paths if x != p)}")
    return problems


def warn_tree(cases_dir: Path | None = None) -> list[str]:
    """Every dead-metadata warning across the tree, as flat 'path: warning' strings.

    Shared with sweep.py's preflight so there is exactly one implementation. Warnings
    were previously reachable only by running this file by hand, which meant a release
    verdict could be built over cases carrying keys nothing reads.
    """
    cases_dir = Path(cases_dir) if cases_dir else Path("evals/cases")
    out: list[str] = []
    for path in sorted(cases_dir.rglob("*.yaml")):
        out.extend(f"{path}: {w}" for w in warn_case(path))
    return out


def main() -> int:
    cases_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/cases")
    paths = sorted(cases_dir.rglob("*.yaml"))
    problems = validate_tree(cases_dir)

    warnings = warn_tree(cases_dir)
    if warnings:
        print("Warnings (non-blocking):")
        for w in warnings:
            print(f"  {w}")
        print()

    if not problems:
        print(f"All {len(paths)} cases valid.")
        return 0

    for path, errs in sorted(problems.items()):
        print(f"\n{path}")
        for e in errs:
            print(f"  - {e}")
    print(f"\n{len(problems)} of {len(paths)} cases invalid.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
