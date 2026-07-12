# Plan: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
slug: explore-fork-agent-opportunities
approved: false
started: 20260712-134424
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: contract-helpers
    file: 01-contract-helpers.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-review-common.py test-agent-mode-dispatch.py
  - number: 2
    name: review-backends-and-clis
    file: 02-review-backends-and-clis.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-review-prepare-envelope.py test-review-discussion-flow.py test-review-plan-flow.py test-review-code-flow.py test-review-cli-error-envelope.py test-review-plan-finalize-round.py
  - number: 3
    name: prompt-surfaces
    file: 03-prompt-surfaces.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py test-render.py
  - number: 4
    name: orchestrator-skills
    file: 04-orchestrator-skills.md
    depends-on: [2]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skill-helper-drift.py test-skills-index.py
  - number: 5
    name: output-contract-conformance
    file: 05-output-contract-conformance.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-output-contract.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: reviewers-only — never touch the implementer path

- **Decision:** This task changes the output contract for the **three reviewer dispatch
  sites only** (discussion review, plan review, code review). `_implementer_common.py`,
  `millpy-implement.py`, `millpy-fix.py`, `millpy-merge-in-subagent.py`, all five
  non-review brief templates, and `plugins/mill/agents/mill-implementer.md` are **not in
  the edit set**. No card may modify them. `_implementer_common.py:892`'s `html.unescape`
  **stays** — the implementer payload still arrives via the HTML-escaped
  `<task-notification>`, so unescaping is still correct there.
- **Rationale:** The implementer's `finalize` infers completion from git state, and its
  recovery paths carry the `#574` false-success hazard (a partial batch must never be
  accepted as done). Reviewers are pure — read files, write a report, report a verdict —
  and carry the *bigger* payloads. This is the deliberate descope from discussion.md
  (`reviewers-only-scope`).
- **Applies to:** all batches

### Decision: every new flag defaults to False

- **Decision:** Both new parameters — `write_brief(..., output_contract: bool = False)` and
  the agent-mode flag on `build_tool_rule` / each backend's `prepare()` — default to
  `False` (the non-agent, pre-existing behaviour). Only the three review CLIs' `--stage
  prepare` branches pass `True`.
- **Rationale:** This default is what makes the descope safe and is load-bearing in two
  places. (1) `_implementer_common.py:775` calls `write_brief` with five positional
  arguments; the default keeps implementer briefs **byte-identical**. (2)
  `test-review-common.py` calls `build_tool_rule` **positionally with one argument** at
  seven sites (`:615`, `:652`, `:690`, `:691`, `:695`, `:2828`, `:2880`) — a *required*
  second parameter would raise `TypeError` in all seven.
- **Applies to:** all batches

### Decision: all tool statements live in `build_tool_rule` and nowhere else

- **Decision:** `build_tool_rule` is the **only** channel-aware injection point in a review
  prompt, so it becomes the **sole owner** of the read-only clause, the `Write` carve-out,
  and the report destination. The five review templates' static header surrenders its tool
  prohibitions; no template and no agent definition may state a tool permission or an
  output destination.
- **Rationale:** The five templates and `<TOOL_RULE>` are **shared** between agent-mode and
  the `--stage full` fallback. Static template prose cannot be made dispatch-aware, so any
  tool statement left in a template is necessarily wrong on one of the two channels.
- **Applies to:** all batches

### Decision: `--stage full` must keep working — it is not dead code

- **Decision:** The `--stage full` LLM-provider path keeps today's behaviour **verbatim**:
  the reviewer returns its review as text and the backend writes the file. Both non-agent
  `build_tool_rule` cells must stay **byte-identical** to today's strings.
- **Rationale:** `--stage full` is the reviewer's fallback after two consecutive raw API
  errors (`mill-go/SKILL.md:129`). A `--stage full` reviewer has no brief and is granted at
  most `Read,Grep,Glob` (`_llm_claude.py:80`), so telling it to `Write` would break the one
  path that rescues a review round when the Agent API is down — exactly when a second
  failure is least affordable.
- **Applies to:** all batches

### Decision: no `<OUTPUT_FILE>` token anywhere

- **Decision:** No template and no agent definition may contain an `<OUTPUT_FILE>` token —
  or any other new `<UPPERCASE>` token. Templates and agent definitions name the report file
  **by description only**. The literal absolute path arrives **solely** in the footer that
  `write_brief` appends.
- **Rationale:** `_render.render` (`_render.py:35`) matches `<[A-Z][A-Z0-9_]*>` and raises
  `KeyError: Unresolved template tokens` for any such token missing from the caller's
  `values` dict. A token in a template would hard-fail rendering **before** `write_brief`
  ever runs, and is unsuppliable on `--stage full` anyway. Agent definitions are static text
  never passed through `_render`, so a token there would reach the model raw.
- **Applies to:** batches 1, 3, 5

### Decision: `worktree_snapshot_guard` is not affected — verified, do not "fix" it

- **Decision:** Granting `mill-reviewer` the `Write` tool does **not** require any change to
  `worktree_snapshot_guard` or `ReviewerOverstepError` in `_review_common.py`. Leave both
  untouched.
- **Rationale:** The guard is only ever entered from `run()` — `_review_discussion.py:197`,
  `_review_code.py:607`, `_review_plan.py:620` — i.e. the `--stage full` path, where the
  reviewer is an in-process LLM call with no `Write` grant. An **agent-mode** reviewer is
  dispatched by the orchestrator, entirely outside that context manager, so its `.out.md`
  write is never snapshotted and cannot raise `ReviewerOverstepError`. This was verified
  against source while planning; it is recorded here because it is the first question a
  reviewer will ask about the `Write` grant.
- **Applies to:** all batches

### Decision: editing the source tree does not change the mill running this task

- **Decision:** Do not attempt to validate these changes by triggering a live mill review
  round, and do not be alarmed that the running orchestrator still uses the old contract.
- **Rationale:** Operational mill calls run from the **plugin cache**
  (`${CLAUDE_PLUGIN_ROOT}`), which is a *copy*, not a symlink into this worktree. The mill
  that reviews this very task therefore keeps running the old contract until the plugin is
  updated after merge. Unit tests are the only in-task verification surface, and they import
  from `plugins/mill/scripts` directly.
- **Applies to:** all batches

### Decision: unit-test style — plain functions plus a `main()` runner

- **Decision:** New and extended tests follow the existing convention in
  `plugins/mill/unit_tests/`: module-level `test_*` functions, a `main()` that calls each and
  collects failures, `sys.exit(main())`. No pytest. Fixtures are in-memory or `tempfile`; no
  real git, no real LLM. `print("PASS ...")` output is **ASCII-only** (Windows cp1252).
- **Rationale:** `run-all.py` discovers `test-*.py` and executes each as a subprocess. Two
  in-repo styles exist (plain functions in `test-agents-defs.py`, `unittest.TestCase` in
  `test-review-common-guard.py`); match the file being extended, and use plain functions for
  new files.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/agents/mill-reviewer.md`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-agents-defs.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
- `plugins/mill/unit_tests/test-review-output-contract.py`
- `plugins/mill/unit_tests/test-review-prepare-envelope.py`
