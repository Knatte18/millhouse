The implementation is clear. Now let me compile my complete findings.

Summary of what I've found:

**Batch 1 (parser-and-brief):**
- Card 1: `parse_blocking_count` YAML fallback is implemented correctly in `_review_common.py`.
- Card 2: All 6 YAML-fallback test cases are present in `test-review-common.py`.
- Card 3: `millpy-review-discussion.py` line 105 correctly uses `hub_dir` (not `git_root`).
- Card 4: `test_brief_path_nested_layout` is present and correctly wired in `test-review-discussion-flow.py`.

**Batch 2 (implementer-cwd-and-dotnet):**
- Card 5: All 4 changes to `_implementer_common.py` are correct.
- Card 6: `millpy-implement.py` passes `git_root=git_root` in finalize and full branches; `millpy-fix.py` passes `git_root=git_root` in finalize and full branches.
- Card 7: Tests A, B, C (C1, C2, non-dotnet) are all present and correctly structured.

**Batch 3 (done-gate):**
- Card 8: `done_gate: null` is present in `mill-config.yaml` template at line 123.
- Card 9: The "**0. Pre-done gate**" step is **NOT** present in `mill-go/SKILL.md` Handoff. The Handoff section goes directly from scope violations cleanup to step 1.
- Card 10: The "Done-gate reminder" note is **NOT** present in `mill-plan/SKILL.md`.
- Card 11: `test_load_config_done_gate_key_present` function and its registration in `main()` are **NOT** present in `test-config.py`.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-28
```

## Findings

### [BLOCKING] Card 9: Pre-done gate step absent from mill-go/SKILL.md Handoff
**Location:** `plugins/mill/skills/mill-go/SKILL.md:673-716`
**Issue:** The Handoff section contains no "0. Pre-done gate" step. The block immediately follows the scope-violations cleanup gate and jumps to step 1 (`_status.append_phase`). The plan required inserting a new numbered step 0 with an inline Python snippet that reads `pipeline.done_gate`, runs the command from `git_root`, and halts with a `BLOCKED` message on non-zero exit.
**Fix:** Insert the step-0 block as specified in Card 9 between the scope-violations handling note (line 714) and step 1 (line 716).

### [BLOCKING] Card 10: Done-gate reminder note absent from mill-plan/SKILL.md
**Location:** `plugins/mill/skills/mill-plan/SKILL.md` (Phase: Plan section, after Verify command scope)
**Issue:** No "Done-gate reminder" paragraph exists anywhere in the file; the grep for `done_gate`, `done-gate`, and `Done gate` all return zero matches. Card 10 required inserting an advisory note about setting `pipeline.done_gate` for repo-wide test coverage.
**Fix:** Add the standalone paragraph from Card 10 immediately after the "Verify command scope" subsection.

### [BLOCKING] Card 11: `test_load_config_done_gate_key_present` absent from test-config.py
**Location:** `plugins/mill/unit_tests/test-config.py:1233-1279`
**Issue:** Neither the function `test_load_config_done_gate_key_present` nor any `done_gate` reference exists in `test-config.py`. The `main()` function's test list has 35 entries; none matches Card 11's required function. The batch-3 verify command (`test-config.py`) therefore provides zero regression coverage for the `done_gate` template key.
**Fix:** Add `test_load_config_done_gate_key_present` (using the real template path and patching `resolve_plugin_template_path`) before the `if __name__ == "__main__"` block, and register it in `main()`'s test list.

## Verdict

REQUEST_CHANGES
Batches 1 and 2 are fully implemented; batch 3 is missing all three of its non-template deliverables (SKILL.md pre-done gate step, mill-plan reminder, and config test function).
MILL_REVIEW_END