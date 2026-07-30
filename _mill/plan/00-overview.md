# Plan: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
task: Blocking phase-wait gate for mill-plan/mill-go chaining
slug: phase-wait-gate
approved: false
started: 20260730-192330
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
    name: phase-wait-foundation
    file: 01-phase-wait-foundation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py
  - number: 2
    name: mill-go-entry-wait
    file: 02-mill-go-entry-wait.md
    depends-on: [1]
    verify: null
  - number: 3
    name: mill-plan-entry-wait
    file: 03-mill-plan-entry-wait.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: unit conversion happens at the SKILL.md call site, never inside the helper

- **Decision:** `pipeline.entry_wait_timeout_minutes` is stored in minutes.
  `_phase_wait.build_wait_command`'s `giveup_s` parameter takes only seconds
  and performs no unit conversion itself. Each SKILL.md call site computes
  `giveup_s = entry_wait_timeout_minutes * 60` immediately before calling
  `build_wait_command`.
- **Rationale:** keeps the helper a pure, unit-unambiguous function that the
  unit test can exercise directly with plain integers, with no ambiguity
  about which unit a bare `giveup_s` argument represents.
- **Applies to:** mill-go-entry-wait, mill-plan-entry-wait.

### Decision: poll interval is a hardcoded literal, never read from config

- **Decision:** Both SKILL.md call sites pass the literal integer `10` as
  `poll_interval_s` to `build_wait_command`. No config key exposes this
  value.
- **Rationale:** 10s is responsive without spamming and matches the
  original brief's own example; not worth a config key per the task's
  discussion-phase scope decision.
- **Applies to:** mill-go-entry-wait, mill-plan-entry-wait.

### Decision: Monitor's task-identifier and notification-shape contract, empirically verified

- **Decision:** the `Monitor` tool's initial call result exposes a task
  identifier (analogous to the Agent tool's `agentId`, usable as the
  `task_id` argument to `TaskOutput`/`TaskStop`), and a `Monitor` run of
  the phase-wait poll script (which always echoes exactly one line before
  exiting) delivers exactly two `<task-notification>`s: first a per-line
  event notification carrying the echoed line in an `<event>` tag, then a
  separate terminal notification (`<status>completed</status>`, no
  `<event>` tag) once the script process exits. The orchestrator acts on
  the first notification's `<event>` content and needs no separate
  handling for the second.
- **Verified:** this shape was confirmed by a live `Monitor` spike run
  during this task's plan review (round 1), not assumed from documentation
  or inferred solely from the structurally-different Agent-tool
  notification contract this task's discussion phase had cited as a
  precedent — a real `Monitor` call with a two-line script produced two
  distinct per-line event notifications followed by one terminal
  completion notification, and the tool's own launch confirmation
  included a task identifier in the same position/role the Agent tool's
  `agentId` occupies.
- **Rationale:** plan review round 1 flagged the original discussion-phase
  assumption ("mirrors the Agent tool's `agentId`/notification contract")
  as unverified in-repo. Rather than defer this to an execution-time spike
  (as the reviewer's fix suggested), the plan-writing session ran the
  spike directly and recorded the actual confirmed shape here, so batches
  2/3's implementer works from verified behavior instead of an assumption.
- **Applies to:** mill-go-entry-wait, mill-plan-entry-wait.

### Decision: `pipeline.entry_wait` / `pipeline.entry_wait_timeout_minutes` are read at the point of use

- **Decision:** Both new config keys are read with
  `(cfg.get("pipeline") or {}).get("entry_wait", True)` and
  `(cfg.get("pipeline") or {}).get("entry_wait_timeout_minutes", 120)`
  directly at the entry-gate phase-table check, not threaded through an
  earlier config-loading step as a named local variable.
- **Rationale:** matches the existing defensive-read pattern already used
  in `mill-go/SKILL.md` for `pipeline.done_gate_baseline_preflight`
  (`(cfg.get("pipeline") or {}).get("done_gate_baseline_preflight", False)`) —
  no new config-reading convention is introduced.
- **Applies to:** mill-go-entry-wait, mill-plan-entry-wait.

### Decision: retain the Monitor task handle for the duration of the wait

- **Decision:** immediately after calling the `Monitor` tool, record the
  `task_id` it returns in a local orchestrator variable and retain it until
  the wait resolves (`READY` / `BLOCKED` / `TIMEOUT` / harness-level stop).
- **Rationale:** mirrors the existing "record the `agentId`" convention in
  `mill-go/SKILL.md`'s "## Agent-mode dispatch" section (`## Agent-mode
  dispatch`, step 3) and is required so a harness-level stop of the wait
  (via `TaskStop`) can be distinguished from `READY`/`BLOCKED`/`TIMEOUT` and
  handled per the "operator interrupted the wait" case in each batch file.
- **Applies to:** mill-go-entry-wait, mill-plan-entry-wait.

### Decision: on `READY`, re-run the entry-gate phase check from scratch

- **Decision:** on receiving the `READY` notification, do not act on the
  wait outcome directly. Re-read `status_path` fresh (via
  `_status.read_full`) and re-evaluate the whole phase table from its top,
  exactly as on a normal fresh invocation of the skill.
- **Rationale:** matches this codebase's consistent "always re-read status
  fresh, never trust stale in-context state" convention used throughout
  `mill-go/SKILL.md` and `mill-plan/SKILL.md` (e.g. mill-go's own *Resume*
  path). Cheap defensive correctness against the small window between the
  poll script's last `grep` and the notification actually arriving.
- **Applies to:** mill-go-entry-wait, mill-plan-entry-wait.

### Decision: no `sed`, ASCII-only output

- **Decision:** the poll script uses only `grep`, bash parameter expansion,
  and `echo` — never `sed`. Every `echo`'d string (`READY`, `BLOCKED: ...`,
  `TIMEOUT ...`) is ASCII-only.
- **Rationale:** matches CLAUDE.md's project-wide "Don't use `sed`" rule and
  its "`print()`/`_log()` output: ASCII only" convention (Windows cp1252
  crashes on non-ASCII stdout).
- **Applies to:** phase-wait-foundation.

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path
across every batch, sorted alphabetically (Move **source** paths are
excluded — they disappear, like `Deletes:` tokens). Cards are the
source of truth; this section is the input `_plan_validate.py`'s
`all-files-touched-mismatch` check cross-references against the derived
union of every card's `Edits:`/`Creates:`/Move-target paths, to catch
drift between the hand/agent-maintained list here and that derived
union._

- `mill-config.yaml`
- `plugins/mill/scripts/_phase_wait.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-phase-wait.py`
