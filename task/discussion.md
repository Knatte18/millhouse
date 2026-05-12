# Discussion: 54 (A) — Bug-fix batch 6 (post-46/50 triage)

```yaml
task: 54 (A) — Bug-fix batch 6 (post-46/50 triage)
slug: mill-misc-fixes-6
status: discussing
parent: main
```

## Problem

Five bugs identified after tasks 46 and 50 were scope-locked. Three are mill-merge/worktree-teardown failures that can strand a task worktree requiring manual cleanup. One is a startup failure in mill-go when `spawn.branch_prefix` is absent from config. One is dead code in `scripts/` that causes confusion when adding new reviewers.

The bugs cause real operator pain: #265 and #264 together caused a manual `rmdir` + `git branch -D` teardown in a live session (2026-05-12). #261 and #262 cause hard startup failures that abort mill-go before it does any work.

## Scope

**In:**
- `_worktree.remove_safe` — handle "is not a working tree" via rmtree fallback (#264, #265)
- `_marker.slug_from_branch` — self-healing retry when branch has user prefix but `spawn.branch_prefix` is unset (#261)
- `mill-go` SKILL.md Entry — detect empty `$CLAUDE_PLUGIN_ROOT` and resolve fallback path (#262)
- Delete `_reviewer_opushigh.py`, `_reviewer_opusmax.py`, `_reviewer_opusmid.py` from `scripts/` (#267)
- Unit tests for `_worktree.remove_safe` "is not a working tree" case and `_marker.slug_from_branch` user-prefix-with-empty-config case

**Out:**
- Root-cause investigation of why the `.git` pointer disappears after the cleanup commit (#265 root cause is unknown and unreproducible; the defensive fix in `remove_safe` is sufficient)
- mill-setup changes (CLAUDE_PLUGIN_ROOT is already written as a Windows user env var in Phase 4.7; the fix is a skill-level fallback, not a setup change)
- Deleting `_reviewer_single.py` or `_reviewer_test_stub.py` (both are actively imported by `_review_code.py`, `_review_discussion.py`, `_review_plan.py`, and `_reviewer_single.py` respectively)
- Any change to `wiki/reviewers.yaml` or the reviewer dispatch architecture

## Decisions

### #264/#265 — "is not a working tree" triggers rmtree fallback

- **Decision:** Extend `remove_safe`'s long-path fallback trigger to include "is not a working tree" alongside "Filename too long". Rename the condition variable to `rmtree_fallback` for clarity.
- **Rationale:** "is not a working tree" means git has already deregistered the worktree. Junctions are stripped in step 1, so `shutil.rmtree` is safe. If the path is locked (CWD session on Windows), rmtree raises `PermissionError` → `WorktreeLockedError`, giving callers the right error with recovery instructions. If the path doesn't exist, rmtree is skipped and `git worktree prune` runs. This covers both the CWD-lock case (#264) and the deregistered-dir case (#265) with one change and no new conditional branches.
- **Rejected:** Adding "is not a working tree" to `_lock_patterns` — this always raises `WorktreeLockedError` without attempting cleanup, leaving deregistered-but-existing directories orphaned on disk.

### #261 — self-healing slug retry when branch has user prefix

- **Decision:** In `_marker.slug_from_branch`, after the slug (derived by stripping `prefix`) is not found in Home.md: if the branch contains `/` and the prefix is empty, strip everything up to and including the first `/` and retry the Home.md lookup. On failure, raise `MarkerError` with both the original slug and the stripped slug in the message.
- **Rationale:** No config changes needed. Backward-compatible — only activates when prefix is empty AND branch contains `/` AND the exact-match lookup already failed. Does not affect the configured-prefix path.
- **Rejected:** Having mill-spawn write `spawn.branch_prefix` to `config.local.yaml` — requires mill-spawn changes and adds coupling between mill-spawn and config schema; the marker self-heal is simpler and localised.
- **Rejected:** Reading `.millhouse/active.slug.md` as a fallback — that file is a legacy marker from v1 and not guaranteed to exist.

### #262 — CLAUDE_PLUGIN_ROOT fallback in mill-go skill preamble

- **Decision:** At mill-go Entry (before step 1), add a shell detection block: if `$CLAUDE_PLUGIN_ROOT` is empty or unset, resolve it by running `git rev-parse --show-toplevel` and appending `plugins/mill` (the source-tree path). Assign result to `PLUGIN_ROOT` and use `$PLUGIN_ROOT` in all subsequent `uv run` commands within the skill. Log the resolution path so the operator can see which root was used.
- **Rationale:** Skill-level fix with zero infrastructure cost. Consistent with CLAUDE.md guidance: "fall back to `plugins/mill/` source-tree paths only when running from the millhouse repo itself". Using `git rev-parse --show-toplevel` is more robust than a hardcoded path for the worktree case.
- **Rejected:** Writing plugin root to `.millhouse/plugin-root` during mill-setup — more infrastructure, and mill-setup already handles this via the Windows env var; the skill preamble is enough to cover the shell-inheritance gap.
- **Rejected:** A wrapper shell script — adds a new file with no benefit over the inline skill preamble.

### #267 — which reviewer files are dead code

- **Decision:** Delete `_reviewer_opushigh.py`, `_reviewer_opusmax.py`, `_reviewer_opusmid.py`. Keep `_reviewer_single.py` and `_reviewer_test_stub.py`.
- **Rationale:** The three opus-variant files export a `MODE` constant and a `run()` function matching the old reviewer-module protocol. Nothing imports them: grep across all scripts confirms zero import sites. `_reviewer_single.py` is the active spec-dispatching layer imported by all three review CLIs; `_reviewer_test_stub.py` is imported by `_reviewer_single.py` for the `test_stub` provider case.
- **Rejected:** Deleting all five — `_reviewer_single.py` is production code, removing it breaks `_review_code.py`, `_review_discussion.py`, and `_review_plan.py`.

## Technical context

**`_worktree.remove_safe`** (`plugins/mill/scripts/_worktree.py` lines 198–285):
The fallback path already exists for `"Filename too long"`. The change is minimal: extend the `long_path_marker` boolean to include `"is not a working tree"` in the OR condition (or rename it `rmtree_fallback`). No new branches, no new exceptions.

**`_marker.slug_from_branch`** (`plugins/mill/scripts/_marker.py` lines 28–62):
The retry logic inserts a single additional block after the `task is None` check. Algorithm:
1. If `task is None` AND `"/" in branch` AND `prefix == ""`:
   - `stripped_slug = branch.split("/", 1)[1]`
   - Re-query `tasks` for `stripped_slug`
   - If found, return `stripped_slug`
2. If still None: raise `MarkerError` with a message including both slugs tried.

**mill-go SKILL.md** (`plugins/mill/skills/mill-go/SKILL.md`):
The preamble block goes between Entry step 0 (not yet numbered) and step 1. It is a Bash snippet the operator (or mill-go orchestrator) runs once before all other `uv run` calls. It sets `PLUGIN_ROOT` and is used via `$PLUGIN_ROOT` everywhere `$CLAUDE_PLUGIN_ROOT` appears in the skill. The skill file is documentation — the implementer modifies the SKILL.md text.

**Dead reviewer files** (`plugins/mill/scripts/`):
- `_reviewer_opushigh.py` — 25 lines, wraps `run_bulk` for Opus at high effort
- `_reviewer_opusmax.py` — 25 lines, wraps `run_bulk` for Opus at max effort
- `_reviewer_opusmid.py` — 25 lines, wraps `run_bulk` for Opus at medium effort
- Grep confirms zero import sites for all three.

**Unit test infrastructure**: `plugins/mill/unit_tests/test-worktree.py` uses `unittest.mock.patch` on `_subprocess_util.run` to inject fake git output. Adding test cases for "is not a working tree" follows the same pattern as the existing "Permission denied" and "Filename too long" tests. `test-marker.py` uses `_test_helpers._make_task_worktree` with real git repos; the new test needs a worktree with branch `hanf/foo` and empty `spawn.branch_prefix` in cfg.

## Testing

**`_worktree.remove_safe` (test-worktree.py):**
- New case: mock git stderr = "fatal: 'path' is not a working tree", path.exists() True → rmtree called, exits cleanly (success).
- New case: mock git stderr = "fatal: 'path' is not a working tree", path.exists() True, shutil.rmtree raises PermissionError → `WorktreeLockedError` raised.
- New case: mock git stderr = "fatal: 'path' is not a working tree", path.exists() False → no rmtree call, `git worktree prune` runs, exits cleanly.
- Regression: existing "Permission denied" and "is in use" cases still raise `WorktreeLockedError`. Existing "Filename too long" still uses rmtree fallback.

**`_marker.slug_from_branch` (test-marker.py):**
- New case: branch = `hanf/foo`, cfg has empty/absent `spawn.branch_prefix`, Home.md has `[[foo]] [active]` → returns `"foo"`.
- New case: branch = `hanf/bar`, cfg has empty prefix, Home.md has only `[[foo]]` → raises `MarkerError` (not found after both attempts).
- Regression: existing `test_slug_from_branch_empty_prefix` (branch = `foo`, no prefix, found in Home.md) still passes.
- Regression: `test_slug_from_branch_prefix_mismatch` (cfg prefix = `hanf/`, branch = `other/foo`) still raises `MarkerError`.

**mill-go SKILL.md changes:** No unit test — skill files are documentation. Manual verification: run `/mill-go` in a worktree from a fresh VS Code terminal where `$CLAUDE_PLUGIN_ROOT` is unset; confirm the preamble resolves the path and the first `uv run` succeeds.

**Reviewer file deletion:** No unit test needed — deletion is verified by confirming the files no longer exist. Run `plugins/mill/unit_tests/run-all.py` after deletion to confirm no test imports the deleted modules.

## Q&A log

- **Q:** How should `remove_safe` handle "is not a working tree"? Options: 1) rmtree fallback (same as long-path) 2) add to `_lock_patterns` (always WorktreeLockedError) 3) check worktree list membership. **A:** [auto-pick] rmtree fallback. **Why:** Handles both CWD lock and deregistered-dir with one code path; if locked, rmtree raises PermissionError → WorktreeLockedError; if dir is gone, rmtree is skipped; cleaner than branching on worktree list membership.
- **Q:** How to fix slug_from_branch for user prefix with no configured branch_prefix? Options: 1) self-healing retry in _marker.py 2) mill-spawn writes branch_prefix to config.local.yaml 3) fallback to active.slug.md. **A:** [auto-pick] self-healing retry. **Why:** Zero config changes, backward-compatible, localised to _marker.py.
- **Q:** How to resolve empty CLAUDE_PLUGIN_ROOT in mill-go? Options: 1) skill preamble detection + PLUGIN_ROOT variable 2) .millhouse/plugin-root file 3) wrapper script. **A:** [auto-pick] skill preamble detection. **Why:** No infrastructure changes needed; consistent with CLAUDE.md guidance.
- **Q:** Which reviewer files are dead code? Options: 1) delete opushigh/opusmax/opusmid only 2) delete all five including _reviewer_single.py 3) keep all with comment. **A:** [auto-pick] delete only the three unused opus variants. **Why:** grep confirms _reviewer_single.py is imported by three production modules; _reviewer_test_stub.py is imported by _reviewer_single.py.
