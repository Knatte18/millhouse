# Discussion: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
task: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows
slug: mill-baseline-snapshot-windows-path-gap
status: discussing
parent: main
```

## Problem

On Windows, `millpy-implement.py --stage baseline` (mill-go's task-scoped
module-wide verify-baseline pre-flight, run once before batch 1) sometimes
fails with:

```
[millpy-implement] baseline computation failed: [WinError 3] The system cannot find the path specified: 'C:\...\.scratch\verify-baseline-a4fb073a7a16\src\csharp\NORCE.Models\NORCE.Models.JsonCodeGenTestModels\JsonSerialization\Migrations\CollectionVariants.311c5305'
{"stage": "baseline", "result": "error", "reason": "[WinError 3] ..."}
```

Reported in GitHub issue #738 against `NORCE-DrillingAndWells/Models`. The
failure is already non-fatal — `_run_baseline_stage` in
`millpy-implement.py` catches any exception from `compute_baseline`, logs
it, and leaves the baseline field unset, which makes the next
`_run_verify_gates` call run the module-wide gate strictly (the same
fail-safe as an inconclusive read; see `_verify_baseline.py`'s module
docstring). So the task itself is never blocked. But it means the
module-wide verify baseline is silently never computed for any task that
hits this race — the regression-catching gate degrades to "always strict"
instead of getting the one-time pre-existing-failure classification it's
meant to provide, with no signal to the operator beyond a log line.

**Why now:** the underlying race is real and will recur on any Windows
repo whose module-wide verify command (e.g. a `dotnet build`) generates
and later cleans up transient/generated files during the run — the
`CollectionVariants.311c5305`-style JsonCodeGen output in issue #738 is
one instance, not a one-off.

## Scope

**In:**
- Harden `_walk_strip_reparse_points` in `plugins/mill/scripts/_safe_rmtree.py`
  so a file or directory that vanishes between being listed by a parent
  `os.scandir()` call and being recursed into / stat'd no longer raises
  an uncaught `FileNotFoundError` out of `safe_rmtree`. Skip the vanished
  entry and log it (ASCII-only, `[safe-rmtree]`-prefixed) instead of
  hard-failing the whole strip pass.
- Apply the identical fix to the sibling `_walk` closure inside
  `_junction.strip_all_in_worktree` in `plugins/mill/scripts/_junction.py`
  (lines 314-336). This walk has the same list-then-recurse `os.scandir`
  shape and the same unguarded TOCTOU gap — its `try/except` currently
  catches only `PermissionError` (line 318), not `FileNotFoundError` — and
  it runs *unconditionally as step 1* of `_worktree.remove_safe`, before
  `git worktree remove` is even attempted. Every `remove_safe` caller
  (including `compute_baseline`'s teardown) hits this walk first, on
  every call, not just on the long-path git-failure fallback that
  `_safe_rmtree`'s walk guards — making this the more likely actual
  crash site for issue #738's reported race, not just a parallel one.
  Same treatment: skip the vanished entry, log it
  (`[junction]`-prefixed, ASCII-only, matching this file's existing
  `[junction] WARNING: permission denied...` convention), continue the
  walk.
- Apply both guards unconditionally (both Windows and POSIX) — the same
  list-then-open race can occur on POSIX (ENOENT), and
  `_safe_rmtree.py`'s existing docstring already commits to symmetric
  cross-platform strip behavior; `_junction.py`'s walk has no existing
  platform asymmetry to preserve either.
- Add unit test coverage in `plugins/mill/unit_tests/test-safe-rmtree.py`
  and `plugins/mill/unit_tests/test-junction.py` that simulates a vanished
  entry mid-walk (mocking `os.scandir`) and asserts `safe_rmtree` /
  `strip_all_in_worktree` respectively complete without raising and still
  process the rest of the tree.

**Out:**
- No change to `_verify_baseline.compute_baseline`'s control flow, retry
  logic, or return contract ("clean" / "pre-existing-failures") — the fix
  is entirely inside the teardown helper it calls transitively via
  `_worktree.remove_safe`.
- No change to `millpy-implement.py`'s `_run_baseline_stage` catch-all
  (lines ~147-158). It already treats any exception from
  `compute_baseline` as non-fatal and leaves the baseline unset; once the
  root-cause race is fixed there, that catch-all becomes a true
  last-resort backstop for genuinely unexpected failures rather than the
  primary mitigation for this specific race. Adding narrower handling
  there too would be redundant.
- No change to the primary `git worktree remove --force` path in
  `_worktree.remove_safe` (the fast path that runs before the
  `_safe_rmtree` fallback) — that path shells out to git and never raises
  a Python-level `WinError`; it is not implicated in this bug.
- No investigation into changing how the target repo's JsonCodeGen build
  step generates/names its output files — out of scope for this repo
  (millhouse); the fix must be robust to whatever a downstream build tool
  does, not rely on downstream naming conventions.
- No change to `_onexc_chmod_retry` (the `shutil.rmtree(..., onexc=...)`
  handler used for the actual delete pass) — it already no-ops safely
  when a path is already gone (`if not os.path.exists(path): return`).
  Only the earlier, unguarded `_walk_strip_reparse_points` pre-pass needs
  the fix.

## Decisions

### Fix location: both shared walks feeding `_worktree.remove_safe` — `_safe_rmtree._walk_strip_reparse_points` AND `_junction.strip_all_in_worktree`'s `_walk`

- Decision: fix the race in both of `remove_safe`'s recursive walks:
  `_safe_rmtree._walk_strip_reparse_points` (reached via the
  `safe_rmtree` long-path/not-a-working-tree/directory-not-empty
  fallback) and `_junction.strip_all_in_worktree`'s inner `_walk`
  (reached unconditionally, as `remove_safe`'s step 1, on *every* call —
  before `git worktree remove` is even attempted). Every `safe_rmtree`/
  `remove_safe` caller (mill-cleanup, mill-spawn, and
  `_verify_baseline.compute_baseline` via `_worktree.remove_safe`) goes
  through both.
- Rationale: this is where the uncaught exception actually originates.
  `compute_baseline` itself does no direct file I/O on the checked-out
  tree; it uses `git worktree add`/`git worktree remove` (subprocess
  calls, not raising Python `WinError`s) and delegates teardown to
  `_worktree.remove_safe`. Discussion-review round 1 (see Q&A log)
  surfaced that `strip_all_in_worktree`'s walk is actually the more
  likely crash site for issue #738's reported race, not merely a
  parallel one: it runs first, unconditionally, on the full transient
  worktree tree (including deep tool-generated subtrees like
  `src/csharp/NORCE.Models/...`), and its `try/except` around
  `os.scandir` (`_junction.py` line 318) catches only `PermissionError`
  — an identical list-then-recurse shape to `_safe_rmtree`'s walk, but
  with no `FileNotFoundError` guard at all. Fixing only
  `_safe_rmtree._walk_strip_reparse_points` would have left this
  sibling gap live and unaddressed. Fixing both closes the gap for every
  `remove_safe` caller regardless of which code path (unconditional
  junction-strip step 1, or the conditional rmtree fallback) actually
  hits the vanished entry — matching the GH issue's ask to "investigate
  whether this is a recurring Windows path issue" rather than
  special-casing one call site.
- Rejected: patching only `_verify_baseline.py`'s cleanup call (leaves
  the identical race live in mill-cleanup/mill-spawn teardowns, which
  run over similarly deep, tool-generated trees); fixing only
  `_safe_rmtree._walk_strip_reparse_points` and treating
  `_junction.strip_all_in_worktree` as out of scope (leaves a
  structurally identical, unguarded TOCTOU race live in the walk that
  actually runs first on every `remove_safe` call); a broad
  `except OSError` wrapped around the whole fallback rmtree call in
  `_worktree.remove_safe` (would also swallow genuine permission/lock
  errors that should surface as `WorktreeLockedError` or propagate).

### Exception scope: `FileNotFoundError` only, unconditional on platform

- Decision: catch `FileNotFoundError` specifically (which Python already
  maps both WinError 2 "file not found" and WinError 3 "path not found",
  as well as POSIX `ENOENT`, onto) around each entry's processing inside
  `_walk_strip_reparse_points`'s loop, plus around the function's own
  top-level `os.scandir(root)` call. No `sys.platform` gate — apply on
  both Windows and POSIX.
- Rationale: `FileNotFoundError` is narrow enough not to mask real
  problems (permission errors, disk errors, or a genuinely
  malformed reparse point should still propagate and fail loudly), and
  wide enough to cover both of the two concrete winerror codes seen in
  practice (2 for a vanished file, 3 for a vanished directory whose
  `os.scandir` call fails to even open it) without needing to inspect
  `.winerror` and special-case per platform. The module's own docstring
  already states "kept cross-platform behaviour symmetric" for the
  existing symlink-strip logic, so gating the fix to Windows-only would
  contradict that stated intent and leave POSIX with a real (if less
  frequently observed) TOCTOU gap.
- Rejected: catching broad `OSError` (too broad — would hide permission
  and other I/O failures that are not the vanished-file race);
  Windows-only guard via `sys.platform == "win32"` (unnecessary
  divergence from the module's existing symmetric-platform stance, adds
  a branch with no POSIX test coverage).

### Guard placement: per-entry try/except plus a top-of-function guard, applied symmetrically to both walks

- Decision: in `_safe_rmtree._walk_strip_reparse_points`, wrap each
  entry's full per-iteration body — explicitly: the `entry.is_symlink()`
  check, the `_is_reparse_point(ep)` check, **the `_junction.remove(ep)`
  call** (the actual `os.unlink`/`os.rmdir` at removal time — a real
  `FileNotFoundError` source in its own right if the entry vanishes
  between being detected as a symlink/junction and being removed), and
  the recursive `_walk_strip_reparse_points(ep)` call for directories —
  in one `try/except FileNotFoundError: continue` per entry inside the
  loop. Separately, guard the function's own `os.scandir(root)` call at
  the top (the case where `root` itself vanished between being listed by
  its *parent's* scandir and being recursed into) so a vanished
  subdirectory doesn't raise before the loop even starts. Apply the
  identical shape to `_junction.strip_all_in_worktree`'s `_walk`: widen
  its existing `try/except PermissionError` around
  `os.scandir(str(dir_path))` (line 318) to also catch
  `FileNotFoundError` (skip-and-log, return early — same as the existing
  `PermissionError` branch's shape), and wrap the per-entry body
  (`entry.is_symlink()`, `_is_junction_or_symlink(ep)`, **the
  `remove(ep)` call**, `entry.is_dir()`, and the recursive `_walk(ep)`
  call) in the same per-entry `try/except FileNotFoundError: continue`.
  Both walks' calls into the single `_junction.remove` (there is exactly
  one implementation, in `_junction.py`, called from both
  `_safe_rmtree._walk_strip_reparse_points` and `_junction.py`'s own
  `_walk`) already re-check `os.path.lexists`/idempotency at that
  function's own entry, but that check happens before this fix's guard
  is entered — it narrows, but does not close, the removal-time TOCTOU
  window this decision now explicitly covers.
- Rationale: `_is_reparse_point`/`_is_junction_or_symlink` already
  swallow `OSError`/`AttributeError` internally, but `entry.is_symlink()`,
  `entry.is_dir(follow_symlinks=False)`, and the `_junction.remove(ep)`
  call itself are not guarded anywhere in either call chain. Wrapping the
  whole per-entry body — removal call included — in both walks is the
  minimal change that covers every place a vanished entry could raise,
  without threading a check through each individual call site
  separately, and keeps the two walks' resilience shape consistent with
  each other now that both are in scope.
- Rejected: guarding only the top-level `os.scandir` call in either walk
  (leaves entry-level races — a file that vanishes between being listed
  and `entry.is_symlink()` being called on it, or between being detected
  and `_junction.remove(ep)` being called on it — unguarded); giving the
  two walks different guard shapes (adds needless divergence between two
  now-parallel implementations of the same resilience requirement);
  leaving the removal call's coverage ambiguous/implicit rather than
  stating it explicitly (this is exactly the gap discussion-review round
  2 flagged — the removal call is the same TOCTOU class as the
  detection calls and belongs unambiguously inside the guarded region).

### Logging: explicit skip-and-log, not silent

- Decision: log each skipped vanished entry to stderr with the existing
  `[safe-rmtree]` prefix convention, e.g.
  `print(f"[safe-rmtree] skip vanished entry: {ep}", file=sys.stderr)`.
  ASCII-only per CLAUDE.md's `print()`/`_log()` convention.
- Rationale: the GH issue's suggested fix explicitly asks for
  "skip-and-log rather than hard-fail." A silent skip during this
  pre-pass would make the exact race that prompted the bug report
  invisible again, just non-fatal instead of fatal — worse for future
  debugging than today's loud (if ugly) crash.
- Rejected: silent skip, matching `_onexc_chmod_retry`'s existing silent
  "if not exists: return" behavior — that handler protects a different,
  later phase (the actual delete pass, which already has its own
  onexc-based recovery); the pre-pass has no equivalent visibility today
  so a silent skip there would be a net loss of signal.

## Technical context

- `plugins/mill/scripts/_safe_rmtree.py` — one of the two files to
  change. `_walk_strip_reparse_points` (lines 61-69) is the unguarded
  recursive walk. `_onexc_chmod_retry` (lines 34-46) is the sibling
  handler for the actual `shutil.rmtree` delete pass and needs no
  change — it already no-ops when the target is already gone.
- `plugins/mill/scripts/_junction.py` — the other file to change.
  `strip_all_in_worktree`'s inner `_walk` closure (lines 314-336) is the
  sibling unguarded recursive walk surfaced by discussion-review round 1.
  Its `try/except` around `os.scandir(str(dir_path))` (line 318)
  currently catches only `PermissionError`, logging a `[junction]
  WARNING: permission denied...` and returning early — the pattern to
  extend for `FileNotFoundError` too.
- `plugins/mill/scripts/_worktree.py` — `remove_safe` (lines 180-276) is
  the caller relevant to this bug's reproduction path. Step 1
  (lines 219-224) calls `_junction.strip_all_in_worktree` unconditionally
  whenever `path.exists()`, before attempting `git worktree remove` at
  all — this is the walk that runs first, every time, on the full
  transient worktree tree. Only if `git worktree remove --force`
  subsequently fails with a message matching
  `_rmtree_fallback_patterns` (long path / "not a working tree" /
  "directory not empty") does `remove_safe` fall back to
  `_safe_rmtree.safe_rmtree` (line 261), which invokes
  `_walk_strip_reparse_points` a second time over the same tree.
- `plugins/mill/scripts/_verify_baseline.py` — `compute_baseline`'s
  `finally` block (line 216-217) calls
  `_worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})`
  unconditionally, on every code path (success, verify failure, or any
  exception). This is the entry point that surfaces the bug for the
  baseline stage specifically, but the module itself needs no changes.
- `plugins/mill/scripts/millpy-implement.py` — `_run_baseline_stage`
  (lines 78-161) is the caller that currently catches the exception
  non-fatally (lines 147-158) and is why the bug is silent/non-blocking
  today. No changes needed here per the Scope/Decisions above.
- Other `remove_safe`/`safe_rmtree` callers that benefit from this fix
  without any changes of their own: `millpy-cleanup.py` (mill-cleanup's
  worktree sweep) and `millpy-spawn.py` (mill-spawn's worktree
  creation/rollback path), plus the test fixtures exercising worktree
  teardown under `test-worktree.py`, `test-finalize-cleanup.py`,
  `test-millpy-spawn.py`, `test-junction.py`, and others listed under
  `plugins/mill/unit_tests/` / `plugins/mill/integration_tests/` that
  reference `safe_rmtree` or `strip_all_in_worktree`. `mill-merge` does
  **not** call `remove_safe`/`safe_rmtree` — its own SKILL.md states
  worktree/portal/wiki-active-dir teardown is handled by `/mill-cleanup`,
  not by mill-merge itself (confirmed absent from
  `millpy-merge-in-subagent.py` and `mill-merge/SKILL.md` by grep during
  discussion-review round 1); it is not a beneficiary of this fix and is
  not listed as one.
- Existing test conventions to follow: `test-safe-rmtree.py` already uses
  `unittest.mock.patch` against `_safe_rmtree.shutil.rmtree` for a
  comparable "simulate a failure that shouldn't propagate" case (see its
  "ignore_errors=True swallows OSError from rmtree" case). The new tests
  should mock `os.scandir` (or a `DirEntry`-shaped stand-in) to raise
  `FileNotFoundError` for one specific path partway through a walk of a
  small fixture tree, following the same tempfile-based fixture pattern
  used throughout `test-safe-rmtree.py` and `test-junction.py`
  respectively.

## Constraints

No `CONSTRAINTS.md` present at the hub root — none apply beyond the
repo-wide conventions already referenced above (ASCII-only
`print()`/`_log()` output; `unit_tests/` restricted to in-memory/tempfile
fixtures, no real git/LLM calls).

## Testing

- **TDD candidates:** `_safe_rmtree._walk_strip_reparse_points` (via the
  public `safe_rmtree` entry point) in `test-safe-rmtree.py`, and
  `_junction.strip_all_in_worktree` in `test-junction.py`. For each, write
  the new "vanished entry mid-walk does not raise" case first, confirm it
  fails against the current unguarded implementation, then implement the
  fix.
- **Scenario 1 — vanished file entry (both walks):** a fixture tree with
  two sibling files under a directory; mock the walk so one file's
  presence-check (`entry.is_symlink()` or equivalent) raises
  `FileNotFoundError` mid-iteration. Assert `safe_rmtree` /
  `strip_all_in_worktree` completes without raising, the surviving
  fixture content is still processed, and (if feasible to assert on
  captured stderr) the skip is logged. Recommended approach: mock
  `os.scandir` to return a stand-in `DirEntry`-shaped object for the
  vanished path.
- **Scenario 2 — vanished subdirectory entry (both walks):** a fixture
  tree with a nested subdirectory that is removed from disk (or whose
  recursive `os.scandir` call is mocked to raise `FileNotFoundError`)
  between being listed by its parent and being recursed into. Assert
  `safe_rmtree` / `strip_all_in_worktree` completes without raising and
  the rest of the tree (siblings of the vanished subdirectory) is still
  processed.
- **Scenario 3 — `strip_all_in_worktree` specifically:** since its walk
  runs unconditionally as `remove_safe`'s step 1 (before any git call),
  add a `test-junction.py` case asserting `strip_all_in_worktree` itself
  (not just its inner `_walk` in isolation) completes when the
  underlying worktree tree has a vanished entry. Coverage stays confined
  to the two Scope-named files (`test-safe-rmtree.py`,
  `test-junction.py`) — `test-worktree.py` is not touched by this task
  (see Technical context: it is a `remove_safe`-level beneficiary of
  this fix with no changes of its own required).
- **Regression guard (existing coverage, must still pass):** every
  existing case in `test-safe-rmtree.py` (blacklist refusal, containment
  refusal, junction/symlink stripping before rmtree — the wiki-wipe
  regression guard, path-is-junction/symlink refusal, missing-path
  no-op, `ignore_errors` semantics) and `test-junction.py`'s actual 5
  existing cases — `strips-undeclared-junction`, `multiple-junctions`,
  `non-junction-untouched`, `missing-worktree`, `nested-junction` (all
  scoped to `strip_all_in_worktree`'s FS-scan behavior per that file's
  own docstring; it has no `PermissionError`/junction
  create-remove-points_to case of its own — those are exercised
  incidentally by other test files, e.g. `test-worktree.py`'s
  `remove_safe`-level `PermissionError` coverage, not by
  `test-junction.py` directly). The fix must not change any of these
  behaviors. Note: widening `_walk`'s `except PermissionError` (line 318)
  to also catch `FileNotFoundError` currently has zero direct unit
  coverage protecting the existing permission-denied skip-and-return-early
  branch — the new test should not regress that branch, but adding
  coverage for it is not required by this task's scope. A
  `FileNotFoundError` on a genuinely-absent top-level `path`/
  `worktree_path` is already handled earlier in both functions (the
  existing "missing path is no-op" / `not worktree_path.exists()`
  early-return cases) and is out of scope for the new guard, which only
  covers entries discovered mid-walk.
- **Not covered by new automated tests (acceptable per Decisions):** the
  real end-to-end Windows repro from issue #738 (a live `dotnet build`
  deleting a JsonCodeGen output file at exactly the right moment during
  `compute_baseline`'s teardown) is a genuine race condition that cannot
  be reliably reproduced with real filesystem timing in CI. The mocked
  unit tests above exercise the same code paths deterministically
  instead.

## Q&A log

- **Q:** Where should the fix for the TOCTOU race live? **A:** [auto-pick] Harden `_walk_strip_reparse_points` in `_safe_rmtree.py` (shared helper used by every `safe_rmtree` caller). **Why:** the uncaught exception originates there, not in baseline-specific code; fixing the shared helper closes the same gap for mill-cleanup/mill-merge/mill-spawn teardowns too, matching the GH issue's ask to investigate whether this is a recurring (not baseline-only) Windows path issue.
- **Q:** What exception class should the walk catch and skip-and-log? **A:** [auto-pick] `FileNotFoundError` only. **Why:** narrow enough not to mask permission/disk errors; wide enough to cover both WinError 2 and WinError 3 (and POSIX ENOENT) without platform-specific winerror inspection.
- **Q:** Should the fix apply symmetrically on POSIX or be Windows-gated? **A:** [auto-pick] Unconditional, both platforms. **Why:** the same list-then-open race exists on POSIX, and the module's own docstring already commits to symmetric cross-platform behavior for this strip pass.
- **Q:** Where exactly should the skip-and-log wrap the per-entry work? **A:** [auto-pick] Wrap each entry's full loop body in one `try/except FileNotFoundError: continue`, plus a guard at the top-level `os.scandir(root)` call. **Why:** covers every place a vanished entry could raise (`entry.is_symlink()`, `entry.is_dir()`, the recursive call, and the directory's own scandir open) with one consistent pattern.
- **Q:** What logging format for the skip? **A:** [auto-pick] `[safe-rmtree] skip vanished entry: <path>` to stderr, ASCII-only. **Why:** the GH issue explicitly asks for skip-and-log, not silent skip — this race should stay visible even though it's non-fatal.
- **Q:** Test coverage approach? **A:** [auto-pick] Mocked unit test in `test-safe-rmtree.py` simulating a vanished entry mid-walk via `os.scandir` mocking, following the file's existing `unittest.mock.patch` conventions. **Why:** a real TOCTOU race can't be reliably reproduced with real filesystem timing in CI; the existing integration test (`test-verify-baseline.py`) already covers `compute_baseline`'s real-git behavior end-to-end and doesn't need duplicated coverage for this specific race.
- **Q:** Does `millpy-implement.py`'s `_run_baseline_stage` catch-all need any change? **A:** [auto-pick] No. **Why:** it already treats any `compute_baseline` exception as non-fatal (leaves baseline unset, logs, returns 0) — once the root-cause race is fixed upstream, this remains a correct last-resort backstop; adding narrower handling here too would be redundant per YAGNI.
- **Q:** [discussion-review r1 GAP] `_junction.strip_all_in_worktree`'s sibling `_walk` has the identical unguarded `os.scandir` race and runs unconditionally as `remove_safe`'s step 1, before git is even attempted — is it in scope? **A:** [auto-resolved] Yes, extend scope to `_junction.py`'s `_walk` with the same `FileNotFoundError`-skip-and-log treatment. **Why:** it is structurally identical to the `_safe_rmtree` walk and, since it runs first and unconditionally on every `remove_safe` call, is arguably the more likely actual crash site for issue #738 than the git-failure-gated `_safe_rmtree` fallback; leaving it unfixed would reproduce this exact bug through an unaddressed path.
- **Q:** [discussion-review r1 NOTE] Is `mill-merge` actually a `safe_rmtree`/`remove_safe` beneficiary as originally claimed? **A:** [auto-resolved] No — corrected. **Why:** grep of `millpy-merge-in-subagent.py` and `mill-merge/SKILL.md` shows no reference to worktree teardown; `mill-merge/SKILL.md` states teardown is handled by `/mill-cleanup`. The attribution was factually wrong and has been removed/corrected.
- **Q:** [discussion-review r2 GAP] Does the Testing section accurately describe `test-junction.py`'s existing coverage? **A:** [auto-resolved] No — corrected to name the actual 5 cases (`strips-undeclared-junction`, `multiple-junctions`, `non-junction-untouched`, `missing-worktree`, `nested-junction`); the claimed permission-denied and create/remove/points_to coverage does not exist in that file. **Why:** verified by reading the file's docstring and case list directly — the original claim was inaccurate.
- **Q:** [discussion-review r2 GAP] Is the `_junction.remove(ep)` / `remove(ep)` call itself inside the per-entry `try/except FileNotFoundError` guard, or ambiguous? **A:** [auto-resolved] Explicitly inside — the Decisions section now names the removal call directly as a covered TOCTOU source (the `os.unlink`/`os.rmdir` it performs can itself raise `FileNotFoundError` if the entry vanishes between detection and removal). **Why:** the removal call is the same TOCTOU class as the detection calls already covered by "wrap the whole per-entry body"; leaving it unnamed left real ambiguity about whether the fix's stated scope actually included it.
- **Q:** [discussion-review r3 GAP] Testing Scenario 3 offered `test-worktree.py` as an alternative to `test-junction.py`, contradicting Technical Context's claim that `test-worktree.py` needs no changes — which wins? **A:** [auto-resolved] `test-junction.py` only; dropped the `test-worktree.py` option from Scenario 3. **Why:** Scope's "In" bullet and Technical Context both already commit to `test-worktree.py` being an unmodified beneficiary of the fix, not a file this task adds coverage to; the Scenario 3 wording was the stale/contradicting side, not the other two sections.
- **Q:** [discussion-review r3 NOTE] Does "Both `_junction.remove` implementations" wording imply two separate implementations exist? **A:** [auto-resolved] Reworded to "both walks' calls into the single `_junction.remove`" — there is exactly one implementation. **Why:** the original phrasing was imprecise and could mislead a plan writer into looking for a second `remove` function that doesn't exist.
