# Batch: strict-verify-gates

```yaml
task: "Drop the eager verify-baseline pre-flight"
batch: "strict-verify-gates"
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-done-gate.py test-millpy-implement.py test-fix-finalize.py
depends-on: [1, 2, 4]
```

## Batch Scope

Makes the verify gate chain in `_implementer_common.py` strict (overview Decision `strict-gate-semantics`): removes the `module_verify_baseline` / `batch_verify_baseline` parameters everywhere, the subset-diff waiver, the `"pre-existing-failures"` module-wide skip, the stuck dict's `"signatures"` field, `_normalize_failure_signature`, and `_extract_failure_signatures`' `returncode` synthesis (discussion Decision `signatures-field`).
Depends on batches 1 and 2 (no caller still passes the removed kwargs) and batch 4 (`_verify_baseline.py`, the other `returncode=` caller, is gone).
`_extract_failure_signatures` itself stays: `_done_gate.py` and `_run_verify_gate`'s tail-truncation recovery call it.

## Cards

### Card 12: Make _run_verify_gates strict and drop the signature machinery

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Before editing, grep `plugins/mill/scripts` and `plugins/mill/skills` for `module_verify_baseline`, `batch_verify_baseline`, `"signatures"`, `get("signatures")`, `_normalize_failure_signature`, `returncode=` next to `_extract_failure_signatures`; the only hits must be inside `_implementer_common.py` itself.
  - `_extract_failure_signatures`: remove the `*, returncode: int | None = None` parameter, the `if returncode and not matches:` synthesis block, and the docstring paragraphs about `NONZERO_EXIT` and `returncode` (including the `returncode:` Args entry).
    Rewrite the remaining docstring so it no longer says the lines feed `_normalize_failure_signature` or "baseline/finalize signature-set comparison": the function returns every line starting with a known failure-marker prefix, in order, uncapped; callers (`_run_verify_gate`'s truncation excerpt, `_done_gate`) apply their own `[:20]` cap.
  - Delete `_normalize_failure_signature` in full.
  - `_run_verify_gate`:
    - delete the `signatures = _extract_failure_signatures(output, returncode=effective_returncode,)` statement and its preceding `# Extract every raw failure-marker line from the FULL, untruncated output ...` comment;
    - drop the `"signatures": signatures,` entry from the returned stuck dict;
    - delete the two `effective_returncode = ...` assignments (nothing reads them after this);
    - in the docstring, delete the paragraph starting `The non-zero-exit stuck dict also carries a "signatures" field`, and in `Returns:` change the dict shape to `{"status": "stuck", "stuck_type": "verify", "reason": <tail>}` and delete the sentence `The separate exception-path stuck dict (missing binary, etc.) has no "signatures" key.`.
    Keep the `fail_lines = _extract_failure_signatures(omitted)[:20]` truncation recovery unchanged.
  - `_run_verify_gates`:
    - remove the `module_verify_baseline` and `batch_verify_baseline` keyword parameters;
    - body becomes: run the batch gate, `return batch_result` when it is not `None`; return `None` when `module_wide_verify_cmd is None`; run the module-wide gate and prefix its reason with `[module-wide verify] ` on failure — delete the subset-diff waiver block and the `if module_verify_baseline == "pre-existing-failures":` skip with their comments;
    - docstring: delete the `module_verify_baseline is a cached, task-scoped read-only signal ...` paragraph and both removed Args entries; `Returns:` becomes "A stuck dict from the first gate that fails, or None when both pass (or are not configured)."
  - `finalize_from_output`, `_fixer_logic_ancestor_override`, `_forward_output`: remove both keyword parameters from each signature, both kwargs from every call they make (the `_forward_output(...)` call in `finalize_from_output`, the `_run_verify_gates(...)` call in `_fixer_logic_ancestor_override`, the `_fixer_logic_ancestor_override(...)` call and every `_run_verify_gates(...)` call site inside `_forward_output`), and their docstring text:
    the `module_verify_baseline:` and `batch_verify_baseline:` Args entries in `finalize_from_output`;
    the names `module_verify_baseline` and `batch_verify_baseline` from the `git_root, module_verify_baseline, cwd_override, module_wide_cwd_override, batch_verify_baseline: forwarded unchanged ...` Args line in `_fixer_logic_ancestor_override` (it becomes `git_root, cwd_override, module_wide_cwd_override: forwarded unchanged to `_run_verify_gates`.`);
    the `module_verify_baseline is forwarded to _run_verify_gates unchanged ...` and `batch_verify_baseline is forwarded unchanged to every _run_verify_gates call site below ...` paragraphs in `_forward_output`.
  - After editing, grep the file for `module_verify_baseline`, `batch_verify_baseline`, `signatures"`, `_normalize_failure_signature`, `NONZERO_EXIT`, `pre-existing-failures`, `waiv` and confirm zero hits.
  - Then apply the overview's `unused-import-check` Decision to this file (`re` is still used elsewhere in the module; keep it if so).
- **Commit:** `refactor(implementer): strict verify gates, drop baseline waiver and signature field`

### Card 13: Update implementer-common tests for strict gates

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Remove `_normalize_failure_signature` from the `from _implementer_common import (...)` block.
  - Delete Case 59 (`module_verify_baseline="pre-existing-failures"` skip), Case 71c (`_extract_failure_signatures` returncode synthesis / `NONZERO_EXIT`), Case 71b (`_normalize_failure_signature`), and Case 72 (the `batch_verify_baseline` subset-diff matrix) in full.
    Keep Case 71a (marker matching).
  - Cases 60, 61, 62: drop the `module_verify_baseline=` argument (60 and 61 become duplicates of each other once it is gone — keep one as "module-wide gate runs strictly when configured" and delete the other; 62's "kwarg omitted" premise disappears with the parameter, so delete 62).
  - Cases 78, 79, 80: drop the `batch_verify_baseline=` argument from each call and keep their strict-block assertions (a failing verify blocks, no checkout attempted, status.md untouched); reword each leading comment to describe a failing verify blocking strictly, without the corroboration/subset-diff/baseline framing.
  - Add a strict-semantics case block (one `try`/`except` case per bullet, matching the file's `PASS:`/`FAIL:` + `errors += 1` convention) calling `_run_verify_gates` with commands that pass/fail deterministically (e.g. `exit 0` / `exit 1` run through the real gate, as existing cases do):
    - batch verify fails -> returns the stuck dict with `stuck_type == "verify"`, and the module-wide command never runs;
    - batch verify passes and module-wide fails -> stuck dict whose `reason` starts with `[module-wide verify] `;
    - batch verify passes and `module_wide_verify_cmd=None` -> `None`;
    - a failing `_run_verify_gate` stuck dict has exactly the keys `status`, `stuck_type`, `reason` (no `"signatures"`);
    - `_run_verify_gates(..., module_verify_baseline="clean")` and `_run_verify_gates(..., batch_verify_baseline=["x"])` each raise `TypeError`.
  - After this card, grep the file for `module_verify_baseline`, `batch_verify_baseline`, `_normalize_failure_signature`, `NONZERO_EXIT`, `returncode=` next to `_extract_failure_signatures`, `pre-existing-failures`; the only hits are the two `TypeError` checks.
- **Commit:** `test(implementer): replace waiver cases with strict-gate cases`

## Batch Tests

`verify:` runs `test-implementer-common.py` (the gate chain), `test-done-gate.py` (the surviving `_extract_failure_signatures` caller), and `test-millpy-implement.py` / `test-fix-finalize.py`, which exercise the `finalize_from_output` signature from the two CLIs.
All were green on the task branch tip before planning.
