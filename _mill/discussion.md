# Discussion: mill-merge-in --recompute-baseline crashes uncaught on absent status.md

```yaml
task: mill-merge-in --recompute-baseline crashes uncaught on absent status.md
slug: mill-merge-in-recompute-baseline-crash
status: discussing
parent: main
```

## Problem

`mill-merge-in --recompute-baseline` crashes with an uncaught exception (exit 1) when `_mill/status.md` is entirely absent, instead of following its own documented fail-safe contract.

This is the last of three related crash sites originally reported in GitHub issue #803 ("mill-merge/mill-merge-in: multiple call sites crash on the closed-PR re-entry path where status.md is already absent"). The other two have since been fixed and verified during this task's Explore phase:

- `mill-merge` Entry Step 4 now branches on `status_path.exists()` before calling `_parent_branch.resolve(...)`, falling back to `cfg.git.base_branch` when the file is absent (`mill-merge/SKILL.md` lines 78-80).
- `_plan_dag.iter_batch_verifies` already returns `[]` gracefully when `plan_dir / "00-overview.md"` doesn't exist (`_plan_dag.py:534`).

Only the third site remains: `_run_recompute_baseline()` in `millpy-merge-in-subagent.py:199`. Its docstring explicitly promises "Never raises -- every failure path ... prints a JSON line describing the outcome and returns 0 without blocking the merge-in." But the very first line of the function body, `status_path = _paths.require_status_path(project_root, cfg)` (line 224), calls a helper that raises `_paths.TaskHubError` when `status.md` doesn't exist, and this call sits outside any try/except — so the promised fail-safe is violated at the first possible opportunity.

**Reproduction path:** `git.require_pr_to_base: true` → mill-finalize opens a PR and its cleanup commit `git rm -r`'s the whole `_mill/` directory (including `status.md`) before pushing → operator reviews and closes the PR without merging → operator re-runs `/mill-merge` → the `closed`-route re-invokes `mill-merge-in` with `--recompute-baseline` → crash.

## Scope

**In:**
- Wrap the `_paths.require_status_path(project_root, cfg)` call at `millpy-merge-in-subagent.py:224` in a try/except so status.md absence follows the same fail-safe shape as the function's other two failure paths (parent-branch resolution failure, baseline computation failure).
- One regression unit test in `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` exercising `_run_recompute_baseline` (or the full `--recompute-baseline` CLI path) with status.md absent, asserting it returns 0 and prints `{"status": "success", "baseline": "error", ...}` without raising.

**Out:**
- The other two crash sites from issue #803 — already fixed, verified in Explore, not touched here.
- Backfilling unit test coverage for `_run_recompute_baseline`'s other paths (no-module-wide-verify-configured "skipped" case, successful "computed" case) — currently untested but pre-existing gaps unrelated to this bug.
- Rewording `_paths.TaskHubError`'s message or `require_status_path`'s contract — it's shared by other callers (e.g. `millpy-implement.py:561`, where the file's absence is a genuine startup error, not an expected state) and changing it is out of scope.
- Any change to the PR-state gate / closed-route logic in `mill-merge/SKILL.md` itself — that flow already produces the expected re-entry state correctly; only the crash on the receiving end is being fixed.

## Decisions

### wrap-require-status-path

- Decision: Wrap just the `require_status_path` call in `try/except Exception as e:`, printing `json.dumps({"status": "success", "baseline": "error", "reason": str(e)})` and `return 0` — the same shape as the two existing try/except blocks later in the function (parent-branch resolution at line 248, baseline computation at line 253).
- Rationale: Matches the fail-safe output format already documented in the wiki task brief verbatim (`{"status":"success","baseline":"error",...}`, exit 0, no Rollback trigger). Using broad `Exception` (not narrowly `_paths.TaskHubError`) keeps this call site consistent in shape with its two siblings in the same function, which also catch bare `Exception`.
- Rejected: Narrowing the catch to `_paths.TaskHubError` only — no functional difference today since that's the only exception `require_status_path` raises, but it breaks the established local pattern of the two sibling blocks for no benefit. Pre-checking `status_path.exists()` before calling `require_status_path` and reporting a distinct `baseline: "skipped"` value — rejected because the wiki brief already narrows the desired output to the `"error"` shape, and a `"skipped"` value would diverge from what's documented as expected without any consumer benefit (the JSON line is not currently branched on by `baseline` value anywhere in the caller).

### reuse-exception-message-verbatim

- Decision: The `reason` field reuses `str(e)` verbatim (i.e., `TaskHubError`'s own message, including its "run this CLI from the task hub dir" suggestion), rather than substituting a call-site-specific message.
- Rationale: Consistent with the two sibling try/except blocks in the same function, both of which use `str(e)` verbatim. The JSON line is machine-consumed by `mill-merge-in`'s Verify step, not surfaced raw to the operator, so the suggestion's inaccuracy in this specific expected-absence case has no practical audience.
- Rejected: A custom message like "status.md absent (expected on closed-PR re-entry after mill-finalize's cleanup commit)" — more accurate but inconsistent with the function's existing error-reporting style, and not worth the inconsistency for a string nothing currently reads.

## Technical context

- **Crash site:** `plugins/mill/scripts/millpy-merge-in-subagent.py:224`, inside `_run_recompute_baseline(project_root, git_root, cfg)`. Currently:
  ```python
  status_path = _paths.require_status_path(project_root, cfg)
  ```
  with no surrounding try/except — the only unguarded call in an otherwise fully-guarded function.
- **`_paths.require_status_path`** (`plugins/mill/scripts/_paths.py:608-628`): computes the status.md path via `status_path(project_root, cfg)` and raises `_paths.TaskHubError` if it doesn't exist. `_paths.TaskHubError` (`_paths.py:375`) is a plain `Exception` subclass.
  Note the naming collision: the module-level helper `_paths.status_path(worktree_root, cfg)` (line 598) and the local variable `status_path` inside `_run_recompute_baseline` share a name — not a bug, just worth knowing when reading the function.
- **`_paths` is already imported** in `millpy-merge-in-subagent.py` (line 47), so no new import is needed for either `require_status_path` or `TaskHubError`.
- **Sibling error-handling shape already in the same function** (lines 247-260), to mirror exactly:
  ```python
  try:
      parent_branch = _parent_branch.resolve(status_path, interactive=False)
  except Exception as e:
      print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)}))
      return 0

  try:
      result = _verify_baseline.compute_baseline(
          project_root, git_root, parent_branch, module_wide_verify_cmd
      )
  except Exception as e:
      print(f"[millpy-merge-in-subagent] baseline recompute failed: {e}", file=sys.stderr)
      print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)}))
      return 0
  ```
  The fix for the require_status_path call should follow the same `except Exception as e: print(json.dumps({"status": "success", "baseline": "error", "reason": str(e)})); return 0` shape. Whether to also add the `file=sys.stderr` diagnostic line (present on the second sibling block, absent on the first) is a minor style choice left to mill-plan/implementer judgment — either sibling is a legitimate precedent to match.
- **Sibling function for context (not touched by this task):** `millpy-implement.py`'s `_run_baseline_stage` calls the same `_paths.require_status_path` (line 561) but *is* wrapped in `try/except _paths.TaskHubError as e: print(str(e), file=sys.stderr); return 1` — that's correct there because task-start pre-flight expects status.md to exist; its absence is a genuine startup error, not an expected post-merge-in state. Do not use that function's handling as a model for this fix — the two call sites have opposite correctness requirements for the same exception.
- **Caller / entry point:** `main()` dispatches `--recompute-baseline` to `_run_recompute_baseline` at line 359, independent of `--mode`.
- **No existing test coverage** for `_run_recompute_baseline` at all — `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` only tests the `--mode`/`--recompute-baseline` argparse mutual-requirement (`test_9_missing_mode`, line 363), not the function's actual behavior in any of its three outcome branches (skipped / computed / error).

## Constraints

- Per repo `CLAUDE.md`: this is a Python project (`plugins/mill/` has `pyproject.toml`), so the plan's `verify:` command must start with `PYTHONPATH=` (literal, empty value) so the test subprocess doesn't load V2-cache modules instead of worktree code.
- Per repo `CLAUDE.md`: unit tests run via `uv run --project plugins/mill` (the one CLAUDE.md-documented exception to the `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` cache-invocation form) — the plan's verify command for the new/existing unit test should use that form, not the cache form.
- `_run_recompute_baseline` must continue to **never raise** under any internal failure — this fix must not narrow that guarantee, only extend it to cover the one remaining gap.

## Testing

- **TDD candidate:** `_run_recompute_baseline` in `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`.
- **New scenario to cover:** status.md absent (e.g. a `project_root` fixture with no `_mill/status.md` file, or `_mill/` entirely absent) → function returns `0`, printed JSON has `"status": "success"` and `"baseline": "error"`, and no exception propagates out of the call.
- Existing tests in the same file (`test_1_conflicts_success` through `test_2x_marker_gate_*`) show the established fixture/mocking patterns (tmp project root, `_subprocess_util` stubbing, `capsys`/stdout capture for the JSON-line assertions) — follow those conventions rather than introducing a new test style.
- Out of scope per the Scope section above: backfilling tests for the "skipped" (no module-wide verify configured) and "computed" (successful recompute) branches of the same function — pre-existing gaps, not part of this bug fix.

## Q&A log

- **Q:** How should the crash site be fixed? **A:** [auto-pick] Wrap the `require_status_path` call in `try/except Exception as e:`, printing `{"status": "success", "baseline": "error", "reason": str(e)}` and returning 0 — mirrors the two existing try/except blocks later in the same function and matches the fail-safe output format already documented in the wiki task brief. **Why:** consistency with the function's own established local pattern and with the already-narrowed expected output from the wiki brief.
- **Q:** How much test coverage should this task add? **A:** [auto-pick] One regression unit test scoped to this bug: `_run_recompute_baseline` returns 0 and prints `baseline: "error"` JSON when status.md is absent, without raising. **Why:** YAGNI — backfilling coverage for the function's other untested-but-unrelated paths is pre-existing debt outside this bug's scope.
- **Q:** Should the `reason` field reuse `str(e)` verbatim or use a call-site-specific message, given `TaskHubError`'s message includes misleading "run this CLI from the task hub dir" advice for this expected-absence case? **A:** [auto-pick] Reuse `str(e)` verbatim, consistent with the two sibling try/except blocks in the same function. **Why:** the JSON line is machine-consumed, not operator-read raw, so the inaccuracy has no practical audience, and consistency with sibling blocks outweighs a marginal wording improvement nothing currently reads.
