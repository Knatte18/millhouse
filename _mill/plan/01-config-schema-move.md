# Batch: config-schema-move

```yaml
task: Keep psmux TUI alive across calls for session continuity
batch: config-schema-move
number: 1
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
depends-on: []
```

## Batch Scope

Foundational batch. Promotes the flat `llm.claude.via_psmux` key into a nested `llm.claude.psmux:` sub-block in both the hub `mill-config.yaml` and the plugin template, adds the sibling `llm.claude.psmux.reuse_idle_timeout_s: 10` key, and migrates `_llm_claude._get_via_psmux_flag()` to read the nested path. Hard cutover — no compat shim. After this batch the wrapper still auto-generates session names (`mill-{uuid.uuid4().hex[:8]}`) and ignores the new `reuse_idle_timeout_s` key; behaviour is unchanged for one-shot calls and `resume=True` still raises the existing "psmux path does not support session resume" guard. The new key exists in config only so batches 2 and 3 can read it.

External interface for batch 2: the nested config path `cfg["llm"]["claude"]["psmux"]["reuse_idle_timeout_s"]` is guaranteed present in the deep-merged config (template provides the default `10`). Batch-local decision: the module-level fallback constant lives in `millpy-claude-sub.py` (batch 2), NOT in `_llm_claude.py`, because the wrapper is the only consumer.

## Cards

### Card 1: migrate hub `mill-config.yaml` schema

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-config.yaml` at the hub root, under `llm.claude:`, replace the existing line `via_psmux: false  # Route claude calls through psmux for subscription billing (requires psmux on PATH; resume flows unsupported)` with a nested `psmux:` sub-block that has two keys: `via_psmux: false` and `reuse_idle_timeout_s: 10`. Update the inline comment on `via_psmux:` to read: `Route claude calls through psmux for subscription billing (requires psmux on PATH; mill-go reaps sessions automatically after each implement-review-fix loop)`. Add an inline comment on `reuse_idle_timeout_s:` reading: `Seconds to wait for an existing psmux session to return to its idle prompt before reuse fails`.
- **Commit:** `config: nest llm.claude.psmux block; add reuse_idle_timeout_s`

### Card 2: mirror schema change into plugin template

- **Context:**
  - `mill-config.yaml`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the identical change from card 1 to `plugins/mill/templates/mill-config.yaml` so the template ships with the new schema (CLAUDE.md "template must mirror wiki/config.yaml schema" rule — same rule applies to `mill-config.yaml`). The template's `llm.claude:` block currently has only `via_psmux: false`; after the change it has the nested `psmux:` sub-block with the same two keys and the same inline comments as card 1.
- **Commit:** `template: mirror llm.claude.psmux schema change`

### Card 3: read nested key in `_get_via_psmux_flag()`

- **Context:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_llm_claude.py`, change the body of `_get_via_psmux_flag()` to read the nested path: replace the current line `return bool(cfg.get("llm", {}).get("claude", {}).get("via_psmux", False))` with `return bool(cfg.get("llm", {}).get("claude", {}).get("psmux", {}).get("via_psmux", False))`. Leave the docstring and the `except (Exception, SystemExit)` fallback unchanged. Do not introduce a `reuse_idle_timeout_s` reader in `_llm_claude.py` — that key is consumed inside the wrapper (batch 2).
- **Commit:** `_llm_claude: read nested llm.claude.psmux.via_psmux`

## Batch Tests

`verify:` re-runs `test-llm-claude.py`. The existing eleven psmux-branch tests in that file all mock `_get_via_psmux_flag` directly (return_value=True/False), so the rename of the read path is invisible to them — they should pass unchanged. Test 11 (`_get_via_psmux_flag` catches SystemExit and returns False) does NOT mock the function; it actually calls it with `_paths.resolve_git_root` patched to raise. The new nested-read path still returns False on any exception, so Test 11 also passes unchanged. No new test is added in this batch — the regression coverage for "reads from nested path correctly" is exercised indirectly by batch 3's tests (which set up a real config dict and assert the wrapper receives the correct timeout) and by manual smoke (the operator runs mill-go after the schema move; if `_get_via_psmux_flag` returned False incorrectly, the direct-CLI path would activate and the operator would notice immediately).
