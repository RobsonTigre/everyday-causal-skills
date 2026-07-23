"""Guard tests: the pyproject `evals` extra must declare every Python package the
eval environment actually executes, and every declared pip-name must really provide
the import-name the templates use.

The second test is the one that matters. `templates/python/timeseries.md` used to map
import-name `causalimpact` to pip-name `"causalimpact"`, but the code was written
against `pycausalimpact` — a different distribution that happens to install a module
of the same name. Because the import line is identical under both, the mismatch was
invisible until an accessor was touched, and it survived two rounds of review being
misdiagnosed as a template bug. A name-to-distribution check catches that class of
error directly.

Run: python3 -m pytest evals/test_env_deps.py   (from repo root)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_PY_TEMPLATES = _REPO_ROOT / "templates" / "python"
_R_TEMPLATES = _REPO_ROOT / "templates" / "r"
_LAYER3 = _REPO_ROOT / "evals" / "cases" / "layer3"

# Import names that ship with CPython or are otherwise never pip-declared.
_STDLIB_OK = {"importlib", "os", "sys", "json", "re", "math", "random"}


def _normalize(name: str) -> str:
    """PEP 503 normalization: lowercase, runs of -_. collapse to a single -."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _extra_packages(extra: str) -> set[str]:
    """Package names declared in one [project.optional-dependencies] array,
    following self-references like `everyday-causal-skills-evals[parity]`."""
    text = _PYPROJECT.read_text()
    m = re.search(rf"(?ms)^\s*{re.escape(extra)}\s*=\s*\[(.*?)^\]", text)
    assert m, f"pyproject.toml has no `{extra}` optional-dependencies array"

    names: set[str] = set()
    for raw in re.findall(r'"([^"]+)"', m.group(1)):
        base = re.split(r"[<>=!~;\s\[]", raw, 1)[0].strip()
        if not base:
            continue
        # Self-reference (`everyday-causal-skills-evals[parity]`) pulls in that extra.
        ref = re.match(r'^[^\[]+\[([^\]]+)\]', raw)
        if ref and _normalize(base) == _normalize("everyday-causal-skills-evals"):
            for nested in ref.group(1).split(","):
                names |= _extra_packages(nested.strip())
            continue
        names.add(_normalize(base))
    return names


def _template_preflight_maps() -> dict[str, str]:
    """import-name -> pip-name, harvested from every Python template's preflight.

    Covers both `required = {...}` (hard-gated, always needed) and `optional = {...}`
    (D7: variant-only packages, e.g. `templates/python/timeseries.md`'s CausalImpact vs
    CausalArima split — noted but not blocked for a live user, per
    `references/preflight.md`'s "Required vs optional"). The eval harness still needs
    both installed to execute every L3 case regardless of that user-facing framing, so
    this guard treats them identically for pyproject-coverage purposes.
    """
    mapping: dict[str, str] = {}
    for path in sorted(_PY_TEMPLATES.glob("*.md")):
        text = path.read_text()
        for block in re.findall(r"(?:required|optional)\s*=\s*\{(.*?)\}", text, re.S):
            for imp, pip in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', block):
                mapping[imp] = pip
    assert mapping, "no preflight `required = {...}` maps found in templates/python"
    return mapping


def _l3_python_requires() -> set[str]:
    """Import names declared by `requires:` on Python-executed L3 cases."""
    req: set[str] = set()
    for path in sorted(_LAYER3.glob("*.yaml")):
        case = yaml.safe_load(path.read_text()) or {}
        # Absent `language` falls to the scorer's Python default.
        if (case.get("language") or "python").lower() != "python":
            continue
        for mod in case.get("requires") or []:
            req.add(mod)
    return req


def _r_template_required_packages() -> set[str]:
    """R package names declared in any R template's `required <- c(...)` preflight.

    R has no pyproject-equivalent lockfile, so unlike the Python guard this can't check
    installability -- it checks documentation: every package an R-executed L3 case
    depends on must be named in some template's Prerequisites block, or a live user
    following that template has no way to know they need it before the skill's
    generated code fails on a missing library().
    """
    packages: set[str] = set()
    for path in sorted(_R_TEMPLATES.glob("*.md")):
        text = path.read_text()
        for block in re.findall(r"required\s*<-\s*c\((.*?)\)", text, re.S):
            packages.update(re.findall(r'"([^"]+)"', block))
    return packages


def _l3_r_requires() -> set[str]:
    """R package names declared by `requires:` on R-executed L3 cases (D7)."""
    req: set[str] = set()
    for path in sorted(_LAYER3.glob("*.yaml")):
        case = yaml.safe_load(path.read_text()) or {}
        if (case.get("language") or "python").lower() != "r":
            continue
        for pkg in case.get("requires") or []:
            req.add(pkg)
    return req


def test_r_l3_requires_are_documented_in_r_templates():
    documented = _r_template_required_packages()
    missing = sorted(_l3_r_requires() - documented)
    assert not missing, (
        f"L3 R cases declare `requires:` packages not documented in any "
        f"templates/r/*.md Prerequisites block: {missing}. A live user following the "
        "template has no way to know they need these."
    )


def test_evals_extra_covers_templates_and_l3_cases():
    declared = _extra_packages("evals")
    preflight = _template_preflight_maps()

    required = {_normalize(pip) for pip in preflight.values()}
    for mod in _l3_python_requires():
        if mod in _STDLIB_OK:
            continue
        # A case names the import; translate via the templates' own map when known.
        required.add(_normalize(preflight.get(mod, mod)))

    missing = sorted(required - declared)
    assert not missing, (
        f"pyproject [evals] extra is missing packages the eval environment runs: "
        f"{missing}. Add them so `pip install -e \".[evals]\"` reproduces a complete "
        "eval environment."
    )


def test_declared_pip_names_provide_their_import_names():
    """Every template's declared pip-name must be the distribution that actually
    supplies the import-name next to it. Skips packages absent from this env, so the
    test is honest rather than green-by-omission."""
    from importlib.metadata import packages_distributions

    provides = packages_distributions()
    mismatches = []
    for imp, pip in sorted(_template_preflight_maps().items()):
        dists = provides.get(imp)
        if not dists:
            continue  # not installed here; test_evals_extra_* covers declaration
        if _normalize(pip) not in {_normalize(d) for d in dists}:
            mismatches.append(
                f"template maps import '{imp}' -> pip '{pip}', but '{imp}' is "
                f"actually provided by {sorted(dists)}"
            )
    assert not mismatches, "\n".join(mismatches)


def test_causalimpact_resolves_to_pycausalimpact():
    """Regression lock on the specific mixup: two distributions install a module
    named `causalimpact`, and only pycausalimpact matches the shipped template code."""
    from importlib.metadata import packages_distributions

    dists = packages_distributions().get("causalimpact")
    if not dists:
        pytest.skip("causalimpact not installed in this environment")
    assert {_normalize(d) for d in dists} == {"pycausalimpact"}, (
        f"`causalimpact` is provided by {sorted(dists)}, expected pycausalimpact. "
        "The `causalimpact` distribution has a different API (needs .run(), has no "
        "summary_data) and inverted effect-bound labels."
    )
