# Batch: templates-skills-fixtures

```yaml
task: 'status.md: rename parent to parent_branch, add parent_thread'
batch: templates-skills-fixtures
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-abandon.py test-agent-mode-dispatch.py test-millpy-fix.py test-millpy-implement.py test-millpy-merge-in-subagent.py test-cleanup.py
depends-on: [1]
```

## Batch Scope

Brings the remaining `parent:` mentions in line with batch 1's key rename: the `discussion.md` and `plan-overview.md` template yaml rows, the skill prose that names the row, the skill call sites that rebind it (switching from `_status.update_field(status_path, "parent", ...)` to batch 1's `_status.set_parent_branch`), and the hand-written status.md fixtures in other tests.
Fixtures that deliberately exercise the legacy fallback stay on `parent:` per Shared Decision `fixture-migration-policy`.
Lines that use "parent" in ordinary English ("on the parent:", "treat child and parent as branches", the parent-worktree error text) are not the key and stay unchanged.

## Cards

### Card 8: discussion and plan-overview templates use parent_branch

- **Context:**
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/templates/discussion.md`
  - `plugins/mill/templates/plan-overview.md`
  - `plugins/mill/integration_tests/test-plan-assets.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In both templates, change the fenced-yaml row `parent: <PARENT_BRANCH>` to `parent_branch: <PARENT_BRANCH>`.
    The `<PARENT_BRANCH>` token name is unchanged.
  - In `test-plan-assets.py`, change `test_overview_template_renders`'s assertion `"parent: main" in rendered` to `"parent_branch: main" in rendered` (message text `"parent_branch yaml not substituted"`), and change the `'parent: main\n'` row of `test_plan_dag_accepts_minimal_plan`'s hand-written overview fixture to `'parent_branch: main\n'`.
    This file is not run by `verify:` (see Shared Decision `integration-tests-excluded-from-verify`).
- **Commit:** `refactor(templates): rename parent yaml row to parent_branch`

### Card 9: mill-merge and mill-merge-in rebind via set_parent_branch

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `mill-merge/SKILL.md` Entry Step 4:
    in the paragraph that branches on `status_path.exists()`, change "the `parent:` row is missing" to "the `parent_branch:` row (or legacy `parent:` row) is missing";
    in the "Liveness check (#817)" confirmation text, change "rebind `status.md`'s `parent:` row" to "rebind `status.md`'s `parent_branch:` row";
    in the rebind bash snippet, replace `_status.update_field(status_path, 'parent', '<resolved_branch>')` with `_status.set_parent_branch(status_path, '<resolved_branch>')` and add one sentence after the snippet: `set_parent_branch` rewrites `parent_branch:` or migrates a legacy `parent:` row in place;
    in the `ParentBranchError` paragraph, change "(status.md is missing the `parent:` row)" to name `parent_branch:`, the `set_blocked` reason to `f"missing parent_branch: row for {slug}"`, the commit message to `"mill-merge: blocked (missing parent_branch: row) for {slug}"`, and the halt text to `BLOCKED: status.md is missing the parent_branch: row for <slug> -- mill-spawn should have written it; set it manually and re-run /mill-merge.`
  - `mill-merge-in/SKILL.md` Entry:
    step 2's hoist sentence, replace `_status.update_field(status_path, "parent", resolved_branch)` with `_status.set_parent_branch(status_path, resolved_branch)`;
    step 3's "**Source of truth is `_mill/status.md`'s `parent:` row**" becomes "`parent_branch:` row (legacy `parent:` accepted)";
    the `status_path.exists()` True sub-case, change "rebind `status.md`'s `parent:` row via `_status.update_field(status_path, "parent", resolved_branch)`" to "rebind `status.md`'s `parent_branch:` row via `_status.set_parent_branch(status_path, resolved_branch)`".
  - After editing, `grep -n 'update_field(status_path, .parent' ` over both files returns nothing.
- **Commit:** `docs(merge): rebind parent_branch via set_parent_branch`

### Card 10: mill-go-base, mill-finalize and mill-start name parent_branch

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `mill-go-base/SKILL.md` and `mill-go-base/handoff.md`: in each dead-parent auto-rebind bullet (the `outcome` is `"resolved"` bullet), replace `_status.update_field(status_path, "parent", resolved_branch)` with `_status.set_parent_branch(status_path, resolved_branch)`.
    Nothing else in those bullets changes.
  - `mill-finalize/SKILL.md`: in the `parent_branch = _parent_branch.resolve(...)` bullet, change "reads `parent:` from status.md" to "reads `parent_branch:` (legacy `parent:` accepted) from status.md".
  - `mill-start/SKILL.md` Phase: Active: change "Verify it exists and the `parent:` branch is recorded." to "Verify it exists and the parent branch is recorded as `parent_branch:` (or legacy `parent:`)."
  - `mill-start/SKILL.md` Phase: Discussion File: change the render sentence so `<PARENT_BRANCH>` is read via `_status.read_parent_branch(status_path)` while `<TASK_TITLE>` and `<SLUG>` still come from `status_path`.
  - After editing, `grep -rn 'update_field(status_path, .parent' ` over the `mill-go-base` skill directory returns nothing.
- **Commit:** `docs(skills): name parent_branch row and rebind via set_parent_branch`

### Card 11: unit-test status fixtures move to parent_branch

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In each edited file, change every hand-written status.md yaml row `parent: main` to `parent_branch: main`, whether it sits in a standalone `"parent: main\n"` string or inside a one-line fixture such as `"```yaml\nslug: test-slug\nparent: main\n```\n"` or `"```yaml\nparent: main\n```\n"`.
  - In `test-cleanup.py`, change `_make_status_md`'s row `f"parent: {parent}\n"` to `f"parent_branch: {parent}\n"`, and in the `read_parent_branch` absent-key case change the comment and `PASS`/assert message text "absent parent: key" to "absent parent_branch: key".
  - Do not touch lines where "parent" is a git branch name or ordinary English, e.g. `test-cleanliness.py`'s `"parent"` branch is not involved.
  - `grep -n 'parent: ' ` over the six edited files afterwards shows no remaining status.md yaml row using the legacy key.
- **Commit:** `test: move hand-written status.md fixtures to parent_branch`

### Card 12: integration-test fixtures move to parent_branch, legacy kept where it is the point

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/integration_tests/test-go-assets.py`
  - `plugins/mill/integration_tests/test-baseline-waiver.py`
  - `plugins/mill/integration_tests/test-agent-mode-commit-target.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `test-go-assets.py`, `test-baseline-waiver.py`, `test-agent-mode-commit-target.py`: change every `"parent: main\n"` fixture row to `"parent_branch: main\n"`.
  - `test-merge.py`: change to `parent_branch: main` exactly these fixtures:
    the `Demo merge` plan overview (`task: Demo merge` / `approved: true` block),
    the `Demo merge` status.md (`phase: done` / `task: Demo merge`),
    and the `Nested verify-cwd` plan overview (`slug: nested-verify-cwd`).
  - `test-merge.py`: keep legacy `parent:` in the `Other task` status.md, the `Nested merge` child status.md (`parent: parent-feature`), the foreign `other-task` status.md in the slug-mismatch sub-scenario, and the archived `Parent task` and `Legacy task` status.md fixtures.
    Add a one-line comment above the `Nested merge` fixture and above the `Parent task` fixture stating the legacy `parent:` key is deliberate (fallback coverage for in-flight worktrees / archived status.md).
  - These files are not run by `verify:` (see Shared Decision `integration-tests-excluded-from-verify`).
- **Commit:** `test(integration): move status fixtures to parent_branch, keep legacy fallback cases`

## Batch Tests

`verify:` runs the six unit-test files card 11 edits, all of which read status.md through `_status` / `_parent_branch` and so exercise batch 1's `parent_branch:` readers on the migrated fixtures.
Cards 8, 9, 10 and 12 edit markdown and integration tests only; no unit test covers them (integration tests excluded per Shared Decision `integration-tests-excluded-from-verify`).
