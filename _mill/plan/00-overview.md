# Plan: Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports

```yaml
task: 'Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports'
slug: mill-pipeline-silent-failure-and-report-bugs
approved: false
started: 20260729-172419
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: archive-tag-push-failure
    file: 01-archive-tag-push-failure.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-archive-tag-conflict.py
  - number: 2
    name: plan-review-holistic-rounds-gate
    file: 02-plan-review-holistic-rounds-gate.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py
  - number: 3
    name: test-registry-local-overlay-redirect
    file: 03-test-registry-local-overlay-redirect.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-plan-flow.py test-review-discussion-flow.py
  - number: 4
    name: implementer-commit-sha-validation
    file: 04-implementer-commit-sha-validation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: All four batches are independent

- **Decision:** No batch depends on another (`depends-on: []` on every entry); all four may implement in any order or in parallel.
- **Rationale:** the four bugs (`_archive_tag.py` push reporting, `_review_plan.py`'s holistic-rounds gate, `_test_registry.write_to`'s dead target, `_implementer_common.py`'s commit_sha override) share no code path — each batch's `Edits:`/`Context:` file set is disjoint from every other batch's.
- **Applies to:** all batches

### Decision: Items explicitly out of scope are not touched by any batch

- **Decision:** the following stay untouched by every batch: the `reviewer_override`-specific rounds gate in `_review_plan.py::run()` (~line 718) and the sibling `batch`-rounds gate (~line 711); the 11 existing `_test_registry.write_to(wiki_root)` call sites (`test-agent-mode-dispatch.py` x1, `test-review-code-flow.py` x7, `test-review-plan-flow.py` x2, `test-review-discussion-flow.py` x1) — these remain harmless no-ops after Batch 03's redirect since they all use the `"test_stub"` reviewer, which bypasses registry lookup entirely; and any forensic reproduction of the historical #744 incident beyond the one gap Batch 04 closes.
- **Rationale:** `_mill/discussion.md`'s Scope > Out and Decisions sections document these as deliberate, already-investigated exclusions, not oversights a reviewer should flag as missing.
- **Applies to:** all batches

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `plugins/mill/scripts/_archive_tag.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/templates/fixer-batch-brief.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/merge-in-verify-brief.md`
- `plugins/mill/unit_tests/_test_helpers.py`
- `plugins/mill/unit_tests/_test_registry.py`
- `plugins/mill/unit_tests/test-archive-tag-conflict.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-reviewers.py`
