# Plan: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash

```yaml
task: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash
slug: mill-plan-and-start-gaps
approved: true
started: 20260630-185645
parent: main
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

## Batch Index

```yaml
batches:
  - number: 1
    name: moves-target-docs-and-messages
    file: 01-moves-target-docs-and-messages.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 2
    name: parse-batch-refs-leading-token
    file: 02-parse-batch-refs-leading-token.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-plan-validate.py
  - number: 3
    name: mill-start-utf8-fix
    file: 03-mill-start-utf8-fix.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: three-independent-bugfixes-no-shared-code

- **Decision:** Each batch fixes one of three independent, source-filed bugs (#584/#585, #580, #583). No batch depends on another — they touch disjoint file sets and share no helpers, types, or runtime state.
- **Rationale:** Confirmed file-disjointness during discussion: Batch 1 touches `plan-overview.md`, `mill-plan/SKILL.md`, `_plan_validate.py`; Batch 2 touches `_review_common.py`, `test-review-common.py`, `test-plan-validate.py`; Batch 3 touches `mill-start/SKILL.md`. Zero overlap, so all three batches are safe to run in parallel.
- **Applies to:** all batches.

### Decision: validator-logic-unchanged-docs-and-messages-only

- **Decision:** `_check_all_files_touched_mismatch`'s pass/fail logic (which already includes `Moves:` target paths in the required union — see `_plan_validate.py:1170-1182`) is NOT modified by this plan. Only prose describing that logic (template, SKILL fix-table row, and the check's own two error-message strings) is corrected to match the already-correct behavior.
- **Rationale:** The Moves-target-inclusive behavior is a deliberate, already-shipped decision (issue #494, commit `2eed551c`). Changing the logic would regress that decision. The bug is that documentation and the check's own error-message text never caught up.
- **Applies to:** moves-target-docs-and-messages.

### Decision: parse-batch-refs-leading-token-defense-in-depth

- **Decision:** `parse_batch_refs`'s multi-line sub-bullet extraction is hardened to take only the leading backtick-wrapped token per sub-bullet line, discarding any further backtick spans on the same line (prose parentheticals). The single-line inline form (e.g. `` - **Edits:** `a`, `b` ``) is untouched — it is an established, separately-tested convention where multiple comma/backtick-separated tokens on one line are legitimate.
- **Rationale:** This change is deliberate defense-in-depth alongside plan-validate Check 6 (`_check_ref_not_backtick_path` / `reads-not-backtick-path`), which already rejects the same multi-backtick sub-bullet shape at `--stage prepare` time but cannot catch edits made to a batch file after that one-time gate (batch files remain mutable working state post-approval — the originating bug report explicitly notes the offending bullet was added by the implementer during/after implementation). Check 6 is not modified by this plan.
- **Applies to:** parse-batch-refs-leading-token.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-common.py`
