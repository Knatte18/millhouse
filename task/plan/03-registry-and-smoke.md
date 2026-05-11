# Batch: registry-and-smoke

```yaml
task: 31 (A) — Simple Gemini Flash reviewer
batch: registry-and-smoke
number: 3
cards: 2
verify: uv run --project plugins/mill python plugins/mill/integration_tests/smoke-llm-gemini.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
depends-on: [2]
```

## Batch Scope

Wire the new `_llm_gemini.py` (built in batch 2) into the reviewer registry by appending two entries (`gemini_flash`, `gemini_flash_tool`) to `wiki/reviewers.yaml`, then write the integration smoke test `smoke-llm-gemini.py` that exercises the live `gemini` CLI for both bulk and tool-use modes plus the `resume=True → LLMSessionError` negative case. The registry edit lives in the wiki repo (separate from the task branch) and is committed via `@mill-wiki-push`. The smoke test lives on the task branch and is skip-on-missing-binary so CI without `gemini` installed exits 0.

Operator validation (out of scope for this batch but documented for completeness): flip `roles.discussion-review.holistic.reviewer: gemini_flash_tool` in `.millhouse/config.local.yaml`, run one `millpy-review-discussion.py` invocation, confirm a review file is produced. That step is a manual operator action, not a CI step, and is not part of this batch's verify.

## Cards

### Card 5: Append `gemini_flash` and `gemini_flash_tool` entries to `wiki/reviewers.yaml`

- **Context:** none
- **Edits:**
  - `wiki/reviewers.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. Append two top-level entries to `wiki/reviewers.yaml` after the last existing entry (preserve the existing `sonnetmax`, `sonnetmax_tool`, `sonnetmedium`, etc. blocks verbatim — do NOT reorder, deduplicate, or reflow them). Add one blank line between the previous final entry and the new `gemini_flash:` block.
  2. The two new entries are exactly:
     ```yaml
     gemini_flash:
       type: single
       provider: gemini
       model: gemini-2.5-flash

     gemini_flash_tool:
       type: single
       provider: gemini
       model: gemini-2.5-flash
       tooluse: true
     ```
     Note: NO `effort:` key on either entry — gemini-cli has no effort flag and `_llm_gemini.run_bulk` / `run_tool_use` ignore the kwarg. NO trailing blank line beyond a single newline at end-of-file.
  3. After editing the file at the absolute wiki path (resolve via `_paths.resolve_wiki_path(_paths.resolve_git_root())` if scripted; the operator-level path on this machine is `C:\Code\millhouse\wiki\reviewers.yaml`), invoke the `@mill-wiki-push` skill to commit and push the change in the wiki repo. The wiki-push handles the wiki lock, the commit, the push, and rebase-on-conflict.
  4. The TASK branch sees no diff from this card — the wiki repo is separate. Do NOT add `wiki/reviewers.yaml` to the task-branch git index. Do NOT invoke `@git-commit` for this card; the wiki-push commit is the only commit. The `Commit:` field below is the wiki-side commit message that `@mill-wiki-push` will use.
- **Commit:** `wiki(reviewers): add gemini_flash and gemini_flash_tool`

### Card 6: Create `smoke-llm-gemini.py`

- **Context:**
  - `plugins/mill/scripts/_llm_gemini.py`
  - `plugins/mill/integration_tests/smoke-llm-claude.py`
  - `plugins/mill/unit_tests/test-llm-gemini.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_gemini.py`
  - `plugins/mill/unit_tests/test-llm-gemini.py`
- **Creates:**
  - `plugins/mill/integration_tests/smoke-llm-gemini.py`
- **Deletes:** none
- **Requirements:**
  1. Create `plugins/mill/integration_tests/smoke-llm-gemini.py`. Structure mirrors `smoke-llm-claude.py`: top-level docstring, `HUB`/`SCRIPTS`/`SCRATCH` path constants, three test functions (`test_bulk`, `test_tool_use`, `test_resume_not_supported`), a `main() -> int` that ORs the return codes, and `if __name__ == "__main__": sys.exit(main())`.
  2. Imports: `from __future__ import annotations`, then `import shutil`, `import sys`, `import uuid`, then `from pathlib import Path`. Then `HUB = Path(__file__).resolve().parent.parent.parent.parent`, `SCRIPTS = HUB / "plugins" / "mill" / "scripts"`, `SCRATCH = HUB / ".scratch"`, `sys.path.insert(0, str(SCRIPTS))`. Then `import _llm_gemini`.
  3. **Skip-on-missing-binary guard:** at the top of `main()`, before any test runs, check `if shutil.which("gemini") is None:`. When true, print `print("SKIP: gemini CLI not found on PATH; integration smoke skipped.", file=sys.stderr)` and `return 0`. The CI machine without gemini installed must exit 0.
  4. Prompt constants (module-level):
     - `PROMPT_BULK` — reviewer-style prompt asking the model to emit `verdict: APPROVE` for an inline 2-line Python function (`def greet(name: str) -> str: return f"Hello, {name}!"`). Exact format and wording style match `smoke-llm-claude.py`'s `PROMPT_BULK` but include explicit `Do NOT use any tools.` (gemini interprets this in conjunction with the `-e ""` flag the wrapper passes).
     - `PROMPT_TOOL` — same shape as `smoke-llm-claude.py`'s `PROMPT_TOOL`: reviewer prompt that names a file path and asks the model to read it (using gemini's built-in read tool, which is allowed in `--approval-mode plan` / tool-use mode) and emit a verdict. Format string with `{path}`.
  5. `test_bulk() -> int`: print banner, call `_llm_gemini.run_bulk(PROMPT_BULK, model="gemini-2.5-flash", timeout=120)`, catch any exception as failure. Assert `"verdict:" in text.lower()` and `sid` is non-empty (synthetic ids satisfy this). Return 0 on success, 1 on failure. Print the returned text and session_id to stderr for diagnostic visibility (matches `smoke-llm-claude.py`'s pattern).
  6. `test_tool_use() -> int`: create `SCRATCH / f"mill-smoke-llm-{uuid.uuid4().hex[:8]}"` with `mkdir(parents=True)`, write a tiny `sample.py` inside. Format `PROMPT_TOOL` with the absolute path. Call `_llm_gemini.run_tool_use(prompt, model="gemini-2.5-flash", timeout=180)`. Assert `"verdict:" in text.lower()` and `sid` is non-empty. Use a `try/finally` that deletes the temp dir on success, preserves it on failure (matches `smoke-llm-claude.py`'s pattern with a `failed` flag).
  7. `test_resume_not_supported() -> int`: invoke `_llm_gemini.run_bulk("ignored", model="gemini-2.5-flash", session_id="anything", resume=True)`. Assert `LLMSessionError` is raised; on success return 0, on no-exception or wrong-exception return 1. This test does NOT spawn `gemini` (the short-circuit raises before subprocess), so it runs even on machines that have `gemini` installed but offline — it remains a green test in all environments where the guard above did not fire.
  8. NO session-reuse positive test (session reuse is not supported). NO `test_session_reuse` function — do not adapt the Claude smoke's `PROMPT_SESSION_SEED` / `PROMPT_SESSION_RECALL` constants.
  9. `main() -> int`: ORs the three test results into `rc`. Prints `OK — all Gemini smoke tests passed` on rc==0 and `FAIL — at least one Gemini smoke test failed` on rc!=0. Returns rc.
- **Commit:** `test(_llm_gemini): integration smoke for live gemini CLI`

## Batch Tests

`verify: uv run --project plugins/mill python plugins/mill/integration_tests/smoke-llm-gemini.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py`. Two commands chained with `&&`:

1. **Integration smoke first.** `smoke-llm-gemini.py` is CI-safe because of the `shutil.which("gemini") is None → return 0` guard at the top of `main()`. On machines without the binary it exits 0 and the second command runs; on machines with the binary it exercises the real `gemini` CLI for bulk + tool-use + the `resume=True → LLMSessionError` negative case. This is the only end-to-end signal that the wiring works.
2. **Registry validation second.** `test-reviewers.py` calls `_reviewers.load` on the live wiki registry and asserts every entry parses. The two new gemini entries must pass that validation (`type: single`, string `provider`, string `model`).

The integration smoke does not require `_reviewer_single.py` to be modified — per the Shared Decision in `00-overview.md`, `_reviewer_single.py` already routes `provider: gemini` to `_llm_gemini` via `importlib.import_module`, so the smoke and the live operator validation flow both work without further code changes.
