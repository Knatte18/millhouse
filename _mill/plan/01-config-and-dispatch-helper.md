# Batch: config-and-dispatch-helper

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: config-and-dispatch-helper
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-llm-claude.py test-agent-dispatch.py
depends-on: []
```

## Batch Scope

Delivers the configuration surface and the shared helper module that every
later batch consumes: the `llm.claude.dispatch` enum (with the `via_psmux`
back-compat shim) and a new `_agent_dispatch.py` exposing
`resolve_dispatch_mode`, `model_to_tier`, and `write_brief`. Also re-points
`_llm_claude`'s psmux branch at the new enum so the existing subprocess/psmux
paths keep working. External interface consumed by batches 3-6:
`_agent_dispatch.resolve_dispatch_mode(cfg) -> "subprocess"|"psmux"|"agent"`,
`_agent_dispatch.model_to_tier(model: str) -> "sonnet"|"opus"|"haiku"`, and
`_agent_dispatch.write_brief(briefs_dir, role, scope, round_n, prompt_text) -> Path`.

## Cards

### Card 1: New `_agent_dispatch.py` helper module

- **Context:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_render.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Deletes:** none
- **Requirements:** Create `_agent_dispatch.py` with three pure functions and a
  module constant. `resolve_dispatch_mode(cfg: dict) -> str` reads
  `cfg["llm"]["claude"]["dispatch"]` (default `"subprocess"`), validates it is one
  of `{"subprocess","psmux","agent"}` (raise `ValueError` on unknown), and
  returns it; it does NOT itself reject `agent` for non-Claude providers (the
  caller knows the provider). `model_to_tier(model: str) -> str` maps a concrete
  model id to a tier: prefix `claude-sonnet` -> `"sonnet"`, `claude-opus` ->
  `"opus"`, `claude-haiku` -> `"haiku"`; raise `ValueError` for an unrecognized
  family. `write_brief(briefs_dir: Path, role: str, scope: str, round_n: int, prompt_text: str) -> Path`
  computes `briefs_dir / f"{role}-{scope}-r{round_n}.md"`, creates parent dirs,
  writes `prompt_text` (utf-8, overwriting any existing file), and returns the
  path. Define `SUBAGENT_REVIEWER = "mill-reviewer"` and
  `SUBAGENT_IMPLEMENTER = "mill-implementer"` constants. ASCII-only docstrings.
- **Commit:** `feat(dispatch): add _agent_dispatch helper (mode/tier/brief)`

### Card 2: `dispatch` enum + `via_psmux` back-compat shim in `_config.py`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `load_config`, after the deep-merge completes and before
  the return (current end of `load_config`, ~line 217-222), apply a back-compat
  shim: read `cfg["llm"]["claude"]`. If `dispatch` is absent and a legacy
  `psmux.via_psmux` is present: set `dispatch = "psmux"` when `via_psmux` is
  truthy else `"subprocess"`, and emit ONE stderr deprecation line
  (`[config] llm.claude.psmux.via_psmux is deprecated -- use llm.claude.dispatch`).
  If `dispatch` is present, leave it and still emit the deprecation line if a
  stray `via_psmux` key exists. Validate the final `dispatch` value against
  `{"subprocess","psmux","agent"}`; on an unknown value emit a stderr error line
  and fall back to `"subprocess"` (do NOT raise -- match the warn-not-raise
  posture of `warn_unknown_keys`). In `warn_unknown_keys` (~line 112-122), ensure
  `via_psmux` does NOT produce the generic `[config] unknown key` warning (the
  shim owns its messaging) -- add `llm.claude.psmux.via_psmux` to the
  known/deprecated set the unknown-key check consults. Keep all output ASCII.
- **Commit:** `feat(config): add llm.claude.dispatch enum with via_psmux shim`

### Card 3: Replace `via_psmux` with `dispatch` in config files

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both files, under `llm.claude`, remove the
  `psmux.via_psmux` key and add `dispatch: subprocess` as the documented default.
  Keep the other psmux sub-keys (`shell_path`, `reuse_idle_timeout_s`) in the
  `psmux:` block (they apply only when `dispatch: psmux`). Add a short comment
  listing the three valid values (`subprocess | psmux | agent`) and that `agent`
  is Claude-only. Keep the template and hub file structurally in sync (they must
  stay synchronized per CLAUDE.md).
- **Commit:** `feat(config): replace via_psmux with dispatch in config files`

### Card 4: Point `_llm_claude` psmux branch at the dispatch enum

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace `_get_via_psmux_flag()` (currently reads
  `psmux.via_psmux`) with logic that loads config and returns
  `_agent_dispatch.resolve_dispatch_mode(cfg) == "psmux"`. Keep the function's
  name/signature and its single call site in `_invoke` (line ~307) unchanged in
  behavior: it still returns a bool selecting the psmux vs direct-subprocess
  branch. `_invoke` is never reached in `agent` mode (the SKILL bypasses the
  Python LLM call), so no `agent` handling is added here; if `dispatch == "agent"`
  is somehow seen by `_invoke`, treat it as `subprocess` (direct `claude -p`) as a
  safe fallback. Preserve the silent-False-on-error behavior.
- **Commit:** `refactor(llm): select psmux branch via dispatch enum`

### Card 5: Tests for dispatch helper + config shim

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Deletes:** none
- **Requirements:** New `test-agent-dispatch.py`: assert `resolve_dispatch_mode`
  returns the configured value, defaults to `subprocess`, and raises on unknown;
  `model_to_tier` maps the three families and raises on unknown; `write_brief`
  writes to `<briefs_dir>/<role>-<scope>-r<n>.md`, creates parents, overwrites,
  and returns the path. Extend `test-config.py`: a `via_psmux: true` config with
  no `dispatch` key resolves to `dispatch == "psmux"` and emits the deprecation
  line (capture stderr); an explicit `dispatch: agent` wins over a stray
  `via_psmux`; `via_psmux` does not trigger the generic unknown-key warning; an
  unknown `dispatch` value falls back to `subprocess`. Mirror the existing
  in-memory/tempfile fixture style in `test-config.py`. If Card 4's rename of
  `_get_via_psmux_flag` internals is asserted anywhere in `test-llm-claude.py`,
  update those assertions to the dispatch-enum behavior (the function name is
  retained, so most should be unaffected).
- **Commit:** `test(dispatch): cover dispatch enum, shim, and helper`

## Batch Tests

`verify:` runs `test-config.py` (config shim + enum), `test-llm-claude.py`
(psmux-branch selection still correct after the `_get_via_psmux_flag` rewrite),
and the new `test-agent-dispatch.py` (helper unit tests). All use in-memory /
tempfile fixtures; no real git or LLM. Scoped to exactly the files this batch
edits.
