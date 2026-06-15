MILL_REVIEW_BEGIN
# Review: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [BLOCKING] Card 8 targets wrong entry point for prepare gate
**Location:** Batch 3 / Card 8
**Issue:** The prepare-stage validator gate added by Card 7 lives in `millpy-review-plan.py:main()`, but `test-review-plan-flow.py` only ever imports/calls `from _review_plan import run as plan_run` and never invokes `main()` — so following the file's "existing harness style" would test `plan_run` (the `--stage full` backend), which does NOT contain the prepare gate, leaving #465 uncovered.
**Fix:** Specify that Card 8 must invoke `millpy-review-plan.py.main(["--stage","prepare", ...])` after `os.chdir(project_root)` (the fixture already seeds wiki/registry/config.local for `load_config`+`find_active_slug`), not reuse the `plan_run` harness.

### [NIT] Card 9 mis-cites SKILL.md:133 scope of the "BOTH modes" note
**Location:** Batch 4 / Card 9
**Issue:** SKILL.md:133's "runs unchanged in BOTH modes" note sits under the subprocess/psmux dispatch branch and asserts the gate "never dispatches an LLM, so it is independent of dispatch mode" — but the agent-mode gate this task adds runs inside the CLI `--stage prepare` brief render, a different mechanism than step 1.5's bash gate; "keep it, it's now accurate" conflates the two.
**Fix:** Card 9 should clarify that line 133's claim refers to step 1.5's Python bash gate and have Card 9 add the prepare-envelope handling under the agent-mode dispatch (line 131) section, not lean on 133 as covering the new CLI gate.

### [NIT] Card 6 import of _load_root_from_overview not reflected in Context completeness
**Location:** Batch 3 / Card 6
**Issue:** Card 6 requires importing `_load_root_from_overview` from `_review_common` into `millpy-review-plan.py`; `_review_common.py` is listed in Context, so this is satisfied — but `millpy-review-plan.py` currently imports only `resolve_path` etc. from `_review_common` (line 98), and the card should name that the new symbol joins that existing import line for atomicity.
**Fix:** Add to Card 6 Requirements that `_load_root_from_overview` is appended to the existing `from _review_common import (...)` block at `millpy-review-plan.py:98`.

## Verdict

REQUEST_CHANGES
Card 8 would test the wrong entry point and miss the #465 prepare gate entirely.
MILL_REVIEW_END