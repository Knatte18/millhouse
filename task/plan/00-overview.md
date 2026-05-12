# Plan: (A) — Add /mill-fold skill with active-task guard

```yaml
task: (A) — Add /mill-fold skill with active-task guard
slug: mill-fold
approved: false
started: 20260512-171727
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: helpers
    file: 01-helpers.md
    depends-on: []
    verify: c:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe c:/Code/millhouse/wts/millhouse/plugins/mill/unit_tests/run-all.py
  - number: 2
    name: cli-script
    file: 02-cli-script.md
    depends-on: [1]
    verify: c:/Code/millhouse/wts/millhouse/plugins/mill/.venv/Scripts/python.exe c:/Code/millhouse/wts/millhouse/plugins/mill/unit_tests/run-all.py
  - number: 3
    name: skills-and-docs
    file: 03-skills-and-docs.md
    depends-on: [2]
    verify: null
```

## Shared Decisions

### Decision: invocation-form-for-scripts

- **Decision:** Mill scripts are invoked via the cache venv's Python binary directly (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" …`). Source-tree form (`uv run --project plugins/mill plugins/mill/scripts/millpy-fold.py …`) is reserved for unit tests run from inside the millhouse repo.
- **Rationale:** External repos use the plugin without a millhouse source checkout. SKILL.md examples must work against the cache. This rule is already documented in project CLAUDE.md under `## Conventions worth carrying`.
- **Applies to:** all batches.

### Decision: locked-fold-phases-tuple

- **Decision:** `_tasks_md.LOCKED_FOLD_PHASES = ("active", "ready-to-merge", "pr-pending")`. This module-level constant is the **only** source of truth for which Home.md phases reject a fold operation. Both `millpy-fold.py` and `mill-ghissues-to-tasks/SKILL.md` (via Python invocations the skill prose describes) import this tuple — no skill or script duplicates the literal phase names.
- **Rationale:** A second copy of the tuple drifts the moment one call-site is updated and the other lags. The `test_locked_fold_phases_constant` test in `test-fold.py` asserts the tuple's value verbatim so a silent edit fails CI.
- **Applies to:** batches 1, 2, 3.

### Decision: close-comment-strings

- **Decision:** Two close-comment strings are used in the v2 fold subsystem:
  - **Fold-in (single-source):** `"Folded into wiki task: <slug>"` — used by `millpy-fold.py` (GH path) and by `mill-ghissues-to-tasks`'s fold-in branch after the retrofit.
  - **New-task (multi-source consolidation):** `"Consolidated into wiki task: <slug>"` — kept verbatim for the new-task branch of `mill-ghissues-to-tasks`.
- **Rationale:** "Fold-in" semantically matches the skill name and the `- Sources: #N — <title>` Home.md bullet; "consolidated" remains accurate when several issues collapse into one new task. The retrofit splits `mill-ghissues-to-tasks` Step 5's single `close_with_comment` call into a per-decision branch.
- **Applies to:** batches 2, 3.

### Decision: fold-operation-order

- **Decision:** Inside `millpy-fold.py`, the operation order is fixed: `lock → parse → phase-guard → fetch_one (GH path only) → body-append → sidebar regen → commit/push → optional GH close-with-comment → release`. The GH `close_with_comment` runs **after** `_wiki.write_commit_push` returns successfully, never before.
- **Rationale:** Mirrors the load-bearing `mill-ghissues-to-tasks` invariant "Close only on approval + actual write — never close an issue before the task is committed to Home.md". If the wiki commit fails, the issue stays OPEN so a re-run can retry without orphaning provenance.
- **Applies to:** batch 2.

### Decision: test-injection-seams

- **Decision:** `millpy-fold.py main(...)` accepts two keyword-only test seams: `_fetch_one: Callable | None = None` and `_close_with_comment: Callable | None = None`. When `None` (production) the script imports and calls `_gh_issues.fetch_one` and `_gh_issues.close_with_comment`. When supplied (tests) the script uses the injected callables. Unit tests use these to exercise the GH path without invoking `gh`.
- **Rationale:** Discussion's "no real `gh`" rule for tests. Keeps the production wiring unchanged and avoids monkey-patching `sys.modules`. Same pattern in spirit as `_gh_issues._render_body_with_comments` being a private free function — the seam is the dependency, not the module.
- **Applies to:** batch 2.

### Decision: yaml-bound-token-quoting

- **Decision:** The plan files themselves were rendered with `_yaml_writer.quote_scalar` applied to every token whose substitution lands in a fenced yaml block. Implementer cards do NOT touch the rendered plan tokens. This decision is informational — implementer authors of new scripts that themselves render YAML templates must follow the same rule (`_render.render(template, {"K": quote_scalar(v)})`).
- **Rationale:** mill-plan SKILL.md `Pre-quote YAML-bound tokens` rule. None of the cards in this plan render YAML themselves, so no card needs to call `quote_scalar`.
- **Applies to:** documentation only.

## All Files Touched

- `CLAUDE.md`
- `SKILLS.md`
- `plugins/mill/scripts/_gh_issues.py`
- `plugins/mill/scripts/_tasks_md.py`
- `plugins/mill/scripts/millpy-fold.py`
- `plugins/mill/skills/mill-fold/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/unit_tests/test-fold.py`
