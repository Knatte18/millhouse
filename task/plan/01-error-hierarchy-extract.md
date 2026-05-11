# Batch: error-hierarchy-extract

```yaml
task: 31 (A) — Simple Gemini Flash reviewer
batch: error-hierarchy-extract
number: 1
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Extract the LLM exception hierarchy (`LLMError`, `LLMSessionError`, `LLMRateLimitError`) from `_llm_claude.py` into a new neutral module `_llm_common.py`, then make `_llm_claude.py` re-export the same class objects so its public surface is unchanged. Update the three `_review_*.py` modules to import `LLMError` from `_llm_common` instead of `_llm_claude` so a future `_llm_gemini.py` (built in batch 2) can raise the same class objects and still be caught by existing `except LLMError` patterns. Pure refactor — no behaviour change, all existing unit tests must continue to pass.

External interface batch 2 will consume: `from _llm_common import LLMError, LLMSessionError, LLMRateLimitError`.

## Cards

### Card 1: Create `_llm_common.py` and re-export from `_llm_claude.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:**
  - `plugins/mill/scripts/_llm_common.py`
- **Deletes:** none
- **Requirements:**
  1. Create new file `plugins/mill/scripts/_llm_common.py` containing exactly three exception classes plus a module docstring. The class bodies (docstrings) MUST be copied verbatim from the current `_llm_claude.py` so the public class docstring text does not change:
     - `class LLMError(Exception):` with the docstring `"""Raised on timeout, auth failure, or non-zero exit from claude CLI.\n\nCallers use str(exc) to get a human-readable error message. Backends\ncatch LLMError at the per-sub-review boundary and record\n{verdict: "ERROR", file: null, error: "<msg>"} in the ReviewResult.\n"""` — the docstring text references the claude CLI by name because it documents the original origin; rewrite it to be provider-neutral: `"""Raised on timeout, auth failure, or non-zero exit from an LLM-provider CLI.\n\nCallers use str(exc) to get a human-readable error message. Backends\ncatch LLMError at the per-sub-review boundary and record\n{verdict: "ERROR", file: null, error: "<msg>"} in the ReviewResult.\n"""`.
     - `class LLMSessionError(LLMError):` with provider-neutralized docstring: `"""Raised when an LLM-provider's `--resume <id>` call fails because the session is gone.\n\nCallers (mill-go's builder) catch this specifically to fall back to a\nfresh session instead of aborting the batch.\n"""`.
     - `class LLMRateLimitError(LLMError):` with provider-neutralized docstring: `"""Raised when an LLM-provider CLI exits non-zero AND its output indicates a rate-limit/throttle event.\n\nBackends record verdict: ERROR with error: 'rate_limit: ...' and the orchestrator's\nERROR-only retry handles it. Inherits from LLMError so existing catch sites continue\nto handle it as a generic provider failure unless they specifically want the typed split.\n"""`.
  2. Module docstring of `_llm_common.py`: a single short paragraph: `"""Shared LLM-provider exception hierarchy.\n\nDefined here (not inside any specific `_llm_<provider>` module) so callers\ncan catch errors from any provider with a single `except LLMError` clause.\nEach provider module re-exports these classes via\n`from _llm_common import LLMError, LLMSessionError, LLMRateLimitError`.\n"""`.
  3. The new file uses `from __future__ import annotations` at the top to match the codebase style. No other imports.
  4. In `plugins/mill/scripts/_llm_claude.py`, delete the existing `LLMError`, `LLMSessionError`, `LLMRateLimitError` class definitions (the three `class ...(...): """..."""` blocks between the `# Exceptions` header and the next `# Internal helpers` header). Replace them with a single import line at module top, placed immediately after the existing `import _subprocess_util` statement: `from _llm_common import LLMError, LLMSessionError, LLMRateLimitError`. Keep the `# Exceptions` header comment block intact but the body underneath becomes only a one-line comment: `# Re-exported from _llm_common — see that module for the class definitions.`.
  5. Do NOT remove any other public symbol from `_llm_claude.py`. `_build_argv`, `_scan_rate_limit`, `_parse_stream_json`, `_invoke`, `run_bulk`, `run_tool_use`, `run_implementer`, `_claude_argv_prefix` all stay verbatim. After the edit, `from _llm_claude import LLMError, LLMSessionError, LLMRateLimitError` must still succeed and return the same class objects as `from _llm_common import ...` (i.e. the names refer to the same object, verified by `_llm_claude.LLMError is _llm_common.LLMError`).
- **Commit:** `refactor(_llm_common): extract LLMError hierarchy from _llm_claude`

### Card 2: Update `_review_*.py` imports to `_llm_common`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `plugins/mill/scripts/_review_discussion.py`, replace the line `from _llm_claude import LLMError` with `from _llm_common import LLMError`. Exact one-line substitution; no other change to the file.
  2. In `plugins/mill/scripts/_review_plan.py`, replace the line `from _llm_claude import LLMError` with `from _llm_common import LLMError`. Exact one-line substitution; no other change to the file.
  3. In `plugins/mill/scripts/_review_code.py`, replace the line `from _llm_claude import LLMError` with `from _llm_common import LLMError`. Exact one-line substitution; no other change to the file.
  4. Do NOT change any `except LLMError` clause, any other import, or any function body in these three files. The semantic guarantee is that `LLMError` refers to the same class object before and after the edit (because card 1 made `_llm_claude.LLMError` a re-export of `_llm_common.LLMError`).
- **Commit:** `refactor(_review): import LLMError from _llm_common`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The refactor touches the import graph used by `test-llm-claude.py`, `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`, and any other test that imports the affected modules — run the full unit-test suite to verify no regression. `test-llm-claude.py` explicitly imports `LLMError`, `LLMSessionError`, `LLMRateLimitError` from `_llm_claude` and asserts hierarchy/instance behaviour; that assertion passes because the re-exported classes are the same objects defined in `_llm_common`.
