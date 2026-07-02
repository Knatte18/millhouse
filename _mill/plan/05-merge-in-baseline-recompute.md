# Batch: merge-in-baseline-recompute

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: merge-in-baseline-recompute
number: 5
cards: 2
verify: null
depends-on: [3]
```

## Batch Scope

After `mill-merge-in` pulls new parent commits into the task branch, the cached `module_verify_baseline` must be reset and eagerly recomputed at `mill-merge-in`'s own clean post-sync boundary — never left to whichever batch's `finalize` happens to run next, per `_mill/discussion.md`'s Decision (a lazy recompute inside a mid-task finalize would run after that batch's implementer has already run against the post-merge-in tree, possibly after touching a manifest again — the same manifest-boundary hazard the eager batch-1 pre-flight rule exists to avoid). Depends on batch 3 (`--stage baseline` / `_status.get_module_verify_baseline` / `_verify_baseline.compute_baseline` must all exist). This is a synchronous computation with no LLM dispatch involved — it does not touch `millpy-merge-in-subagent.py`'s existing `--mode conflicts`/`--mode verify-fix` Agent-mode dispatch machinery at all; it is a new, independent, purely-synchronous branch in the same file.

## Cards

### Card 11: millpy-merge-in-subagent.py --recompute-baseline flag

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Add a new `parser.add_argument("--recompute-baseline", action="store_true", help="Reset and eagerly recompute the cached module_verify_baseline after a successful parent-branch sync. Independent of --mode; when set, --mode is not required and no other mode-specific flag is consulted.")` to `main`'s argparse setup (`millpy-merge-in-subagent.py:107-158`).
  2. Change `--mode`'s `required=True` (`:113`) to `required=False`, and add a manual validation check immediately after `args = parser.parse_args(argv)` (`:158`): `if not args.recompute_baseline and not args.mode: print("--mode is required unless --recompute-baseline is set", file=sys.stderr); return 1`.
  3. Immediately after the existing marker-check block (`:174-178`, right after `_marker.slug_from_branch(...)` succeeds) and BEFORE the `--stage == "finalize"` early-exit block (`:181`), add:
     ```python
     if args.recompute_baseline:
         return _run_recompute_baseline(project_root, git_root)
     ```
  4. Implement `_run_recompute_baseline(project_root: Path, git_root: Path) -> int` as a new module-level function (placed near `_collect_task_intent`, before `main`):
     - Resolve `status_path` via `_paths.require_status_path(project_root, cfg)` — note `cfg` must be loaded first (this function needs its own `cfg = _review_common.load_config(git_root, project_root / ".millhouse")` call, or accept `cfg` as a parameter from the already-loaded value in `main` — prefer threading the already-loaded `cfg` in as a third parameter, `_run_recompute_baseline(project_root, git_root, cfg)`, since `main` already loads it at `:169` before this new branch would run; avoid a second redundant config load).
     - Read the plan overview's module-wide verify command the same way `millpy-implement.py` does: resolve `plan_base = _paths.resolve_task_path(project_root, cfg.get("paths", {}).get("plan_dir", "_mill/plan/"))`, `overview_path = plan_base / "00-overview.md"`, `overview_frontmatter = _plan_dag._read_batch_frontmatter(overview_path)` (import `_plan_dag` at module level), `module_wide_verify_cmd = overview_frontmatter.get("verify") or None`. If `module_wide_verify_cmd` is `None`, print `{"status": "success", "baseline": "skipped", "reason": "no module-wide verify configured"}` and return 0.
     - Call `_status.clear_module_verify_baseline(status_path)` (import `_status` at module level) to force recomputation regardless of any currently-cached value — this is the "reset" half of "reset-then-recompute"; `--stage baseline`'s own idempotent no-op-if-cached behavior (batch 3, Card 6) is exactly why a bare `--stage baseline` call alone would NOT recompute after a merge-in without this explicit reset first.
     - Resolve `parent_branch = _parent_branch.resolve(status_path, interactive=False)` (import `_parent_branch` at module level) inside `try`/`except Exception as e`; on failure, print `{"status": "success", "baseline": "error", "reason": str(e)}` and return 0 (fail-safe — a merge-in that already succeeded should not be blocked by a baseline-recompute failure; the field simply stays unset, and the next gate call falls back to strict per batch 2's `None` behavior).
     - Call `_verify_baseline.compute_baseline(project_root, git_root, parent_branch, module_wide_verify_cmd)` (import `_verify_baseline` at module level) inside `try`/`except Exception as e`. On success, call `_status.set_module_verify_baseline(status_path, result)`, print `{"status": "success", "baseline": "computed", "value": result}`, return 0. On exception, print an ASCII stderr message and `{"status": "success", "baseline": "error", "reason": str(e)}` to stdout, return 0 — same fail-safe-inconclusive policy as `millpy-implement.py --stage baseline` (batch 3, Card 6): a baseline-recompute failure must never fail the whole merge-in.

  Mirror `millpy-implement.py`'s `_run_baseline_stage` (batch 3, Card 6) as closely as possible in structure and error-handling shape — the two functions do the same underlying computation from two different entry points (task-start pre-flight vs. post-merge-in recompute) and should read as siblings, not divergent reimplementations.
- **Commit:** `feat(millpy-merge-in-subagent): add --recompute-baseline for post-sync module_verify_baseline recompute`

### Card 12: mill-merge-in/SKILL.md — invoke the recompute after a successful sync

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new step "3.5. Baseline recompute" between "### 3. Merge parent into current" and "### 4. Verify" (`mill-merge-in/SKILL.md`, currently steps 3 at lines 44-59 and 4 at lines 61-73). This step runs unconditionally after step 3 completes successfully (including after any conflict resolution sub-dispatch in step 3's table), before step 4's verify replay begins:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --recompute-baseline
  ```
  State explicitly: (a) this call is synchronous and does not go through Agent-mode dispatch — unlike steps 3/4's conflict/verify-fix sub-agent dispatches, `--recompute-baseline` runs the same deterministic computation `millpy-implement.py --stage baseline` uses, with no LLM session involved, so it needs no `<cli>`/`<args>` Agent-mode dispatch pattern reference; (b) it never blocks or fails the merge — on any internal error it prints a `baseline: "error"` result and returns exit 0 (fail-safe, per Card 11's Requirements), so this step never triggers the Rollback section; (c) if step 1's no-op check already exited early ("Nothing to merge"), this step never runs at all — the no-op guarantee (`mill-merge-in/SKILL.md`'s closing "## No-op guarantee" section) must continue to hold: "this skill touches nothing" when there was nothing to merge.

  Cite `_mill/discussion.md`'s `baseline-aware module-wide verify gate (#590)` Decision's merge-in paragraph (beginning "Whenever `mill-merge-in` pulls new parent commits into the task branch, it must recompute the baseline eagerly at its own clean post-sync boundary") as the authoritative rationale.
- **Commit:** `docs(mill-merge-in): recompute module_verify_baseline after a successful parent-branch sync`

## Batch Tests

`verify: null` — Card 11's new function is exercised end-to-end by batch 6's `--stage baseline` integration test pattern is the closest analog, but this specific `--recompute-baseline` entry point has no dedicated automated test in this task's scope (mirrors `millpy-merge-in-subagent.py`'s existing `--mode conflicts`/`--mode verify-fix` paths, which also have no unit-test coverage in this repo — they are exercised via `plugins/mill/integration_tests/test-merge.py`'s real-git flow). Card 12's SKILL.md change is prose-only. Validate both by re-reading the new step 3.5 for internal consistency with steps 1-6 (in particular the No-op guarantee) before committing this batch.
