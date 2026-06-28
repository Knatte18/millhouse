I have enough to assess the plan. Let me compile findings.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate -- holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-28
```

## Findings

### [BLOCKING] Card 4 brief-path test is tautological, guards nothing
**Location:** Batch 1 / Card 4
**Issue:** The mandated "minimal" test only asserts `resolve_task_path(hub_dir, ...)` differs from `resolve_task_path(git_root, ...)` -- it never imports or invokes `millpy-review-discussion`'s prepare branch, so reverting Card 3's one-line fix leaves batch-1 verify green; the card's claim that it "catches a regression if the fix is reverted" is false.
**Fix:** Have the test patch `resolve_hub_path`/`resolve_git_root` in the `millpy-review-discussion` namespace and assert the emitted `brief_path` (or the `briefs_dir` actually used by prepare) resolves under `hub_dir`, exercising the changed code path.

### [BLOCKING] Card 5 misses the multi-line `_run_verify_gates` call site
**Location:** Batch 2 / Card 5, Change 3
**Issue:** `_forward_output` has four `_run_verify_gates` calls (lines 647, 771, 826, 882); the call at 771-773 is split across lines and will not match the single-line find/replace string the card gives, so `git_root` is not threaded on the drift-commit success path -- reintroducing the #554 cwd bug there. No test covers `_forward_output` threading, so the miss is silent.
**Fix:** Enumerate all four call sites explicitly (including the multi-line 771-773 form) and add `git_root=git_root` to each.

### [BLOCKING] Card 5 dotnet cleanup placement contradicts "regardless of return code"
**Location:** Batch 2 / Card 5, Change 1 (#556)
**Issue:** The card says run cleanup "regardless of the return code" but places it after the `if result.returncode != 0:` block, which `return`s the stuck dict (and the win32-benign and except paths also return early) -- so cleanup only fires on rc==0. Failed dotnet runs (exactly the re-run lock scenario #556 targets) leave testhost/build-server processes alive. Test C only checks the success path, encoding the gap.
**Fix:** Move the dotnet shutdown to immediately after `result = subprocess.run(...)` (before any return), or wrap in try/finally, so it runs on success and failure alike.

### [NIT] Card 9 references nonexistent `_subprocess_util.run_allow_fail`
**Location:** Batch 3 / Card 9
**Issue:** `_subprocess_util` exposes only `run` (line 40), not `run_allow_fail`; the primary SKILL snippet calls the missing helper, forcing the implementer onto the hedged inline `subprocess.run` form and leaving the `_subprocess_util` import unused.
**Fix:** Make the inline `subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)` the primary snippet and drop the `_subprocess_util` import/reference.

### [NIT] Card 11 helper reference conflicts with real-template assertion
**Location:** Batch 3 / Card 11
**Issue:** The card says to use `_setup_plugin_template` (which seeds a synthetic template lacking `done_gate`) yet also wants `resolve_plugin_template_path` mocked to the real `templates/mill-config.yaml`; using the stub would make the `done_gate is None` assertion meaningless.
**Fix:** Drop `_setup_plugin_template`; point `resolve_plugin_template_path` at the real template path and assert `cfg["pipeline"]["done_gate"] is None`.

## Verdict

REQUEST_CHANGES
Two test cards guard nothing and one cwd/cleanup path is left unfixed.
MILL_REVIEW_END
