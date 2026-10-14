MILL_REVIEW_BEGIN
# Review: Instrument and bound the verify runner — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-10-14
```

## Findings

### [NIT:consistency] END marker and Verify-log failure note are not ASCII-normalised
**Location:** `plugins/mill/scripts/_verify_run.py:302-304` and `:319`
**Issue:** `_emit_marker` prints `output={output_path}` and `could not write Verify log row: {exc}` raw, while START normalises `cwd` and `label`; a non-cp1252 character in the checkout path makes `print(..., file=sys.stderr)` raise `UnicodeEncodeError` out of `run_verify`, breaking its never-raises contract and the repo's ASCII-only output rule.
**Fix:** Pass the path and exception text through `_status.normalize_log_field` (or guard the stderr print in `_emit_marker`).

### [NIT:consistency] Failure-reason composition is reimplemented at several sites
**Location:** `plugins/mill/scripts/_implementer_common.py:808-820` (`_verify_failure_reason`, `_timed_out_stuck`), `plugins/mill/scripts/millpy-merge-in-subagent.py:259-282` (`_verify_stuck_envelope`), `plugins/mill/scripts/millpy-verify-run.py:32-42` (`_failure_reason`), `plugins/mill/scripts/_done_gate.py:120-131`
**Issue:** Each repeats `prefix + _truncate_verify_output(run.output.strip()) + output_suffix(run)` plus the launch-failure wording.
`_done_gate._build_truncated_reason` is also a verbatim copy of `_implementer_common._truncate_verify_output`, the helper batch 3 extracted for reuse.
The plan prescribes these per card, so this is a consolidation opportunity rather than a plan deviation.
**Fix:** Have `_done_gate` call `_truncate_verify_output`, and expose one shared reason builder taking a `VerifyRun` that the CLIs and gates call.

### [NIT:consistency] Unused imports left after moving `_posix_shell_run_args`
**Location:** `plugins/mill/scripts/_implementer_common.py:7` and `:9`
**Issue:** `import os` and `import shutil` have no remaining use in the module (verified by searching for `os.` / `shutil.` references); no test patches `_implementer_common.os` or `.shutil`.
**Fix:** Remove both imports.

### [NIT:consistency] Done-gate re-run text still shows the old call shape
**Location:** `plugins/mill/skills/mill-go-base/handoff.md:155`
**Issue:** The fixer-dispatch re-run says "a second `_done_gate.run_gate(gate_cmd, git_root)` call", contradicting the snippet at line 137 and the overview's decision that every snippet passes `hub_root=hub_root`.
**Fix:** Write the call as `_done_gate.run_gate(gate_cmd, git_root, hub_root=hub_root)` or refer to the snippet without restating the signature.

## Verdict

APPROVE
All six batches are realised and cross-batch contracts hold; only non-blocking NITs remain.
MILL_REVIEW_END
