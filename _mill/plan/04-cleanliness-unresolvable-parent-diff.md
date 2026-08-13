# Batch: cleanliness-unresolvable-parent-diff

```yaml
task: 'mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies'
batch: cleanliness-unresolvable-parent-diff
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #818: `_cleanliness._parent_diff_names` currently treats a failed `git diff --name-only <parent>...HEAD` (e.g. exit 128 from a deleted parent branch) identically to a genuinely empty diff — both return `[]`. This makes real out-of-scope drift silently undetectable for the rest of the task: the gate reports "no drift" when it actually could not check. The fix changes `_parent_diff_names` to return `None` (distinct from `[]`) on a resolution failure, and propagates that distinction through its two callers (`compute_terminal_dirt`, `revert_out_of_scope_drift`) and their two production consumers (`mill-go-base/handoff.md`'s Terminal cleanliness gate, `mill-go-base/SKILL.md` step 2b), both of which must add an explicit `is None` branch — a plain `if not in_scope_dirt:` truthiness check would silently treat `None` exactly like `[]`, since both are falsy in Python.

`_implementer_common._in_scope_dirty_stuck` is explicitly NOT a consumer of this fix (see batch 3 / #825 — that function's owned-paths source is now a distinct `start_sha`-based `git diff` call, not `_parent_diff_names` or anything derived from it, unrelated to this batch).

External interface: `_parent_diff_names`, `compute_terminal_dirt`, and `revert_out_of_scope_drift` all change their return-type annotations to include `| None`; every call site in this codebase is enumerated and updated in this batch's cards. Self-contained batch.

## Cards

### Card 7: `_cleanliness.py` — propagate `None` through `_parent_diff_names`, `compute_terminal_dirt`, `revert_out_of_scope_drift`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In `_parent_diff_names` (`plugins/mill/scripts/_cleanliness.py:113-130`): change the return-type annotation from `-> list[str]` to `-> list[str] | None`. Change the `if result.returncode != 0:` branch's `return []` (line 129) to `return None`. Update the stderr warning message — it currently reads `f" exited {result.returncode} -- treating parent diff as empty"`; change the trailing clause to `" -- parent diff is unresolvable (unknown, not empty)"`. Add a `Returns:` note to the docstring (`_cleanliness.py:113-118`, which today has no `Returns:` section) stating that `None` signals an unresolvable diff, distinct from an empty `[]` result — the current docstring text does not use the word "empty" anywhere, so this is an addition, not a reword of existing wording.
  2. In `compute_terminal_dirt` (`plugins/mill/scripts/_cleanliness.py:157-187`): change the return-type annotation from `-> list[str]` to `-> list[str] | None`. Immediately after `parent_diff_names = _parent_diff_names(worktree, parent_branch)` (line 177), add:
     ```python
     if parent_diff_names is None:
         return None
     ```
     before the existing `owned_paths = set(parent_diff_names)` line. Update the docstring's `Returns:` section to note `None` is returned when the parent diff itself is unresolvable, distinct from an empty result.
  3. In `revert_out_of_scope_drift` (`plugins/mill/scripts/_cleanliness.py:326-447`): change the return-type annotation from `-> tuple[list[str], list[str]]` to `-> tuple[list[str], list[str] | None]`. Immediately after `parent_diff_names = _parent_diff_names(worktree, parent_branch)` (line 363), add:
     ```python
     if parent_diff_names is None:
         # Owned-path set is unknown -- nothing can be safely reverted (would risk
         # reverting genuinely task-owned files), so report unknown scope rather than
         # silently proceeding as if nothing were owned.
         return ([], None)
     ```
     before the existing `owned_paths = set(parent_diff_names)` line. Update the docstring's `Returns:` section: `remaining_in_scope_lines` is now `list[str] | None`, and `reverted_paths` is `[]` (never `None`) in the unresolvable case since nothing was attempted.
- **Commit:** `fix(cleanliness): propagate unresolvable-parent-diff as None, not empty (#818)`

### Card 8: `mill-go-base/handoff.md` — explicit `is None` branch at both Terminal cleanliness gate call sites

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the "**Terminal cleanliness gate.**" section of `plugins/mill/skills/mill-go-base/handoff.md` (currently lines 45-61, from the `**Terminal cleanliness gate.**` heading through the `If the list is empty, proceed to scope violations cleanup.` line) with:
  ```
**Terminal cleanliness gate.**
Resolve the parent branch and check for in-scope uncommitted changes:

```python
parent_branch = _parent_branch.resolve(status_path, interactive=False)
in_scope_dirt = _cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)
```

If `in_scope_dirt is None` (the parent diff is unresolvable -- e.g. the parent branch ref no longer exists), halt immediately with: `BLOCKED: cannot determine in-scope dirt at task completion -- parent diff unresolvable (parent branch: <parent_branch>). Investigate the parent branch and retry.` Do NOT fall through to the self-resolve step below -- with the owned-path scope itself unknown, there is no safe file list to commit.

If `in_scope_dirt` is non-empty (and not `None`), self-resolve once: this is the agent's own uncommitted work on the task branch, so commit it directly — `_status.append_phase(status_path, "self-resolved-terminal-dirt", _timestamp.now_utc_iso())`, then `git -C <worktree> add <in_scope_dirt files> <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: commit in-scope work at task completion"` (folding the status.md append into the same commit as the audit trail, per Shared Decision `audit-trail-via-status-timeline`;
no push -- matches every other Builder-owned Handoff-phase commit in `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Board discipline").
Re-run `_cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)`.

If the re-check returns `None` (the parent diff became unresolvable between the two checks), halt with the same `BLOCKED: cannot determine in-scope dirt at task completion -- ...` message as above.

If it is STILL non-empty (e.g. the commit or the re-check itself failed, or new dirt appeared concurrently), halt with: `BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.` where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the in-scope dirt.
Do NOT set `phase: done` when the gate fires;
the task remains in its current phase so the operator can inspect and fix.

If the list is empty, proceed to scope violations cleanup.
  ```
  Both call sites (the initial check and the post-self-resolve re-check) now each have their own explicit `is None` halt branch, distinct in wording from the "STILL non-empty" halt.
- **Commit:** `docs(mill-go-base): handoff.md Terminal cleanliness gate handles unresolvable parent diff (#818)`

### Card 9: `mill-go-base/SKILL.md` step 2b — explicit `is None` branch + signature doc-comment update

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-go-base/SKILL.md`'s "### 2b. Cleanliness gate" section (currently lines 638-664):
  1. Update the `signature:` doc-comment at line 653 from
     `` `signature: _cleanliness.revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str, git_root: Path | None = None) -> tuple[list[str], list[str]]` ``
     to
     `` `signature: _cleanliness.revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str, git_root: Path | None = None) -> tuple[list[str], list[str] | None]` ``.
  2. Insert a new branch, before the existing "If `in_scope_dirt` is non-empty..." branch (currently starting at line 655), for the `is None` case:
     ```
     If `in_scope_dirt is None` (the parent diff is unresolvable -- e.g. the parent branch ref no longer exists -- so `reverted_paths` is `[]` and nothing was safely revertable):
     - `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
     - `_status.set_batch_field(status_path, batch_name, "blocked_reason", "parent diff unresolvable -- cannot determine in-scope drift")`
     - `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
     - Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: blocked on <batch_name> — parent diff unresolvable"`
     - Go to *Blocked*.
     ```
  3. Reword the existing "If `in_scope_dirt` is non-empty..." branch's lead-in (currently line 655) to `If `in_scope_dirt` is non-empty (and not `None`; genuine implementer-introduced dirt within task scope that did not pre-date the batch):` — everything below that lead-in (the four bullets + "Go to *Blocked*.") is unchanged.
  4. Reword the existing "If `in_scope_dirt` is empty..." line (currently line 662) to `If `in_scope_dirt` is empty (and not `None`), record `commit_sha` via ...` — the rest of that line and the following "Then continue to..." line are unchanged.
- **Commit:** `docs(mill-go-base): SKILL.md step 2b handles unresolvable parent diff, fixes stale signature doc (#818)`

### Card 10: regression tests for `None`-propagation through `_cleanliness.py`

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Update the existing **PDN-1** block (`plugins/mill/unit_tests/test-cleanliness.py:453-470`, "`_parent_diff_names: non-zero git exit emits stderr warning and returns []`"): change `assert result == [], f"expected [], got {result!r}"` (line 462) to `assert result is None, f"expected None, got {result!r}"`. Update the comment on line 453 and the `print("PASS: ...")` message on line 466 to say `-> None` instead of `-> []`. The stderr-warning assertion (`assert "[cleanliness]" in fake_err.getvalue()`) is unchanged.
  2. Add a new **CTD-6** block, inserted immediately after the existing CTD-5 block (the "`compute_terminal_dirt: absolute task_dir is relativized...`" case, ending around line 451, right before the PDN-1 block). `compute_terminal_dirt` calls `_pygit2_util.status_porcelain` (line 174) BEFORE `_parent_diff_names` (line 177) — every existing CTD-\* case already patches BOTH (see CTD-1..5 at `test-cleanliness.py:371-451`, each wrapping `with unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=...)` around the inner `_parent_diff_names` patch), because against a plain `tempfile.TemporaryDirectory()` (not a real git repo), an unpatched `status_porcelain` call raises `GitOpsError` before `_parent_diff_names` is ever reached. Mirror that same nesting: patch `_cleanliness._pygit2_util.status_porcelain` to `return_value=[]` (outer), patch `_cleanliness._parent_diff_names` to `return_value=None` (inner), then call `compute_terminal_dirt(Path(tmp), Path("_mill"), "main")`; assert the result `is None`. `print("PASS: compute_terminal_dirt: unresolvable parent diff -> None")`.
  3. Add a new **ROOD-5** block, inserted immediately after the existing ROOD-4 block (the "`revert_out_of_scope_drift: file in parent-diff owned set but outside task_dir is in-scope`" case). `revert_out_of_scope_drift` has the identical status_porcelain-before-parent_diff_names ordering (lines 360 and 363). Use ROOD-1/2/3's fully-mocked tempdir fixture shape specifically (`test-cleanliness.py:472-493`: nested `unittest.mock.patch("_cleanliness._pygit2_util.status_porcelain", return_value=[...])` → `unittest.mock.patch("_cleanliness._parent_diff_names", return_value=...)` → `unittest.mock.patch("_cleanliness._subprocess_util.run")`, no real `git init`) — NOT ROOD-4's real-git-repo fixture, which is a different, heavier setup used only where ROOD-4 needed an actual parent-branch merge-base. Patch `status_porcelain` to `return_value=[" M _mill/briefs/prior.out.md"]` (any non-empty in-scope-shaped porcelain line is fine — the point is proving the function returns before ever reaching the in-scope/out-of-scope partition), patch `_parent_diff_names` to `return_value=None`, and call `revert_out_of_scope_drift(Path(tmp), Path("_mill"), "main")`; assert the returned tuple is `([], None)` — `reverted_paths == []` and `remaining_in_scope_lines is None`. `print("PASS: revert_out_of_scope_drift: unresolvable parent diff -> ([], None), nothing reverted")`.

  Every other existing CTD-\*/ROOD-\* case already mocks `_parent_diff_names` with `return_value=[]` (a real empty list, not the failure path) — those cases are unaffected by this change and require no edits.
- **Commit:** `test(cleanliness): regression coverage for unresolvable-parent-diff None propagation (#818)`

## Batch Tests

`verify:` runs `test-cleanliness.py` directly (single file). Card 10 updates the one existing case whose assertion is invalidated by Card 7's behavior change (PDN-1) and adds two new cases (CTD-6, ROOD-5) covering the two propagation call sites. `handoff.md` and `SKILL.md` step 2b (Cards 8-9) are prose/pseudocode, not directly unit-testable Python — per the discussion's Testing section, this is left to the unit-level `None`-propagation tests plus a manual read-through at plan-review time, which this card's Requirements make mechanically verifiable against the actual markdown text.
