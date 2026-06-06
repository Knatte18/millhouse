# Plan: Replace subprocess LLM dispatch with the Claude Code Agent tool

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
slug: subprocess-to-agents
approved: true
started: "20260606-134500"
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches._

```yaml
batches:
  - number: 1
    name: config-and-dispatch-helper
    file: 01-config-and-dispatch-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-llm-claude.py test-agent-dispatch.py
  - number: 2
    name: subagent-definitions
    file: 02-subagent-definitions.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py
  - number: 3
    name: impl-fix-merge-seam
    file: 03-impl-fix-merge-seam.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py
  - number: 4
    name: review-seam
    file: 04-review-seam.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-cli.py test-review-discussion-flow.py test-review-code-flow.py test-review-plan-flow.py
  - number: 5
    name: skill-mill-go
    file: 05-skill-mill-go.md
    depends-on: [2, 3, 4]
    verify: null
  - number: 6
    name: skill-others
    file: 06-skill-others.md
    depends-on: [2, 3, 4]
    verify: null
  - number: 7
    name: agent-mode-parity-test
    file: 07-agent-mode-parity-test.md
    depends-on: [3, 4, 5, 6]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-mode-dispatch.py
```

## Shared Decisions

### Decision: dispatch-mode is resolved by the SKILL, the seam by the CLIs

- **Decision:** The Agent tool is callable only from inside a Claude Code
  session, so the dispatch-mode branch lives in the SKILL, not in Python. Each
  dispatch CLI is refactored to expose three stages via a `--stage` flag:
  `prepare`, `finalize`, and `full` (default). `full` is the current monolithic
  behavior (setup -> render -> spawn LLM via `_llm_claude` -> finalize), used
  unchanged by `subprocess`/`psmux` modes through `millpy-bg`. `prepare` and
  `finalize` split that flow at the LLM-call boundary so the SKILL can run
  `prepare -> Agent tool -> finalize` in `agent` mode.
- **Rationale:** Keeps all tested logic (render, parse, cleanliness, review-file
  write, envelope) in Python; only the LLM-call hop relocates. `full` guarantees
  byte-for-byte parity for the existing modes.
- **Applies to:** all batches.

### Decision: --stage contract (identical across all six dispatch CLIs)

- **Decision:**
  - `--stage prepare`: do setup + the atomic pre-commit + render the brief, then
    write the rendered brief to `_mill/briefs/<role>-<scope>-r<round>.md` via
    `_agent_dispatch.write_brief(...)`, and print ONE JSON line to stdout:
    `{"stage":"prepare","brief_path":"<abs>","subagent_type":"mill-implementer"|"mill-reviewer","model":"<tier>","session_id":"<id>","role":"<role>","scope":"<scope>","round":<int>}`.
    No LLM call. Exit 0.
  - `--stage finalize --agent-output <path>`: read the sub-agent's final message
    text from `<path>`, run the existing finalize logic verbatim (`_forward_output`
    for implementer/fix/merge; `parse_verdict` + `write_review_file` +
    `ReviewResult.to_dict()` for reviews), and print the SAME JSON envelope the
    `full` run prints. No LLM call.
  - `--stage full` (default): unchanged current behavior. Used by `subprocess`/
    `psmux` via `millpy-bg`.
- **Rationale:** A single uniform contract lets every SKILL agent-mode branch use
  the same three-step shape.
- **Applies to:** batches 3, 4 (define) and 5, 6 (consume).

### Decision: SKILL agent-mode three-step flow

- **Decision:** At each dispatch point, the SKILL first resolves the mode via
  `_agent_dispatch.resolve_dispatch_mode(cfg)`. If `agent` (Claude provider
  only): (1) run `<cli> --stage prepare <args>`, parse the JSON for `brief_path`,
  `subagent_type`, `model`; (2) call the **Agent tool** synchronously with
  `subagent_type`=that type, `model`=that tier, and prompt
  `"Read this file and follow the instructions exactly: <brief_path>"`; (3) write
  the Agent's returned final message to `<brief_path>.out`; (4) run
  `<cli> --stage finalize <args> --agent-output <brief_path>.out`; (5) parse the
  printed JSON envelope and branch on the verdict EXACTLY as the existing
  `millpy-bg` path does. If `subprocess`/`psmux`: the existing `millpy-bg` flow
  is unchanged. No log-polling, liveness check, or `infrastructure` stuck path in
  agent mode (no detached worker); the `transient` stuck path still applies via
  `finalize`'s synthetic stuck JSON.
- **Rationale:** Reuses every existing verdict branch; the only change is how the
  worker is launched and its output captured.
- **Applies to:** batches 5, 6.

### Decision: model -> Agent-tool tier mapping

- **Decision:** `prepare` resolves the role's model spec exactly as the existing
  CLI does (see per-batch cards), reads `spec["model"]` (a concrete id like
  `claude-sonnet-4-6`), and maps it to an Agent-tool tier via
  `_agent_dispatch.model_to_tier`: `claude-sonnet-*` -> `sonnet`,
  `claude-opus-*` -> `opus`, `claude-haiku-*` -> `haiku`. `effort` is read but
  NOT emitted (the Agent tool has no effort knob). The implementer cards verify
  whether the deployed Agent tool also accepts a full model id; if so,
  pass-through is allowed, but the tier map is the guaranteed-safe default.
- **Rationale:** Honors the configured model; drops effort, which is unavailable.
- **Applies to:** batches 1 (helper), 3, 4 (use).

### Decision: ASCII-only stdout, cache-path operational calls, PYTHONPATH-isolated verify

- **Decision:** All new Python `print`/log output is ASCII (` -- `, ` -> `).
  Every `verify:` starts with literal `PYTHONPATH= ` so the test subprocess loads
  worktree modules, not cache modules. Operational mill calls in SKILLs use
  `${CLAUDE_PLUGIN_ROOT}` (cache); tests use `uv run --project plugins/mill`.
- **Rationale:** Project invariants (CLAUDE.md).
- **Applies to:** all batches.

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/.claude-plugin/plugin.json`
- `plugins/mill/agents/mill-implementer.md`
- `plugins/mill/agents/mill-reviewer.md`
- `plugins/mill/integration_tests/test-agent-mode-commit-target.py`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-fix.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- `plugins/mill/unit_tests/test-agents-defs.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
