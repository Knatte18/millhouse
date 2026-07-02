# Batch: implement-baseline-stage

```yaml
task: "Fix agent-mode dispatch races and pipeline gaps"
batch: implement-baseline-stage
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-status.py
depends-on: [1, 2]
```

## Batch Scope

Add the `module_verify_baseline` computation itself: a new `plugins/mill/scripts/_verify_baseline.py` module holding the transient-worktree computation, and a new `millpy-implement.py --stage baseline` CLI stage that reads/writes the cached value via batch 1's `_status.py` helpers and calls it. Also wires the cached baseline value into the existing `finalize`/`full` stage calls so every batch's own module-wide gate (batch 2's `_run_verify_gates`) actually consults it. Depends on batch 1 (the `_status.py` get/set/clear helpers this batch's CLI stage and wiring both call) and batch 2 (`_run_verify_gates`'s new `module_verify_baseline` parameter, and `_forward_output`/`finalize_from_output`'s threading of it, that the wiring card passes a value into).

## Cards

### Card 5: _verify_baseline.py — transient-worktree computation

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `_verify_baseline.py` with a single public function:

  `compute_baseline(project_root: Path, git_root: Path, parent_branch: str, module_wide_verify_cmd: str) -> str`

  Returns the literal string `"clean"` or `"pre-existing-failures"`. Raises on any infrastructure failure (git worktree creation failure, junction creation failure) — the caller (Card 6) is responsible for catching and applying the fail-safe policy; this function's job is only to compute the answer when it CAN, not to decide what happens when it can't.

  Implementation, in order:
  1. Resolve the parent branch's current tip SHA: `git -C <git_root> rev-parse <parent_branch>` via `_subprocess_util.run`; raise `RuntimeError` with the command's stderr on non-zero exit.
  2. Create a fresh, uniquely-named subdirectory under `<project_root>/.scratch/` (e.g. `verify-baseline-<uuid4 hex>`) as the transient worktree target path. `.scratch/` is gitignored per CLAUDE.md's repo-layout convention — never use the system temp directory. Ensure `.scratch/` itself exists (`mkdir(parents=True, exist_ok=True)`) before the `git worktree add` call, since git requires the target's parent directory to already exist.
  3. Create the transient worktree via a direct `git -C <git_root> worktree add <tmp-path> <parent-sha>` call through `_subprocess_util.run` (a detached-HEAD checkout at that SHA — NOT `_worktree.create`, which always does `git worktree add -b <branch>` and would try to create a new branch, which is the wrong shape here and would collide if re-run). Raise on non-zero exit.
  4. From this point on, wrap all remaining steps in `try`/`finally` so the transient worktree is torn down via `_worktree.remove_safe(tmp_path, cwd=git_root, junctions_cfg={})` (imported from `_worktree`) unconditionally — on success, on a verify failure, and on any exception raised inside the `try` block. `junctions_cfg={}` is correct and sufficient: `_junction.strip_all_in_worktree`'s `junctions_cfg` parameter is vestigial ("retained for backward compatibility; it is no longer read" per its own docstring) — the function scans the transient worktree tree itself and strips every junction/symlink it finds, including the dependency junctions this function creates in step 5, with no declared config needed.
  5. Reuse the task worktree's already-installed gitignored dependency state: for each name in the fixed candidate list `(".venv", "venv", "node_modules", "vendor")`, if `(project_root / name).exists()`, create a junction from it into the transient worktree via `_junction.create(project_root / name, tmp_path / name)` (imported from `_junction`). Skip names that don't exist at the task worktree's top level. Do not consult `mill-config.yaml` for this list — there is no existing venv/dependency-dir convention there to mirror (confirmed absent from both the hub config and the template schema); this fixed probe-list IS the mechanism.
  6. Run `module_wide_verify_cmd` with cwd set to `tmp_path`, using `_posix_shell_run_args` (imported from `_implementer_common`, the same helper `millpy-merge-in-subagent.py` already uses for shell-escaped user verify commands — see `millpy-merge-in-subagent.py:190,290,358`) plus `subprocess.run(..., capture_output=True, text=True, cwd=tmp_path, **run_kwargs)`. If the exit code is 0, return `"clean"` immediately (skip steps 7-8 entirely).
  7. On a non-zero exit, re-run the exact same command in the same `tmp_path` once more (the flakiness-guard retry). If this second run passes, treat the first failure as a spurious/transient fluke (flaky test, stale absolute path in a relocated venv, a flaky package registry) and return `"clean"` — do not proceed to step 8.
  8. If the retry in step 7 also fails (two consecutive failures in the transient worktree), run a control check: run `module_wide_verify_cmd` once more, this time with cwd set to `project_root` (the task worktree itself — always safe, no mutation, this is exactly what a batch's own module-wide gate already does at its own path). If the control run ALSO fails, return `"pre-existing-failures"` (both a deterministic-environment-mismatch and a flakiness explanation have been ruled out). If the control run passes, print an ASCII warning to stderr (e.g. `"[_verify_baseline] warning: module-wide verify failed twice in transient worktree but passed in task worktree -- treating as path/environment-induced, caching 'clean'"`) and return `"clean"` instead — the transient-worktree failures are path/environment-induced, not a real pre-existing failure.

  Module docstring: explain the three-way return contract and that this function is the ONLY place that runs `module_wide_verify_cmd` against the parent branch's own content — `_run_verify_gates` (batch 2) only ever reads the cached result this function produces.
- **Commit:** `feat(_verify_baseline): add compute_baseline transient-worktree computation`

### Card 6: millpy-implement.py — add --stage baseline

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Make the `batch_name` positional argument optional: change `parser.add_argument("batch_name", help=...)` (`millpy-implement.py:81-84`) to `parser.add_argument("batch_name", nargs="?", default=None, help=...)`. Immediately after `args = parser.parse_args(argv)` (`:133`), add a validation check: `if args.stage != "baseline" and not args.batch_name: print("batch_name is required unless --stage baseline", file=sys.stderr); return 1`.
  2. Add `"baseline"` to the `--stage` argument's `choices` list (`millpy-implement.py:87`), alongside the existing `"prepare"`, `"finalize"`, `"full"`.
  3. Restructure the setup sequence so the `--stage baseline` branch can dispatch before batch-name resolution ever runs, since `batch_name` is `None` for this stage and the existing batch-entry lookup (`millpy-implement.py:239-242`, `next((b for b in batches if b["name"] == args.batch_name), None)` followed by a hard `return 1` on no match) would always fail with `batch_name=None`. Concretely: after the overview-file existence check (`:225-230`), move the `overview_frontmatter`/`module_wide_verify_cmd` read (currently `:262-266`, `overview_frontmatter = _plan_dag._read_batch_frontmatter(overview_path)` / `module_wide_verify_cmd = overview_frontmatter.get("verify") or None`) to run immediately after `:230`, BEFORE the `batches = _plan_dag.extract_batch_index(...)` / `batch_entry` resolution block (`:231-242`). Insert the new baseline-stage branch right after that moved read, still before `:231`:
     ```python
     if args.stage == "baseline":
         return _run_baseline_stage(project_root, git_root, status_path, module_wide_verify_cmd)
     ```
     All other stages (`prepare`, `finalize`, `full`) then fall through to the unchanged `batches`/`batch_entry` resolution block exactly as today — `args.batch_name` is guaranteed non-`None` for those stages by the validation added in step 1.
  4. Implement `_run_baseline_stage(project_root: Path, git_root: Path, status_path: Path, module_wide_verify_cmd: str | None) -> int` as a new module-level function in `millpy-implement.py`, placed near `classify_stuck_type` (before `main`):
     - If `module_wide_verify_cmd` is `None` (no module-wide verify configured for this task), print `{"stage": "baseline", "result": "skipped", "reason": "no module-wide verify configured"}` as a JSON line and return 0 — there is nothing to compute a baseline for.
     - Read the current cached value via `_status.get_module_verify_baseline(status_path)`. If it is already non-`None` (`"clean"` or `"pre-existing-failures"`), the stage is idempotent-no-op: print `{"stage": "baseline", "result": "cached", "value": "<value>"}` and return 0 without recomputing — this is what makes the stage safe to invoke unconditionally on a resumed/restarted mill-go run.
     - Otherwise, resolve the parent branch via `_parent_branch.resolve(status_path, interactive=False)` (already imported in this file; wrap in `try`/`except Exception` — on failure, print `{"stage": "baseline", "result": "error", "reason": "<str(e)>"}` to stdout, log to stderr, and return 0 without persisting anything, matching the fail-safe-inconclusive policy).
     - Call `_verify_baseline.compute_baseline(project_root, git_root, parent_branch, module_wide_verify_cmd)` inside `try`/`except Exception as e`. On success, call `_status.set_module_verify_baseline(status_path, result)`, print `{"stage": "baseline", "result": "computed", "value": "<result>"}`, and return 0. On any exception, print an ASCII stderr message describing the failure (e.g. `f"[millpy-implement] baseline computation failed: {e}"`), print `{"stage": "baseline", "result": "error", "reason": str(e)}` to stdout, and return 0 WITHOUT calling `_status.set_module_verify_baseline` — this is the "do NOT cache a baseline verdict... fall back to running the module-wide gate strictly" fail-safe path from `_mill/discussion.md`'s Decision; leaving the field unset means the next `_run_verify_gates` call sees `module_verify_baseline=None` and runs the gate strictly (batch 2's `None`-fallback behavior).
     - Import `_verify_baseline` and `_parent_branch` at module level alongside the file's existing imports (`_parent_branch` is already imported at `millpy-implement.py:38`; add `import _verify_baseline`).
- **Commit:** `feat(millpy-implement): add --stage baseline for module-wide verify baseline computation`

### Card 7: wire cached baseline into finalize/full stage verify gates

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In both the `finalize` stage's `finalize_from_output(...)` call (`millpy-implement.py:289-301`) and the `full` stage's `_forward_output(...)` call (`millpy-implement.py:508-520`), add a new keyword argument `module_verify_baseline=_status.get_module_verify_baseline(status_path)` — read the cached value once, immediately before each call (or hoist a single `module_verify_baseline = _status.get_module_verify_baseline(status_path)` read to right after the (moved, per Card 6) `module_wide_verify_cmd` computation, since both stages need the same value and it is cheap to read once). Pass it through unchanged alongside the existing `module_wide_verify_cmd=module_wide_verify_cmd` argument at both call sites. This is the only change in this card — `finalize_from_output`/`_forward_output` and `_run_verify_gates` already know how to consume this parameter as of batch 2; this card only supplies the real cached value instead of the implicit `None` default that batches 1-2 leave in place for every other caller (e.g. `millpy-fix.py`, which is intentionally NOT touched by this task — see `_mill/discussion.md`'s Scope/Out).
- **Commit:** `feat(millpy-implement): pass cached module_verify_baseline into the finalize/full verify gates`

## Batch Tests

`verify:` runs `test-implementer-common.py` (Card 5/6/7's downstream effect on the gate — already covered by batch 2's cases 59-62, re-run here as a regression check since this batch changes the real call sites those cases model) and `test-status.py` (Card 6/7's use of the batch-1 helpers). The transient-worktree computation itself (`_verify_baseline.compute_baseline`, real git/junctions) is deliberately NOT covered by this batch's `verify:` — it belongs in `integration_tests/` per CLAUDE.md's repo-layout convention (unit tests use in-memory/tempfile fixtures, no real git) and is covered by batch 6 (`baseline-integration-test`).
