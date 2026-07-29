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
- Apply the guard unconditionally (both Windows and POSIX) — the same
  list-then-open race can occur on POSIX (ENOENT), and the module's
  existing docstring already commits to symmetric cross-platform strip
  behavior.
- Add unit test coverage in `plugins/mill/unit_tests/test-safe-rmtree.py`
  that simulates a vanished entry mid-walk (mocking `os.scandir`) and
  asserts `safe_rmtree` completes without raising and still removes the
  rest of the tree.

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

### Fix location: shared `_walk_strip_reparse_points` helper, not a baseline-specific patch

- Decision: fix the race inside `_safe_rmtree._walk_strip_reparse_points`,
  the shared junction/symlink-stripping walk that every `safe_rmtree`
  caller (mill-cleanup, mill-merge, mill-spawn, and
  `_verify_baseline.compute_baseline` via `_worktree.remove_safe`'s
  fallback) goes through before `shutil.rmtree`.
- Rationale: this is where the uncaught exception actually originates.
  `compute_baseline` itself does no direct file I/O on the checked-out
  tree; it uses `git worktree add`/`git worktree remove` (subprocess
  calls, not raising Python `WinError`s) and delegates teardown to
  `_worktree.remove_safe`, which falls back to `_safe_rmtree.safe_rmtree`
  → `_walk_strip_reparse_points` when git's own removal fails with a
  long-path / "not a working tree" / "directory not empty" pattern.
  Fixing the shared helper closes the same gap for every other
  `safe_rmtree` caller, not just the baseline stage — matching the GH
  issue's ask to "investigate whether this is a recurring Windows path
  issue" rather than special-casing one call site.
- Rejected: patching only `_verify_baseline.py`'s cleanup call (leaves
  the identical race live in mill-cleanup/mill-merge/mill-spawn
  teardowns, which run over similarly deep, tool-generated trees); a
  broad `except OSError` wrapped around the whole fallback rmtree call in
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

### Guard placement: per-entry try/except plus a top-of-function guard

- Decision: wrap each entry's full per-iteration body (the
  `entry.is_symlink()` check, `_is_reparse_point(ep)` check, and the
  recursive `_walk_strip_reparse_points(ep)` call for directories) in one
  `try/except FileNotFoundError: continue` per entry inside the loop.
  Separately, guard the function's own `os.scandir(root)` call at the top
  (the case where `root` itself vanished between being listed by its
  *parent's* scandir and being recursed into) so a vanished subdirectory
  doesn't raise before the loop even starts.
- Rationale: `_is_reparse_point` already swallows `OSError`/`AttributeError`
  internally, but `entry.is_symlink()` and `entry.is_dir(follow_symlinks=False)`
  (called deeper via the recursive `os.scandir` inside the next-level
  call) are not guarded anywhere in the current call chain. Wrapping the
  whole per-entry body is the minimal change that covers every place a
  vanished entry could raise, without threading a check through each
  individual call site separately.
- Rejected: guarding only the top-level `os.scandir(root)` call (leaves
  entry-level races — a file that vanishes between being listed and
  `entry.is_symlink()` being called on it — unguarded).

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

- `plugins/mill/scripts/_safe_rmtree.py` — the file to change.
  `_walk_strip_reparse_points` (lines 61-69) is the unguarded recursive
  walk. `_onexc_chmod_retry` (lines 34-46) is the sibling handler for the
  actual `shutil.rmtree` delete pass and needs no change — it already
  no-ops when the target is already gone.
- `plugins/mill/scripts/_worktree.py` — `remove_safe` (lines 180-276) is
  the only caller relevant to this bug's reproduction path: it tries
  `git worktree remove --force` first, and only falls back to
  `_safe_rmtree.safe_rmtree` (line 261) when git's own removal fails with
  a message matching `_rmtree_fallback_patterns` (long path / "not a
  working tree" / "directory not empty"). The fallback is what invokes
  `_walk_strip_reparse_points` via `safe_rmtree`.
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
- Other `safe_rmtree` callers that benefit from this fix without any
  changes of their own: `millpy-cleanup.py` (mill-cleanup's worktree
  sweep) and worktree teardown paths exercised by `test-worktree.py`,
  `test-finalize-cleanup.py`, `test-millpy-spawn.py`, and others listed
  under `plugins/mill/unit_tests/` / `plugins/mill/integration_tests/`
  that reference `safe_rmtree`.
- Existing test conventions to follow: `test-safe-rmtree.py` already uses
  `unittest.mock.patch` against `_safe_rmtree.shutil.rmtree` for a
  comparable "simulate a failure that shouldn't propagate" case (see its
  "ignore_errors=True swallows OSError from rmtree" case). The new test
  should mock `os.scandir` (or a `DirEntry`-shaped stand-in) to raise
  `FileNotFoundError` for one specific path partway through a walk of a
  small fixture tree, following the same tempfile-based fixture pattern
  used throughout that file.

## Constraints

No `CONSTRAINTS.md` present at the hub root — none apply beyond the
repo-wide conventions already referenced above (ASCII-only
`print()`/`_log()` output; `unit_tests/` restricted to in-memory/tempfile
fixtures, no real git/LLM calls).

## Testing

- **TDD candidate:** `_safe_rmtree._walk_strip_reparse_points` (via the
  public `safe_rmtree` entry point) in `test-safe-rmtree.py`. Write the
  new "vanished entry mid-walk does not raise" case first, confirm it
  fails against the current unguarded implementation, then implement the
  fix.
- **Scenario 1 — vanished file entry:** a fixture tree with two sibling
  files under a directory; mock the walk so one file's presence-check
  (`entry.is_symlink()` or equivalent) raises `FileNotFoundError`
  mid-iteration. Assert `safe_rmtree` completes without raising, the
  surviving fixture content is still removed, and (if feasible to assert
  on captured stderr) the skip is logged.
  Recommended approach: I favor mocking `os.scandir` to return a stand-in `DirEntry`-shaped
  object for the vanished path.
- **Scenario 2 — vanished subdirectory entry:** a fixture tree with a
  nested subdirectory that is removed from disk (or whose recursive
  `os.scandir` call is mocked to raise `FileNotFoundError`) between being
  listed by its parent and being recursed into. Assert `safe_rmtree`
  completes without raising and the rest of the tree (siblings of the
  vanished subdirectory) is still removed.
- **Regression guard (existing coverage, must still pass):** every
  existing case in `test-safe-rmtree.py` — blacklist refusal, containment
  refusal, junction/symlink stripping before rmtree (the wiki-wipe
  regression guard), path-is-junction/symlink refusal, missing-path
  no-op, `ignore_errors` semantics. The fix must not change any of these
  behaviors; a `FileNotFoundError` on a genuinely-absent top-level `path`
  is already handled earlier in `safe_rmtree` (the existing
  "missing path is no-op" case) and is out of scope for the new guard,
  which only covers entries discovered mid-walk.
- **Not covered by new automated tests (acceptable per Decisions):** the
  real end-to-end Windows repro from issue #738 (a live `dotnet build`
  deleting a JsonCodeGen output file at exactly the right moment during
  `compute_baseline`'s teardown) is a genuine race condition that cannot
  be reliably reproduced with real filesystem timing in CI. The mocked
  unit tests above exercise the same code path deterministically instead.

## Q&A log

- **Q:** Where should the fix for the TOCTOU race live? **A:** [auto-pick] Harden `_walk_strip_reparse_points` in `_safe_rmtree.py` (shared helper used by every `safe_rmtree` caller). **Why:** the uncaught exception originates there, not in baseline-specific code; fixing the shared helper closes the same gap for mill-cleanup/mill-merge/mill-spawn teardowns too, matching the GH issue's ask to investigate whether this is a recurring (not baseline-only) Windows path issue.
- **Q:** What exception class should the walk catch and skip-and-log? **A:** [auto-pick] `FileNotFoundError` only. **Why:** narrow enough not to mask permission/disk errors; wide enough to cover both WinError 2 and WinError 3 (and POSIX ENOENT) without platform-specific winerror inspection.
- **Q:** Should the fix apply symmetrically on POSIX or be Windows-gated? **A:** [auto-pick] Unconditional, both platforms. **Why:** the same list-then-open race exists on POSIX, and the module's own docstring already commits to symmetric cross-platform behavior for this strip pass.
- **Q:** Where exactly should the skip-and-log wrap the per-entry work? **A:** [auto-pick] Wrap each entry's full loop body in one `try/except FileNotFoundError: continue`, plus a guard at the top-level `os.scandir(root)` call. **Why:** covers every place a vanished entry could raise (`entry.is_symlink()`, `entry.is_dir()`, the recursive call, and the directory's own scandir open) with one consistent pattern.
- **Q:** What logging format for the skip? **A:** [auto-pick] `[safe-rmtree] skip vanished entry: <path>` to stderr, ASCII-only. **Why:** the GH issue explicitly asks for skip-and-log, not silent skip — this race should stay visible even though it's non-fatal.
- **Q:** Test coverage approach? **A:** [auto-pick] Mocked unit test in `test-safe-rmtree.py` simulating a vanished entry mid-walk via `os.scandir` mocking, following the file's existing `unittest.mock.patch` conventions. **Why:** a real TOCTOU race can't be reliably reproduced with real filesystem timing in CI; the existing integration test (`test-verify-baseline.py`) already covers `compute_baseline`'s real-git behavior end-to-end and doesn't need duplicated coverage for this specific race.
- **Q:** Does `millpy-implement.py`'s `_run_baseline_stage` catch-all need any change? **A:** [auto-pick] No. **Why:** it already treats any `compute_baseline` exception as non-fatal (leaves baseline unset, logs, returns 0) — once the root-cause race is fixed upstream, this remains a correct last-resort backstop; adding narrower handling here too would be redundant per YAGNI.
