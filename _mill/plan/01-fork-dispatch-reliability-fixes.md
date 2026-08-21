# Batch: fork-dispatch-reliability-fixes

```yaml
task: "mill-go2: fork-based dispatch reliability, shared-skill preloading, and catalog accuracy"
batch: fork-dispatch-reliability-fixes
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch closes the four implementation Decisions from `_mill/discussion.md` in a single file, `plugins/mill/skills/mill-go2/SKILL.md`: it fixes the catalog-facing `description` (#851), populates the previously-empty `## Driver preamble` with a one-time shared-skill preload (#849), bookends the implementer fork's de-briefing text and moves its Stuck-escalation self-resolve re-fire to a cold dispatch, and adds the same bookended de-briefing treatment to the fixer fork (which currently has none). All four cards are sequential edits to the same file by the same implementer session — no other file is touched, no external interface changes, and there is no next batch (this plan has only one).

There are no batch-local decisions beyond the two `## Shared Decisions` in `00-overview.md`.

## Cards

### Card 1: fix mill-go2 catalog description to name both forked roles (#851)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the YAML frontmatter at the top of the file, replace the `description:` field's value. The current value reads (single line): `Experimental, opt-in variant of the mill-go orchestrator. Forks the fixer role instead of dispatching it cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator.`

  Replace it with: `Experimental, opt-in variant of the mill-go orchestrator. Forks the implementer (every attempt) and the first fixer dispatch per scope/round, instead of dispatching cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator.`

  Do not change the `name:` field or anything else in the frontmatter.
- **Commit:** `docs(mill-go2): correct catalog description to name both forked roles (#851)`

### Card 2: preload shared skills once via Driver preamble (#849)

- **Context:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the `## Driver preamble` section's body. It currently reads just `(none)` on its own line below the heading. Replace `(none)` with the following preload instructions (keep the `## Driver preamble` heading itself unchanged):

  ```
  Before Step 0, preload skills every fork dispatch would otherwise reload independently -- run once per task session, never per-batch or per-fork:

  - `Skill(mill:code-quality)`
  - `Skill(mill:markdown)`
  - For each language detected in the worktree via `mill:workflow`'s Language Detection marker-file table: `pyproject.toml`/`setup.py`/`setup.cfg` -> `Skill(python:python-build)`, `Skill(python:python-comments)`, `Skill(python:python-testing)`; `.csproj`/`.sln` -> `Skill(csharp:csharp-build)`, `Skill(csharp:csharp-comments)`, `Skill(csharp:csharp-testing)`; `go.mod` -> `Skill(golang:golang-build)`, `Skill(golang:golang-comments)`, `Skill(golang:golang-testing)`.
  ```

  Read `plugins/mill/skills/workflow/SKILL.md`'s "## Language Detection" table (listed in this card's `Context:`) to confirm the marker-file-to-skill-name mapping above matches it exactly before writing this text -- do not invent skill names.

  Do not add or remove any other heading in the file. This section is mill-go-base's documented "Override point B" extension point (`mill-go-base/SKILL.md`'s Entry section: "treat your variant's `## Driver preamble` text as if written here, ahead of everything below") -- it already runs before Step 0 of every mill-go2 session, so no other wiring is needed to make this preload fire once, early, before any fork dispatch.
- **Commit:** `feat(mill-go2): preload shared skills once before forking (#849)`

### Card 3: bookend implementer fork de-briefing; cold-dispatch the stuck-escalation self-resolve re-fire

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the entire `**implementer**` paragraph and its four following bullets (starting at `**implementer** — replace the default \`Agent()\` call at step 2 with a fork.` and ending at the bullet whose last line reads `escalation applies; forking gets no marker.`, i.e. everything between the `### fixer` section's `Risks:` paragraph above it and the `**Known limits.**` paragraph below it) with the following text. This merges the old two-bullet split (a "Fork every fresh attempt" bullet plus a separate "De-briefing (prompt opening)" bullet) into one bullet that emits the full bookended prompt as a single literal, narrows which attempts are forked (dropping the Stuck-escalation self-resolve re-fire), and folds that re-fire into the cold-fallback bullet alongside the existing transient-retry cold fallback:

  ```
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
    escalation applies; forking gets no marker.
  ```

  Do not touch the `**Known limits.**` paragraph that follows, or anything above the `### fixer` section's `Risks:` paragraph.
- **Commit:** `fix(mill-go2): bookend implementer fork de-briefing, cold-dispatch the stuck-escalation self-resolve re-fire`

### Card 4: add bookended de-briefing text to fixer fork dispatch

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `### fixer` section, replace the paragraph that currently reads:

  ```
Otherwise: `Agent(subagent_type: "fork", prompt: "Read this file and follow the
instructions exactly: <brief_path>")`. Omit `model`/`isolation` -- a fork runs on
the driver's model regardless and must commit in the real worktree.
  ```

  with:

  ```
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
  ```

  Do not touch the paragraph above it (the `fork_attempted`/cold-dispatch condition) or the "On the first terminal failure" cold-fallback block below it -- those are unchanged by this task (see `_mill/discussion.md`'s "warm-resume-then-cold-fallback unchanged" Decision, which scopes to the implementer's `incomplete` path only and does not touch fixer's own existing cold-fallback mechanics).
- **Commit:** `fix(mill-go2): add bookended de-briefing text to fixer fork dispatch`

## Batch Tests

`verify:` runs the full unit-test suite (`run-all.py`, unbounded, no `--only` scoping) as a pure regression guard. This batch edits only `plugins/mill/skills/mill-go2/SKILL.md`, which is prose consumed by an LLM orchestrator session, not by any script under `plugins/mill/unit_tests/` -- no existing test exercises this file's content, so there is no scoped subset of tests to target with `--only`. The full suite confirms these edits introduce no incidental breakage (e.g. if any script happens to parse `SKILL.md` frontmatter) without claiming positive coverage of the prompt-text changes themselves, which (per `_mill/discussion.md`'s Testing section) cannot be verified synchronously -- efficacy against the non-deterministic identity-confusion failure is judged empirically by the absence of further GitHub issues over time, outside this task's scope. This is the documented `verify-full-suite` skip-check escape hatch's justification case; `mill-plan` applies `--skip-check verify-full-suite` when self-validating this plan.

Manual cross-reference review (also per the discussion's Testing section, not an automated check): confirm each card's replacement text keeps the `Agent()` call shape (`subagent_type`, omitted `model`, the `prompt` argument) consistent with `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" → Override point A contract, and that Card 2's Driver-preamble text is read as "Override point B" content (runs before Step 0, ahead of everything else) rather than as a new independent phase.
