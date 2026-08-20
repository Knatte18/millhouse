# Discussion: millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts

```yaml
task: millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts
slug: mill-go-windows-baseline-teardown-winerror145
status: discussing
parent: main
```

## Problem

On Windows, `millpy-implement.py --stage baseline` (and `millpy-merge-in-subagent.py --recompute-baseline`, which shares the same code path) creates a disposable git worktree under `.scratch/verify-baseline-<hash>/` to replay a batch's `verify:` command against the pre-implementation commit. Tearing that worktree down afterward has been failing repeatedly — 8 GitHub issues (#870, #874, #878, #883, #884, #889, #892, #898) report the same `WinError 145` ("The directory is not empty") during teardown, on `.NET` repos on Windows. Each failure leaves an orphaned `.scratch/verify-baseline-*` directory on disk (sometimes still registered in `git worktree list`), and in at least one case (#898) the leftover directory's duplicate `.csproj` file corrupted a later `dotnet run` project-resolution step for an unrelated batch.

Why now: this is a *fresh* wave of reports (all dated 2026-08-15 through 2026-08-20), all filed against the same failure family as the already-completed `mill-go-windows-buildserver-lock-hygiene` task, but with a distinguishable root cause the completed fix (commit `07334bff`) doesn't address.

## Scope

**In:**
- `_worktree.remove_safe`: pass `-c core.longpaths=true` to the `git worktree remove` and `git worktree prune` invocations, matching the flag `_verify_baseline.py` already passes to `git worktree add`.
- `_junction.py::strip_all_in_worktree`'s `_walk`, and `_safe_rmtree.py::_walk_strip_reparse_points`: stop misclassifying Windows long-path (`MAX_PATH`, ~260 char) `FileNotFoundError`s as "entry vanished mid-walk" — these entries are real and non-empty, and skipping them leaves content (and any nested junctions) unaccounted for, which then trips `WinError 145` when the actual removal step runs.
- `_safe_rmtree.safe_rmtree`'s `shutil.rmtree` call: make the root path long-path-safe so descendant path strings shutil builds internally inherit that safety.
- `_junction.remove()` / `_is_junction_or_symlink()`: apply the same long-path-safe path form so a junction sitting at a deep path can actually be removed, not just detected.
- New unit tests for all of the above per existing repo conventions.

**Out:**
- The `dotnet build-server shutdown` + single-retry logic added in `07334bff` for locked `obj/`-directory teardown failures (issues #883, #884, #874, #878 match that pattern exactly). That mechanism belongs to the already-completed `mill-go-windows-buildserver-lock-hygiene` task; those reports are presumed to predate the fix reaching the affected branches' plugin cache rather than exposing a residual gap in it. Not touched here.
- Any change to `kill_stale_holders`'s process-matching heuristic.
- The bare `_worktree.remove()` function — it has no callers in `plugins/mill/scripts/`; only `remove_safe` is used anywhere. Not touched (YAGNI).
- Environment-level fixes (Windows registry `LongPathsEnabled`, Python long-path-aware manifest). The chosen fix is code-level and works regardless of that registry setting.
- Any change to `millpy-cleanup.py`, `millpy-spawn.py`, or `millpy-implement.py` call sites — they all call `_worktree.remove_safe`, so fixing it there fixes all callers with no per-caller changes needed.

## Decisions

### core-longpaths-on-removal

- Decision: Add `-c core.longpaths=true` to both the `git worktree remove --force <path>` and `git worktree prune` argv lists inside `_worktree.remove_safe` (currently at `_worktree.py` lines ~298 and ~364).
- Rationale: `_verify_baseline.py:106` already passes this flag on `git worktree add`, but `remove_safe` — the sole teardown path for that same worktree — omits it. This is a straightforward, provable inconsistency, and matches the "Filename too long" failures reported when operators manually retried `git worktree remove --force` (#889, #884).
- Rejected: Setting `core.longpaths=true` globally via `git config --global` — rejected because it mutates shared git config outside the worktree/task scope; the existing `-c` per-invocation form (already the pattern `_verify_baseline.py` uses) is scoped correctly and requires no environment mutation.

### long-path-safe-walkers

- Decision: Add a new module `_long_path.py` exposing `to_extended(path: Path) -> str`, which on Windows only prepends the `\\?\` extended-length prefix (or `\\?\UNC\` for UNC paths) to an already-resolved absolute path, and returns `str(path)` unchanged on POSIX. Use this helper to build the string passed to:
  - `os.scandir(...)` at the top of `_walk` in `_junction.py::strip_all_in_worktree`.
  - `os.scandir(...)` at the top of `_walk_strip_reparse_points` in `_safe_rmtree.py`.
  - the `shutil.rmtree(...)` root argument in `_safe_rmtree.safe_rmtree` (sufficient to cover all descendants — `shutil.rmtree` builds child path strings via `os.path.join` on whatever root string it's given, so a `\\?\`-prefixed root makes every descendant operation long-path-safe without per-file changes).
  - `_junction.remove()`'s `os.path.lexists`, `os.lstat`, `os.rmdir`, `os.unlink` calls, and `_is_junction_or_symlink()`'s `os.lstat`/`os.path.islink`/`os.path.isjunction` calls — so a junction sitting at a long path can be both detected and actually removed.
- Rationale: The exact same relative path (`doc\cuttings-transport-report\literature-verification\...`) recurs verbatim across 4 separate issues (#870, #889, #892, #898) in different worktrees on different task branches. A genuine TOCTOU race (concurrent deletion) would hit essentially random paths depending on timing; a deterministic, repeatable path recurring across unrelated runs is the signature of a path whose absolute length under `.scratch/verify-baseline-<hash>/...` consistently exceeds Windows' 260-char `MAX_PATH`, not an actual race. Neither walker nor `shutil.rmtree` currently opts into Windows' extended-length path API, so calls against such paths raise `FileNotFoundError` even though the entry exists — the walker currently treats this identically to a real vanished-entry race and silently skips it, which means: (a) any junction nested under that path is never stripped, and (b) the walker doesn't know the directory still has content. The subsequent actual removal (`git worktree remove --force` or `shutil.rmtree`) then hits `WinError 145` on that same directory because it was never actually emptied.
- Rejected:
  - Retry-with-extended-path-only-in-the-except-block (catch first, retry second): rejected in favor of prefixing proactively, because a proactive prefix prevents the failure outright (one code path, no duplicated try/except-retry logic per call site) rather than reacting to it after the fact.
  - Environment-only fix (registry `LongPathsEnabled=1` + relying on Python's long-path-aware manifest): rejected because mill cannot verify or enforce that registry setting is present on every Windows machine the task worktree runs on, and a code-level fix works unconditionally.
  - Inlining the extended-path logic separately into `_junction.py` and `_safe_rmtree.py` instead of a shared module: rejected — `_safe_rmtree.py` already imports `_junction`, so a third shared leaf module (`_long_path.py`, importing nothing project-internal) avoids duplicating the prefix logic and avoids any import-order concern.

### preserve-genuine-vanished-handling

- Decision: The existing "genuinely vanished" `FileNotFoundError` handling (a real TOCTOU race — sibling deletion, concurrent teardown) is NOT removed. After the long-path-safe retry (via `to_extended`) is attempted, if the operation *still* raises `FileNotFoundError`, the existing skip-and-log behavior applies unchanged.
- Rationale: Genuine concurrent-deletion races are a real, previously-fixed scenario (the comments in both walkers reference this explicitly) and must keep being handled gracefully — the long-path fix is additive, not a replacement for that handling.
- Rejected: Removing the try/except entirely and assuming long-path-safety eliminates all `FileNotFoundError` cases — rejected, that would reintroduce the original TOCTOU crash risk the comments describe.

### buildserver-lock-retry-out-of-scope

- Decision: No changes to the `dotnet build-server shutdown` + single-retry logic in `_worktree.remove_safe`'s `_is_dir_not_empty_error` exception handler (added by `07334bff`).
- Rationale: Issues #883, #884, #874, #878 all show the `obj/Debug/net9.0[-windows]/...` locked-build-output pattern that mechanism was specifically built to handle. Given the task brief's own framing ("Same failure family as the already-completed mill-go-windows-buildserver-lock-hygiene task... that target is done"), these are treated as reports that predate the fix propagating to the affected branches' plugin cache, not evidence of a residual code gap. Re-auditing that mechanism without new evidence of an actual gap would be scope creep.
- Rejected: Proactively adding a second retry / broader process-matching now — rejected absent concrete evidence the single retry is insufficient; can be revisited as its own task if a *new* report shows the retry itself failing (as opposed to predating it).

## Technical context

- Shared teardown entry point: `_worktree.remove_safe` (`plugins/mill/scripts/_worktree.py:244`) is called by `_verify_baseline.py:224` (used by both `millpy-implement.py --stage baseline` and `millpy-merge-in-subagent.py --recompute-baseline`), `millpy-implement.py:383`/`:436`, `millpy-spawn.py:204`, and `millpy-cleanup.py:572`. Fixing it once fixes all these callers; no per-caller changes needed.
- `_verify_baseline.py:106` is the existing precedent for the `-c core.longpaths=true` pattern (creation side) — mirror its placement (`-c core.longpaths=true` immediately after `-C <cwd>`, before the `worktree` subcommand token) for the removal-side fix, per `test-verify-baseline.py`'s existing argv-shape assertions for the creation call.
- `_junction.py::strip_all_in_worktree`'s `_walk` (lines 305-346) and `_safe_rmtree.py::_walk_strip_reparse_points` (lines 60-79) are structurally near-identical recursive walkers; both need the same `to_extended()` treatment at their `os.scandir` call.
- `_safe_rmtree.safe_rmtree` (lines 95-178) already has an `_onexc_chmod_retry` handler for read-only git pack files during `shutil.rmtree`; the long-path fix is independent of that (different failure mode) and should not disturb it — only the root string passed to `shutil.rmtree` changes.
- `_worktree.py::_is_windows_junction` (used by `copy_millhouse`, worktree-creation-time only, not teardown) operates on shallow `.millhouse/` paths and is out of scope — lower risk, not part of the reported failure pattern.
- `DirEntry.is_symlink()`/`is_dir()` calls inside the walkers use cached stat data from a successful `os.scandir()` call in most cases; the primary risk is the `os.scandir()` call itself failing on a long path, which is exactly what `to_extended()` on the scandir target fixes.

## Testing

- **TDD candidate:** `_long_path.to_extended()` — pure function, no filesystem access needed to test. Cover: already-prefixed idempotency, drive-absolute path (`C:\foo\bar` → `\\?\C:\foo\bar`), UNC path (`\\server\share\x` → `\\?\UNC\server\share\x`), POSIX no-op (returns `str(path)` unchanged regardless of `sys.platform` mocking).
- `test-worktree.py`: assert `-c core.longpaths=true` appears as an adjacent `-c`/value pair between `-C <cwd>` and the `worktree` token, in both the `git worktree remove` and `git worktree prune` argv built by `remove_safe` — mirror the existing argv-shape assertion pattern already used in `test-verify-baseline.py` for the creation-side call.
- `test-junction.py`: simulate a long-path `FileNotFoundError` during `os.scandir` inside `_walk` (mock) and assert the walker retries via the extended-path form before falling back to "vanished" — and separately, assert a *second* `FileNotFoundError` (even after the extended-path retry) still logs "vanished" and does not raise, preserving existing TOCTOU-tolerance behavior.
- `test-safe-rmtree.py`: same two scenarios (retry-then-succeed, retry-then-still-vanished) for `_walk_strip_reparse_points`, plus a case asserting `shutil.rmtree` is invoked with the extended-path-prefixed root string.
- No real Windows box or real git repo needed — all of this is testable via mocks per existing repo convention (in-memory/mock fixtures, no real git/LLM per `plugins/mill/unit_tests/` conventions).

## Q&A log

- **Q:** Which failure clusters are in scope? **A:** [auto-pick] Fix both Cluster A (missing `core.longpaths=true` on removal) and Cluster B (long-path-unsafe walkers) — both directly reproduce the reported `WinError 145`s and share one fix location. **Why:** both clusters are evidenced by the linked issues and fixing them together avoids a second discussion/plan round for what is really one coherent root-cause investigation.
- **Q:** What mechanism should fix Cluster B? **A:** [auto-pick] New `_long_path.py` helper (`to_extended(path) -> str`, Windows-only `\\?\` prefixing, no-op on POSIX) used to build scandir/rmtree/junction-removal path strings, preventing the long-path failure at the source. **Why:** testable on any OS via pure string logic, avoids duplicated try/except-retry logic per call site, and doesn't depend on an unenforceable environment prerequisite (registry `LongPathsEnabled`).
- **Q:** Is the dotnet build-server lock retry logic (07334bff) in scope for changes? **A:** [auto-pick] No — out of scope; that mechanism belongs to the already-completed sibling task, and the cluster-2 reports are presumed to predate that fix reaching the affected branches, not a residual gap in it. **Why:** avoids re-doing already-completed work and scope creep absent concrete evidence of a gap in that mechanism itself.
- **Q:** Should new unit tests be added? **A:** [auto-pick] Yes — `test-long-path.py` plus targeted additions to `test-worktree.py`, `test-junction.py`, `test-safe-rmtree.py`, following existing mock-based repo conventions. **Why:** matches `mill:testing` conventions and makes the fix verifiable without a real Windows box.
