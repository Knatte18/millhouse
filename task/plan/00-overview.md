# Plan: 39 (A) — mill-start question-format UX

```yaml
task: 39 (A) — mill-start question-format UX
slug: mill-start-question-ux
approved: true
started: 20260509-104703
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: skill-text-rules
    file: 01-skill-text-rules.md
    depends-on: []
    verify: null
  - number: 2
    name: inplace-reorder
    file: 02-inplace-reorder.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: subprocess-popup-fix
    file: 03-subprocess-popup-fix.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: recommended-option-is-position-1

- **Decision:** Whenever a SKILL.md, helper, or script presents a numbered choice list, the option tagged `(Recommended)` MUST be option 1. When a heuristic or condition decides which option is recommended, the menu reorders so the recommended option lands at position 1; remaining options keep their relative order.
- **Rationale:** Lets users pick "1" without reading every option. Aligned with the global rule that `conversation/SKILL.md` will declare in batch 1.
- **Applies to:** all batches.

### Decision: subprocess-routing-via-_subprocess_util

- **Decision:** All non-interactive subprocess invocations under `plugins/mill/scripts/` go through `_subprocess_util.run` or `_subprocess_util.popen_detached`. Interactive launchers (`millpy-terminal.py`, `millpy-vscode.py`) are exempt and keep their bare `subprocess.run` calls with a one-line code comment marking the exemption.
- **Rationale:** Centralised flag handling (`CREATE_NO_WINDOW` on Windows + UTF-8 env injection + breadcrumbs) eliminates the popup-flash drift that emerged when individual call sites bypassed the helper.
- **Applies to:** subprocess-popup-fix.

### Decision: tests-import-modules-directly

- **Decision:** Unit tests under `plugins/mill/unit_tests/` import the helper module directly and patch attributes on the helper module, not on the global `subprocess` module. When a script that previously called `subprocess.run` directly is refactored to call `_subprocess_util.run`, the test's `patch.object(<module>, "subprocess", "run")` target is updated to `patch.object(<module>, "_subprocess_util", "run")` (or `popen_detached`).
- **Rationale:** Existing test conventions; keeps unit tests offline and deterministic. Refactoring without updating patch targets would cause silent test passes against an un-mocked real subprocess.
- **Applies to:** subprocess-popup-fix.

### Decision: no-new-tests-for-skill-md-text

- **Decision:** Pure SKILL.md text changes (rule wording, batch caps, menu-reorder instructions) do not get unit tests. The change is reviewed by reading the file. Existing helper tests (`test-inplace.py`, etc.) are updated only when the underlying code mapping changes.
- **Rationale:** SKILL.md is human-readable instruction text consumed by Claude at runtime; no machine-checkable invariant to assert. Adding tests for text content would be brittle and high-maintenance.
- **Applies to:** skill-text-rules.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_inplace.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/scripts/millpy-bg.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-skills-index.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/conversation/SKILL.md`
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- `plugins/mill/skills/mill-groom/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-inplace.py`
- `plugins/mill/unit_tests/test-millpy-bg.py`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-subprocess-util.py`
