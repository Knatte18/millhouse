# Discussion: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash

```yaml
task: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash
slug: mill-script-fixes
status: discussing
parent: main
```

## Problem

Three independent, code-level bugs were filed against mill (via `mill-self-report` / operator feedback) and bundled into one task since each is a small, self-contained fix with no shared code path:

1. **#600** — `mill-merge-in`'s Step 1 "no-op check" (`git log HEAD..<parent-branch> --oneline`) compares `HEAD` against the **local** parent-branch ref without fetching. If the parent branch happens to be checked out (and unpulled) in a sibling worktree — the exact scenario mill's own container layout encourages (a primary hub worktree with `main` checked out, alongside task worktrees) — the local ref is stale. The no-op check then reports "Nothing to merge — already up to date" and skips the entire checkpoint/merge/verify/rollback safety net, even though real upstream commits exist. This was caught only because `git-pr`'s own later fetch-and-merge step independently discovered the missed commits.
2. **#602** — `_worktree._default_enumerate_processes` (used by the live-process safety guard before killing stale worktree holders) invokes `powershell -Command "... | ConvertTo-Json -AsArray"`. `-AsArray` is a PowerShell 7-only parameter; under Windows PowerShell 5.1 (the Windows default `powershell` alias) it errors with a non-zero exit, so the helper's `except`/`returncode != 0` path silently returns `[]` — the safety check is effectively disabled on any PS5.1 machine. It was non-fatal in the observed case but silently defeats the guard.
3. **#597** — `_status.append_phase(status_path, phase, timestamp)` calls `status_path.read_text(...)` assuming a `pathlib.Path`. Passed a `str` (as happened when an operator/LLM session reconstructed `status_path` from subprocess-printed text instead of re-deriving it via `_paths.resolve_task_path`), it crashes with a bare `AttributeError: 'str' object has no attribute 'read_text'` — no hint that the fix is to wrap the argument in `Path(...)`.

**Why now:** all three are live correctness/reliability bugs in scripts every mill task exercises (merge-in on every `mill-merge`, process-enum on every `mill-go` batch pre-flight, `append_phase` on every phase transition); none require design work, just a fix consistent with existing project conventions.

## Scope

**In:**
- `plugins/mill/skills/mill-merge-in/SKILL.md` Step 1 (no-op check), Step 3 (merge command), and the "## No-op guarantee" section: fetch-then-compare-against-origin, with local-ref fallback when the parent branch has no upstream, and updated wording reflecting that Step 1 now always performs a network fetch (see #600 Decision's "No-op guarantee impact" note).
- `plugins/mill/scripts/_worktree.py` `_default_enumerate_processes`: drop `-AsArray` from the `ConvertTo-Json` invocation.
- `plugins/mill/scripts/_status.py`: replace the bare `AttributeError` on non-`Path` `status_path` with a clear, named `TypeError`, applied uniformly across every public `status_path`-taking function via one shared internal helper.
- Matching unit/integration test updates (`test-status.py`, `test-worktree.py`, `test-merge.py`) so the fixes are regression-covered.

**Out:**
- No behavior change to `mill-merge-in`'s conflict-resolution policy, verify-replay, or codeguide-update steps (Steps 2, 3.5, 4, 5) beyond the ref used for the merge itself.
- No change to `_worktree.py`'s non-Windows (`sys.platform != "win32"`) path, or to the taskkill logic.
- No broader `_status.py` API redesign (e.g. no switch to accepting `str | Path` unions, no new public coercion helper) — the fix is a clearer failure, not a more permissive signature.
- No attempt to install or depend on `pwsh` (PowerShell 7) being present — the `_worktree.py` fix must work on stock Windows PowerShell 5.1.

## Decisions

### #600 — fetch-and-compare-origin, with local-ref fallback

- Decision: At the start of Step 1, run `git fetch origin <parent-branch>`. If it succeeds, run the no-op diff as `git log HEAD..origin/<parent-branch> --oneline`, and change Step 3's merge command from `git merge <parent-branch>` to `git merge origin/<parent-branch>`, so the ref validated by the no-op check is the exact ref that gets merged. If the fetch fails (e.g. `<parent-branch>` is a sibling task branch never pushed to origin — a real case in mill's DAG-dependency model), fall back to today's behavior: diff and merge against the local `<parent-branch>` ref, printing a one-line note that the fetch was skipped/failed and why.
- Rationale: The reported bug is that the local ref can be stale relative to origin because the same branch name is checked out unpulled in a sibling worktree. Fetching updates `origin/<parent-branch>` regardless of what's checked out locally, so it works even for the reported scenario. Using `origin/<parent-branch>` for the actual merge (not just the no-op check) avoids re-introducing the same bug one step later — a fetch-only fix that still merges the stale local branch would mean Step 1 correctly reports "there are new commits" while Step 3 merges old content.
- Rejected: (a) Fixing only the no-op check's ref while leaving Step 3 merging the local branch — leaves a subtler version of the same inconsistency. (b) `git fetch origin <parent>:<parent>` to force-update the local ref before comparing — fails outright in the exact reported repro (git refuses to update a branch ref checked out in another worktree), so it does not fix the reported case at all.
- **No-op guarantee impact:** SKILL.md's "## No-op guarantee" section currently promises "this skill touches nothing" and frames Step 1 as a "cheap exit" `mill-merge` depends on for every call. An unconditional `git fetch` is still a **read-only, non-mutating** network call — no local ref, working tree, checkpoint, or branch state changes as a result of the fetch alone, so the "touches nothing" guarantee about local state still holds — but it is no longer a zero-network-cost check. Update the "## No-op guarantee" section's wording to state this explicitly (network fetch happens on every call; no local mutation happens when there's nothing to merge) rather than leaving the stronger "cheap exit" framing uncorrected. This cost is accepted as necessary: there is no way to detect a stale local ref without asking origin.

### #602 — drop `-AsArray`, do not switch to `pwsh`

- Decision: Remove `-AsArray` from the `ConvertTo-Json` call in `_worktree._default_enumerate_processes`. No other change — the existing Python-side normalization (`data = [data] if data else []`, ~line 375-376) already handles the single-object case that `-AsArray` existed to prevent.
- Rationale: This is the issue's own stated "minimal, most portable fix" — it works identically on PowerShell 5.1 and 7, with no new dependency.
- Rejected: Switching the invocation to `pwsh` (PowerShell 7) — not every machine running mill has `pwsh` on PATH; this would trade one silent-failure mode for another on any PS7-less machine, and CLAUDE.md's own environment notes confirm PS7 availability is machine-specific, not guaranteed.

### #597 — clear `TypeError`, not silent coercion, applied to every `status_path` function

- Decision: Add a small internal helper in `_status.py` (e.g. `_require_path(status_path, fn_name)`) that raises `TypeError(f"{fn_name}: status_path must be a pathlib.Path, got {type(status_path).__name__}")` when `status_path` is not a `Path`. Call it at the top of every public function in the module that takes `status_path` as its first argument — all seventeen, per the module docstring's Public API list (`_status.py` lines 18-37): `read`, `read_full`, `read_parent_branch`, `read_slug`, `read_branch`, `phase_entry_timestamp`, `update_field`, `set_blocked`, `append_phase`, `init_batches`, `set_batch_field`, `set_batch_fields`, `read_batches`, `read_status`, `get_module_verify_baseline`, `set_module_verify_baseline`, `clear_module_verify_baseline`.
- Rationale: This repo's established convention (see project memory on fixing misuse at the call site rather than loosening the API) is that a strict API surfaces caller mistakes clearly rather than absorbing them. Every current internal caller of these functions already derives `status_path` via `_paths` helpers (which return `Path`), so there is no real internal callsite to "fix" — the reported misuse came from an ad-hoc, dynamically-generated Bash/Python one-liner in an interactive mill-start/mill-plan session, not a fixed code path. Making the failure self-explanatory (clear `TypeError` naming the expected type) is the right-sized fix for that shape of misuse; the same latent bug exists identically in every sibling function, so the guard belongs in one shared helper rather than only in `append_phase`.
- Rejected: (a) Scoping the fix to `append_phase` only — the shared helper costs nothing extra and leaves no sibling function with the same unclear crash. (b) Silently coercing `str` → `Path` inside the functions — rejected as an API-permissiveness retrofit that masks caller mistakes instead of surfacing them; also risks accepting other wrong types (e.g. `None`) as an accidental side effect of a broad `try/except`.

## Technical context

- `plugins/mill/skills/mill-merge-in/SKILL.md` Steps 1 and 3 are plain inline bash in the SKILL markdown — there is no backing Python script for the no-op check or merge command. The fix is a markdown edit, not a Python change. No unit test can exercise markdown directly; coverage comes from `plugins/mill/integration_tests/test-merge.py`, which currently hand-replicates the Step 1 command (lines ~446-453) as a sanity check against real git state. That replica must be updated to match the new fetch-then-compare-origin behavior, or it will silently drift from the doc it verifies.
- `_worktree.py`'s `kill_stale_holders(worktree, enumerate_processes=...)` already exposes `enumerate_processes` as an injectable seam (see `plugins/mill/unit_tests/test-worktree.py` lines ~358-397, which inject `_fake_enumerate` / `_bad_enumerate` / `_fake_enumerate_500`). The `-AsArray` removal only touches the default real enumerator (`_default_enumerate_processes`, `_worktree.py` ~lines 358-386); the injectable-seam tests are unaffected and don't need changes, but a new test should exercise the real `_default_enumerate_processes` path (or at minimum assert the constructed PowerShell command string no longer contains `-AsArray`) since it was previously untested and is exactly where the bug lived.
- `_status.py`'s public API list is documented in its module docstring (lines 18-37). All seventeen `status_path`-taking public functions are listed there — including `phase_entry_timestamp` (line 797), `set_batch_field` (line 920), and `set_batch_fields` (line 953), which are easy to miss since they're defined well below the more commonly-used functions. `_write_batches` (line 606) is a private helper (leading underscore) and should NOT get the guard applied redundantly if it's always called from an already-guarded public function — verify this at plan time by checking its callers.
- `plugins/mill/unit_tests/test-status.py` already has extensive `append_phase` coverage (Path-typed `status_path` throughout, e.g. lines 135-300) to extend with the new str-input-raises-TypeError case.

## Constraints

- ASCII-only in any new `print()`/error messages that could hit stdout on Windows (cp1252 crashes on non-ASCII) — per CLAUDE.md conventions. The `TypeError` message is fine (ASCII), just don't introduce em-dashes or arrows in it.
- Verify commands in this task's plan must be Python-project-shaped (`PYTHONPATH=` prefix) per CLAUDE.md's "Verify command shape" rule, since this repo has `pyproject.toml`.
- No `_status.py` behavior change for existing valid (`Path`-typed) callers — every existing unit test in `test-status.py` must continue to pass unmodified.

## Testing

- **`_status.py` (TDD candidate):** new unit test(s) in `test-status.py` — call `append_phase("some/str/path", "phase", "ts")` (and at least one or two of the other guarded functions, e.g. `update_field`, `set_blocked`) with a plain `str` and assert a `TypeError` is raised whose message names the function and the actual type received (not a bare `AttributeError`). Keep all existing `Path`-typed test cases passing unchanged.
- **`_worktree.py` (TDD candidate):** new unit test in `test-worktree.py` — assert the constructed PowerShell command string (or the subprocess call args) for `_default_enumerate_processes` no longer contains `-AsArray`. If feasible without excessive mocking, also add a regression case that fakes a single-dict (non-list) `ConvertTo-Json` result to confirm the existing normalization (`data = [data] if data else []`) still produces a one-element list — this is the exact case `-AsArray` was (incorrectly) relied upon to prevent.
- **`mill-merge-in` no-op check:** update `test-merge.py`'s Step 1 replica (~lines 446-453) to `git fetch origin <parent>` then diff against `origin/<parent>`, keeping the integration test aligned with the corrected SKILL.md steps. No new test scenario is required for the "parent branch never pushed to origin" fallback path given this task's scope (documented behavior, not exercised by the existing test fixture) — mill-plan may add one if it's cheap within the existing `_setup_trio` fixture, but it is not required.

## Q&A log

- **Q:** #600 — fetch-and-compare-origin (with local-ref fallback) vs. fixing only the no-op check's ref vs. force-updating the local ref via `git fetch origin <parent>:<parent>`? **A:** [auto-pick] Fetch `origin/<parent-branch>`, compare and merge against it, with local-ref fallback on fetch failure. **Why:** the reported bug is specifically a stale *local* ref; fetching updates the remote-tracking ref regardless of what's checked out elsewhere, and using that same ref for the actual merge (not just the check) avoids reintroducing the bug one step later. Force-updating the local ref was rejected because it fails outright in the exact reported repro (branch checked out in a sibling worktree).
- **Q:** #602 — drop `-AsArray` vs. switch to invoking `pwsh`? **A:** [auto-pick] Drop `-AsArray`, keep invoking `powershell`. **Why:** the issue's own suggested minimal fix; works identically on PS5.1 and PS7; switching to `pwsh` would depend on PowerShell 7 being installed and on PATH, which is not guaranteed on every machine running mill.
- **Q:** #597 — raise a named `TypeError` (scoped to `append_phase` only, or to every `status_path`-taking function) vs. silently coerce `str` → `Path`? **A:** [auto-pick] Raise a named `TypeError`, applied via one shared helper to every public `status_path`-taking function in `_status.py`. **Why:** matches this repo's established convention of surfacing caller misuse clearly rather than loosening the API to absorb it; every current internal caller already passes a `Path`, so there's no real callsite to fix instead — the misuse came from an ad-hoc interactive one-liner, not a fixed code path. Scoping to every function (not just `append_phase`) costs nothing extra since the guard is a shared helper and removes the same latent bug from every sibling function.
- **Q:** Should `test-merge.py`'s manual no-op-check replica be updated to match the new fetch-then-compare-origin behavior? **A:** [auto-pick] Yes, update it. **Why:** the test exists specifically to sanity-check the documented SKILL.md steps against real git state; leaving it comparing only the local ref would let it silently drift from the doc it verifies.
