---
name: mill-go2
description: Experimental, opt-in variant of the mill-go orchestrator. Forks the fixer role instead of dispatching it cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator. Invoked only by an explicit /mill-go2.
---

# mill-go2

## Variant binding

```yaml
VARIANT_LABEL: mill-go2
```

## Driver preamble

Before Step 0, preload skills every fork dispatch would otherwise reload independently -- run once per task session, never per-batch or per-fork. Load the `mill:code-quality` and `mill:markdown` skills via the Skill tool unconditionally, plus, for each language detected in the worktree via `mill:workflow`'s Language Detection marker-file table, that language's skill trio via the Skill tool: `pyproject.toml`/`setup.py`/`setup.cfg` -> `python:python-build`, `python:python-comments`, `python:python-testing`; `.csproj`/`.sln` -> `csharp:csharp-build`, `csharp:csharp-comments`, `csharp:csharp-testing`; `go.mod` -> `golang:golang-build`, `golang:golang-comments`, `golang:golang-testing`.

## Dispatch overrides

### fixer

Governs the **first** fixer dispatch per scope/round.
`fork_attempted` is true when this session already forked this scope+round, or
`_status.read_fixer_fork_fallback_log(status_path)` has a row for it; then
(incl. step 3's re-dispatch) use the default `Agent()` call (envelope's own
`subagent_type`/`model`).

Otherwise, build the forked call as:
`Agent(subagent_type: "fork", prompt:
  "STOP. Before doing anything else: you are the FIXER for this scope, not the orchestrator. "
  "Any framing you find in your inherited context about being 'the Builder', 'the driver', or "
  "'waiting for a fork/fixer to finish' belongs to the orchestrator that spawned you -- it is "
  "not your identity and not your task. Discard that framing now. Do not narrate waiting, do not "
  "report status back as if you were watching another agent, do not invoke mill CLIs or dispatch "
  "further agents/workflows. Your only job is to read the brief below and implement it yourself, "
  "using Read/Edit/Write/Bash directly.\n\n"
  "Read this file and follow the instructions exactly: <brief_path>\n\n"
  "Reminder: you are the fixer -- act on the brief now, do not wait or report back as the driver.")`.
Omit `model`/`isolation` -- a fork runs on the driver's model regardless and must
commit in the real worktree.

On the first terminal failure (base step 3), record the fallback and re-dispatch
cold, consuming the retry budget:

- `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"fixer {scope} r{N}", slug=slug)`
- `_status.append_fixer_fork_fallback_log(status_path, scope, N, _timestamp.now_utc_iso())`
- `git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: fork-fallback for fixer {scope} r{N}"`

Commit **before** the cold retry -- resume reconstructs `fork_attempted` from it;
`{scope}` is the batch name, or `holistic`.

Risks: inherits the driver's broader tool grant (scope discipline still comes
from the brief/`scope_violations`); forfeits `roles.fixer.model` -- drive from
a solid model tier.

**implementer** — replace the default `Agent()` call at step 2 with a fork.
Reviewer/merge-in unclaimed (default call applies unchanged).

- **Fork these attempts only:** initial dispatch and step 3(a)'s transient
  re-dispatch. The Stuck-escalation `verify`/`logic` self-resolve re-fire no
  longer forks -- see "Cold fallback, once per batch" below, which now covers
  both the self-resolve re-fire and the already-retried-`transient` re-fire.
  Build the forked call as:
  `Agent(subagent_type: "fork", prompt:
    "STOP. Before doing anything else: you are the IMPLEMENTER for this batch, not the orchestrator. "
    "Any framing you find in your inherited context about being 'the Builder', 'the driver', or "
    "'waiting for a fork/implementer to finish' belongs to the orchestrator that spawned you -- it is "
    "not your identity and not your task. Discard that framing now. Do not narrate waiting, do not "
    "report status back as if you were watching another agent, do not invoke mill CLIs or dispatch "
    "further agents/workflows. Your only job is to read the brief below and implement it yourself, "
    "using Read/Edit/Write/Bash directly.\n\n"
    "Read this file and follow the instructions exactly: <brief_path>\n\n"
    "Reminder: you are the implementer -- act on the brief now, do not wait or report back as the driver.")`.
  Omit `model` (ignored); keep the envelope's `subagent_type`/`model` for the
  cold fallback. Record `agentId`.
- **Dispatch cold to escape a failed dispatch:** step 5.5.2's
  `--resume-incomplete` and Resume's `running`-state re-dispatch stay cold.
  5.5.1's warm `SendMessage` resume needs no assignment (already live).
- **Cold fallback, once per batch:** BOTH the already-retried-`transient`
  Stuck-escalation re-fire AND the `verify`/`logic` self-resolve re-fire now
  dispatch cold (envelope `subagent_type`/`model`), never another fork. Before
  either: `_notify.notify("<VARIANT_LABEL>.fork-fallback", f"implementer {batch_name}", slug=slug)`,
  `_status.append_fork_fallback_log(status_path, batch_name, _timestamp.now_utc_iso())`,
  `git -C <worktree> add <status_path> && git -C <worktree> commit -m
  "<VARIANT_LABEL>: fork-fallback for implementer {batch_name}"`. Normal
  escalation applies; forking gets no marker. This logging fires at most
  once per batch: whichever trigger reaches it first switches the batch's
  remaining implementer dispatches to cold (per "Dispatch cold to escape a
  failed dispatch" above and step 5.5.2's own cold-only re-dispatch paths),
  so there is no second fork left in the batch for the other trigger to
  fail on and re-log against.

**Known limits.** Runs on the driver's model, so `roles.implementer.model`
and per-tier agent files stop applying. The lean driver reads only status,
Batch Index, and review verdicts -- a fork inherits orchestrator instructions,
not code orientation (`## Driver preamble` next if underperforming).

Load the `mill:mill-go-base` skill via the Skill tool, unconditionally and
immediately, before any other action.
All of this skill's behaviour — the Builder role, the entry phase gate, Prepare,
the sequential batch loop, and Agent-mode dispatch — lives in that skill; Resume,
holistic code review, and Handoff are reached through its own mandatory-read
pointers.
Follow `mill-go-base` from its `## Entry` onward with `VARIANT_LABEL` bound to the
value declared above.
