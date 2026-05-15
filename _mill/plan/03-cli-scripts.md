# Batch: cli-scripts

```yaml
task: Make implementer model configurable via config.yaml
batch: cli-scripts
number: 3
cards: 4
verify: null
depends-on: [1]
```

## Batch Scope

Updates all three CLI scripts that dispatch implementer sessions (`millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py`) to read `roles.implementer.model` from config, resolve it against the registry via `_reviewers`, and pass `model` + `effort` to `_implementer_claude.run()`. Then deletes `_implementer_sonnet.py` (now unreferenced by any production code). `verify: null` because unit tests still mock the old module name — that is fixed in batch 4.

After this batch:
- All three CLI scripts import `_implementer_claude` (not `_implementer_sonnet`).
- `_implementer_sonnet.py` is deleted.
- The common config-reading pattern is: read `roles.implementer.model` (default `sonnethigh`), call `_reviewers.load(wiki_path)` + `_reviewers.resolve(registry, model_name)`, extract `impl_model` and `impl_effort`.

---

### Card 6: Update `millpy-implement.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Four changes to `millpy-implement.py`:

  1. **Replace import**: change `import _implementer_sonnet` to `import _implementer_claude`. Also add `import _reviewers` to the imports block (alphabetical position among the other `_` imports).

  2. **Add config reading after `timeout` line** (around line 98, after `timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)`):
     ```python
     implementer_cfg = cfg.get("roles", {}).get("implementer", {})
     model_name = implementer_cfg.get("model", "sonnethigh")
     try:
         registry = _reviewers.load(wiki_path)
         impl_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     impl_model = impl_spec["model"]
     impl_effort = impl_spec.get("effort")
     ```

  3. **Replace call site 1** (initial dispatch, around line 176):
     Change `_implementer_sonnet.run(prompt_text, session_id=session_id, resume=False, cwd=project_root, timeout=timeout,)` to:
     ```python
     _implementer_claude.run(
         prompt_text,
         model=impl_model,
         effort=impl_effort,
         session_id=session_id,
         resume=False,
         cwd=project_root,
         timeout=timeout,
     )
     ```

  4. **Replace call site 2** (fix-cycle resume, around line 249):
     Change `_implementer_sonnet.run(prompt_text, session_id=session_id, resume=True, cwd=project_root, timeout=timeout,)` to:
     ```python
     _implementer_claude.run(
         prompt_text,
         model=impl_model,
         effort=impl_effort,
         session_id=session_id,
         resume=True,
         cwd=project_root,
         timeout=timeout,
     )
     ```
- **Commit:** `feat(millpy-implement): read implementer model from config via _reviewers registry`

---

### Card 7: Update `millpy-implement-holistic.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Same four-step pattern as card 6, applied to `millpy-implement-holistic.py`:

  1. Replace `import _implementer_sonnet` → `import _implementer_claude`; add `import _reviewers`.

  2. Add config reading after `timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)` (around line 82):
     ```python
     implementer_cfg = cfg.get("roles", {}).get("implementer", {})
     model_name = implementer_cfg.get("model", "sonnethigh")
     try:
         registry = _reviewers.load(wiki_path)
         impl_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     impl_model = impl_spec["model"]
     impl_effort = impl_spec.get("effort")
     ```

  3. **Replace the single call site** (around line 164):
     Change `_implementer_sonnet.run(prompt_text, session_id=session_id, resume=False, cwd=project_root, timeout=timeout,)` to:
     ```python
     _implementer_claude.run(
         prompt_text,
         model=impl_model,
         effort=impl_effort,
         session_id=session_id,
         resume=False,
         cwd=project_root,
         timeout=timeout,
     )
     ```

  This script has only one call site (unlike `millpy-implement.py` which has two).
- **Commit:** `feat(millpy-implement-holistic): read implementer model from config via _reviewers registry`

---

### Card 8: Update `millpy-merge-in-subagent.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Same four-step pattern as card 6, applied to `millpy-merge-in-subagent.py`. This script has **two** call sites.

  1. Replace `import _implementer_sonnet` → `import _implementer_claude`; add `import _reviewers`.

  2. Add config reading in `main()` after `timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)` (around line 89):
     ```python
     implementer_cfg = cfg.get("roles", {}).get("implementer", {})
     model_name = implementer_cfg.get("model", "sonnethigh")
     try:
         registry = _reviewers.load(wiki_path)
         impl_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     impl_model = impl_spec["model"]
     impl_effort = impl_spec.get("effort")
     ```
     Note: `main()` dispatches to `_run_conflicts()` and `_run_verify_fix()`, passing `cfg` and `timeout`. Also pass `impl_model` and `impl_effort` as additional parameters to both helpers. Update the helper signatures to accept `impl_model: str` and `impl_effort: str | None`.

  3. **Replace call site 1** in `_run_conflicts()` (around line 111): change `_implementer_sonnet.run(...)` to `_implementer_claude.run(..., model=impl_model, effort=impl_effort, ...)`.

  4. **Replace call site 2** in `_run_verify_fix()` (around line 172): same replacement.

  Ensure `impl_model` and `impl_effort` are threaded through to both helper functions via their parameter lists (they cannot be read from globals).
- **Commit:** `feat(millpy-merge-in-subagent): read implementer model from config via _reviewers registry`

---

### Card 9: Delete `_implementer_sonnet.py`

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_implementer_sonnet.py`
- **Requirements:**
  Delete `plugins/mill/scripts/_implementer_sonnet.py`. Before deleting, verify (via grep) that no file in `plugins/mill/scripts/` or `plugins/mill/unit_tests/` still has `import _implementer_sonnet` or `from _implementer_sonnet` at module level. Unit tests mock it via `patch.object(module._implementer_sonnet, ...)` — those patches will break (AttributeError) until batch 4 updates the mock targets; this is expected and is why `verify: null` for this batch.
- **Commit:** `chore: delete _implementer_sonnet.py (replaced by _implementer_claude.py)`

## Batch Tests

`verify: null` — unit tests reference `_implementer_sonnet` as a mock target and will fail until batch 4 updates them. The production code is correct after this batch; test correctness is verified in batch 4.
