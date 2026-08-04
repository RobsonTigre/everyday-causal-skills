"""Repository governance audit: find work that exists but nothing points at.

Written after a stash holding eight real `evals/results/HISTORY.md` rows spent
six weeks in `refs/rescue/history-2026-04-06`, invisible to `git branch -a`,
`git tag` and `git stash list` alike. The data survived; the only reason anyone
found it was an exhaustive `git for-each-ref`. This makes that sweep one
command instead of a lucky guess.

Run: python3 evals/repo_doctor.py   (from repo root)
Exits 0 when no blocker is found, 1 otherwise. Notes never affect the exit code.

Two rules it enforces that are easy to break by accident:

- **Preserve with tags, never ad-hoc ref namespaces.** A tag appears in
  `git tag`, pushes by default and carries a message saying why it exists.
  Anything under `refs/<something-else>/` appears in none of those.
- **A run's ledger row is committed with the run.** Loose `HISTORY.md` rows in
  the working tree are what a pre-merge `git stash` silently swallows.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HISTORY = "evals/results/HISTORY.md"
TRUNK = "main"

# refs/heads, refs/tags and refs/remotes are the namespaces every standard git
# command lists. Anything else is invisible to routine inspection.
STANDARD_NAMESPACES = ("refs/heads/", "refs/tags/", "refs/remotes/")

HISTORY_ROW = re.compile(r"^\| \d{4}-\d{2}-\d{2} ")


def _git(*args: str) -> str:
    """Run git in the repo and return stdout, or '' if the command failed."""
    proc = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _is_ancestor(sha: str, of: str = TRUNK) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, of],
            cwd=REPO,
            capture_output=True,
        ).returncode
        == 0
    )


def parse_refs(for_each_ref_output: str) -> list[tuple[str, str]]:
    """Split `git for-each-ref` output into (refname, sha) pairs."""
    refs = []
    for line in for_each_ref_output.splitlines():
        if " " in line:
            name, _, sha = line.partition(" ")
            refs.append((name, sha))
    return refs


def nonstandard_refs(refs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Refs outside heads/tags/remotes — the namespaces nothing routinely lists."""
    return [
        (name, sha)
        for name, sha in refs
        if not name.startswith(STANDARD_NAMESPACES)
    ]


def added_history_rows(diff_output: str) -> list[str]:
    """Ledger rows added but not committed, read from a HISTORY.md diff."""
    return [
        line[1:]
        for line in diff_output.splitlines()
        if line.startswith("+") and HISTORY_ROW.match(line[1:])
    ]


def check_refs() -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    notes: list[str] = []
    refs = parse_refs(_git("for-each-ref", "--format=%(refname) %(objectname)"))

    for name, sha in nonstandard_refs(refs):
        short = sha[:7]
        reachable = "reachable from" if _is_ancestor(sha) else "NOT in"
        blockers.append(
            f"{name} ({short}) lives outside refs/heads, refs/tags and "
            f"refs/remotes, so no routine git command lists it. "
            f"It is {reachable} {TRUNK}. "
            f"Preserve it as an annotated tag instead, then delete the ref."
        )

    for name, sha in refs:
        if not name.startswith("refs/heads/"):
            continue
        branch = name[len("refs/heads/") :]
        if branch == TRUNK or _is_ancestor(sha):
            continue
        ahead = _git("rev-list", "--count", f"{TRUNK}..{sha}") or "?"
        notes.append(
            f"branch {branch} ({sha[:7]}) has {ahead} commits not in {TRUNK} "
            f"— active work, or forgotten?"
        )
    return blockers, notes


def check_history_rows() -> tuple[list[str], list[str]]:
    """Loose ledger rows are what a pre-merge stash swallows. Block on them."""
    unstaged = added_history_rows(_git("diff", "--", HISTORY))
    staged = added_history_rows(_git("diff", "--cached", "--", HISTORY))
    rows = unstaged + staged
    if not rows:
        return [], []
    dates = ", ".join(sorted({r.split("|")[1].strip()[:10] for r in rows}))
    return [
        f"{HISTORY} has {len(rows)} uncommitted row(s) ({dates}). "
        f"Commit them with the run that produced them — a pre-merge stash "
        f"will otherwise carry them off and they will not come back."
    ], []


def check_worktrees_and_stashes() -> tuple[list[str], list[str]]:
    notes: list[str] = []
    worktrees = [
        line.split()[0]
        for line in _git("worktree", "list").splitlines()
        if line.strip()
    ]
    for path in worktrees[1:]:
        notes.append(f"worktree {path} — confirm its ignored files are archived before removal")

    stashes = [s for s in _git("stash", "list").splitlines() if s.strip()]
    for s in stashes:
        notes.append(f"stash: {s} — stashes are dropped silently; promote to a tag if it matters")
    return [], notes


def check_unpushed() -> tuple[list[str], list[str]]:
    upstream = _git("rev-parse", "--abbrev-ref", f"{TRUNK}@{{upstream}}")
    if not upstream:
        return [], [f"{TRUNK} has no upstream — nothing is backed up off this machine"]
    count = _git("rev-list", "--count", f"{upstream}..{TRUNK}")
    if count and count != "0":
        return [], [
            f"{count} commits on {TRUNK} are not on {upstream} "
            f"— they exist only on this machine"
        ]
    return [], []


def stale_results(recorded: list[tuple[str, str]], head: str) -> list[tuple[str, str]]:
    """(name, detail) for each stored result whose measured commit is not HEAD.

    A sweep is a statement about three things at once — the skill, the case and the
    harness. When any of them moves, the stored numbers describe a tree that is gone.
    The commit is the cheapest decisive proxy: if it is not HEAD, the result cannot be
    cited as current without checking what changed.

    Pure by design so it can be tested without a repository. The caller does the IO.
    """
    out: list[tuple[str, str]] = []
    for name, commit in recorded:
        if commit == head:
            continue
        if commit:
            detail = (f"measured at {commit[:7]}, HEAD is {head[:7]} "
                      f"— not evidence about the current tree")
        else:
            detail = (f"no commit recorded, HEAD is {head[:7]} "
                      f"— cannot describe any tree")
        out.append((name, detail))
    return out


def stale_results_note(stale: list[tuple[str, str]], total: int) -> list[str]:
    """At most one line. An alert that fires 21 times is an alert nobody reads.

    Every stored sweep predates HEAD the moment anything is committed, so listing them
    individually buries every other finding. Report the scale and name the newest one —
    that is the result somebody is about to cite.
    """
    if not stale:
        return []
    newest, detail = stale[-1]
    return [
        f"{len(stale)} of {total} stored sweeps predate HEAD; newest is {newest} "
        f"({detail}). Re-measure before citing any of them as current."
    ]


def _recorded_result_commits() -> list[tuple[str, str]]:
    """(name, commit) for every stored ledger and release verdict under evals/results."""
    results = REPO / "evals" / "results"
    if not results.exists():
        return []
    found: list[tuple[str, str]] = []
    paths = sorted(results.glob("*/ledger.json")) + sorted(results.glob("verdict-v*.json"))
    for path in paths:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        commit = str((data.get("fingerprint") or {}).get("commit") or "")
        found.append((path.parent.name if path.name == "ledger.json" else path.name, commit))
    return found


def check_stale_results() -> tuple[list[str], list[str]]:
    """Stored sweeps that no longer describe HEAD. Notes, never blockers.

    An expired result is not a defect — it is a correct record of a tree that has since
    moved. It becomes a problem only when someone reads it as current, which is exactly
    what happened on 2026-08-04.
    """
    head = _git("rev-parse", "HEAD")
    if not head:
        return [], []
    recorded = _recorded_result_commits()
    return [], stale_results_note(stale_results(recorded, head), len(recorded))


def check_integrity() -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    notes: list[str] = []
    proc = subprocess.run(
        ["git", "fsck", "--no-progress"], cwd=REPO, capture_output=True, text=True
    )
    for line in proc.stderr.splitlines():
        if line.startswith("error:"):
            blockers.append(f"git fsck: {line[len('error:'):].strip()}")

    junk = list((REPO / ".git").rglob(".DS_Store"))
    for path in junk:
        notes.append(f"{path.relative_to(REPO)} — Finder junk inside .git; safe to delete")

    dangling = len(
        [
            line
            for line in proc.stdout.splitlines()
            if line.startswith("dangling commit")
        ]
    )
    if dangling:
        notes.append(
            f"{dangling} dangling commit(s) — usually dropped stashes. "
            f"They expire from the object database; tag any you want to keep."
        )
    return blockers, notes


CHECKS = (
    ("refs", check_refs),
    ("ledger rows", check_history_rows),
    ("worktrees and stashes", check_worktrees_and_stashes),
    ("backup", check_unpushed),
    ("stale results", check_stale_results),
    ("integrity", check_integrity),
)


def main() -> int:
    all_blockers: list[str] = []
    all_notes: list[str] = []

    for label, check in CHECKS:
        blockers, notes = check()
        all_blockers += [f"[{label}] {b}" for b in blockers]
        all_notes += [f"[{label}] {n}" for n in notes]

    if all_blockers:
        print("BLOCKERS\n")
        for b in all_blockers:
            print(f"  - {b}\n")

    if all_notes:
        print("NOTES\n")
        for n in all_notes:
            print(f"  - {n}")
        print()

    if all_blockers:
        print(f"{len(all_blockers)} blocker(s), {len(all_notes)} note(s).")
        return 1

    print(f"No blockers. {len(all_notes)} note(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
