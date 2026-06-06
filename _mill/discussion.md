# Discussion: Replace subprocess LLM dispatch with the Claude Code Agent tool

```yaml
task: Replace subprocess LLM dispatch with the Claude Code Agent tool
slug: subprocess-to-agents
status: discussing
parent: main
```

## Problem

Mill dispatches every LLM worker (per-batch implementer, code/plan/discussion
reviewers, fixers, merge sub-agent) by spawning a `claude -p` subprocess from
deep inside Python (`_llm_claude._invoke`). The orchestrator SKILL (mill-go,
mill-start, mill-plan, mill-merge) fires the relevant `millpy-*.py` CLI through
`millpy-bg.py` as a detached background worker, then polls a log file until
`[mill-bg] EXIT` appears.

To get a warm/reusable Claude session, an alternative `via_psmux` path drives a
full Claude Code TUI inside a psmux (tmux-on-Windows) pane and scrapes the
screen. That path is fragile: `doc/psmux-tui-behavior.md` documents a long list
of TUI-scraping bugs (non-ASCII status-bar spaces, `paste-buffer` silently
dropping content, `pipe-pane` not working on Windows, idle/processing detection
races). It works today but is high-maintenance.

Claude Code now exposes an in-session **Agent tool** that spawns sub-agents
directly: the orchestrator calls it, the sub-agent runs to completion, and its
final message is returned as the tool result -- no subprocess, no log file, no
polling, no TUI scraping. This is exactly the "one-shot worker, no polling"
model the V3 architecture proposal (`doc/v3-architecture.md` section 2) calls
for. **Why now:** the psmux workaround is the only mechanism that gives a
managed, in-tool Claude worker today, and it is brittle; the Agent tool replaces
the entire spawn+poll+scrape chain with a single synchronous tool call.

Terminology note for the plan author: the wiki task title says "Agent tool" and
the seeded `status.md` task line said "Agent SDK calls". These were clarified in
discussion to mean the **Claude Code in-session Agent tool** (the tool the
orchestrator session itself invokes), NOT the programmatic Claude Agent SDK
Python package. No new pip dependency is added.

## Scope

**In:**

- Add a new dispatch mode selected by config: `llm.claude.dispatch:
  subprocess | psmux | agent` (single enum, default `subprocess`). This
  replaces the `llm.claude.psmux.via_psmux` boolean, with a one-release
  back-compat shim that maps legacy `via_psmux: true` -> `dispatch: psmux`
  (see Decisions / dispatch-config-flag for the exact migration rule).
- For every Claude LLM dispatch site, add an **agent-mode** code path that the
  orchestrator SKILL drives as: `prepare` (Python) -> Agent tool (in-session)
  -> `finalize` (Python). The dispatch sites are:
  - `millpy-implement.py` (per-batch implementer) -- mill-go
  - `millpy-review-code.py` (code review, holistic + batch) -- mill-go
  - `millpy-fix.py` (REQUEST_CHANGES fix + NIT-only pass) -- mill-go
  - `millpy-review-discussion.py` (discussion review) -- mill-start
  - `millpy-review-plan.py` (plan review) -- mill-plan
  - `millpy-merge-in-subagent.py` (merge conflict / verify-fix) -- mill-merge
- Refactor each dispatch CLI so the LLM-call boundary is extracted into a
  `prepare` stage (render the role brief to a git-tracked file under `_mill/`
  plus the existing atomic pre-commit) and a `finalize` stage (the existing
  post-LLM logic: parse output, run the cleanliness gate, write the review file
  in the backend per Decision 24, emit the same JSON envelope). The
  subprocess/psmux modes keep running all stages in-process via `millpy-bg`
  exactly as today.
- Define two custom sub-agent types, shipped with the mill plugin under
  `plugins/mill/agents/` (plugin-provided, NOT repo-local `.claude/agents/` --
  see Decisions / subagent-types for why and for the file format):
  - `mill-reviewer` -- read-only tools only (Read, Grep, Glob). MUST NOT write,
    edit, or run Bash. Faithful port of today's `--disallowedTools
    Edit,Write,Bash,NotebookEdit` for reviewers.
  - `mill-implementer` -- full worker tools (Read, Edit, Write, Bash, Grep,
    Glob, Skill).
- Update the SKILL.md files (mill-go, mill-start, mill-plan, mill-merge) to
  branch on the dispatch mode: in `agent` mode use the Agent tool flow; in
  `subprocess`/`psmux` mode use the existing `millpy-bg` flow unchanged.
- Config plumbing: template `mill-config.yaml` + hub config + `_config`
  validation updated for the `dispatch` enum; remove `via_psmux` from the
  config files and add the back-compat shim + deprecation warning in `_config`.

**Out:**

- The Gemini provider (`_llm_gemini.py`) stays subprocess-based and untouched.
  The Agent tool is Claude-only; `dispatch: agent` is rejected/ignored for any
  non-Claude provider.
- The psmux dispatch path is **kept** as an opt-in (`dispatch: psmux`). No psmux
  code, config sub-keys, tests, or `doc/psmux-tui-behavior.md` are deleted.
- No change to review semantics, verdict schemas, the JSON envelope shape, the
  cleanliness gate, self-fix behavior, prompt templates, or the wiki/plan-DAG
  data model. Behavior is identical across modes; only the dispatch hop differs.
- No new pip dependency (no `claude-agent-sdk`, no `anthropic`).
- The broader V3 module rewrite is out of scope; this task only relocates the
  LLM-call boundary.

## Decisions

### dispatch-mechanism

- Decision: Replace the `claude -p` / psmux subprocess dispatch with the
  Claude Code **in-session Agent tool**, invoked **synchronously** by the
  orchestrator SKILL. The Agent tool returns the sub-agent's final message as
  its tool result, which feeds directly into the existing `finalize` parser
  (the same text `claude -p` stream-json `result` produced).
- Rationale: Removes the entire `millpy-bg` detached-worker + log-poll +
  liveness-check chain and the psmux TUI scraping for this mode. Matches the
  V3 "one-shot worker, no polling" design.
- Rejected: (a) Claude Agent SDK in-process Python call inside `_llm_claude`
  -- would keep the bg-worker architecture and add a pip dependency; the user
  wants the SKILL to call the Agent tool directly, not Python to spawn an LLM.
  (b) Background Agent calls + task notifications -- enables parallel workers
  but adds concurrency/notification handling to the SKILL; the current flow is
  sequential per batch, so synchronous is simpler and sufficient.

### dispatch-config-flag

- Decision: Single enum `llm.claude.dispatch: subprocess | psmux | agent`
  (default `subprocess`). The psmux sub-keys (`shell_path`,
  `reuse_idle_timeout_s`) remain in their block and apply only when
  `dispatch: psmux`. `agent` is valid only for the Claude provider (for any
  non-Claude provider it is an error caught by `_config` validation).
- Migration rule (definitive -- resolves the "remove vs map" ambiguity):
  `llm.claude.psmux.via_psmux` is **removed** from the template and hub
  `mill-config.yaml`. For one release, `_config.load_config` keeps a back-compat
  shim: if `dispatch` is **absent** and a legacy `via_psmux: true` is present,
  it maps to `dispatch: psmux` and emits a one-line deprecation warning;
  `via_psmux: false`/absent maps to `dispatch: subprocess`. When `dispatch` is
  present it always wins and any stray `via_psmux` is ignored with the same
  deprecation warning. Note `_config`'s unknown-key check only emits a stderr
  warning (it never raises), so the shim must (a) suppress the generic
  `[config] unknown key` warning for `via_psmux` and (b) emit its own one-line
  deprecation warning instead. The shim is removed in a later cleanup task.
- Rationale: One knob, no contradictory boolean combinations; the shim keeps
  existing hubs that still carry `via_psmux: true` working without edits.
- Rejected: Parallel `via_agent` boolean beside `via_psmux` (ambiguous when both
  true); hard-removing `via_psmux` with no shim (silently changes behavior for
  hubs that relied on it).

### prepare-finalize-split

- Decision: Refactor each dispatch CLI's body so the LLM-call boundary is a
  clean seam. `prepare` does the atomic pre-commit and renders the role brief
  to a git-tracked file under `_mill/`; `finalize` runs the existing
  post-LLM logic unchanged. In `agent` mode the SKILL calls `prepare` ->
  Agent tool -> `finalize` as separate steps. In `subprocess`/`psmux` mode the
  CLI runs prepare + spawn + finalize in-process (via `millpy-bg`), exactly as
  today.
- Rationale: Keeps all heavy, tested logic (rendering, verdict parsing,
  cleanliness gate, review-file writing, envelope assembly, self-fix handling)
  in Python where it is unit-tested; only the LLM-call hop moves. mill-go never
  has to build long prompts -- it sends only "Read this file and follow the
  instructions: <path>".
- Rejected: SKILL renders prompts and parses verdicts inline -- pushes
  untestable logic into markdown and duplicates the parsers.

### brief-file-lifecycle

- Decision: The rendered role brief is written to a **git-tracked** file under
  `_mill/briefs/` and committed as part of the existing atomic pre-commit. The
  Agent-tool prompt references this path.
- Identifier scheme: `_mill/briefs/<role>-<scope>-r<round>.md`, where `role` is
  the dispatch site (`implement`, `review-code`, `review-plan`,
  `review-discussion`, `fix`, `merge`), `scope` is the batch name for
  per-batch roles (implementer/code-review/fix), the review scope (`holistic`)
  for holistic reviews, or `merge` for the merge sub-agent, and `<round>` is the
  review/fix round (`r1` for single-shot roles). Re-dispatch of the SAME
  (role, scope, round) -- e.g. a resume after a mid-dispatch interrupt --
  **overwrites** the same path (idempotent; `prepare` re-renders). Distinct
  rounds/batches get distinct files and accumulate.
- Retention: briefs are NOT pruned during the task (they are the per-dispatch
  audit trail); they are removed with the rest of `_mill/` by mill-cleanup /
  merge teardown, exactly as today's status/review artifacts.
- Rationale: Easy to follow what each sub-agent was told; deterministic paths
  avoid collisions; if the session crashes mid-dispatch the brief is already on
  disk and reusable on resume.
- Rejected: Gitignored/ephemeral scratch brief (harder to audit, not
  recoverable after a crash); random/uuid identifiers (pile up, not resumable).

### output-handling-unchanged

- Decision: Output handling is byte-for-byte the same as today. The reviewer
  stays read-only and the **backend writes the canonical review file**
  (Decision 24 preserved); the implementer self-fixes internally per its brief
  and emits its status JSON as its final message; `finalize` parses that JSON
  and runs the cleanliness gate; the JSON envelope shape is unchanged.
- Rationale: User requirement -- "otherwise exactly the same behavior; the
  only difference is the Agent tool instead of millpy-bg".
- Rejected: Sub-agent writes its own review file per instructions -- would
  overturn Decision 24 and lose the backend's schema guarantee.

### subagent-types

- Decision: Define two custom sub-agent types, `mill-reviewer` (read-only:
  Read, Grep, Glob; MUST NOT write/edit/Bash) and `mill-implementer` (full
  worker tools: Read, Edit, Write, Bash, Grep, Glob, Skill). Each Agent-tool
  call passes the appropriate `subagent_type` plus a per-call `model` override
  taken from config; `effort` is not passed.
- Definition format + location: each is a markdown file with YAML frontmatter --
  `name` (the `subagent_type` string), `description`, `tools` (comma-separated
  allow-list; the read-only set for `mill-reviewer`), and an optional `model`
  (omitted here -- the per-call `model` override supplies it). They are
  **shipped with the mill plugin** (e.g. `plugins/mill/agents/<name>.md`,
  declared in the plugin manifest), NOT repo-local `.claude/agents/`, because
  mill runs in external repos that have no millhouse checkout -- plugin-provided
  agents resolve wherever the plugin is installed. The plan must confirm the
  exact plugin-manifest field/dir name against the installed plugin layout.
- Rationale: The reviewer's read-only constraint must be enforced at the tool
  layer (the user's explicit requirement: "tool access but must not write
  anything"), faithfully porting today's `--disallowedTools`. Custom types pin
  the tool set precisely, unlike the built-in `Explore` (search-tuned, not an
  exact match) or `general-purpose` (no hard read-only enforcement). The
  agent-mode discussion review run during THIS task's design used a
  general-purpose subagent with read-only instructions as a stand-in and
  behaved correctly, which validates the shape.
- Rejected: Built-in `Explore` for reviewers (wrong tuning); `general-purpose`
  for all with brief-only read-only instruction (no hard enforcement);
  repo-local `.claude/agents/` (would not exist in external consumer repos).

### model-and-effort

- Decision: In agent mode, `prepare` resolves the role's model exactly as the
  current CLI does, then passes it to the Agent tool's `model` parameter. The
  per-role `effort`/thinking suffix is **dropped** -- the Agent tool exposes no
  effort knob. Full model+effort control is retained on the `subprocess`/`psmux`
  paths.
- Model value form: the registry resolvers return a spec **dict**; `prepare`
  reads `spec["model"]` (exactly as `millpy-implement.py` reads
  `impl_spec["model"]`), a concrete model string such as `claude-sonnet-4-6` /
  `claude-opus-4-7` / `claude-haiku-4-5`. `spec.get("effort")` is read but not
  used in agent mode. `prepare` maps `spec["model"]` to the Agent tool's
  `model` value by family tier:
  `claude-sonnet-*` -> `sonnet`, `claude-opus-*` -> `opus`, `claude-haiku-*` ->
  `haiku`. If the deployed Agent tool also accepts a full model id, the resolved
  string may be passed through unchanged; the family->tier map is the
  guaranteed-safe fallback. The plan must verify which forms the Agent tool's
  `model` parameter accepts and pick pass-through vs tier-map accordingly.
- Resolution entry point (per dispatch site): `prepare` must reproduce the SAME
  resolution the existing CLI does, then read `spec["model"]`. The three
  distinct paths (do NOT collapse into one generic call, and note
  `_reviewers.resolve_role` is dead code -- no CLI/backend calls it, so do not
  use it):
  - implementer / fixer: `_reviewers.resolve(registry, cfg["roles"]["<role>"]["model"])`
    (implementer default `sonnethigh`, fixer per `roles.fixer.model`).
  - reviewers (discussion / plan / code): read the reviewer name from
    `cfg["roles"]["<role>"]["<scope>"]["reviewer"]`, then
    `_reviewers.resolve(registry, reviewer_name)`, then apply
    `maybe_switch_spec_for_large_prompt` exactly as the backend does today.
    That switch is computed from the rendered prompt size and fires for
    **holistic** reviews only (not batch), so `prepare` must render the brief
    before finalizing the reviewer model.
  - merge sub-agent: `cfg["merge"]["model"]` (fallback `roles.implementer.model`,
    default `haiku`), then `_reviewers.resolve(registry, model_name)`.
- Rationale: The Agent tool cannot set effort; model selection is still
  honored. User: "effort is not possible with the Agent tool, but model is --
  use the same model as in the config."
- Rejected: Encoding effort hints in the brief text (unreliable; not the same
  as the CLI flag).

### resume-and-failure-semantics

- Decision: In agent mode, dispatch is synchronous and in-session. If the
  orchestrator session is interrupted mid-dispatch the sub-agent dies; on resume
  the SKILL re-dispatches based on the committed on-disk state (the brief is
  already committed and reusable). The `infrastructure` stuck path ("bg worker
  died (logout?)") does not apply in agent mode (there is no detached worker).
  The `transient` stuck path still applies: if the sub-agent errors or returns
  empty, `finalize` emits the same synthetic stuck JSON the CLI emits today, and
  the SKILL's existing one-retry policy handles it.
- Rationale: Preserves the atomic-commit-before-heavy-work resume guarantee
  while shedding the bg-worker-specific failure mode that cannot occur in agent
  mode.
- Rejected: Reattaching to a dead in-session sub-agent (not possible).

## Technical context

Current dispatch chain (the thing being re-pathed):

```
SKILL (mill-go / mill-start / mill-plan / mill-merge)
  -> millpy-bg.py            (detached worker + .scratch/bg-*.log)
     -> millpy-<role>.py     (CLI: setup -> atomic pre-commit -> render
                              -> spawn LLM -> parse/finalize -> JSON envelope)
        -> _llm_claude._invoke
           -> claude -p  (direct)  OR  millpy-claude-sub.py + _psmux* (psmux)
SKILL polls the bg log until "[mill-bg] EXIT", then reads the JSON summary line.
```

Key files and helpers to reuse (do not rewrite):

- `plugins/mill/scripts/_llm_claude.py` -- `_invoke` is the current LLM-call
  boundary; `_get_via_psmux_flag()` reads config today and must be replaced by
  the new `dispatch` enum lookup. The subprocess and psmux branches stay.
- `plugins/mill/scripts/millpy-implement.py` -- canonical CLI shape: setup ->
  atomic pre-commit (status `running`, commit, push) -> `_render.render(...)` ->
  `_implementer_claude.run(...)` (LLM boundary) -> `_forward_output(...)`
  (parse/cleanliness/self-fix/JSON). The `prepare`/`finalize` seam goes around
  the `run()` call.
- `_implementer_common._forward_output`, `_cleanliness` -- finalize-side logic
  (parsing, cleanliness gate); reused verbatim.
- `_reviewer_single.py`, `_reviewers.py` (`load`/`resolve`), `_review_common.py`
  -- reviewer model resolution + backend that renders, dispatches, parses, and
  WRITES the review file (Decision 24). The review-file write stays in the
  backend (finalize).
- `_render.py` -- brief/prompt rendering from `plugins/mill/templates/*.md`
  (implementer-brief.md, review-prompt templates). Unchanged; `prepare` writes
  its output to a git-tracked `_mill/` file instead of returning a string.
- `_config.py` (`load_config`, unknown-key validation) and the template
  `plugins/mill/templates/mill-config.yaml` + hub `mill-config.yaml` -- add the
  `dispatch` enum, retire `via_psmux`.
- `millpy-bg.py` -- still used by subprocess/psmux modes; not used by agent mode.

Gotchas:

- The Agent tool is only callable from inside a Claude Code session (the
  orchestrator). It cannot be invoked from a detached Python worker. Therefore
  the dispatch-mode branch lives in the SKILL, not inside `_llm_claude._invoke`.
- `_llm_claude` strips git env vars (`STRIP_VARS`: GIT_DIR, GIT_WORK_TREE, ...)
  before spawning, so the child does not inherit a redirected git context. In
  agent mode the guarantee is different but sufficient: the Agent-tool sub-agent
  runs in the orchestrator session's cwd, which is the task worktree, and CC
  sessions do not set GIT_DIR/GIT_WORK_TREE -- so the implementer's `git`
  commits land on the task branch in the correct worktree. The agent-mode
  integration test MUST assert this (implementer commit appears on the task
  branch, not the hub/main). If a future orchestrator ever runs with those vars
  set, `prepare` is the place to neutralize them.
- The reviewer backend writes the review file under `_mill/reviews/`; in agent
  mode the file is written by `finalize` (Python), not the sub-agent.
- ASCII-only stdout for Python scripts (Windows cp1252); use ` -- ` and ` -> `.

## Constraints

- Hard read-only enforcement for reviewer sub-agents (no write/edit/Bash) --
  via the `mill-reviewer` custom subagent type.
- No new pip dependency.
- psmux remains a working opt-in; nothing psmux is removed.
- Behavior parity: agent mode must produce identical review files, envelopes,
  commits, and state transitions as the subprocess mode for the same input.
- Brief files are git-tracked under `_mill/`.
- All path/config/wiki access continues to obey the project invariants in
  CLAUDE.md (cache-path scripts for operational calls, `_paths` resolution,
  no direct wiki writes, junction stripping on deletion).

## Testing

- `_config` dispatch enum: unit-test that `dispatch` parses to the three values,
  defaults to `subprocess`, rejects unknown values, and that the old
  `via_psmux` key is handled per the chosen migration (rejected or mapped).
  TDD candidate.
- `prepare`/`finalize` seam per CLI: unit-test that `prepare` renders the brief
  to the expected git-tracked `_mill/` path and performs the atomic pre-commit,
  and that `finalize` given a captured sub-agent output reproduces today's JSON
  envelope, review-file write, and cleanliness verdict. These reuse existing
  in-memory/tempfile fixtures (no real git/LLM). Strong TDD candidates because
  the contract is "identical output to the current monolithic CLI".
- Reviewer read-only: assert the `mill-reviewer` subagent definition grants only
  Read/Grep/Glob (config-level test of the agent definition file).
- Model mapping: unit-test that the role's configured model name resolves to the
  model value passed to the Agent tool and that effort is omitted in agent mode.
- The Agent-tool orchestration itself (the SKILL calling the Agent tool) is
  SKILL-level and cannot be unit-tested; cover it with an integration test
  and/or a manual smoke per dispatch mode (subprocess, psmux, agent) confirming
  identical artifacts. Scenarios: implementer success, implementer transient
  stuck, reviewer APPROVE, reviewer REQUEST_CHANGES/GAPS_FOUND, mid-dispatch
  interrupt -> resume.
- Regression: existing subprocess/psmux tests must still pass unchanged.

## Q&A log

- **Q:** Mechanism -- in-session Agent tool vs Claude Agent SDK (in-process Python)? **A:** Claude Code Agent tool (in-session); the SKILL calls the Agent tool directly instead of spawning Python/`claude -p`.
- **Q:** What happens to psmux? **A:** Keep it as an opt-in dispatch mode, like `via_psmux` today, but via a config setting; the Agent tool only works for the Claude provider.
- **Q:** Is the Gemini provider in scope? **A:** Out of scope -- leave `_llm_gemini` as-is.
- **Q:** Is there still a Python CLI in agent mode? **A:** No dispatch CLI -- mill-go (etc.) calls the Agent tool itself. The brief is pre-rendered to a file; the SKILL sends only "Read this file and follow the instructions: <path>", so it never builds long prompts.
- **Q:** Which dispatch sites convert? **A:** All Claude dispatch sites (implementer, code/plan/discussion reviews, fixer, merge sub-agent).
- **Q:** Output handling (review file, status JSON, cleanliness)? **A:** Exactly the same behavior as before; the only difference is the Agent tool instead of millpy-bg. (Decision 24 read-only reviewer + backend-writes-file preserved.)
- **Q:** Config flag shape? **A:** Single `dispatch` enum (`subprocess | psmux | agent`).
- **Q:** Brief-file lifecycle? **A:** Git-tracked under `_mill/` -- easier to follow and reusable if the process crashes.
- **Q:** Model + effort mapping? **A:** Effort is not possible via the Agent tool; model is -- use the same model specified in config.
- **Q:** Reviewer tool enforcement in agent mode? **A:** The sub-agent can have tool access but must NOT write anything (hard read-only for the reviewer).
