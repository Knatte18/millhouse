# Plan: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
task: 'Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch'
slug: mill-review-verdict-and-counting-gaps
approved: false
started: 20260728-184433
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
    name: review-plan-counting-fix
    file: 01-review-plan-counting-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
  - number: 2
    name: review-plan-counting-tests
    file: 02-review-plan-counting-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py
  - number: 3
    name: plan-review-templates
    file: 03-plan-review-templates.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-templates.py
  - number: 4
    name: plugin-manifest-validator
    file: 04-plugin-manifest-validator.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: nit-count-fix-mechanism

- **Decision:** In `_review_plan.py`'s `run()` and `_review_one_batch()`, refactor the 4 terminal-write call sites that write a NEW review file on a successful verdict parse AND whose result reaches the returned `ReviewResult` — per-batch in `_review_one_batch()`; holistic NEED_CONTEXT retry-success; holistic NEED_CONTEXT no-resolve; holistic normal — to call `finalize_scope()` from `_review_common.py` instead of duplicating `parse_verdict` + `write_review_file` + `parse_blocking_count` + `count_unrecognized_severity_findings` inline. Use `finalize_scope()`'s returned `verdict`, `blocking_count`, `nit_count`, `file` for the review entry dict. Six error-path sites that never obtain a parseable raw response (or whose parse fails) get `"nit_count": 0` added to their literal dict for schema parity with `finalize()`'s equivalent catches — no `finalize_scope()` call, since there is no successful raw response to compute real counts from. `_scan_approved_batches()`'s skip-approved carryforward dicts get both `blocking_count` and `nit_count` computed via `parse_blocking_count` + `count_unrecognized_severity_findings` directly (not `finalize_scope()`, since no review file is written at that site). The final `ReviewResult` construction sums `nit_count` across `reviews[]` the same way `aggregate_blocking` already sums `blocking_count`.
- **Rationale:** Eliminates the exact code duplication that caused #709 for every site whose output is actually observable in `ReviewResult`; the resume-round disk-scan block (a 5th `blocking_count` computation site) is excluded because its output (`_disk_reviews`) is never merged into `reviews[]` — a separate pre-existing dead-code bug, out of scope for this fix.
- **Applies to:** review-plan-counting-fix, review-plan-counting-tests

### Decision: medium-severity-regression-test

- **Decision:** Treat #720 as already resolved by `cf075f93`'s `count_unrecognized_severity_findings` fold-in (confirmed present and exercised in both `finalize_scope()` and `run()`'s existing `blocking_count` computations on this branch's HEAD). Add regression tests asserting a `[MEDIUM]`-only review folds into `blocking_count` (not silently dropped, and `nit_count` stays 0) for the holistic path of `run()` and for an isolated `finalize_scope()` case. No production code change for #720 itself — the per-batch case is already covered once the nit-count-fix-mechanism tests land (see review-plan-counting-tests Card 7's `[MAJOR]`-fold-in extension; the fold-in logic treats any off-vocabulary label identically, so `[MEDIUM]` vs `[MAJOR]` is not a distinct case).
- **Rationale:** the loomyard repro predates the fix reaching that repo's plugin cache; millhouse's own code already does the right thing. A regression test is cheap insurance without reopening a settled design decision (fold vs. separate counter).
- **Applies to:** review-plan-counting-tests

### Decision: all-files-touched-brief-fix

- **Decision:** Add one sentence to both `review-plan-holistic.md` and `review-plan-batch.md` (near the existing criteria list) stating: the overview's `## All Files Touched` section is the union of `Edits:`/`Creates:`/Move-target paths across all batches, with `Deletes:` tokens and Move-source paths excluded — a Deletes-only or Move-source-only path missing from that list is correct, not a finding.
- **Rationale:** both templates bulk the full overview (including `## All Files Touched`) into the reviewer's prompt, so both are equally exposed to raising the same false NIT that #717 reported; `mill-plan/SKILL.md` and `_plan_validate.py` check 8 already encode this exact rule for the plan-writing side — the reviewer brief was the only place missing it.
- **Applies to:** plan-review-templates

### Decision: platform-claim-verification

- **Decision:** Add a criteria bullet to `review-plan-holistic.md` and `review-plan-batch.md`: when a plan or discussion claim describes Claude Code's own platform/harness behavior and a manifest or doc file that could confirm or refute the claim is present in the reviewer's context, the reviewer must check that file before accepting the claim as given — BLOCKING if the claim is checkable from available context, unverified, and the plan's correctness depends on it. Add a new `_plan_validate.py` check (`plugin-manifest-context-missing`) requiring any batch whose `Creates:`/`Edits:`/`Deletes:` touches a file under `plugins/mill/agents/` to have `plugins/mill/.claude-plugin/plugin.json` present in that batch's `Context:` **or** `Edits:` (not `Context:` alone — the primary expected case is a batch that registers a new agent by editing `plugin.json`'s `agents` array directly, and existing convention never duplicates an `Edits:` file into `Context:`). `Deletes:` is included alongside `Creates:`/`Edits:` for the symmetric removal case. Add a corresponding `mill-plan/SKILL.md` Step 1.5 fix-table row (`plugin-manifest-context-missing`).
- **Rationale:** matches #714's own suggested fix direction; the new `_plan_validate.py` rule specifically closes the gap for bulk-mode reviewers, who cannot fetch files on their own — without it, the criteria bullet alone is a no-op for that dispatch mode, which is exactly the mode #714 occurred in. Scoped to agent-definition files only — `plugin.json` currently declares only an `agents` array (no `commands`/`hooks` key), so those two categories have no source-grounded path pattern to check against today.
- **Applies to:** plan-review-templates, plugin-manifest-validator

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-review-templates.py`
