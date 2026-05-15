# Discussion: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs

```yaml
task: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs
slug: mill-go-runtime-bugs
status: discussing
parent: main
```

## Problem

A cluster of ten behavioral bugs accumulated across mill-go, mill-start, mill-plan, mill-merge, and mill-merge-in, all observed in production runs. The bugs cause silent data loss (uncommitted work passes the cleanliness gate undetected), blocked automation (round-cap halts a converging fix loop), and incorrect halts (validator looks at the wrong path, PLUGIN_ROOT points to stale scripts). None have workarounds embedded in the codebase; operators have been patching them manually per-session. The fix set is bounded and self-contained -- no new subsystems, no API surface additions beyond one unit test each for the Python code changes.

## Scope

**In:**
- `plugins/mill/scripts/_paths.py` -- `resolve_task_path`: treat empty directories as non-existent so the `task/` fallback triggers (#281)
- `plugins/mill/scripts/_implementer_common.py` -- `_forward_output`: require fully-clean working tree (not just no new dirt) before emitting inferred success (#282 Gap 1)
- `plugins/mill/unit_tests/test-paths.py` -- add empty-dir fallback test case (#281)
- `plugins/mill/unit_tests/test-implementer-common.py` -- update Case 3b expected outcome to stuck/logic; add absolute-cleanliness test case (#282 Gap 1)
- `plugins/mill/templates/review-code-holistic.md` -- fix nested triple-fence in output-format example (#278)
- `plugins/mill/templates/implementer-brief.md` -- add explicit cross-worktree isolation rule banning `cd <parent-path>` (#287)
- `plugins/mill/skills/mill-go/SKILL.md` -- Entry Step 0: override PLUGIN_ROOT to task worktree when `plugins/mill` exists locally (#283); Handoff: add terminal cleanliness gate before `phase: done` (#282 Gap 2); Resume section: use fresh-retry (not `--resume`) for `state:running` (#290)
- `plugins/mill/skills/mill-start/SKILL.md` -- Discussion Review auto-mode: add progress-vs-non-progress check before applying cap (#279); add status.md working-tree safeguard before each `_status.append_phase` call (#289)
- `plugins/mill/skills/mill-merge/SKILL.md` -- Entry: cache `task:` and `task_description:` before Step 4 deletes `_mill/` (#285)
- `plugins/mill/skills/mill-merge-in/SKILL.md` -- verify loop: rewrite `${PLUGIN_ROOT}` to task worktree's local `plugins/mill` path before running each verify command (#292)

**Out:**
- No changes to the wiki config schema or `config.yaml` template.
- No new CLI scripts or Python modules.
- No changes to `millpy-implement.py` (the #290 fix is SKILL.md only).
- No changes to the review backend (`_review_code.py`, `_review_plan.py`, `_review_discussion.py`).
- No changes to `millpy-review-code.py` or its holistic path beyond the template fix.
- No changes to the per-batch review template (`review-code-batch.md`).

## Decisions

### #278 — template-only fix for holistic reviewer drift

- Decision: Fix the nested triple-fence in `review-code-holistic.md` only; do not add a lenient parse fallback to `parse_verdict`.
- Rationale: The model's drift output ("All 4 review findings are addressed...") contains no `verdict:` key, so any fallback that searches for `verdict:` anywhere in raw output would never trigger. The root cause is the nested ` ``` ` / ` ```yaml ` structure: the outer anonymous fence on line 35 is "closed" by the inner yaml block's closing ` ``` `, leaving lines 44-65 outside the fenced block and line 66 as an orphaned fence. The model reads this ambiguous structure and drifts. Fix: remove the outer anonymous fence and show the yaml block and surrounding scaffold as a literal indented example (no fence wrapping).
- Rejected: Adding a lenient fallback -- it is a no-op for the observed failure mode and would create a false sense of robustness for future unrelated drift patterns.

### #279 — progress-vs-non-progress check in mill-start auto-mode

- Decision: Before applying the round-cap block in mill-start auto-mode Discussion Review, compare the current round's gap titles against the previous round's. If the title set is entirely disjoint (no overlap), allow one extra round. If there is any overlap with the previous round (partial or full), apply the cap.
- Rationale: Mirrors mill-plan Phase: Plan Review step 5 semantics. A disjoint title set means the previous fix-pass worked and exposed a new surface; halting here is a false positive. Partial overlap is treated conservatively (block) to avoid infinite extension.
- Rejected: Allowing any number of extra rounds when progress is detected -- too permissive; partial overlap could still be non-convergent.

### #281 — fix resolve_task_path to handle empty directories

- Decision: In `resolve_task_path`, after `target.exists()` returns True, additionally check that the target is non-empty (for directories). If the directory exists but is empty, skip the early-return and attempt the `task/` fallback.
- Rationale: An in-flight task that had `_mill/plan/` created (e.g. from a failed mill-plan run that wrote the directory but not the files) causes `resolve_task_path` to return the empty `_mill/plan/` path. The validator then fails with `missing-overview` even though `task/plan/00-overview.md` exists. The existing test suite (case 4) documents the current behavior but does not cover the empty-dir case. The fix is one conditional in `_paths.py` and covers all callers.
- Rejected: Fixing each CLI caller individually -- duplicates logic; misses future callers.

### #282 Gap 1 — absolute cleanliness required for inferred success

- Decision: In `_forward_output`, when the inferred-success fallback would fire (no JSON, new commit exists, no NEW dirt vs snapshot), also run a full `git status --porcelain --untracked-files=no` and require the output to be empty. If any files are dirty (pre-existing or new), downgrade to `stuck_type: logic`.
- Rationale: The snapshot-diff gate catches new dirt but is blind to pre-batch dirt that persisted unnoticed. Inferred success is already a fallback of last resort; requiring a fully-clean tree is the correct invariant. Test Case 3b documented the bug behavior and must be updated to expect `stuck/logic`.
- Rejected: Keeping Case 3b's expected behavior ("pre-existing dirt is OK on inferred success") -- this IS the bug.

### #282 Gap 2 — terminal cleanliness gate in mill-go Handoff

- Decision: Add a SKILL.md step in mill-go Handoff (before appending `phase: done`) that runs `git status --porcelain --untracked-files=no` and halts with `BLOCKED: dirty working tree at task completion` if any files are dirty.
- Rationale: Even if Gap 1 is fixed (inferred success is stricter), a structured `status:success` report from the implementer does not guarantee the working tree is clean at task end -- the implementer could have committed only some files. A terminal gate catches this class of errors before `mill-merge-in` hits a merge conflict.
- Rejected: Relying solely on Gap 1 fix -- structured success reports bypass the inferred-success path and would not be caught.

### #283 — PLUGIN_ROOT override for self-modifying tasks

- Decision: In mill-go Entry Step 0, after resolving `PLUGIN_ROOT` from `${CLAUDE_PLUGIN_ROOT}`, check if `$(git rev-parse --show-toplevel)/plugins/mill` exists. If it does, override `PLUGIN_ROOT` to that path and emit a `[mill-go] NOTE: self-modifying repo detected; PLUGIN_ROOT overridden to worktree-local scripts` message.
- Rationale: If `plugins/mill` exists in the current worktree, this is the millhouse repo and the task is modifying mill scripts. Using the cache (CLAUDE_PLUGIN_ROOT) means the orchestrator runs stale scripts for every subsequent batch. The simple directory-existence check has zero false-positive risk for non-millhouse repos (they have no `plugins/mill/`). The log message makes the override visible to operators.
- Rejected: Plan-file scan for `plugins/mill/scripts/` -- overly specific; the directory check is simpler and equally accurate.

### #285 — cache task: field before cleanup commit

- Decision: In mill-merge Entry (after reading status.md for the phase gate), extract `task:` and `task_description:` into local variables and use them in Step 5's commit message and Step 6's PR title/body. Never re-read status.md after Step 4.
- Rationale: Step 4 runs `git rm -r _mill/`, deleting status.md from the working tree before Step 5 fires. The SKILL.md currently says "use `<task: field from status.md>`" in Step 5 without noting the ordering hazard. The fix is to read once in Entry and reference local variables throughout.
- Rejected: Reading from `git show HEAD~1:_mill/status.md` after the delete -- fragile; assumes the cleanup commit is exactly one parent away and the path hasn't migrated.

### #287 — cross-worktree isolation rule in implementer brief

- Decision: Add an explicit "Cross-worktree isolation" section to `implementer-brief.md` that bans `cd <parent-worktree>`, explains the cwd-corruption consequence, and gives the `git -C <path>` substitution pattern.
- Rationale: The implementer read-only explores the parent worktree by `cd`-ing into it, corrupting cwd for the rest of the session. The `conversation/SKILL.md` rule exists for orchestrator sessions but is not loaded by the implementer session. Embedding the rule verbatim in the brief is the only reliable delivery mechanism.
- Rejected: Loading `conversation/SKILL.md` in the implementer brief -- the brief is a prompt template, not a skill loader; adding a skill-load instruction would require the implementer to execute a skill command first, which is fragile.

### #289 — status.md working-tree safeguard

- Decision: In mill-start SKILL.md, before each `_status.append_phase(status_path, ...)` call in the Discussion Review loop, check if `status_path` exists in the working tree. If missing, restore via `git -C <worktree> checkout HEAD -- _mill/status.md` before proceeding.
- Rationale: Root cause of the silent deletion is unknown (not reproducible on demand; no plausible trigger in the session's operations). A defensive restore from HEAD is low-cost (idempotent if the file is present) and eliminates the `FileNotFoundError` that would otherwise crash the auto-mode loop. Investigating root cause is a separate follow-up task.
- Rejected: Adding the guard to `_status.append_phase` itself -- the Python helper should not perform git operations; side-effects belong at the orchestrator (SKILL.md) level.

### #290 — state:running resume uses fresh-retry not --resume

- Decision: Update mill-go SKILL.md Resume section so that `state:running` uses a fresh-retry invocation (`millpy-implement.py <batch_name>` with no `--resume` flag) instead of `--resume`.
- Rationale: When mill-go is interrupted mid-implementation, the underlying `claude` subprocess is killed. The session is dead and cannot be reattached via `--resume`. The SKILL.md was wrong to document `--resume` for this state; `--resume` is exclusively for the fix-cycle path (state:fixing) where a reviewer returned REQUEST_CHANGES. Fresh-retry re-runs the batch from the start, which is correct for a dead session. No Python code change needed.
- Rejected: Adding `--resume` without `--review-file` support to `millpy-implement.py` -- adds Python complexity for a code path that can't work (dead session).

### #292 — PLUGIN_ROOT substitution in verify commands

- Decision: In mill-merge-in SKILL.md, before the verify command loop, set `local_plugin_root = str(git_root / "plugins" / "mill")` and substitute `${PLUGIN_ROOT}` in each verify command string with `local_plugin_root` before executing.
- Rationale: Verify commands in batch plan files reference `${PLUGIN_ROOT}/unit_tests/<test>.py`. If the task created new test files, they exist only in the task worktree's `plugins/mill/`, not in the CLAUDE_PLUGIN_ROOT cache. The substitution is one line in the verify loop; `_plan_dag.iter_batch_verifies` stays clean. Only applies when `plugins/mill` exists in the current git root (millhouse repo tasks).
- Rejected: Adding a `plugin_root` parameter to `iter_batch_verifies` -- expands the library API for one caller's environment-specific need.

## Technical context

**Key files:**
- `plugins/mill/scripts/_paths.py` -- `resolve_task_path` (line 448): directory-existence check that needs empty-dir guard.
- `plugins/mill/scripts/_implementer_common.py` -- `_forward_output` (line 9): inferred-success fallback; add absolute-cleanliness check before emitting.
- `plugins/mill/scripts/_review_common.py` -- `parse_verdict` (line 828): unchanged; the #278 fix is template-only.
- `plugins/mill/unit_tests/test-paths.py` -- existing cases 1-6 for `resolve_task_path`; add case 7 (empty `_mill/plan/` dir -> fallback to `task/plan/`).
- `plugins/mill/unit_tests/test-implementer-common.py` -- existing cases 1-5; Case 3b changes expected outcome; add case 6 (pre-existing dirt, no new dirt, new commit -> stuck/logic).
- `plugins/mill/templates/review-code-holistic.md` -- lines 35-66: the nested-fence block that causes reviewer drift.
- `plugins/mill/templates/implementer-brief.md` -- add isolation section after `## Tools`.
- `plugins/mill/skills/mill-go/SKILL.md` -- Entry Step 0 (PLUGIN_ROOT), Resume section (state:running), Handoff (terminal gate).
- `plugins/mill/skills/mill-start/SKILL.md` -- Discussion Review section: round-cap and status.md safeguard.
- `plugins/mill/skills/mill-merge/SKILL.md` -- Entry: read and cache task:/task_description: fields.
- `plugins/mill/skills/mill-merge-in/SKILL.md` -- verify loop: `${PLUGIN_ROOT}` substitution.

**Pattern for resolve_task_path fix:** The function currently does `if target.exists(): return target`. The fix: for directory targets, additionally check `any(target.iterdir())` before returning. If the directory is empty, fall through to the fallback. The `any(iterdir())` guard only runs when `target.is_dir()` is True, so file targets are unaffected. The compat stderr message (`[compat] falling back to task/...`) should still print on the empty-dir path.

**Pattern for _forward_output fix:** After computing `new_dirt == []` and `HEAD != start_sha`, before emitting the inferred-success JSON, run `git -C <project_root> status --porcelain --untracked-files=no`. If stdout is non-empty, emit `{"status": "stuck", "stuck_type": "logic", "reason": "inferred success but working tree dirty -- implementer likely skipped git-commit on N file(s)"}` instead.

**review-code-holistic.md fix:** The current template wraps the entire example in an outer ` ``` ` fence (line 35) with an inner ` ```yaml ` block inside it. Because the opening ` ``` ` on line 35 has no language specifier, the parser treats the first ` ``` ` it encounters (the yaml block's closing fence, line 43) as closing the outer block, leaving lines 44-65 as raw text outside any fence. The fix: remove the outer anonymous fence entirely. Show the yaml block inline (just ` ```yaml ` ... ` ``` `), and wrap the surrounding non-yaml example lines in a prose description without a fence. This eliminates the ambiguity without changing the output format requirements.

**mill-go Step 0 PLUGIN_ROOT logic:** After the existing `if [ -z "$PLUGIN_ROOT" ]` block, add:
```bash
WORKTREE_PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
if [ -d "$WORKTREE_PLUGIN_ROOT" ]; then
    PLUGIN_ROOT="$WORKTREE_PLUGIN_ROOT"
    echo "[mill-go] NOTE: self-modifying repo detected; PLUGIN_ROOT overridden to $PLUGIN_ROOT"
fi
```

**mill-merge-in verify PLUGIN_ROOT substitution:** In the verify loop (after calling `_plan_dag.iter_batch_verifies`), for each `(batch_name, verify_cmd)` pair, replace `${PLUGIN_ROOT}` with `str(git_root / "plugins" / "mill")` when that local directory exists, before running the command.

**#279 progress tracking in mill-start:** Add a variable `prev_gap_titles: set[str] = set()` before the loop. After each GAPS_FOUND round's gap titles are parsed, compare with `prev_gap_titles`. If `current_titles.isdisjoint(prev_gap_titles)` and round >= 2, allow one extra round. Update `prev_gap_titles = current_titles` at end of each round. On overlap (not disjoint) at or past `max_review_rounds`: block. This mirrors mill-plan's step 5 semantics.

## Testing

**Python code changes (Batch 1) — unit tests required:**

- `test-paths.py` case 7: create `_mill/plan/` as an empty directory (no files inside), call `resolve_task_path(root, "_mill/plan/")`, assert it returns `root / "task" / "plan"` and `[compat]` appears in stderr. Also create `task/plan/` for the fallback to succeed.
- `test-implementer-common.py` Case 3b update: change expected outcome from `status=success/inferred=True` to `status=stuck/stuck_type=logic`. The scenario (pre-existing dirt, no new dirt, new commit) must now yield stuck.
- `test-implementer-common.py` Case 6 (new): pre-existing dirt captured in snapshot, implementer makes an empty commit (new HEAD), working tree is dirty. Expected: `stuck/logic`.
- Run `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` as the batch verify command.

**Template changes (Batch 2) — no automated test:** Visual inspection of the rendered template; the reviewer must no longer see nested fence ambiguity.

**SKILL.md changes (Batches 3 and 4) — no automated test:** The skills are prose instructions; correctness is verified by code review.

## Q&A log

- **Q:** Should all 10 bugs be addressed in one task or split by component? **A:** [auto-pick] All 10 in one task. **Why:** Same codebase surface, shared test infra, no inter-task dependencies; splitting adds merge/sequencing overhead.
- **Q:** Should the #278 fix include a runtime parse fallback in `parse_verdict`, or template fix only? **A:** [auto-pick] Template fix only. **Why:** Model drift output contains no `verdict:` key; a fallback would never trigger for the observed failure mode.
- **Q:** Should `test-implementer-common.py` Case 3b be updated to expect stuck/logic, or should a separate code path be added? **A:** [auto-pick] Update Case 3b. **Why:** Case 3b was documenting a bug; absolute cleanliness is the correct invariant for inferred success.
- **Q:** For #290, add `--resume`-without-`--review-file` support in Python, or fix SKILL.md to use fresh-retry? **A:** [auto-pick] SKILL.md fresh-retry. **Why:** Interrupted sessions are dead; Python change would add complexity for a code path that can't work.
- **Q:** Should the #281 fix go into `resolve_task_path` or into each CLI caller? **A:** [auto-pick] Fix `resolve_task_path`. **Why:** Single point of fix; all callers benefit automatically.
- **Q:** Should `${PLUGIN_ROOT}` substitution for verify commands go into the SKILL.md loop or into `iter_batch_verifies`? **A:** [auto-pick] SKILL.md loop. **Why:** `_plan_dag.iter_batch_verifies` stays clean; the substitution is environment-specific, not plan-DAG logic.
