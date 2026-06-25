# Batch: verify-and-implementer

```yaml
task: Fix spawn lifecycle integrity, agent-mode async assumption, merge-in conflicts, and pre-existing failure validation
batch: verify-and-implementer
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
depends-on: []
```

## Batch Scope

Delivers the implementer-side correctness fixes: #541 wires the currently-dead
top-level `verify:` slot in the plan overview as an opt-in module-wide check run
as a second gate at each batch boundary, and #542 gives the implementer brief a
`<PARENT_BRANCH>` token plus an instruction to validate any "pre-existing" failure
against the parent before emitting `stuck_type: verify`. Concentrated in
`millpy-implement.py`, `_implementer_common.py`, the `implementer-brief.md`
template, and the `plan-overview.md` template. Independent of the spawn/teardown
batches (no shared files), so `depends-on: []`.

Batch-local decision: the module-wide gate is **opt-in and backward-compatible** —
the new `module_wide_verify_cmd` parameter defaults to `None`, so plans that leave
the overview `verify:` null behave exactly as before. The callee signature change
(card 9) lands before the caller wiring (card 10) so every card ends green.

## Cards

### Card 8: Document the overview-level module-wide `verify:`
- **Context:**
  - `plugins/mill/templates/plan-batch.md`
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plan-overview.md` update the template HTML comment and the `verify: null` frontmatter slot's guidance to document its semantics: the top-level `verify:` is an OPTIONAL module-wide check run at each batch boundary AFTER the batch's own `verify:` passes; `null` means skip (default, no behavior change); when set it follows the same `PYTHONPATH= ` shape rule as per-batch `verify:` and should be a cheap whole-module compile/vet/smoke command (e.g. `go vet ./...` or a scoped `run-all.py`) that catches cross-package regressions from shared-helper edits at the introducing batch. Template-comment/guidance edit only — do not change any rendered plan file.
- **Commit:** `docs(plan): document overview-level module-wide verify slot (#541)`

### Card 9: Run the module-wide verify as a second gate
- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add an optional `module_wide_verify_cmd: str | None = None` parameter to `finalize_from_output` and `_forward_output` (thread it through any intermediate call between them). After the existing batch-scoped `_run_verify_gate(project_root, verify_cmd)` returns success (None), call `_run_verify_gate(project_root, module_wide_verify_cmd)`; if it returns a stuck dict, propagate that `stuck_type: verify` result (prefix the reason to indicate the module-wide scope so the operator can tell the two gates apart). When `module_wide_verify_cmd` is None, behavior is unchanged (single gate). Add tests in `test-implementer-common.py`: a passing batch verify + a failing module-wide verify yields `stuck_type: verify`; `module_wide_verify_cmd=None` runs only the batch gate.
- **Commit:** `feat(implementer): run module-wide verify as second gate (#541)`

### Card 10: Thread the overview `verify:` into the implementer
- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`, in the finalize stage (where `verify_cmd = batch_frontmatter.get("verify")` is resolved) and the full stage, additionally read the overview file's top-level `verify:` by parsing the leading ```yaml block of the overview (`OVERVIEW_FILE`), paralleling `_plan_dag._read_batch_frontmatter`; pass the result as `module_wide_verify_cmd` to `finalize_from_output` / `_forward_output`. A null/absent overview `verify:` passes `None`. Add a test in `test-millpy-implement.py` that an overview with a non-null top-level `verify:` causes that command to be threaded as `module_wide_verify_cmd`, and a null one passes `None`.
- **Commit:** `feat(implementer): thread overview-level verify into batch gate (#541)`

### Card 11: Add the `<PARENT_BRANCH>` render token
- **Context:**
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`, in the implementer-brief render token map passed to `_render.render(template_path, {...})`, add `"PARENT_BRANCH": parent_branch or ""` using the already-resolved `parent_branch` value (resolved earlier in the same function for the dirty-tree gate). When `parent_branch` is `None`, the token renders empty. Add a test in `test-millpy-implement.py` asserting the rendered brief includes the `<PARENT_BRANCH>` substitution populated from the resolved parent, and renders empty (not the literal `None`) when the parent is unresolvable.
- **Commit:** `feat(implementer): expose PARENT_BRANCH render token (#542)`

### Card 12: Require parent-branch validation before `stuck_type: verify`
- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `implementer-brief.md` `## Verify`, before the instruction that emits `stuck` with `stuck_type: verify`, add: before reporting any failure as "pre-existing" or "unrelated to my changes", confirm it reproduces on the parent branch using the `<PARENT_BRANCH>` token — e.g. `git log <PARENT_BRANCH>..HEAD -- <files in the failure's import/dependency chain>` (a same-task commit touching those files means it is NOT pre-existing) or `git show <PARENT_BRANCH>:<path>` (the brief already permits cross-worktree/parent reads). If the failure does NOT reproduce on the parent, treat it as in-scope: fix it, or escalate `logic` — never label it "pre-existing verify". Add the unresolved-parent fallback: if `<PARENT_BRANCH>` renders empty, skip the parent-reproduction check and treat the failure as in-scope (never auto-label pre-existing on an empty token). Update the `verify` entry in the `## Report` `stuck_type` enum to reference this validation requirement. Documentation edit only; no runnable test (covered by review).
- **Commit:** `docs(implementer): require parent-branch validation for pre-existing claims (#542)`

## Batch Tests

`verify:` runs `test-implementer-common.py` (the two-gate logic: module-wide verify as a
second gate, None = single gate) and `test-millpy-implement.py` (overview `verify:` threaded
as `module_wide_verify_cmd`; the `<PARENT_BRANCH>` token present and empty-safe). Both are
existing files extended in place. Cards 8 and 12 are template/brief documentation edits with
no runnable surface; they are verified by the plan/code review gates and leave `verify:`
green (nothing broken). Scope is the implementer subsystem only — focused `--only` is correct.
