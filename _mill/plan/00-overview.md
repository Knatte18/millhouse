# Plan: _plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose

```yaml
task: '_plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose'
slug: plan-validate-context-completeness-false-positive-exemptions
approved: false
started: '20260904-164017'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: validator-exemptions
    file: 01-validator-exemptions.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: structural-exemption-tests
    file: 02-structural-exemption-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 3
    name: lexical-exemption-tests
    file: 03-lexical-exemption-tests.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 4
    name: reviewer-and-docs-sync
    file: 04-reviewer-and-docs-sync.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
```

## Shared Decisions

### Decision: eight exemptions, three placement groups

- **Decision:** The task adds eight exemptions to the `context-completeness` check. Four are path-shape exemptions placed in the path branch (directory-intent, out-of-repo, gitignored, forward cross-card Creates). Three are line-level exemptions placed before the path/symbol branch split, so they apply to both branches (negation phrase, contrast citation, quoted material). One is an escape marker appended to the existing citation-marker tuple, therefore also line-level and branch-agnostic.
- **Rationale:** the seven reported false-positive shapes split into four with crisp machine-checkable structural signatures and three that are genuinely a matter of English phrasing. Structural signals are preferred wherever they exist; lexical matching is used only where the distinction lives in the prose; one escape marker covers the residue that neither reaches.
- **Applies to:** all batches

### Decision: the primary risk is over-exemption, so every exemption ships a dirty case

- **Decision:** every exemption gets both a clean-case test (the exemption fires, zero findings) and a dirty-case test (the exemption must not fire, exactly one finding). A rule that breaks an existing dirty-case test is too broad and must be narrowed, never the test loosened.
- **Rationale:** the check exists to catch genuine unlisted read dependencies. Trading a fixed false positive for a silent false negative is strictly worse than leaving the false positive in place, because a suppressed finding is invisible.
- **Applies to:** all batches

### Decision: implementation and tests are separate batches, forced by the context cap

- **Decision:** batch 1 changes the validator; batches 2 and 3 add its tests. No batch contains both the validator source and the validator test file.
- **Rationale:** `plugins/mill/scripts/_plan_validate.py` is 153,516 bytes (about 38k estimated tokens) and `plugins/mill/unit_tests/test-plan-validate.py` is 400,833 bytes (about 100k). Together they are roughly 139k estimated tokens, over the 120,000 `pipeline.max_batch_context_tokens` cap, so a single test-driven batch would fail the `batch-oversized` validator check. The same arithmetic is why the test batches do not list the validator source in `Context:` at all: 554,349 bytes is about 139k tokens either way. Test cards therefore carry the exact call signature and the exact fixture text they need, inline in `Requirements:`.
- **Applies to:** validator-exemptions, structural-exemption-tests, lexical-exemption-tests

### Decision: verify uses direct single-file test invocation, not run-all.py --only

- **Decision:** every batch's `verify:` invokes its test file directly rather than through `run-all.py --only`.
- **Rationale:** the `verify-unrelated-test-file` check flags an `--only` token that the batch does not itself touch and that is unchanged versus the parent branch. Batch 1 changes only the validator source, so an `--only test-plan-validate.py` token would fire that check at plan-validation time. Direct single-file invocation is a sanctioned pattern in mill-plan's own "Verify command scope" section and the check only scans `--only` token lists, so it sidesteps the problem without weakening the gate.
- **Applies to:** all batches

### Decision: done_gate stays null

- **Decision:** `pipeline.done_gate` is left at its current `null` value; this plan does not modify `mill-config.yaml`.
- **Rationale:** mill-plan's done-gate guidance says to default `done_gate` to the language's lint command only when that command exits 0 against the current worktree tip. `uvx ruff check .` reports 1969 pre-existing errors here, so adopting it would make every future task in this hub depend on unrelated lint debt being cleared first. There is also no cheap repo-wide Python test command — the full suite is multiple minutes. Recording the finding here is the guidance's prescribed alternative.
- **Applies to:** all batches

### Decision: no fork dispatch during implementation

- **Decision:** implementers work directly; no `Agent(subagent_type: "fork")` research dispatch is planned or required.
- **Rationale:** every file this task touches is named explicitly in a card's `Context:` or `Edits:`, and every behavior change is specified with a concrete line anchor. There is no open research question that needs the parent's in-flight reasoning.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-templates.py`
