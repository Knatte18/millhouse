# Plan: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons

```yaml
task: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons
slug: mill-plan-review-validation-gaps
approved: true
started: 20260729-132742
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: plan-validate-pipeline
    file: 01-plan-validate-pipeline.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 2
    name: review-code-soft-fail
    file: 02-review-code-soft-fail.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-code-flow.py
  - number: 3
    name: verify-gate-enrichment
    file: 03-verify-gate-enrichment.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
```

## Shared Decisions

### Decision: three independent root batches, one per bug cluster

- **Decision:** Batch 1 bundles Fix 1 (template), Fix 2 (SKILL.md wording), and Fix 3 (new Go integration-tag check) because Fix 2 and Fix 3 both add rows to the same `plugins/mill/skills/mill-plan/SKILL.md` step-1.5 fix table and Fix 1's regression test lands in the same `plugins/mill/unit_tests/test-plan-validate.py` file Fix 3's tests land in — splitting them would force an artificial `depends-on` edge purely to dodge the `parallel-modifies-overlap` validator check (which compares whole-batch `Edits:` sets, not per-card). Batch 2 is Fix 4 (`_review_common.py`/`_review_code.py`). Batch 3 is Fix 5 (`_implementer_common.py`). No two batches share an `Edits:` target, so all three are root batches (`depends-on: []`) and are fully parallel-eligible.
- **Rationale:** Keeps each batch a coherent "smart unit" (one bug-cluster's touched files) while respecting the file-level constraints the validator enforces. Estimated context per batch (sum of `Edits:` file bytes / 4, no `Context:` needed — see below) is well under the 120000-token cap: batch 1 ~80k, batch 2 ~90k, batch 3 ~71k.
- **Applies to:** all batches.

### Decision: Context: is `none` on every card; every referenced helper/signature is fully specified in Requirements or already lives in the file being edited

- **Decision:** None of the 12 cards below list a `Context:` file. Every card's `Requirements:` gives the exact function signature, call shape, or algorithm needed, and every existing helper a card calls (`resolve_existing_paths`, `_subprocess_util.run`, `_plan_dag.parse_verify_field`, `_test_helpers.init_minimal_git_repo`/`checkout_new_branch`, `_make_fixture`) is either already imported into the file being edited or already lives in a test file already listed in that card's own `Edits:` (so it is read implicitly).
- **Rationale:** Keeps every batch's context estimate far under the `batch-oversized` cap — the two largest files in this task (`test-review-common.py` at ~164KB and `test-plan-validate.py` at ~183KB) are already counted once each via `Edits:`; adding any of them again as `Context:` for a sibling card in the same batch would not change the byte-sum estimate (it is a per-batch set union, not per-card), but adding a *different* large file as `Context:` (e.g. `_review_common.py` as `Context:` for a `_plan_validate.py` card) would. Every genuinely-needed signature is instead transcribed verbatim into `Requirements:`, verified against the actual source in this task-worktree (not the plugin cache) during planning.
- **Note on `mill-plan/SKILL.md`'s "Context: is an allowlist ... An empty or terse Context: is a review-blocker" Principle:** this plan's blanket `Context: none` is a deliberate, reviewed exception to that Principle, not an oversight. The Principle exists to prevent an implementer from needing an unlisted file it wasn't told to read (a cold-start defect); every cross-file helper this plan's cards call (`resolve_existing_paths`, `_subprocess_util.run`, `_plan_dag.parse_verify_field`, `_test_helpers.init_minimal_git_repo`/`checkout_new_branch`, `_make_fixture`) has its exact signature and behavior transcribed verbatim into the calling card's `Requirements:`, verified against actual source during planning — the implementer never needs to open the defining file to know how to call it correctly. This was audited card-by-card during plan-fix round 2 and no case was found where the narrower cold-start harm the Principle guards against actually applies.
- **Applies to:** all batches.

### Decision: no Creates:/Deletes:/Moves: anywhere in this plan

- **Decision:** Every card in every batch edits an existing file. No new files are created, no files are deleted, no files are renamed. `Creates:`/`Deletes:`/`Moves:` are `none` on every card; no batch needs a `## Rename mechanic` section.
- **Rationale:** Matches the discussion's own Scope — all five fixes extend existing modules and their existing test files (no new test files, per the discussion's explicit Q&A entry on that point).
- **Applies to:** all batches.

### Decision: verify: commands are `run-all.py --only`-scoped per touched test file, no module-wide overview verify:

- **Decision:** Each batch's `verify:` runs only the test file(s) it edits, via `run-all.py --only <basenames>`, prefixed with the mandatory `PYTHONPATH= ` isolation reset (this is a Python project — `plugins/mill/pyproject.toml` exists). The overview's own module-wide `verify:` stays `null` (the default) — the three batches' scoped verifies already cover every file this task touches, and `pipeline.done_gate` in `mill-config.yaml` is not overridden by this task.
- **Rationale:** Matches the project's per-batch verify-scoping convention (CLAUDE.md, `mill-plan/SKILL.md`'s "Verify command scope" section) — the full 104-file suite is multiple minutes and none of these fixes touch a cross-cutting helper every test imports.
- **Applies to:** all batches.

### Decision: follow each touched test file's own existing fixture/assertion convention exactly

- **Decision:** `test-plan-validate.py` uses one `def test_<name>() -> int` function per scenario, returning 0/1 and printing `PASS`/`FAIL` (see its own `_make_overview`/`_make_batch_file`/`_write_plan` fixture helpers). `test-review-common.py` and `test-implementer-common.py` use a single `def main() -> int` with inline scenario blocks (tempfile fixtures, inline `try`/`assert`/`except AssertionError` with `errors += 1`, no per-scenario function). `test-review-code-flow.py` mixes both — new integration-level additions in this task use its newer standalone-`def test_<name>() -> int` convention (matching its own `test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path`), not the older `main()`-inline style. New test code in every file MUST match that file's own existing convention exactly rather than introducing a new style.
- **Rationale:** Verified directly against each file's current structure during planning; mixing conventions within one file makes the file harder to navigate and is not requested by the discussion.
- **Applies to:** batch 1 (test-plan-validate.py), batch 2 (test-review-common.py, test-review-code-flow.py), batch 3 (test-implementer-common.py).

### Decision: ASCII-only output in every new print()/warning/marker string

- **Decision:** Any new `print()`/warning/marker text introduced by these fixes (Fix 4's new stderr warning in `resolve_ref_paths`, Fix 5's enrichment marker string) uses only ASCII characters — `...` not an ellipsis glyph, `->` not `→`, no em-dash.
- **Rationale:** CLAUDE.md: "`print()` / `_log()` output: ASCII only ... Windows cp1252 crashes on non-ASCII stdout."
- **Applies to:** batch 2 (Fix 4 warning), batch 3 (Fix 5 marker).

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
