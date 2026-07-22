"""Guard test: shipped Python code must only call networkx APIs that actually exist.

Scope, stated precisely: this currently guards **networkx `nx.*` attribute references
only** (see `_CHECKED`). It is not a general shipped-API checker. Extending it to another
library is a one-line addition to that map, provided the library is a declared eval
dependency so its absence cannot be confused with a defect.

The parity gate executes `evals/parity/reference/*.py`, but it only *text-greps* the
templates — so nothing ever runs the code the plugin actually ships. That gap let
`nx.d_separated` survive in `templates/python/dag.md` and `references/assumptions/dag.md`
after networkx removed it in 3.5. Users who executed the d-separation sections on a
networkx where `d_separated` was unavailable got:

    AttributeError: module 'networkx' has no attribute 'd_separated'

The parity recipe carried the identical call (it mirrors the template), and its failure was
being swallowed as a "known disparity" because the dag baseline documented an unrelated
collider gap. Two independent gates, both blind to the same shipping defect.

This checks attribute references against the *installed* library rather than a hardcoded
blocklist, so the next deprecation is caught without anyone remembering to add it here.

Run: python3 -m pytest evals/test_shipped_apis.py   (from repo root)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Import alias -> module name, for libraries whose attribute use we verify.
#: Only libraries that are a declared eval dependency belong here; anything else may
#: legitimately be absent from this environment.
_CHECKED = {"nx": "networkx"}

#: Attributes that are never module-level API (locals, shadowed names, etc.).
_IGNORE = {"__version__"}

_DIRS = ("templates", "references", "evals/parity/reference")


def _python_blocks(text: str) -> str:
    """Concatenate fenced python blocks; .py files are returned whole."""
    blocks = re.findall(r"```(?:python|py)\n(.*?)```", text, re.DOTALL)
    return "\n".join(blocks)


def _shipped_sources() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for rel in _DIRS:
        root = _REPO_ROOT / rel
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix == ".md":
                code = _python_blocks(path.read_text())
            elif path.suffix == ".py":
                code = path.read_text()
            else:
                continue
            if code.strip():
                out.append((path, code))
    return out


def _referenced_attrs(code: str, alias: str) -> set[str]:
    """`alias.attr` occurrences that the code actually depends on existing.

    Two exclusions:
      - assignment targets (`alias.attr = ...`), which define rather than call;
      - the version-tolerant binding idiom, whose whole purpose is to name an attribute
        that may be absent:
            d_separated = getattr(nx, "is_d_separator", None) or nx.d_separated
        Flagging that line would punish the correct fix for the very bug this guards.
    """
    found = set()
    for m in re.finditer(rf"\b{re.escape(alias)}\.([A-Za-z_][A-Za-z0-9_]*)", code):
        attr = m.group(1)
        line_start = code.rfind("\n", 0, m.start()) + 1
        line_end = code.find("\n", m.end())
        line = code[line_start:line_end if line_end != -1 else len(code)]
        if "getattr(" in line:
            continue
        tail = code[m.end():m.end() + 40]
        if re.match(r"\s*=(?!=)", tail):  # assignment target, not a call
            continue
        found.add(attr)
    return found - _IGNORE


@pytest.mark.parametrize("alias,module_name", sorted(_CHECKED.items()))
def test_shipped_code_only_calls_existing_apis(alias, module_name):
    module = pytest.importorskip(module_name)

    missing: list[str] = []
    for path, code in _shipped_sources():
        for attr in sorted(_referenced_attrs(code, alias)):
            if not hasattr(module, attr):
                rel = path.relative_to(_REPO_ROOT)
                missing.append(f"{rel}: {alias}.{attr}")

    assert not missing, (
        f"shipped code calls {module_name} attributes that do not exist in the installed "
        f"version ({getattr(module, '__version__', '?')}):\n  " + "\n  ".join(missing)
        + "\n\nUse a version-tolerant binding rather than a bare rename, e.g.\n"
          '  d_separated = getattr(nx, "is_d_separator", None) or nx.d_separated')


def test_the_d_separated_migration_stayed_migrated():
    """The specific regression this file was written for: a bare `nx.d_separated` call
    (as opposed to the compatibility binding) must not come back."""
    offenders = []
    for path, code in _shipped_sources():
        for line_no, line in enumerate(code.splitlines(), 1):
            if "nx.d_separated" in line and "getattr(" not in line:
                offenders.append(f"{path.relative_to(_REPO_ROOT)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "bare nx.d_separated calls found; networkx removed it in 3.5:\n  "
        + "\n  ".join(offenders))
