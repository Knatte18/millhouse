# Plan: 31 (A) — Simple Gemini Flash reviewer

```yaml
task: 31 (A) — Simple Gemini Flash reviewer
slug: gemini-reviewer
approved: false
started: 20260511-120728
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: error-hierarchy-extract
    file: 01-error-hierarchy-extract.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: gemini-llm-provider
    file: 02-gemini-llm-provider.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-gemini.py
  - number: 3
    name: registry-and-smoke
    file: 03-registry-and-smoke.md
    depends-on: [2]
    verify: uv run --project plugins/mill python plugins/mill/integration_tests/smoke-llm-gemini.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
```

## Shared Decisions

### Decision: `LLMError` hierarchy lives in `_llm_common.py`

- **Decision:** `LLMError`, `LLMSessionError`, `LLMRateLimitError` are defined once in `plugins/mill/scripts/_llm_common.py`. Both `_llm_claude.py` and `_llm_gemini.py` re-export the same class objects via `from _llm_common import LLMError, LLMSessionError, LLMRateLimitError` at module top. Callers may `from _llm_<provider> import LLMError` for symmetry; `from _llm_common import LLMError` is the canonical form. `_review_discussion.py`, `_review_plan.py`, `_review_code.py` use the canonical form so `except LLMError` catches errors from any provider.
- **Rationale:** A single class object is the only way `except LLMError as exc:` in review code catches both Claude and Gemini failures. Discussion.md decision `shared-llm-error-hierarchy` is the source of truth.
- **Applies to:** batches 1, 2.

### Decision: Verify commands use `uv run`

- **Decision:** Every batch `verify:` command is of the form `uv run --project plugins/mill python plugins/mill/unit_tests/<test>.py`. Batch 1 uses `run-all.py` (refactor touches the import graph used by many tests); batches 2 and 3 use targeted unit tests for the surface they introduce.
- **Rationale:** Matches the established pattern (44 (A) batches and earlier). `uv run` resolves the right interpreter via `plugins/mill/pyproject.toml`.
- **Applies to:** all batches.

### Decision: Gemini argv flag set is fixed across modes

- **Decision:** `_llm_gemini._build_argv(model, ..., tooluse)` produces argv `[*_gemini_argv_prefix(), "-p", "-o", "stream-json", "-m", model, "--approval-mode", "plan"]` plus `["-e", ""]` when `tooluse=False`. No `--effort`, no `--session-id`, no `--resume` (resume is handled by raising `LLMSessionError` before the spawn). `_gemini_argv_prefix()` returns `["cmd", "/c", "gemini"]` on Windows, `["gemini"]` on POSIX.
- **Rationale:** Locked by discussion.md decisions `bulk-mode-argv`, `tool-use-mode-argv`, `windows-path-wrap`, `session-reuse-not-supported`, `effort-kwarg-accepted-and-ignored`. The implementer does not choose the flag set; the plan does.
- **Applies to:** batch 2.

### Decision: Per-card commit message uses `@git-commit`

- **Decision:** Each card's `Commit:` line is a single conventional-commit subject. The implementer invokes the `@git-commit` skill once per card.
- **Rationale:** Existing mill-go convention. Per-card commits trigger lint + codeguide-update; squashing into batch-level commits loses that signal.
- **Applies to:** all batches.

### Decision: `_reviewer_single.py` requires no edit — dispatch already routes by `provider:`

- **Decision:** `plugins/mill/scripts/_reviewer_single.py` is intentionally absent from `## All Files Touched`. The existing `run(spec, ...)` body reads `spec.get("provider")` and calls `importlib.import_module(f"_llm_{provider}")` — `provider: gemini` already routes to `_llm_gemini.py` (the file batch 2 creates) without any code change in `_reviewer_single.py`. Adding a card to edit it would be a no-op at best and could introduce regressions in the existing `_llm_claude` / `test_stub` paths.
- **Rationale:** Task 34 (`_reviewer_single.py`'s introduction) designed this for exactly this scenario: drop in a new `_llm_<provider>.py` + registry entries and dispatch works. Documenting the load-bearing fact here saves a future maintainer from re-discovering it during the next provider addition.
- **Applies to:** all batches (defines what is intentionally NOT touched).

### Decision: Wiki edits commit on the wiki repo, not the task branch

- **Decision:** Card 5 edits `wiki/reviewers.yaml`, which lives in the wiki repo at `<container>/wiki/`. The implementer commits and pushes that change in the wiki repo by invoking `@mill-wiki-push` (or by running `git -C <wiki-path>` directly). The task branch sees no change from this card. The card's `Commit:` value is the wiki-side commit message.
- **Rationale:** `wiki/reviewers.yaml` is in a separate git repo. The mill-wiki-push skill exists for exactly this case — it acquires the wiki lock, commits, pushes, and handles rebase-on-conflict.
- **Applies to:** batch 3 card 5 only.

## All Files Touched

- `plugins/mill/integration_tests/smoke-llm-gemini.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_llm_common.py`
- `plugins/mill/scripts/_llm_gemini.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/unit_tests/test-llm-gemini.py`
- `wiki/reviewers.yaml`
