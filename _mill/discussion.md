# Discussion: Accumulated bug fixes

```yaml
task: Accumulated bug fixes
slug: mill-bug-fixes
status: discussing
parent: main
```

## Problem

Two bugs surfaced during recent mill-go/mill-merge runs and were documented as self-report files in `.scratch/`. Both cause incorrect "stuck" or invalid-state outcomes that require manual operator intervention to recover from.

**Bug 1 — verify-fix-no-report:** `millpy-merge-in-subagent.py --mode verify-fix` returns `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}` even when the sub-agent successfully fixes failing tests and commits. Root cause: after the sub-agent runs, `_forward_output` is called without `start_sha` or `snapshot_path`, so the inferred-success fallback is unavailable; if the sub-agent's output contains no `{"status": ...}` sentinel, a stuck verdict is emitted regardless of whether the tests now pass.

**Bug 2 — mill-plan-approved-false:** `mill-plan` can write `phase: planned` to `status.md` and commit a "mill-plan: handoff" commit while `_mill/plan/00-overview.md` still carries `approved: false`. `mill-go` then halts at its entry-step 6 plan-approved check, requiring the operator to manually flip the frontmatter. Root cause: Phase: Handoff in `mill-plan/SKILL.md` does not verify that `approved: true` before calling `_status.append_phase`.

## Scope

**In:**
- `plugins/mill/scripts/millpy-merge-in-subagent.py` — add a post-sub-agent re-verification step in `_run_verify_fix`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` — update `test_6` and `test_7`; add a new test for the no-JSON/post-verify-success path
- `plugins/mill/skills/mill-plan/SKILL.md` — add an `approved: true` assertion guard at the start of Phase: Handoff

**Out:**
- `--tools ""` vs `--allowedTools ""` inconsistency in `millpy-claude-sub.py` bulk mode — not confirmed as a runtime bug; leave for a dedicated investigation
- Other self-report items (`automerge-cwd`, `merge-locked-worktree-cwd`, `subagent-active-gate`, `remove-safe-invalid-arg`, review-flow tests, encoding) — all confirmed fixed in current `main`
- Any other mill-go/mill-merge/mill-cleanup behavior not explicitly listed above

## Decisions

### verify-fix: post-sub-agent re-verification

- Decision: After the sub-agent call in `_run_verify_fix` completes, immediately re-run the verify command via `subprocess.run`. If it returns exit code 0, emit `{"status": "success", "commit_sha": <HEAD>}` and return. If it returns non-zero, fall through to `_forward_output(output, project_root)` for structured-JSON parsing.
- Rationale: Directly observes the outcome (tests pass/fail) instead of trusting the sub-agent's output format. Robust even if the prompt template changes or the sub-agent omits a JSON sentinel. Introduces no new dependencies.
- Rejected:
  - Pass `start_sha` + `snapshot_path` to `_forward_output`: requires capturing the pre-sub-agent HEAD before running the verify cmd, and relies on the cleanliness check — more complex with no correctness advantage over a direct re-run.
  - Update the sub-agent prompt to always emit a JSON sentinel: prompt-engineering changes break silently; direct verification is more reliable.

### mill-plan Handoff: approved=true guard

- Decision: At the very start of Phase: Handoff in `mill-plan/SKILL.md`, before calling `_status.append_phase(status_path, "planned", ...)`, read `plan_dir/00-overview.md` and parse the `approved:` field from the fenced YAML block. If the value is not `true`, halt with a clear error: "mill-plan Handoff guard: plan/00-overview.md has approved: false — plan review did not complete. Re-run /mill-plan to enter Phase: Plan Review."
- Rationale: Catches the invalid state before any status.md mutation. The operator gets a clear action rather than a corrupted state that mill-go silently rejects later.
- Rejected:
  - Add the guard at the end of Phase: Plan Review instead: the guard in Handoff is a general safety net and is independent of whether Plan Review ran or was skipped. Handoff is the single exit point for all paths (skip, approve-r1, approve-after-fix, exhausted+user-override) so the guard fires correctly for all of them.
  - Have mill-go re-validate approved: fixes the symptom not the cause; mill-go entry is the wrong layer.

### test updates for verify-fix

- Decision: Update `test_6` and `test_7` to patch `subprocess.run` with `side_effect` (list) instead of `return_value` (single value) so the initial verify call and the post-sub-agent re-verify call can return independent values. Add `test_11_verify_fix_failure_subagent_no_json_post_verify_success` that returns an empty/non-JSON sub-agent output and a successful post-verify, asserting `status: success`.
- Rationale: The new re-verify call changes the `subprocess.run` call count; tests that assume a single call will fail or silently allow the second call to return the mocked first value.
- Rejected: Minimal test changes with no new test — would leave the core fix path untested.

## Technical context

**`millpy-merge-in-subagent.py`** (`plugins/mill/scripts/`):
- `_run_verify_fix` (line ~204): initial verify via `subprocess.run(args.cmd, shell=True, ...)`. On failure, builds prompt with `args.cmd`, verify output, and `git diff` (via `_subprocess_util.run`), spawns sub-agent via `_implementer_claude.run`, then calls `_forward_output(output, project_root)`.
- The fix inserts a post-sub-agent verify step between the `_implementer_claude.run` return and the `_forward_output` call.
- `_subprocess_util.run` is used for `git rev-parse HEAD` and `git diff` calls inside the function; the re-verify uses `subprocess.run` (same as the initial verify) so patching stays symmetrical in tests.

**`_forward_output`** (`plugins/mill/scripts/_implementer_common.py`):
- Calls `_subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)` whenever it finds a `{"status": ...}` JSON in output to attach `commit_sha`.
- When no JSON is found: falls back to inferred-success logic (`start_sha` + `snapshot_path` required, neither provided by verify-fix) → emits stuck/logic.
- Not changed by this task; re-verify in `_run_verify_fix` short-circuits before `_forward_output` on success.

**`test-millpy-merge-in-subagent.py`** (`plugins/mill/unit_tests/`):
- `test_6` (`verify-fix mode: verify fails -> sub-agent dispatched, returns success`): patches `subprocess.run` via `return_value` (single fail result) and `_subprocess_util.run` via `side_effect` [git-diff, git-rev-parse]. After fix: `subprocess.run` needs `side_effect=[fail, success]` (initial-fail, post-verify-success); `_subprocess_util.run` side_effect becomes [git-diff, git-rev-parse-for-post-verify] — same length, different semantics (the second `_subprocess_util.run` is now for the post-verify success path, not for `_forward_output`).
- `test_7` (`verify-fix mode: verify fails, sub-agent returns stuck`): same `subprocess.run` fix (side_effect=[fail, fail]); `_subprocess_util.run` side_effect stays [git-diff, git-rev-parse] because `_forward_output` still calls `_subprocess_util.run` when it finds the stuck JSON to attach `commit_sha`.
- New `test_11`: `subprocess.run` side_effect=[fail, success] (initial-fail, post-verify-success); `_implementer_claude.run` returns `("", "fake")` (empty, no JSON); `_subprocess_util.run` side_effect=[git-diff, git-rev-parse-for-success]; assert `status: success`.

**`mill-plan/SKILL.md`** (`plugins/mill/skills/mill-plan/`):
- Phase: Handoff currently starts with a bare `_status.append_phase(status_path, "planned", _timestamp.now_utc_iso())` call.
- Reading `approved:` from the overview: the field is in a fenced YAML block (` ```yaml ... ``` `) inside `plan_dir/00-overview.md`. Parse it by extracting the YAML text with a regex and reading `approved:`. The simplest approach is to `Read` the file content and grep for `^approved:\s*` in the YAML block.
- The `plan_dir` variable is already in scope at Handoff (set during Phase: Plan or loaded from config for re-entry).
- Halt message should tell the operator exactly what went wrong and how to recover.

## Constraints

No CONSTRAINTS.md present. Key constraints from CLAUDE.md:
- SKILL.md edits must use `${CLAUDE_PLUGIN_ROOT}` for any CLI paths (not applicable here since no CLI paths added).
- `print()` / `_log()` output: ASCII only (`->` not `→`).
- Test files live in `plugins/mill/unit_tests/`; run via `run-all.py`.

## Testing

**`millpy-merge-in-subagent.py`:**
- TDD candidates: `test_6` (update), `test_7` (update), `test_11` (new).
- Scenarios to cover:
  - Initial verify passes → no sub-agent (test_5, unchanged).
  - Initial verify fails, sub-agent returns success JSON → post-verify irrelevant since _forward_output returns success (test_6 still asserts status=success, but now via post-verify path if the mock returns success).
  - Initial verify fails, sub-agent returns no JSON, post-verify passes → status=success (test_11, new).
  - Initial verify fails, sub-agent returns stuck JSON, post-verify still fails → status=stuck (test_7, updated).
  - Run verify after updating test_6/test_7/test_11: `plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`.
  - Run all: `plugins/mill/.venv/Scripts/python.exe plugins/mill/unit_tests/run-all.py`.

**`mill-plan/SKILL.md`:**
- No unit test applies to SKILL.md edits. The guard is validated by reading the modified section and confirming the logic is self-consistent with the rest of the Phase: Handoff description.

## Q&A log

- **Q:** What is the scope? **A:** [auto-pick] Fix exactly the 2 documented open bugs. **Why:** Both are clearly reproduced and located; no speculative scope.
- **Q:** How to fix `_run_verify_fix`? **A:** [auto-pick] Re-run verify after sub-agent; emit success if passes; fall back to `_forward_output` if not. **Why:** Directly confirms the outcome rather than parsing LLM output.
- **Q:** How to update tests? **A:** [auto-pick] Update test_6 and test_7 with side_effect on subprocess.run; add test_11 for no-JSON/post-verify-success path. **Why:** New re-verify call changes call count; the fixed path needs test coverage.
- **Q:** Where in mill-plan SKILL.md should the guard live? **A:** [auto-pick] Start of Phase: Handoff, before `_status.append_phase`. **Why:** Catches the invalid state before any mutation; Handoff is the single exit point for all paths.
