# Plan: Batch verify/baseline/completeness gates produce false positives or time out

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
slug: mill-go-batch-verify-baseline-reliability
approved: false
started: 20260716-113649
parent: hanf/linux-port-more
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: completeness-recount-cards-done
    file: 01-completeness-recount-cards-done.md
    depends-on: []
    verify: null
  - number: 2
    name: go-build-tag-retiering-check
    file: 02-go-build-tag-retiering-check.md
    depends-on: [1]
    verify: null
  - number: 3
    name: batch-verify-list-validation
    file: 03-batch-verify-list-validation.md
    depends-on: []
    verify: null
  - number: 4
    name: done-gate-baseline-preflight
    file: 04-done-gate-baseline-preflight.md
    depends-on: []
    verify: null
  - number: 5
    name: finalize-timeout-guidance-generalization
    file: 05-finalize-timeout-guidance-generalization.md
    depends-on: [4]
    verify: null
  - number: 6
    name: windows-long-path-mitigation
    file: 06-windows-long-path-mitigation.md
    depends-on: []
    verify: null
```

No module-wide `verify:` is set: each batch's own `verify:` scopes directly to the file(s) it changes, there is no shared cross-batch helper whose breakage would only surface at a different batch's boundary, and the existing per-batch code-review + finalize gates already replay each batch's own verify command as a regression guard. A repo-wide sweep would just re-run everything batch 01-06 individually already cover, at higher cost, for no additional signal.

## Shared Decisions

### Decision: never raise from a new gate/check function

- **Decision:** Every new function this plan introduces that runs as part of an automated gate — `_go_build_tag_retiering_stuck` (batch 02), `_check_verify_unrelated_test_files` (batch 03), `_done_gate.run_preflight` (batch 04) — must never let an uncaught exception propagate to its caller. Any git/subprocess failure, unparseable diff, or unexpected input is caught and translated into the function's normal "nothing to report" / fail-safe return value (`None`, an empty list, or a `{"result": ...}` dict per that function's own contract), never a raised exception.
- **Rationale:** This mirrors the established pattern already used throughout `_implementer_common.py` and `_verify_baseline.py` (`_content_commit_count`, `_batch_completeness_stuck`, `_run_baseline_stage` all return a safe default rather than raising on subprocess failure) — every gate in this pipeline is designed so a gate's own internal failure degrades to "run stricter" or "skip," never to a crash that would take down the orchestrator mid-batch.
- **Applies to:** batch 02, batch 03, batch 04.

### Decision: ASCII-only output from new print()/log() call sites

- **Decision:** Any new `print()`, `stderr` log line, or captured-output string this plan's code adds (retiering-gate skip logs in batch 02, validator drop logs in batch 03, `run_preflight`'s captured output in batch 04) uses ASCII only — no em dashes, curly quotes, or Unicode arrows.
- **Rationale:** Per this repo's CLAUDE.md: Windows cp1252 stdout crashes on non-ASCII output. This has bitten mill scripts before and is a standing project-wide rule, not new to this task.
- **Applies to:** batch 02, batch 03, batch 04.

### Decision: new small unit-test files follow the nearest sibling's established style, not a new convention

- **Decision:** This plan's one new test file, `test-done-gate.py` (batch 04), follows `test-verify-baseline.py`'s style exactly: a single `main() -> int` function with inline numbered cases printing `PASS`/`FAIL` and accumulating an error count, no `unittest.TestCase` classes and no `def test_*()` free functions. Existing test files being extended keep their own established style: `test-implementer-common.py` (batches 01, 02) uses the same single-`main()`-with-inline-cases style; `test-millpy-implement.py` (batch 01) uses `unittest.TestCase` subclasses; `test-plan-validate.py` (batch 03) and `test-verify-baseline.py` (batch 06) use individual `def test_*() -> int` functions collected into a `tests` list inside `main()`.
- **Rationale:** This codebase has at least three distinct, already-established test-authoring conventions across different files — matching whichever one a given file already uses (or, for the one new file, whichever sibling it most resembles) avoids introducing a fourth style and keeps each file internally consistent for future readers.
- **Applies to:** batch 01, batch 02, batch 03, batch 04, batch 06.

## All Files Touched

- `_mill/discussion.md` (read-only context; not edited by this plan)
- `mill-config.yaml`
- `plugins/mill/scripts/_done_gate.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-done-gate.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-verify-baseline.py`
