# Batch: docs-and-reviewer-guardrail

```yaml
task: "_plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch"
batch: docs-and-reviewer-guardrail
number: 3
cards: 3
verify: null
depends-on: []
```

## Batch Scope

This batch is doc/prompt-only — no executable surface, so `verify: null` (per the template's "state why" convention for a `verify: null` batch). It wires the `overview-level-escape-hatch`, `fix-table-runner-agnostic-remedy`, `reviewer-prompt-guardrail`, and `config-doc-fix` Shared Decisions into `mill-plan/SKILL.md`, `review-plan-holistic.md`, and the template `mill-config.yaml`. It also updates `mill-plan/SKILL.md`'s self-run call block to pass the new `done_gate` keyword argument that batch 1 added to `_plan_validate.run`'s signature — this batch does not depend on batch 1 at the file level (different files, no shared code), but both must agree on the parameter name `done_gate`, which this plan fixes as the single source of truth for both batches.

## Cards

### Card 4: Update mill-plan/SKILL.md — done_gate self-run wiring, overview-level escape hatch, fix-table remedy

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Four edits to `plugins/mill/skills/mill-plan/SKILL.md`, all in Phase: Plan / Phase: Plan Review:

  1. In the "**Self-run the validator gate**" paragraph, replace:

  ```
This mirrors `millpy-review-plan.py`'s own step-1.5 gate exactly — same seven keyword arguments (`root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`). `git_root` and `wiki_path` are already bound at mill-plan's Entry step, and `worktree_root` at Path Setup, so this needs no new path resolution.
  ```

     with:

     ```
     This mirrors `millpy-review-plan.py`'s own step-1.5 gate exactly — same eight keyword arguments (`root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`, `done_gate`). `git_root` and `wiki_path` are already bound at mill-plan's Entry step, and `worktree_root` at Path Setup, so this needs no new path resolution.
     ```

  2. In the self-run `_plan_validate.run(...)` call block immediately below the `verify-full-suite`/`out-of-worktree-target` skip-check override paragraphs, add a new keyword argument line immediately after `max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000),`:

     ```python
         done_gate=cfg.get("pipeline", {}).get("done_gate"),
     ```

  3. Replace the `verify-full-suite` skip-check escape hatch paragraph:

  ```
**`verify-full-suite` skip-check escape hatch.** Keep the "Verify command scope" section's carve-out (a batch that legitimately touches a cross-cutting helper every test imports MAY use the unbounded `run-all.py`) — but only when the batch's own `## Batch Tests` section documents that justification. If it does, set `skip_checks = skip_checks | frozenset({"verify-full-suite"})` and record the justification in the plan commit message (see "Commit on the task branch" below). If the justification is absent or unconvincing, leave `skip_checks` unchanged for this check — let it fire and halt per the `verify-full-suite` fix-table row (Phase: Plan Review Step 1.5) instead.
  ```

     with:

     ```
     **`verify-full-suite` skip-check escape hatch.** Keep the "Verify command scope" section's carve-out (a batch that legitimately touches a cross-cutting helper every test imports MAY use the unbounded `run-all.py`) — but only when the justification is documented in the location matching the finding's scope: for a **batch-level** finding (`batch:` names a batch), the batch's own `## Batch Tests` section; for an **overview-level** finding (`batch: None`, the overview's own module-wide `verify:`), a `### Decision:` subsection under `00-overview.md`'s `## Shared Decisions` section. If the justification is present in the matching location, set `skip_checks = skip_checks | frozenset({"verify-full-suite"})` and record the justification in the plan commit message (see "Commit on the task branch" below). If the justification is absent or unconvincing, leave `skip_checks` unchanged for this check — let it fire and halt per the `verify-full-suite` fix-table row (Phase: Plan Review Step 1.5) instead.
     ```

  4. In the Step 1.5 fix table, replace the `verify-full-suite` row:

  ```
   | verify-full-suite              | The payload's `path:` field carries the offending `verify:` command (`batch:` names the offending batch, or `None` for the overview's module-wide `verify:`). If the batch's own `## Batch Tests` section already documents the cross-cutting-helper justification (see the `verify-full-suite` skip-check escape hatch in Phase: Plan), re-run with `--skip-check verify-full-suite`. Otherwise scope the command via `-k <pattern>` or `--only <every affected test file>`. |
  ```

     with:

     ```
     | verify-full-suite              | The payload's `path:` field carries the offending `verify:` command; its `message:` field already names the runner-correct scoping flag (`-run <pattern>` for Go, `--filter` for dotnet, `-k <pattern>`/`--only <files>` for run-all.py, `-k <pattern>` for bare pytest — apply that flag directly. If instead the justification is already documented — the batch's own `## Batch Tests` section when `batch:` names a batch, or a `### Decision:` subsection under `00-overview.md`'s `## Shared Decisions` when `batch:` is `None` (see the `verify-full-suite` skip-check escape hatch in Phase: Plan) — re-run with `--skip-check verify-full-suite` instead of scoping. |
     ```

  Every replacement above must match the existing surrounding table/paragraph formatting exactly (table column alignment does not need to be re-padded — this file's existing rows are not column-aligned either, e.g. compare the `verify-not-isolated` and `batch-oversized` row lengths).
- **Commit:** `docs(mill-plan): wire done_gate self-run, overview-level escape hatch, and runner-agnostic fix-table remedy`

### Card 5: Add overview verify: scope reminder to review-plan-holistic.md

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Insert a new section between the end of the existing "## Source-grounding rule" section (ending "...Fabricating file contents — or inferring them from filename / position alone — is a worse failure than halting honestly.") and the "## Criteria (apply to the plan as a whole)" heading:

  ```
  ## Overview verify: scope rule

  The overview's module-wide `verify:` field (if set) must stay a cheap compile/vet/smoke command, per `plan-overview.md`'s own documented intent — never a full test-suite run. Do not suggest, as a fix for any finding, converting it into an unscoped full-test command (e.g. `go test ./...`, `dotnet test`, `pytest`) — `_plan_validate`'s `verify-full-suite` check will reject that on the plan's very next validation pass, costing a review round for nothing.
  ```

  Do not add a corresponding `## Criteria` bullet for this — it governs what the reviewer itself may propose, not what to flag in the plan, so it belongs in its own short section (matching the existing "## Source-grounding rule" section's own precedent of a standalone rule section outside `## Criteria`), not the bulleted criteria list.
- **Commit:** `docs(review-plan-holistic): remind reviewer not to suggest an unscoped overview verify: fix`

### Card 6: Fix the doc/enforcement mismatch in the mill-config.yaml template's verify command shape comment

- **Context:**
  - `CLAUDE.md`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the "verify command shape" comment block in `plugins/mill/templates/mill-config.yaml`:

  ```
# ---------------------------------------------------------------------------
# verify command shape (canonical, enforced by _plan_validate.verify-not-isolated)
# ---------------------------------------------------------------------------
# Every non-null verify: in a per-batch plan file's frontmatter MUST start
# with the literal token "PYTHONPATH=" followed by a single space and the
# command. Example:
#     verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
# The empty value on the same line scopes the PYTHONPATH reset to that one
# command, so the test subprocess does not inherit the mill plugin-cache
# scripts dir (set by every mill skill's PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
# invocation pattern). Without this reset, tests load V2-cache modules
# instead of the worktree code they are meant to validate.
# This is schema documentation only -- no key change here; the planner
# bakes the prefix into each per-batch verify: command per mill-plan SKILL.
  ```

  with:

  ```
  # ---------------------------------------------------------------------------
  # verify command shape (canonical, enforced by _plan_validate.verify-not-isolated)
  # ---------------------------------------------------------------------------
  # For Python/mill projects: every non-null verify: in a per-batch plan
  # file's frontmatter MUST start with the literal token "PYTHONPATH="
  # followed by a single space and the command. Example:
  #     verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  # The empty value on the same line scopes the PYTHONPATH reset to that one
  # command, so the test subprocess does not inherit the mill plugin-cache
  # scripts dir (set by every mill skill's PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
  # invocation pattern). Without this reset, tests load V2-cache modules
  # instead of the worktree code they are meant to validate.
  # For non-Python projects (e.g. Go, C#): use the native test runner
  # directly, with no PYTHONPATH= prefix -- there is no cache-shadowing
  # concern for a non-Python test runner.
  # Enforced conditionally: verify-not-isolated only requires the prefix
  # when the project looks like a Python project (root-level pyproject.toml,
  # setup.py, or setup.cfg, or the plugins/mill/pyproject.toml dogfood
  # marker for this repo's own self-hosted layout) -- see
  # _plan_validate._is_python_project. A non-Python project's verify:
  # commands are exempt from this check entirely.
  # This is schema documentation only -- no key change here; the planner
  # bakes the prefix into each per-batch verify: command per mill-plan SKILL,
  # only when the project is a Python project.
  ```

  This mirrors this repo's own `CLAUDE.md` "Verify command shape" section (unchanged by this batch — it already states the same conditional rule correctly) so the template comment and the enforced behavior agree for every future hub seeded from this template.
- **Commit:** `docs(mill-config): state the Python-project gate the PYTHONPATH= rule actually enforces`

## Batch Tests

`verify: null` — this batch touches only prose/prompt/comment text with no executable surface (a skill markdown file, a review-prompt template, and a YAML comment block). Verified by re-reading each edited section for internal consistency (the batch-level vs. overview-level escape-hatch routing agrees between the Phase: Plan escape-hatch paragraph and the Step 1.5 fix-table row; the mill-config.yaml comment matches CLAUDE.md's existing wording) as part of the code-review pass mill-go runs for every batch regardless of `verify:`.
