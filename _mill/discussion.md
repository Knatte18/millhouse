# Discussion: mill-go / mill-merge / plan-validator follow-up bugs (round 2)

```yaml
task: mill-go / mill-merge / plan-validator follow-up bugs (round 2)
slug: mill-orchestration-hardening-r2
status: discussing
parent: main
```

## Problem

The previous hardening tasks (#007 `mill-orchestration-loop-hardening`, #008 `mill-merge-teardown-recovery`) fixed the first wave of pipeline bugs, but six more surfaced in subsequent runs. Each is small in isolation; they are grouped here to avoid merge churn because they all touch the same surfaces: `mill-go SKILL.md`, `millpy-fix.py`, `_implementer_common.py`, `_plan_validate.py`, `_config.py`, `mill-merge SKILL.md`, `millpy-merge-in-subagent.py`, and the `merge-in-conflict-brief.md` template.

Two of the six (#401 and #402) share a root cause: when the cache install predates a task branch that added new helpers or config keys, the cached template/scripts dir is stale. Three others (#397, #398, #392) are logic gaps in the mill-go pipeline. One (#399) is a semantic miss in conflict resolution.

## Scope

**In:**
- `mill-go SKILL.md` — move `commit_sha` write to after the cleanliness gate (#397)
- `plugins/mill/scripts/_implementer_common.py` — extend `_forward_output` to fire inferred-success when `start_sha` is given but `snapshot_path` is None (#398)
- `plugins/mill/scripts/millpy-fix.py` — capture `start_sha` before the fixer session and pass it to `_forward_output` (#398)
- `plugins/mill/scripts/_plan_validate.py` — add `verify-full-suite` ERROR check (#392)
- `plugins/mill/scripts/_config.py` — augment `template_cfg` with worktree-local template when available (#401)
- `mill-merge SKILL.md` — update step 6 to prefer worktree scripts dir over cache; add `ImportError` fallback message (#402)
- `plugins/mill/templates/merge-in-conflict-brief.md` — add UD-conflict detection instructions with replacement-pattern check (#399)
- Unit tests: `test-implementer-common.py`, `test-millpy-fix.py`, `test-plan-validate.py`, `test-config.py`

**Out:**
- `millpy-implement.py` — #397 only affects the SKILL.md instruction; the CLI already reads `commit_sha` from `_forward_output`'s JSON; no CLI change needed
- `millpy-merge-in-subagent.py` — the bug is in the resolver's brief template, not the dispatcher script
- `mill-plan SKILL.md`, `mill-spawn`, `mill-start`, `wiki` module — not touched
- CONSTRAINTS.md — none exists in this repo

## Decisions

### #397 — commit_sha write timing (cleanliness gate false-positive)

- Decision: Move the `set_batch_field(commit_sha)` write from step 2 ("Parse implementer report") to AFTER the cleanliness gate passes (step 2b), immediately before continuing to the code review loop (step 3). The SKILL.md wording changes from "Record `commit_sha`..." as a step-2 action to a step-2b post-gate action.
- Rationale: Writing `commit_sha` to `status.md` dirties the worktree before `compute_new_dirt` runs, causing the gate to flag the Builder's own bookkeeping write as implementer-introduced dirt. Moving the write past the gate eliminates the false positive with no correctness cost.
- Rejected: Taking the cleanliness snapshot AFTER the `commit_sha` write (proposal option b) — it would correctly measure only implementer dirt, but requires tracking TWO snapshot moments and is harder to follow in the SKILL.

### #398 — inferred-success detection for fixer sessions

- Decision: Extend `_forward_output` in `_implementer_common.py` with a new branch: when `start_sha is not None` AND `snapshot_path is None`, check if HEAD advanced since `start_sha` AND the working tree is clean; if both, emit `{"status":"success","commit_sha":"<sha>","session_id":"<id>","inferred":true}`. In `millpy-fix.py`, capture `start_sha = git rev-parse HEAD` before dispatching the fixer session and pass it as `start_sha=start_sha` to `_forward_output`.
- Rationale: The existing inferred-success fallback requires BOTH `start_sha` and `snapshot_path`. Fixers have no cleanliness snapshot (they are not subject to the implementer cleanliness gate), so the fallback never fires for them. "HEAD advanced + clean tree" is sufficient evidence that the fixer committed its work; the missing JSON is a session-exit artifact, not a logic failure. Status value is `"success"` with `inferred=true` (not a new key) to match mill-go's existing parse logic which routes any non-`success`/non-`stuck` response as an error.
- Rejected: Introducing a new `"success-no-json"` status — mill-go would need a new parse branch and the semantics are identical to inferred-success.

### #392 — full-suite verify validation (ERROR, not warn)

- Decision: Add a new validator check `verify-full-suite` in `_plan_validate.py`. If a batch's `verify:` command contains `run-all.py` AND does NOT contain `-k ` (filter flag), emit an ERROR (hard-fail). The check is added to `validate_plan()`'s error pipeline alongside `verify-not-isolated`.
- Rationale: A verify that runs all 77 test files costs 5+ minutes per review/fix round, ballooning per-batch round cost. This is a structural plan bug, not a style preference — same severity posture as `verify-not-isolated` which is also an ERROR. Warn-only would let bad plans ship.
- Rejected: Warn (non-blocking) — gives teams false comfort that the plan is valid while silently destroying throughput.
- Note: Individual test file invocations (`test-foo.py` directly, no `run-all.py`) are not affected by this check.

### #401 — template_cfg augmentation with worktree-local template

- Decision: In `load_config`, after computing `template_cfg` from the resolved cache template, additionally load `worktree_root / "plugins" / "mill" / "templates" / "mill-config.yaml"` if it exists AND its resolved path differs from the cache template path. Deep-merge it into `template_cfg` so any keys present in the worktree template but absent from the cache template are recognised as valid.
- Rationale: The unknown-key validator compares `check_cfg` against `template_cfg`. When the cache template predates a commit that added `pipeline.max_cards_per_batch` and `pipeline.max_batch_context_tokens` to the worktree template (commit `4ff29d87`), those keys are flagged on every `load_config` call. The worktree template IS the authoritative source; augmenting `template_cfg` with it closes the lag without requiring a cache refresh.
- Rejected: Explicit allowlist in `_config.py` for the two keys — creates drift risk whenever new pipeline keys are added; does not address the general cache-lag problem.

### #402 — mill-merge step 6 PYTHONPATH (worktree scripts over cache)

- Decision: In mill-merge SKILL.md step 6, add a shell preamble that detects whether the task worktree has a local `plugins/mill/scripts/` directory. If yes, set `MILL_SCRIPTS="<git_root>/plugins/mill/scripts"` and use it as `PYTHONPATH` for the `_archive_tag` invocation; otherwise fall back to `${CLAUDE_PLUGIN_ROOT}/scripts`. Additionally, wrap the `import _archive_tag` in a try/except that emits a clear message pointing to `uv sync --project plugins/mill` on `ImportError`.
- Rationale: When the cache predates the task branch that added `_archive_tag.py`, importing from the cache raises `ModuleNotFoundError`. The self-modifying-repo pattern (prefer worktree scripts when available) already exists in mill-go; applying it here eliminates the lag. The fallback error message handles the edge case where the worktree also lacks the file (new helper added in main but not yet merged).
- Rejected: Always using `${CLAUDE_PLUGIN_ROOT}/scripts` and only adding the error message — doesn't prevent the error, only improves diagnostics after it fires.

### #399 — modify/delete conflict resolution for parent-side deletion

- Decision: Extend the `merge-in-conflict-brief.md` template with a new instruction for UD-type conflicts (task branch modified a file that the parent deleted). The resolver must: (a) run `git log --oneline -- <file>` on the parent branch to find the deletion commit; (b) run `git show <deletion-commit>` to inspect context; (c) if the deletion commit message mentions a replacement file OR the commit also adds a file in the same directory with overlapping content, prefer the deletion (`git rm <file>`); (d) otherwise report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement"}` so the operator decides — no silent keep of the modify side.
- Rationale: The existing instruction 5 in the template only handles DU conflicts where the TASK branch's plan lists the file under `Deletes:`. The observed failure mode (`test-no-direct-rmtree.py` kept instead of deleted) is the UD case: main deleted the file as part of a consolidation (`test-guards.py`), but the task branch had modified it. The resolver silently kept the modify side. The fix adds replacement-detection logic; when detection is inconclusive, it prompts the operator rather than making a silent data-loss decision.
- Rejected: Always prefer delete on UD conflicts — too aggressive when the task branch's modification IS the right answer (e.g. main removed a file for unrelated cleanup reasons).

## Technical context

### mill-go SKILL.md — step 2 / 2b

- `plugins/mill/skills/mill-go/SKILL.md` lines 171–198 describe step 2 and 2b.
- Step 2 says "Record `commit_sha` from a successful report on the batch entry." (`_status.set_batch_field(status_path, batch_name, "commit_sha", <value>)`)
- Step 2b says "compute new dirt via `_cleanliness.compute_new_dirt(...)`. If non-empty → blocked; if empty → continue."
- Fix: move the `commit_sha` write sentence from step 2's body to step 2b's "if empty" branch, just before "continue to step 3."

### _implementer_common.py — `_forward_output`

- `plugins/mill/scripts/_implementer_common.py` lines 9–60.
- Current signature: `_forward_output(output, project_root, *, start_sha=None, snapshot_path=None, session_id=None) -> int`
- The inferred-success check at lines 42–56 guards with `if start_sha is not None and snapshot_path is not None and snapshot_path.exists():`. Add a new `elif start_sha is not None:` branch (snapshot_path is None case) that checks HEAD advanced AND tree clean → emit `{"status":"success","commit_sha":head,"session_id":session_id or "unknown","inferred":True}`.
- The new branch lives inside the existing `try/except Exception: pass` block.

### millpy-fix.py — start_sha capture

- `plugins/mill/scripts/millpy-fix.py` line 296: `return _forward_output(output, project_root, session_id=session_id)` — add `start_sha=start_sha`.
- Capture `start_sha` just before the `_implementer_claude.run(...)` call (shared dispatch tail, line ~280). Use `_subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)` and store `result.stdout.strip()` if returncode == 0, else None.

### _plan_validate.py — verify-full-suite check

- `plugins/mill/scripts/_plan_validate.py`: existing `_check_verify_not_isolated` at line 807 is the model for the new check.
- New function `_check_verify_full_suite(batch_files: list[Path]) -> list[dict]`: iterate batch files, parse frontmatter, check if `verify:` contains `"run-all.py"` and does NOT contain `"-k "`. Return an error dict with `"check": "verify-full-suite"` on failure.
- Add call in the `validate_plan()` function at line 1004 alongside `_check_verify_not_isolated`.
- Frontmatter parsing helper is already in place (`_parse_plan_frontmatter` or equivalent — match the pattern used by `_check_verify_not_isolated`).

### _config.py — template_cfg augmentation

- `plugins/mill/scripts/_config.py` `load_config` function, lines 166–172 load the cache template into `template_cfg`.
- After line 172 (`template_cfg = copy.deepcopy(cfg)`), add:
  ```python
  worktree_template = worktree_root / "plugins" / "mill" / "templates" / "mill-config.yaml"
  if worktree_template.exists() and worktree_template.resolve() != template_path.resolve():
      wt_cfg = yaml.safe_load(worktree_template.read_text(encoding="utf-8")) or {}
      template_cfg = deep_merge(template_cfg, wt_cfg)
  ```
- `deep_merge` is already defined in the same file.

### mill-merge SKILL.md — step 6

- `plugins/mill/skills/mill-merge/SKILL.md` lines 180–194.
- Current bash snippet: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "..."`.
- Replace with two-step: first a shell variable assignment that checks for the worktree scripts dir, then the invocation using that variable. Use `git_root` derived from `_paths.resolve_git_root()` (already resolved earlier in the SKILL entry steps).
- Wrap `import _archive_tag` in the Python snippet with try/except that halts with a clear message on ImportError.

### merge-in-conflict-brief.md — UD conflict detection

- `plugins/mill/templates/merge-in-conflict-brief.md` instruction 5 (line 29) handles DU conflicts (task deleted, parent modified).
- Add a new instruction 6 for UD conflicts (task modified, parent deleted) with the replacement-detection steps described in Decisions above.
- The resolver has access to `git -C <PROJECT_ROOT>` per the "Tools" section. For parent-branch log queries, the `git log --oneline -- <file>` command reads from the merged state (MERGE_HEAD is available during merge conflict resolution) — use `git log MERGE_HEAD -- <file>` to inspect the deletion on the parent side.

### Existing unit test files (extend, do not replace)

- `test-implementer-common.py` — add test for the new no-snapshot inferred-success path
- `test-millpy-fix.py` — add test verifying that `start_sha` is captured and passed
- `test-plan-validate.py` — add test for `verify-full-suite` ERROR on `run-all.py` without `-k`, and PASS when `-k` is present
- `test-config.py` — add test for worktree-local template augmenting `template_cfg` (fixture: two temp templates, one missing a key, one with it; verify no unknown-key warning)

## Testing

**#397 — mill-go SKILL.md change**: no unit test (SKILL.md is prose). Covered by the integration smoke run (mill-go pipeline test where a batch completes successfully should show no cleanliness-blocked false-positive).

**#398 — _forward_output / millpy-fix.py**: unit tests in `test-implementer-common.py`:
- `test_forward_output_inferred_success_no_snapshot`: given output with no JSON, `start_sha` != HEAD, clean worktree → asserts `{"status":"success","inferred":true}` on stdout.
- `test_forward_output_no_snapshot_dirty_tree`: given output with no JSON, HEAD advanced, dirty worktree → asserts `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}` (falls through).
- `test_forward_output_no_snapshot_sha_unchanged`: given output with no JSON, HEAD == start_sha → asserts stuck/no structured report.
In `test-millpy-fix.py`:
- `test_fix_captures_start_sha`: mock `_subprocess_util.run` so `git rev-parse HEAD` returns different SHAs before and after; verify `_forward_output` receives the pre-session SHA.

**#392 — _plan_validate.py**: unit tests in `test-plan-validate.py`:
- `test_verify_full_suite_error`: batch file with `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` → `validate_plan` returns error with check=`verify-full-suite`.
- `test_verify_full_suite_pass_with_k`: batch file with `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py -k test_foo` → no error.
- `test_verify_full_suite_no_run_all`: batch file with `verify: PYTHONPATH= uv run ... test-foo.py` → no error (run-all.py absent).

**#401 — _config.py**: unit tests in `test-config.py`:
- `test_load_config_worktree_template_augments_template_cfg`: two temp dirs, one acting as cache (template missing `pipeline.max_cards_per_batch`), one as worktree (template has the key); mock `resolve_plugin_template_path` to return cache template; call `load_config` with a hub config containing `pipeline.max_cards_per_batch`; assert no `[config] unknown key` on stderr.
- `test_load_config_same_path_no_augment`: cache and worktree template resolve to the same path → augmentation skipped (no double-merge).

**#402 — mill-merge SKILL.md change**: no unit test (SKILL.md prose). The `ImportError` fallback in the Python snippet could be verified in an integration test but is out of scope for unit tests.

**#399 — merge-in-conflict-brief.md change**: template-only change. Covered by `test-millpy-merge-in-subagent.py` rendering tests if they check the conflict instructions section; otherwise no new unit tests needed. The resolver behavior is exercised by integration runs.

## Q&A log

- **Q:** For the full-suite verify check (#392), should it be an ERROR (hard-fail) or a WARNING? **A:** ERROR — same posture as `verify-not-isolated`; 5+ minute verify is a structural plan bug.
- **Q:** When holistic fixer commits land but JSON is missing (#398), what status should `_forward_output` return? **A:** `{"status":"success","inferred":true}` — matches the existing inferred-success shape; mill-go's `status: success` branch handles it without changes.
- **Q:** For the `load_config` unknown-key fix (#401), explicit allowlist or worktree-template augmentation? **A:** Worktree-template augmentation — handles cache lag generically; no drift risk as new pipeline keys are added.
