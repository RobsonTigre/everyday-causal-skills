"""Guard test: the six plugin manifests must agree on one version string.

The plugin ships as a single bundle — nothing installs or upgrades a skill on its own —
so the manifests are the only source of version truth. Until now they agreed by manual
discipline alone: there is no CI, no Makefile, and the sole git hook runs parity. A
sixth-manifest miss is silent and ships.

This replaces the old per-skill `metadata.version` field, which 14 SKILL.md files carried
and no code ever read. It had already drifted (12 skills at 0.3.3, one at 0.3.2, one at
0.1.1, none at the plugin's 0.6.0) while `docs/contribution-checklist.md` instructed
keeping it in sync — stale metadata that looked authoritative.

Run: python3 -m pytest evals/test_manifests.py   (from repo root)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent

# manifest path -> dotted location of the version string within it
_MANIFESTS: dict[str, str] = {
    ".claude-plugin/plugin.json": "version",
    ".claude-plugin/marketplace.json": "plugins.0.version",
    ".codex-plugin/plugin.json": "version",
    ".cursor-plugin/plugin.json": "version",
    "plugin.json": "version",
    "gemini-extension.json": "version",
}

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _dig(data, dotted: str):
    """Walk a dotted path; numeric segments index into lists."""
    cur = data
    for seg in dotted.split("."):
        cur = cur[int(seg)] if seg.isdigit() else cur[seg]
    return cur


def _manifest_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for rel, dotted in _MANIFESTS.items():
        path = _REPO_ROOT / rel
        assert path.exists(), f"manifest missing: {rel}"
        try:
            out[rel] = _dig(json.loads(path.read_text()), dotted)
        except (KeyError, IndexError, TypeError) as exc:
            pytest.fail(f"{rel}: no version at {dotted!r} ({exc})")
    return out


def test_all_six_manifests_share_one_version():
    versions = _manifest_versions()
    distinct = sorted(set(versions.values()))
    assert len(distinct) == 1, (
        "plugin manifests disagree on version — they ship as one bundle and must match:\n"
        + "\n".join(f"  {rel}: {v}" for rel, v in sorted(versions.items()))
    )


def test_manifest_version_is_semver():
    version = next(iter(_manifest_versions().values()))
    assert _SEMVER.match(version), (
        f"manifest version {version!r} is not MAJOR.MINOR.PATCH")


def _frontmatter(path: Path) -> dict:
    """The YAML frontmatter block, parsed. {} when absent or unparseable."""
    parts = path.read_text().split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def test_skills_declare_no_version_of_their_own():
    """Skills are not independently versioned. A reintroduced `version` would be
    unenforced and would drift, which is what this deletion fixed.

    Parses the frontmatter rather than regexing the file. The first attempt used
    `^\\s+version:`, which requires indentation — so a TOP-LEVEL `version:` escaped the
    policy the test claimed to enforce, and a `version:` mentioned anywhere in the prose
    body would have produced a false positive.
    """
    offenders = []
    for path in sorted((_REPO_ROOT / "skills").glob("*/SKILL.md")):
        fm = _frontmatter(path)
        rel = str(path.relative_to(_REPO_ROOT))
        if "version" in fm:
            offenders.append(f"{rel} (top-level `version`)")
        if isinstance(fm.get("metadata"), dict) and "version" in fm["metadata"]:
            offenders.append(f"{rel} (`metadata.version`)")

    assert not offenders, (
        "SKILL.md frontmatter must not carry `version` at any level — the six plugin "
        f"manifests are the single source of version truth. Found in: {offenders}")
