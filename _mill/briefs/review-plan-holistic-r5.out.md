I have completed my validation of the plan against the source files. All structural claims hold: the DAG (three independent batches, disjoint file sets, `depends-on: []` correct), global step numbering (1-11 sequential), verify command shapes (`PYTHONPATH= ` prefix, `--only` multi-file syntax confirmed in `run-all.py`), and the line-number/signature references (subprocess.run cwd at 383, finalize call at 561, four `_run_verify_gates` sites at 647/771/826/882, `project_root = resolve_hub_path()` vs `git_root = resolve_git_root()` confirming the #554 bug, template pipeline section, SKILL.md Handoff step 1 at 716) are all accurate.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate -- holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-28
```

## Findings

### [NIT] Card 9 prose vs snippet diverge on pipeline-null guard
**Location:** Batch 3 / Card 9
**Issue:** Step-0 prose says `cfg.get("pipeline", {}).get("done_gate")`, which raises `AttributeError` if `pipeline:` is present but null, whereas the literal snippet correctly uses `(cfg.get('pipeline') or {}).get('done_gate')`.
**Fix:** Align the prose to the `or {}` form so the two never drift; implementer pastes the snippet verbatim regardless.

### [NIT] Card 7 Test C mock not fully hermetic on the failure sub-case
**Location:** Batch 3... Batch 2 / Card 7 (Test C2)
**Issue:** With `subprocess.run` mocked and `returncode=1`, control reaches `_is_benign_windows_cleanup(result.stdout + result.stderr)` where stdout/stderr are bare MagicMocks; the string op raises and is swallowed by the outer `except Exception`. The dotnet-shutdown assertion still passes (call recorded first), but the path is incidental.
**Fix:** Configure `result.stdout`/`result.stderr` as `""` (or use `side_effect` for the verify vs shutdown calls) so the assertion is intentional, not a side effect of an internal raise.

### [NIT] Card 6 Context omits `_paths.py` though Requirements names `_paths.resolve_git_root()`
**Location:** Batch 2 / Card 6
**Issue:** Requirements references `_paths.resolve_git_root()`, but `_paths.py` is not in `Context:`. No cold-start results because `git_root` is already an in-scope local in the edited files (millpy-implement.py L108, millpy-fix.py L134), so the implementer only reads files already in Edits.
**Fix:** Optionally add `_paths.py` to `Context:` for strict completeness; functionally unnecessary.

## Verdict

APPROVE
Plan is correct, DAG-valid, and faithfully implements all decisions; only cosmetic nits remain.
MILL_REVIEW_END
