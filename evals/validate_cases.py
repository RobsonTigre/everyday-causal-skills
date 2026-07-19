"""Static schema check for eval cases.

A case whose shape the runner cannot consume fails identically to a skill that
answers badly — except it fails on every run, forever, and burns live model
calls proving it. Several such cases sat in the tree for months. This validator
catches that class before a sweep starts, not after.

Run: python3 evals/validate_cases.py   (from repo root)
Exits 0 when every case is well formed, 1 with a per-case list otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorer import must_include_alternates  # noqa: E402

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
        rubric = expected.get("rubric") or case.get("rubric")
        if "must_flag" in expected:
            # An explicit [] is a deliberate clean case: it scores whether the
            # skill raises a false alarm on data with nothing wrong.
            if not isinstance(expected["must_flag"], list):
                errors.append("expected.must_flag must be a list")
        elif not _is_nonempty_list(rubric):
            errors.append("L2 needs expected.must_flag (use [] for a clean case) or a rubric")

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
               "expected", "dataset"}

# layer -> (extra top-level keys, allowed expected.* keys)
_SCHEMA: dict[int, tuple[set[str], set[str]]] = {
    0: (set(), {"should_trigger"}),
    1: (set(), {"rubric", "method", "alternative_methods", "must_ask",
                "must_not_recommend", "must_warn"}),
    2: ({"rubric"}, {"must_flag", "severity", "rubric"}),
    3: ({"language", "requires"},
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
