# Batch: Python comment fixes

```yaml
task: Audit and clean up stale V2 references
batch: Python comment fixes
number: 5
cards: 4
verify: "PYTHONPATH= bash -c \"! grep -rq '_wiki[.]' plugins/mill/skills/ && ! grep -rq '_tasks_md[.]' plugins/mill/skills/ && ! grep -rqE 'v2 shape|v2.s contract|valid v2 task|v2.s Home' plugins/mill/scripts/ plugins/mill/integration_tests/\""
depends-on: [1, 2, 3, 4]
```

## Batch Scope

Four Python source files with stale "v2" references in comments or docstrings only — no logic impact. This batch runs last (depends-on all SKILL.md batches) so its verify command can run the three global acceptance greps that confirm the entire task is complete.

## Cards

### Card 16: millpy-add.py — remove "v2" from slug validator docstring

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-add.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Line 43: change the docstring of `_validate_slug` from `"""Reject anything that is not a valid v2 task slug."""` to `"""Reject anything that is not a valid task slug."""`
- **Commit:** `docs(millpy-add): remove stale v2 reference in _validate_slug docstring`

### Card 17: millpy-spawn.py — remove stale V2 comment

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Lines 238–240: the current comment reads:
  ```python
  # Render and write the initial status.md. v2's Home.md has no
  # dedicated description column; use the task title as description so
  # the template renders without empty placeholders.
  ```
  Replace with:
  ```python
  # Use the task title as description so the status.md template renders without empty placeholders.
  ```
- **Commit:** `docs(millpy-spawn): remove stale v2 Home.md comment`

### Card 18: _worktree.py — remove "v2's contract" from docstring

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Line 86: change `in dst are overwritten — v2's contract is that mill-spawn owns` to `in dst are overwritten — mill-spawn owns`
- **Commit:** `docs(_worktree): remove stale v2 reference in docstring`

### Card 19: test-plan-assets.py — remove "v2 shape" from comment

- **Context:** none
- **Edits:**
  - `plugins/mill/integration_tests/test-plan-assets.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Lines 15–18: the current comment reads (paraphrased):
  ```
  - ``_review_plan._load_root_from_overview`` reads the ``root:``
    field from the fenced-yaml frontmatter (the v2 shape) — the
    function used to only understand ``---`` frontmatter, which would
    silently drop ``root:`` on every v2 plan.
  ```
  Replace with:
  ```
  - ``_review_plan._load_root_from_overview`` reads the ``root:``
    field from the fenced-yaml frontmatter — the function used to only
    understand ``---`` frontmatter, which would silently drop ``root:``.
  ```
  (Remove both "the v2 shape" and "on every v2 plan" references.)
- **Commit:** `docs(test-plan-assets): remove stale v2 shape reference in comment`

## Batch Tests

All four files are Python source files with comment-only changes. The verify command runs the three global acceptance greps:
1. `grep -rq '_wiki[.]' plugins/mill/skills/` — zero hits expected
2. `grep -rq '_tasks_md[.]' plugins/mill/skills/` — zero hits expected
3. `grep -rqE 'v2 shape|v2.s contract|valid v2 task|v2.s Home' plugins/mill/scripts/ plugins/mill/integration_tests/` — zero hits expected

All three must pass (exit code 1 from grep, inverted to 0 by `!`) for the batch verify to succeed.
