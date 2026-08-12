# Plan: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
slug: review-pipeline-consistency-bugs
approved: true
started: '20260812-183827'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: error-envelope-contract
    file: 01-error-envelope-contract.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-cli.py
  - number: 2
    name: cli-round-threading
    file: 02-cli-round-threading.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-cli-error-envelope.py test-review-plan-finalize-round.py
  - number: 3
    name: reviewer-kind-finalize-wrappers
    file: 03-reviewer-kind-finalize-wrappers.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-discussion-flow.py test-review-code-flow.py
  - number: 4
    name: verdict-summary-demotion-note
    file: 04-verdict-summary-demotion-note.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-class-taxonomy.py
  - number: 5
    name: skill-error-kind-retry-wiring
    file: 05-skill-error-kind-retry-wiring.md
    depends-on: [1, 3]
    verify: null
```

## Shared Decisions

### Decision: error_kind is additive, per-reviews[]-entry only

- **Decision:** `error_kind: "usage" | "reviewer"` is added as a new key inside each `reviews[]` entry dict (both the `print_error_envelope` envelope shape and the `ReviewResult`/plan-finalize dict shape). It is never mirrored at the envelope's top level, and no new top-level `verdict` value is introduced.
- **Rationale:** Every existing `verdict == "ERROR"` consumer (mill-receiving-review, review-summary, the four SKILL.md ERROR-only-aggregate retry sites) keeps working unmodified against the top-level `verdict` field. Only the retry-logic consumer sites (Batch 5) need to opt into reading the new per-entry field. `ReviewResult` and the plan-finalize `result_dict` already have `reviews: list[dict]`, so an additive key needs no dataclass or key-copy-list change anywhere.
- **Applies to:** all batches.

### Decision: `error_kind` defaulting

- **Decision:** `print_error_envelope`'s new `error_kind` parameter defaults to `"usage"` — every one of its call sites across the three CLIs' `main()` functions is a pre-reviewer usage error, so none of them pass the parameter explicitly. `error_kind: "reviewer"` is set explicitly only inside each CLI-wrapper `finalize()` function's own internal `except ReviewError` block (Batch 3) — the sole site where a `parse_verdict` failure on the reviewer's own raw text lands.
- **Rationale:** Matches the discussion's "error_kind bucketing" Decision exactly; keeps Batch 1/2's edits (all `print_error_envelope` call sites) free of any `error_kind=` argument at every site.
- **Applies to:** Batch 1, Batch 2, Batch 3.

### Decision: #838 regression coverage already exists — no new test added

- **Decision:** The discussion's Scope lists "Regression test confirming `--stage finalize --duration-s <float>` is accepted by all three review CLIs" as an in-scope deliverable. Direct read of `plugins/mill/unit_tests/test-review-finalize.py` confirms `test_review_discussion_finalize_all_cost_flags_written`, `test_review_plan_finalize_all_cost_flags_written`, and `test_review_code_finalize_all_cost_flags_written` (added by commit `479f806b`, already on this branch) already invoke `--stage finalize --duration-s <float> --tool-calls <N> --cost-usd <dollars>` end-to-end for all three CLIs and assert `rc == 0`. No batch in this plan adds a new, redundant test for this — the existing coverage already satisfies the deliverable.
- **Rationale:** YAGNI — duplicating already-passing coverage adds maintenance cost with no additional signal. Documented here (rather than silently dropped) so the plan reviewer can verify the claim by direct read instead of treating the Scope item as unaddressed.
- **Applies to:** all batches (informational; no batch implements this item as new work).

### Decision: test style matches the file being extended

- **Decision:** Every test card in this plan extends an existing test file and follows that file's own established style exactly (its harness functions, its `unittest.TestCase` vs. plain `TESTS = [...]`-list-with-`main()` convention, its naming pattern) rather than introducing a new style into an existing file.
- **Rationale:** `plugins/mill/unit_tests/` mixes both `unittest.TestCase`-based files (e.g. `test-review-cli-error-envelope.py`) and plain-function `TESTS` list files (e.g. `test-review-class-taxonomy.py`, `test-review-plan-flow.py`) with no single project-wide convention; matching the target file's existing style keeps each file internally consistent.
- **Applies to:** Batch 1 (Card 2), Batch 2 (Cards 6-7), Batch 3 (Card 11), Batch 4 (Card 15).

## All Files Touched

- `plugins/mill/scripts/_review_cli.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-go-base/holistic-review.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
