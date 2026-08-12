# Batch: parent-liveness-module

```yaml
task: 'mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution'
batch: parent-liveness-module
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Adds the #817 dead-parent-branch-detection primitives to `plugins/mill/scripts/_parent_branch.py`: a cheap liveness check (`check_liveness`) and the archive-tag chain-walk (`resolve_dead_parent`) that resolves a dead parent branch to a live successor, falls back to the configured base branch, or reports a cycle. This batch is pure Python with no SKILL.md wiring — batches 2 and 3 call these two functions from `mill-merge/SKILL.md` and `mill-merge-in/SKILL.md` respectively; batch 4's integration tests exercise both functions directly against real git repos with real `archive/<slug>` tags. External interface for downstream batches: `_parent_branch.check_liveness(branch: str, git_root: Path) -> bool` and `_parent_branch.resolve_dead_parent(dead_branch: str, git_root: Path, cfg: dict, *, max_hops: int = 10) -> dict`, whose return shape is fixed by the overview's `liveness-check-contract` Shared Decision.

## Cards

### Card 1: Extract reusable status.md parent-row parser; add `check_liveness`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `import _subprocess_util` to the top-level imports (alongside the existing `from pathlib import Path`).
  - Extract the body of the existing `_read_parent_from_status` loop (the `for line in lines:` block that scans the fenced yaml block for `parent:`/`slug:` rows, plus the `expected_slug` mismatch check that follows it) into a new module-level function:
    ```python
    def _parse_parent_from_yaml_text(text: str, *, expected_slug: str | None = None) -> str | None:
    ```
    with the same docstring content as `_read_parent_from_status`'s existing docstring (the parsing-semantics paragraphs — the "scans the first fenced yaml block" / `expected_slug` guard description — move to this function since they now describe its behavior, not the file-reading behavior).
  - Rewrite `_read_parent_from_status` to do only the file read (unchanged `try: text = status_path.read_text(...) except FileNotFoundError: return None` block) and then `return _parse_parent_from_yaml_text(text, expected_slug=expected_slug)`. Its own docstring shrinks to describe only the file-reading contract, cross-referencing `_parse_parent_from_yaml_text` for the parsing rules.
  - Add a new module-level function:
    ```python
    def check_liveness(branch: str, git_root: Path) -> bool:
    ```
    Body: run `_subprocess_util.run(["git", "-C", str(git_root), "ls-remote", "--exit-code", "origin", branch], check=False)` and return `result.returncode == 0`. Docstring: one line — "Return True if `branch` currently exists on `origin` (`git ls-remote --exit-code`)." Note in the docstring that `git branch -a` / local remote-tracking refs are deliberately not used as the liveness signal, because `mill-cleanup`'s remote-branch deletion never prunes them (a torn-down parent's stale local `origin/<branch>` ref would otherwise report as alive).
  - Update the module docstring's `Public API` list (top of file) to add `check_liveness` and `resolve_dead_parent` (the latter added by Card 2) as new bullets, one line each, matching the existing bullet style for `resolve` / `resolve_for_codeguide`.
- **Commit:** `refactor(mill): extract _parse_parent_from_yaml_text; add _parent_branch.check_liveness`

### Card 2: Add `resolve_dead_parent` archive-tag chain-walk

- **Context:**
  - `plugins/mill/scripts/_archive_tag.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new module-level function in `_parent_branch.py`:
    ```python
    def resolve_dead_parent(dead_branch: str, git_root: Path, cfg: dict, *, max_hops: int = 10) -> dict:
    ```
  - Docstring documents the three possible return shapes verbatim: `{"outcome": "resolved", "branch": <live-branch>, "hops": [<slug>, ...]}`, `{"outcome": "fallback", "reason": "no-tag" | "chain-end", "branch": <base_branch>, "hops": [...]}`, `{"outcome": "cycle", "hops": [...]}` — matching the overview's `liveness-check-contract` Shared Decision exactly.
  - Implementation, one hop per loop iteration, `for _ in range(max_hops):`:
    1. `prefix = cfg.get("spawn", {}).get("branch_prefix", "")` and `base_branch = cfg.get("git", {}).get("base_branch", "main")` — read once, before the loop, reusing the exact `removeprefix` pattern `_marker.py`'s `slug_from_branch` uses at its `slug = branch.removeprefix(prefix)` line.
    2. Inside the loop: `slug = branch.removeprefix(prefix)` (where `branch` starts as `dead_branch` and is reassigned to the resolved-but-still-dead parent on each subsequent iteration); append `slug` to a `hops: list[str]` accumulator declared before the loop.
    3. Check tag existence: `_subprocess_util.run(["git", "-C", str(git_root), "rev-parse", "--verify", "--quiet", f"refs/tags/archive/{slug}"], check=False)`. Non-zero return code → return `{"outcome": "fallback", "reason": "no-tag", "branch": base_branch, "hops": hops}` immediately (fallback trigger (a): chain is unresolvable because this ancestor was never archived).
    4. Read the pre-cleanup-commit status.md: try `_subprocess_util.run(["git", "-C", str(git_root), "show", f"archive/{slug}~1:_mill/status.md"], check=False)` first; on non-zero return code, retry with `f"archive/{slug}~1:task/status.md"` (the documented legacy-layout fallback `_paths.resolve_task_path` uses elsewhere). If both fail, return `{"outcome": "fallback", "reason": "chain-end", "branch": base_branch, "hops": hops}` (fallback trigger (b), first sub-case: neither status.md layout exists at that tree).
    5. Parse the successful `show` output's stdout via `_parse_parent_from_yaml_text(text)` (no `expected_slug` — chain-walk trusts the historical tree). `None` result → same `{"outcome": "fallback", "reason": "chain-end", ...}` as step 4 (fallback trigger (b), second sub-case: the status.md exists but has no `parent:` row) — both sub-cases collapse to the identical return since operationally they mean the same thing (no further parent information at this hop).
    6. Call `check_liveness(parent, git_root)` on the parsed `parent` value. If alive: return `{"outcome": "resolved", "branch": parent, "hops": hops}`. If dead: set `branch = parent` and continue the loop (next iteration re-derives `slug` from this new dead branch).
    7. If the loop completes all `max_hops` iterations without returning (every hop stayed dead), return `{"outcome": "cycle", "hops": hops}` after the loop — this is the pathological-cycle guard from the decision; it fires on a genuine cycle exactly as fast as on `max_hops` independent dead hops in a row, since the function has no separate visited-set cycle detector (the hop cap is the only guard, per the decision's own wording: "capped at 10 hops to guard against a pathological cycle").
- **Commit:** `feat(mill): add _parent_branch.resolve_dead_parent archive-tag chain-walk`

## Batch Tests

`verify:` runs the existing `test-parent-branch.py` unit test — it exercises `resolve` / `resolve_for_codeguide`, both of which now route through the refactored `_parse_parent_from_yaml_text` helper Card 1 introduces, so a passing run confirms the refactor preserved existing behavior. `check_liveness` and `resolve_dead_parent` are not unit-tested here — both are pure git-plumbing functions (remote lookups, tag lookups, historical `git show` reads) that need a real git remote and real `archive/<slug>` tags to exercise meaningfully; per `_mill/discussion.md`'s `testing-approach` Decision, they get integration-test coverage instead, in batch 4 (`04-integration-tests.md`), against real git repos with real tags.
