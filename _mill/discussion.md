# Discussion: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading

```yaml
task: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading
slug: mill-junction-and-agent-gaps
status: discussing
parent: main
```

## Problem

Three bugs filed during the `mill-nested-hub-and-skill-sync` and `mill-agent-and-implement-contracts` sessions:

1. `_junction.strip_all_in_worktree` (the mandatory safety prelude before `git worktree remove` / `safe_rmtree`) scans only the worktree root, one level deep. In repos where `hub_relative_path` is a subdir (e.g. `src/csharp/NORCE.Models`), mill-spawn creates junctions there (`<worktree>/src/csharp/NORCE.Models/.wiki`, `.portals`), not at the root. The scan finds nothing, `remove_safe` then chokes on the live junction with "Invalid argument" (matched as WorktreeLockedError), and the worktree husk survives with a live `.wiki` pointing at the real wiki clone. A subsequent manual recursive delete destroyed the wiki's `.git` on 2026-06-17.

2. `millpy-merge-in-subagent.py` runs the plan's `verify:` command via `subprocess.run(cmd, shell=True)` in three places (initial verify-fix check, finalize stage post-agent check, full-stage post-agent re-verification). On Windows `shell=True` routes through cmd.exe, which cannot parse the POSIX `PYTHONPATH= uv run ...` prefix that CLAUDE.md mandates for every Python verify command. Result: false-positive `stuck:verify` during `mill-merge-in` verify replay. The identical fix was already applied to `_implementer_common._run_verify_gate` (bash-routing on Windows) but not to the merge-in subagent.

3. `millpy-review-plan.py --stage finalize` requires `--round` but the mill-plan SKILL only says "follow the Agent-mode dispatch pattern from mill-go". Mill-go's pattern mentions threading `--round` for review CLIs in step 6, but mill-plan's Phase: Plan Review doesn't spell it out explicitly (unlike mill-start, which does). The result is a spurious `verdict: ERROR` on the first finalize attempt.

## Scope

**In:**
- `plugins/mill/scripts/_junction.py` — recursive junction walk in `strip_all_in_worktree`
- `plugins/mill/scripts/_implementer_common.py` — extract `_posix_shell_run_args` helper
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — use `_posix_shell_run_args` in all three verify calls
- `plugins/mill/scripts/millpy-review-plan.py` — auto-discover `round` in finalize when `--round` absent
- `plugins/mill/scripts/millpy-review-discussion.py` — same auto-discovery for symmetry
- `plugins/mill/unit_tests/test-junction.py` — regression test for nested-junction case
- `plugins/mill/unit_tests/test-merge-in-subagent.py` — test for `_posix_shell_run_args` routing

**Out:**
- mill-plan SKILL (`plugins/mill/skills/mill-plan/SKILL.md`) — the CLI fix makes the explicit threading instruction unnecessary; no SKILL edit
- mill-start SKILL — already documents `--round` threading correctly; no change
- mill-go SKILL — Agent-mode dispatch description already says to thread `--round`; no change
- `millpy-implement.py`, `millpy-fix.py` — no verify command routing issues (they use `_run_verify_gate` which is already fixed)
- `_review_common.discover_round` — no changes to the helper itself

## Decisions

### Recursive walk over declared-list approach for junction stripping

- Decision: Walk the worktree tree recursively, stopping at any junction/symlink (do not descend into them); strip every junction/symlink found regardless of depth.
- Rationale: Catches undeclared/legacy junctions at any depth; works regardless of `hub_relative_path`; no coupling to mill-config.yaml's junctions block.
- Rejected: Declared-list approach — only strips known junctions; misses legacy `.active` and any hub-relative path variations not in config.

### junctions_cfg parameter retained in strip_all_in_worktree

- Decision: Keep the `junctions_cfg` parameter on `strip_all_in_worktree` (unused by the new recursive walk).
- Rationale: The only caller is `_worktree.remove_safe`. Removing the param would require touching `remove_safe`'s call site in this fix, mixing a signature change with the bug fix. This round changes only the walk logic; param cleanup is a separate task.
- Rejected: Drop the param and update `remove_safe` — adds scope to this fix for a cosmetic change.

### No max-depth guard on recursive walk

- Decision: Recurse without a depth limit.
- Rationale: Mill worktrees are shallow by construction (hub subdir + `_mill/` + source tree); no known pathological case justifies the extra complexity.
- Rejected: Max-depth guard — YAGNI; adds dead code for a scenario that has never occurred.

### Shared bash-routing helper in `_implementer_common.py`

- Decision: Extract `_posix_shell_run_args(cmd: str) -> tuple[list[str] | str, dict]` at module level in `_implementer_common.py`; import and use it in `millpy-merge-in-subagent.py`.
- Rationale: `millpy-merge-in-subagent.py` already imports from `_implementer_common`; extracting avoids duplicating the bash detection logic.
- Rejected: Inline bash routing in `millpy-merge-in-subagent.py` — duplication.

### `--round` auto-discovery in finalize (not SKILL fix)

- Decision: When `--round` is absent in `--stage finalize`, call `discover_round(reviews_dir, review_type, "holistic")` to compute the same round that prepare would return. Remove the hard error.
- Rationale: Prepare and finalize become symmetric (both can discover round independently); removes the foot-gun from the SKILL caller's perspective; option (a) from issue #507.
- Rejected: SKILL-only fix — still requires all callers to thread `--round`; the CLI foot-gun remains.

### Apply `--round` fix to both review CLIs

- Decision: Apply the auto-discovery change to both `millpy-review-plan.py` and `millpy-review-discussion.py`.
- Rationale: Symmetry; mill-start already threads `--round` explicitly so this is belt-and-suspenders for discussion, but the pattern should be consistent.
- Rejected: Only fix review-plan — inconsistency between CLIs with no structural reason for it.

## Technical context

### Fix 1 — `_junction.strip_all_in_worktree`

File: `plugins/mill/scripts/_junction.py`, function `strip_all_in_worktree` at line 279.

Current implementation:
```python
with os.scandir(str(worktree_path)) as it:
    for entry in it:
        ep = Path(entry.path)
        if entry.is_symlink() or _is_junction_or_symlink(ep):
            remove(ep)
            removed.append(ep)
```
This is a single-level scan of `worktree_path` (the git worktree root). Junctions placed at `<worktree>/<hub_relative_path>/` are under a real subdirectory (`src/`, etc.) and are not seen.

Replacement: a recursive helper (or `os.walk`-equivalent) that descends into real directories but stops at junctions/symlinks. Pseudocode:
```
def _walk(dir_path):
    try:
        entries = list(os.scandir(dir_path))
    except PermissionError:
        # Print a warning so the operator knows a subdir was skipped.
        # Silently swallowing would reproduce the wiki-destruction failure if
        # a junction lives in an ACL-restricted dir.
        print(f"[junction] WARNING: permission denied scanning {dir_path}; junctions inside may survive", file=sys.stderr)
        return
    for entry in entries:
        ep = Path(entry.path)
        if is_junction_or_symlink(ep):
            remove(ep); removed.append(ep)  # do NOT descend
        elif entry.is_dir():
            _walk(ep)  # real dir — recurse
```
`entry.is_dir()` is checked AFTER the junction guard, so a junction-to-directory (which `is_dir()` returns True for on Windows) is never descended into. The `FileNotFoundError` guard wraps the outer call (missing worktree → `[]`). `PermissionError` on an inner scandir prints a warning and skips that subtree — not silently swallowed, so an operator can detect and investigate.

The `junctions_cfg` parameter is retained for backward compatibility (callers still pass it) but continues to be unused.

### Fix 2 — bash-routing for verify commands

New helper in `plugins/mill/scripts/_implementer_common.py` (after existing imports, before `_run_verify_gate`):
```python
def _posix_shell_run_args(cmd: str) -> tuple:
    bash = shutil.which("bash") if os.name == "nt" else None
    if bash:
        return [bash, "-c", cmd], {}
    return cmd, {"shell": True}
```
`_run_verify_gate` already contains this logic inline (lines ~130-136); refactor to call the new helper.

In `millpy-merge-in-subagent.py`:
- Add `_posix_shell_run_args` to the `from _implementer_common import ...` line.
- Three call sites: lines ~176 (finalize stage post-agent), ~275 (full stage initial check), ~341 (full stage post-agent re-verification). All follow the same shape:
  ```python
  result = subprocess.run(args.cmd, shell=True, capture_output=True, text=True, cwd=project_root)
  ```
  Replace with:
  ```python
  _run_args, _run_kwargs = _posix_shell_run_args(args.cmd)
  result = subprocess.run(_run_args, capture_output=True, text=True, cwd=project_root, **_run_kwargs)
  ```

### Fix 3 — `--round` auto-discovery

**`millpy-review-plan.py`**:
- Add `discover_round` to the `from _review_common import ...` line (currently at line ~98).
- In the `elif args.stage == "finalize":` branch (line ~171): replace the hard error when `args.round is None` with:
  ```python
  round_n = args.round
  if round_n is None:
      reviews_dir_for_discovery = resolve_path(cfg["paths"]["reviews_dir"], slug)
      round_n = discover_round(reviews_dir_for_discovery, "plan", "holistic")
  ```
  Use `round_n` everywhere `args.round` was used in that branch.
- Update the `--round` argparse help to "Review round number from prepare envelope; auto-discovered when absent in finalize stage."

**`millpy-review-discussion.py`**:
- Add `discover_round` to the `from _review_common import ...` line (currently at line ~66).
- Same pattern in the `elif args.stage == "finalize":` branch (line ~116), using `"discussion"` as the review type:
  ```python
  round_n = args.round
  if round_n is None:
      reviews_dir_for_discovery = resolve_path(cfg["paths"]["reviews_dir"], slug)
      round_n = discover_round(reviews_dir_for_discovery, "discussion", "holistic")
  ```
- Update `--round` argparse help text.

Note: `resolve_path` is already imported in both CLIs. `discover_round` is in `_review_common` alongside it.

### Key relationships and invariants

- `strip_all_in_worktree` is called only by `_worktree.remove_safe`. No other callers. Changing its walk depth is safe.
- `_posix_shell_run_args` must NOT call `sys.exit` or raise — it is a pure helper returning args/kwargs only.
- `discover_round` for a holistic scope returns `max(found) + 1` where `found` is the set of existing review file round numbers. Since the review file for round N hasn't been written yet when finalize is called, this returns the same N that prepare returned. This is the invariant the auto-discovery relies on — it holds as long as no concurrent review is writing files for the same slug simultaneously (single-task worktrees guarantee this).

## Testing

### `test-junction.py` — add case (e)

Add test case `nested-junction case`:
- Create `wt/src/hub/` as a real directory chain.
- Create junctions `wt/src/hub/.wiki` and `wt/src/hub/.portals` pointing at `tmp/wiki_target` and `tmp/portals_target`.
- Verify `strip_all_in_worktree(wt, {})` returns both junction paths.
- Verify both junctions no longer exist.
- Verify `wt/src/hub/` real directory still exists (not deleted).
- Verify `tmp/wiki_target` and `tmp/portals_target` are untouched.

### `test-merge-in-subagent.py` — add `_posix_shell_run_args` routing tests

Add two test cases (using `unittest.mock.patch` on `os.name` and `shutil.which`):

- `posix-shell-args-windows-with-bash`: mock `os.name = "nt"`, `shutil.which("bash") = "/usr/bin/bash"` → assert returns `(["/usr/bin/bash", "-c", "PYTHONPATH= uv run foo"], {})`.
- `posix-shell-args-windows-no-bash`: mock `os.name = "nt"`, `shutil.which("bash") = None` → assert returns `("PYTHONPATH= uv run foo", {"shell": True})`.
- `posix-shell-args-posix`: mock `os.name = "posix"` → assert returns `("PYTHONPATH= uv run foo", {"shell": True})`.

These test `_implementer_common._posix_shell_run_args` directly. Import `_implementer_common` (already imported in this test file).

The auto-discovery branch lives in the CLI `main()` finalize handler, not in `finalize()` itself, so `test-review-plan-flow.py`'s backend coverage does not reach it. Add CLI-level tests:

- In `test-review-plan-flow.py` (or a new `test-review-plan-cli-round.py`), load `millpy-review-plan` via `importlib.util.spec_from_file_location` (same pattern as `test-merge-in-subagent.py` loads the subagent). Call `main(["--stage", "finalize", "--agent-output", "<out_path>"])` without `--round`. Verify the call succeeds (exit 0) and the returned JSON has the expected round number. A minimal fixture: write a stub `.out.md` containing a valid `MILL_REVIEW_BEGIN` block, set up the reviews_dir (empty → discover_round returns 1). Repeat the same test for `millpy-review-discussion.py`.

## Q&A log

- **Q:** Should `strip_all_in_worktree` recurse without depth limit? **A:** Yes — mill worktrees are shallow by construction; no guard needed.
- **Q:** Where should the bash-routing helper live? **A:** Extracted to `_implementer_common._posix_shell_run_args`; imported in merge-in subagent.
- **Q:** Should `--round` auto-discovery apply to both review CLIs or only review-plan? **A:** Both, for symmetry.
