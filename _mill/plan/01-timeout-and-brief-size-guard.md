# Batch: timeout-and-brief-size-guard

```yaml
task: haiku-4-5 implementer reliability (hang + path mangle)
batch: timeout-and-brief-size-guard
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-llm-claude.py
depends-on: []
```

## Batch Scope

Adds two hang-mitigation mechanisms: (a) per-reviewer timeout override via a new optional `timeout:` field in `mill-agents.yaml`, so haiku gets 600s instead of 1800s; (b) a brief-size guard in both `millpy-implement.py` and `millpy-fix.py` that emits `stuck/transient` before the LLM call when the rendered prompt exceeds `llm.max_implementer_prompt_chars`. Also adds `max_implementer_prompt_chars: 0` to both hub `mill-config.yaml` and the plugin template to keep them in sync. No changes to the LLM layer (`_llm_claude.py`, `_subprocess_util.py`).

## Cards

### Card 1: Add timeout: 600 to haiku in mill-agents.yaml

- **Context:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-agents.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add a `timeout: 600` field to the `haiku:` entry in `plugins/mill/templates/mill-agents.yaml`. The existing haiku entry is:
  ```yaml
  haiku:
    model: claude-haiku-4-5-20251001
    provider: claude
    type: single
  ```
  After the change it must be:
  ```yaml
  haiku:
    model: claude-haiku-4-5-20251001
    provider: claude
    timeout: 600
    type: single
  ```
  (Fields in alphabetical order per the existing file convention.) No other entries in the file are changed. The `timeout` field is intentionally absent from all other entries — agents without it fall back to `llm.implementer_timeout`.
- **Commit:** `feat(agents): add timeout: 600 to haiku agent spec`

### Card 2: Add max_implementer_prompt_chars: 0 to both config files

- **Context:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `max_implementer_prompt_chars: 0` to the `llm:` block in both files. In both files, the `llm:` block currently contains `implementer_timeout: 1800` and the `claude:` sub-block. Add the new key on the line immediately after `implementer_timeout: 1800`:
  ```yaml
  llm:
    implementer_timeout: 1800
    max_implementer_prompt_chars: 0
    claude:
      ...
  ```
  The value `0` means the guard is disabled by default. Both files must receive the identical key-value pair (CLAUDE.md: hub file and plugin template must stay in sync). No other changes to either file.
- **Commit:** `feat(config): add max_implementer_prompt_chars: 0 to llm block`

### Card 3: Per-reviewer timeout + brief-size guard in millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_reviewers.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Two changes to `millpy-implement.py`, both in `main()`:

  1. **Timeout override.** The current code reads:
     ```python
     self_fix_rounds = cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)
     timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
     implementer_cfg = cfg.get("roles", {}).get("implementer", {})
     model_name = implementer_cfg.get("model", "sonnethigh")
     try:
         registry = _reviewers.load(git_root)
         impl_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     impl_model = impl_spec["model"]
     impl_effort = impl_spec.get("effort")
     ```
     Change so that `timeout` is read AFTER `impl_spec` is resolved:
     ```python
     self_fix_rounds = cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)
     implementer_cfg = cfg.get("roles", {}).get("implementer", {})
     model_name = implementer_cfg.get("model", "sonnethigh")
     try:
         registry = _reviewers.load(git_root)
         impl_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     impl_model = impl_spec["model"]
     impl_effort = impl_spec.get("effort")
     timeout = impl_spec.get("timeout") or cfg.get("llm", {}).get("implementer_timeout", 1800)
     ```
     The `timeout =` line moves from before the try-block to after `impl_effort`.

  2. **Brief-size guard.** After the existing `prompt_text = _render.render(...)` call (and before the `try: output, _ = _implementer_claude.run(...)` call), insert:
     ```python
     max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)
     if max_chars > 0 and len(prompt_text) > max_chars:
         print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": f"brief exceeds max_implementer_prompt_chars ({len(prompt_text)} chars)"}))
         return 0
     ```
     The `json` module is already imported at the top of the file.

  No other changes to this file.
- **Commit:** `feat(implement): per-reviewer timeout + brief-size guard`

### Card 4: Per-reviewer timeout + brief-size guard in millpy-fix.py

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Two changes to `millpy-fix.py`, both in `main()`:

  1. **Timeout override.** The current code reads (around line 130):
     ```python
     timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
     fixer_cfg = cfg.get("roles", {}).get("fixer", {})
     model_name = fixer_cfg.get("model", "haiku")
     try:
         registry = _reviewers.load(git_root)
         fixer_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     fixer_model = fixer_spec["model"]
     fixer_effort = fixer_spec.get("effort")
     ```
     Change so that `timeout` is read AFTER `fixer_spec` is resolved:
     ```python
     fixer_cfg = cfg.get("roles", {}).get("fixer", {})
     model_name = fixer_cfg.get("model", "haiku")
     try:
         registry = _reviewers.load(git_root)
         fixer_spec = _reviewers.resolve(registry, model_name)
     except _reviewers.ReviewerError as e:
         print(str(e), file=sys.stderr)
         return 1
     fixer_model = fixer_spec["model"]
     fixer_effort = fixer_spec.get("effort")
     timeout = fixer_spec.get("timeout") or cfg.get("llm", {}).get("implementer_timeout", 1800)
     ```
     Remove the original `timeout =` line at the top; add the new line after `fixer_effort`.

  2. **Brief-size guard.** Both the `batch` and `holistic` branches in `main()` set `prompt_text` via `_render.render(...)`. The shared dispatch tail then calls `_implementer_claude.run(prompt_text, ...)`. Insert the guard in the shared dispatch tail, AFTER both branches have set `prompt_text` and BEFORE the `try: output, _ = _implementer_claude.run(...)` call:
     ```python
     max_chars = cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)
     if max_chars > 0 and len(prompt_text) > max_chars:
         print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": f"brief exceeds max_implementer_prompt_chars ({len(prompt_text)} chars)"}))
         return 0
     ```
     The `json` module is already imported at the top of `millpy-fix.py`.

  No other changes to this file.
- **Commit:** `feat(fix): per-reviewer timeout + brief-size guard`

## Batch Tests

Verify runs `test-millpy-implement.py` (existing tests for `millpy-implement.py` main logic and `_forward_output`) and `test-llm-claude.py` (argv construction, stream-json parsing). The new brief-size guard tests are in batch 3 — this verify is a regression check only. All 8 `TestMillpyImplement` + 8 `TestForwardOutput` + all `test-llm-claude.py` cases must still pass.
