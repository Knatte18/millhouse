# Batch: core-modules

```yaml
task: Make implementer model configurable via config.yaml
batch: core-modules
number: 1
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Creates `_implementer_claude.py` (the provider-named, model-agnostic replacement for `_implementer_sonnet.py`); updates `_reviewers.py` to load from `agents.yaml` with a `reviewers.yaml` fallback and to validate the `roles.implementer.model` config ref; updates `_test_registry.py` to write `agents.yaml` instead of `reviewers.yaml`. After this batch `_implementer_sonnet.py` still exists — it is not yet deleted (that happens in batch 3). The next batches (2 and 3) consume `_implementer_claude` and the updated `_reviewers.load()` API.

Verify runs the full unit test suite. All existing tests pass because: (a) CLI scripts still import `_implementer_sonnet` (not yet changed); (b) tests that call `_test_registry.write_to()` now write `agents.yaml`, and `_reviewers.load()` finds it; (c) tests that write `reviewers.yaml` directly trigger the backward-compat fallback and still pass.

---

### Card 1: Create `_implementer_claude.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_implementer_claude.py`
- **Deletes:** none
- **Requirements:**
  Create `plugins/mill/scripts/_implementer_claude.py` with the following content (mirrors `_implementer_sonnet.py` with these changes):

  - Module docstring: update to say "model-agnostic Claude implementer" and remove the "Sonnet" reference. Keep the `Public API` block but reflect that `model` and `effort` are now caller-supplied.
  - `MODE = "implementer"` — unchanged.
  - `run()` signature: `model: str` and `effort: str | None` are both **required** keyword-only parameters with no default values. The full signature is:
    ```python
    def run(
        prompt_text: str,
        *,
        model: str,
        effort: str | None,
        session_id: str | None = None,
        resume: bool = False,
        cwd: Path | str | None = None,
        timeout: int = 1800,
    ) -> tuple[str, str]:
        return run_implementer(
            prompt_text,
            model=model,
            effort=effort,
            session_id=session_id,
            resume=resume,
            cwd=cwd,
            timeout=timeout,
        )
    ```
  - Imports: `from pathlib import Path` and `from _llm_claude import run_implementer` — same as current `_implementer_sonnet.py`.
  - Do NOT delete `_implementer_sonnet.py` in this card.
- **Commit:** `feat(_implementer_claude): add provider-named model-agnostic implementer module`

---

### Card 2: Update `_reviewers.py` — `load()` path and `validate_role_refs` extension

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Two independent changes to `_reviewers.py`:

  **Change A — `load()` path (around line 45):**
  Replace:
  ```python
  path = wiki_root / "reviewers.yaml"
  if not path.exists():
      raise ReviewerError(f"Missing registry at {path}")
  ```
  With:
  ```python
  path = wiki_root / "agents.yaml"
  if not path.exists():
      path = wiki_root / "reviewers.yaml"
  if not path.exists():
      raise ReviewerError(f"Missing registry at {wiki_root / 'agents.yaml'}")
  ```
  The error message always names `agents.yaml` (the canonical name) even when the fallback was tried and failed. The rest of `load()` is unchanged — `path` is still the variable used for `path.read_text(...)`.

  **Change B — `validate_role_refs()` extension (at end of function, before `if errors: raise`):**
  After the existing `for role, role_cfg in cfg.get("roles", {}).items():` loop closes, add:
  ```python
  impl_model = cfg.get("roles", {}).get("implementer", {}).get("model")
  if impl_model is not None:
      try:
          resolve(registry, impl_model)
      except ReviewerError as exc:
          errors.append(f"roles.implementer.model={impl_model!r}: {exc}")
  ```
  This must be inserted before `if errors:` (not after it).
- **Commit:** `feat(_reviewers): load agents.yaml with reviewers.yaml fallback; validate implementer model ref`

---

### Card 3: Update `_test_registry.py` — `write_to()` writes `agents.yaml`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_test_registry.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `write_to()`, change the output path from `wiki_root / "reviewers.yaml"` to `wiki_root / "agents.yaml"`. Also update the function's docstring to reference `wiki_root/agents.yaml` instead of `wiki_root/reviewers.yaml`. The `make_minimal_registry()` function and the `_deep_merge` helper are unchanged.
- **Commit:** `fix(_test_registry): write agents.yaml instead of reviewers.yaml`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — runs the full suite. All existing tests are expected to pass: `_test_registry.write_to()` now writes `agents.yaml`, which `_reviewers.load()` finds first; tests that write directly to `wiki_root / "reviewers.yaml"` trigger the backward-compat fallback and also pass.
