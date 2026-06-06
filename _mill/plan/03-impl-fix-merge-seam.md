# Batch: impl-fix-merge-seam

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: impl-fix-merge-seam
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py
depends-on: [1]
```

## Batch Scope

Adds the `--stage {prepare,finalize,full}` seam to the three implementer-class
CLIs (`millpy-implement.py`, `millpy-fix.py`, `millpy-merge-in-subagent.py`),
which all share the linear shape `prepare -> _implementer_claude.run(prompt_text)
-> _forward_output(output)`. Two shared helpers in `_implementer_common.py` keep
the three CLIs DRY. `full` (default) is unchanged. External interface consumed by
batch 5/6: each CLI accepts `--stage prepare` (prints the prepare JSON envelope,
all subagent_type=`mill-implementer`) and `--stage finalize --agent-output <p>`
(prints the same final JSON the `full` run prints).

## Cards

### Card 9: Stage helpers in `_implementer_common.py`

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two helpers beside the existing `_forward_output`.
  `emit_prepare(briefs_dir, role, scope, round_n, prompt_text, model_tier, session_id) -> int`
  writes the brief via `_agent_dispatch.write_brief(...)`, then prints ONE JSON
  line `{"stage":"prepare","brief_path":<abs str>,"subagent_type":"mill-implementer","model":<model_tier>,"session_id":<id>,"role":<role>,"scope":<scope>,"round":<round_n>}`
  and returns 0. `finalize_from_output(agent_output_path, project_root, *, start_sha=None, snapshot_path=None, session_id=None) -> int`
  reads the sub-agent's final text from `agent_output_path` (utf-8) and delegates
  to the existing `_forward_output(text, project_root, start_sha=..., snapshot_path=..., session_id=...)`
  unchanged, returning its code. Do not alter `_forward_output` itself. ASCII
  output only.
- **Commit:** `feat(implementer-common): add prepare/finalize stage helpers`

### Card 10: `--stage` in `millpy-implement.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `--stage {prepare,finalize,full}` (default `full`) and
  `--agent-output <path>` (required iff `--stage finalize`). Keep the existing
  setup -> atomic pre-commit (status `running`, commit, push) -> render
  (`_render.render` producing `prompt_text`, ~lines 167-178) for both `full` and
  `prepare`. After render: if `stage == "prepare"`, compute the model tier from
  the resolved spec (`impl_model` is `impl_spec["model"]` at line ~101; use
  `_agent_dispatch.model_to_tier(impl_spec["model"])`), then call
  `_implementer_common.emit_prepare(briefs_dir, "implement", args.batch_name, 1, prompt_text, tier, session_id)`
  and return (no LLM call; the pre-commit already ran, matching `full`). If
  `stage == "full"`: unchanged (`_implementer_claude.run(...)` then
  `_forward_output(...)`). If `stage == "finalize"`: skip setup/commit/render and
  the LLM call; call
  `_implementer_common.finalize_from_output(args.agent_output, project_root, start_sha=<read from status batch entry>, snapshot_path=snapshot_path, session_id=<from status>)`.
  `briefs_dir` is `_paths.resolve_task_path(project_root, "_mill/briefs/")`. For
  `finalize`, `start_sha`/`session_id` come from the batch entry written by
  `prepare`'s commit (read via `_status`), and `snapshot_path` is the same
  `_mill/.cleanliness-snapshot-<batch>.txt` path the prepare stage captured.
- **Commit:** `feat(implement): add --stage prepare/finalize seam`

### Card 11: `--stage` in `millpy-fix.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `--stage {prepare,finalize,full}` (default `full`) and
  `--agent-output <path>`. Preserve both scope paths (`--scope batch` and
  `--scope holistic`) and their commit/render blocks (~lines 181-277). For
  `prepare`: after the scope's render produces `prompt_text`, resolve the model
  via `_reviewers.resolve(registry, cfg["roles"]["fixer"]["model"])`, map with
  `_agent_dispatch.model_to_tier`, and call `emit_prepare` with `role="fix"`,
  `scope=args.batch_name` for batch scope or `"holistic"` for holistic scope,
  `round_n=args.round`. For `full`: unchanged. For `finalize`: call
  `finalize_from_output(args.agent_output, project_root, start_sha=start_sha, snapshot_path=snapshot_path, session_id=session_id)`
  reconstructing `start_sha`/`snapshot_path`/`session_id` the same way `full`
  does (fix uses the inferred-success path when `snapshot_path` is absent -- keep
  that intact via `_forward_output`).
- **Commit:** `feat(fix): add --stage prepare/finalize seam`

### Card 12: `--stage` in `millpy-merge-in-subagent.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `--stage {prepare,finalize,full}` (default `full`) and
  `--agent-output <path>`, covering both `--mode conflicts` and
  `--mode verify-fix`. Model resolution is unchanged
  (`cfg.get("merge",{}).get("model") or cfg["roles"]["implementer"]["model"]` ->
  `_reviewers.resolve`, line ~155); map `impl_spec["model"]` via
  `_agent_dispatch.model_to_tier`. For `prepare`: render the mode's brief
  (`merge-in-conflict-brief.md` or `merge-in-verify-brief.md`) and call
  `emit_prepare` with `role="merge"`, `scope=args.mode`, `round_n=1`. SPECIAL
  CASE (verify-fix): the verify command runs in `prepare` (lines ~204-247); if it
  PASSES, there is nothing to dispatch -- in that case `emit_prepare` must instead
  print a `{"stage":"prepare","dispatch_needed":false, ...,"envelope":<the success JSON _forward_output-equivalent>}`
  line so the SKILL skips the Agent tool and the finalize call and uses the
  embedded envelope directly. When verify FAILS, emit the normal prepare envelope
  with `"dispatch_needed":true`. For `full`/`finalize`: `full` unchanged;
  `finalize` reads `--agent-output`, runs the post-sub-agent re-verification block
  that `full` runs after the LLM call (verify-fix re-runs the verify command;
  lines ~265-282), then `_forward_output`.
- **Commit:** `feat(merge-in): add --stage prepare/finalize seam`

### Card 13: Tests for the impl/fix/merge seam

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-implementer-common.py`: assert `emit_prepare` writes
  the brief at the expected path and prints the prepare JSON with
  `subagent_type=="mill-implementer"` and the mapped tier; assert
  `finalize_from_output` reads a fixture output file and produces the same stdout
  JSON as calling `_forward_output` directly on the same text. In each CLI test
  file: assert (a) `--stage prepare` performs the existing pre-commit and writes
  the brief but does NOT spawn the LLM (mock/guard `_implementer_claude.run` to
  fail if called), and (b) `--stage finalize --agent-output <fixture>` reproduces
  the same final JSON envelope the existing `full`-path test expects. For
  merge-in, add a verify-fix case where the verify command passes and `prepare`
  emits `dispatch_needed:false` with an embedded success envelope. Reuse each
  file's existing fixtures (no real git/LLM); keep `full`-path tests passing
  unchanged.
- **Commit:** `test(seam): cover prepare/finalize for impl, fix, merge-in`

## Batch Tests

`verify:` runs the four affected CLI/helper test files. The contract under test is
parity: `full` behavior is unchanged, and `prepare`+`finalize` together reproduce
the `full` JSON envelope for the same inputs without invoking the LLM. Fixtures
are in-memory/tempfile; `_implementer_claude.run` is guarded so a prepare/finalize
run that accidentally spawns the LLM fails the test.
