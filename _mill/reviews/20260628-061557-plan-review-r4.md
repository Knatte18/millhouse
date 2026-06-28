I have enough to complete the holistic review. Let me compose findings.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-28
```

## Findings

### [BLOCKING] Verify-cwd fix wired into only 1 of 4 verify call sites
**Location:** Batch 2, Cards 5/6 (vs. task goal "verify cwd" / #554)
**Issue:** Card 5 makes the shared helpers git_root-aware, but Card 6 passes `git_root` only at `millpy-implement.py:255` (finalize). The other call sites that run batch verify with a real `verify_cmd` still pass no `git_root` and run from `project_root` (hub): `millpy-implement.py:417` (full stage), `millpy-fix.py:227` (fixer finalize), and `millpy-fix.py:396` (fixer forward). In nested layouts these reproduce the identical MSB1009 / wrong-cwd failure -- notably the fixer loop, which re-runs verify after a code review finds BLOCKING issues.
**Fix:** Add cards passing `git_root` to `finalize_from_output`/`_forward_output` at those three sites (resolve `git_root` in `millpy-fix.py`), or explicitly scope them out in 00-overview with rationale.

### [NIT] Card 4 mock design crashes main() at json.dumps
**Location:** Batch 1, Card 4
**Issue:** With `_review_discussion.prepare` as a bare `MagicMock()`, `prepare_result["scope"/"round"/"model"]` are MagicMocks, so `json.dumps(envelope)` at `millpy-review-discussion.py:113` raises `TypeError` (uncaught by `except ReviewError`). The `resolve_task_path` call is recorded first, but `mod.main()` then raises.
**Fix:** Set `prepare.return_value` to a real dict and `model_to_tier` to a str, or wrap `main()` in try/except for the expected post-assertion raise.

### [NIT] Card 11 Context omits `_config.py`
**Location:** Batch 3, Card 11
**Issue:** Requirements names `resolve_plugin_template_path` (defined in `_config.py`) as the patch target, but Context lists only `mill-config.yaml` and `test-config.py`, forcing cold-start exploration to confirm the symbol.
**Fix:** Add `plugins/mill/scripts/_config.py` to Card 11 Context.

### [NIT] #556 cleanup does not reap testhost
**Location:** Batch 2, Card 5; Batch 3, Card 9; Shared Decision "dotnet cleanup"
**Issue:** `dotnet build-server shutdown` releases VBCSCompiler/MSBuild/Razor servers, not orphaned `testhost.exe` from `dotnet test`, which the #556 description also names. Best-effort per decision, but the testhost leak may persist.
**Fix:** Note testhost is out of scope of the shutdown call, or pursue a testhost teardown.

## Verdict

REQUEST_CHANGES
Verify-cwd fix leaves the fixer and full-stage paths broken in nested layouts.
MILL_REVIEW_END
