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

This batch closes the four implementation Decisions from `_mill/discussion.md` in a single file, `plugins/mill/skills/mill-go2/SKILL.md`: it bookends the implementer fork's de-briefing text and moves its Stuck-escalation self-resolve re-fire to a cold dispatch, adds the same bookended de-briefing treatment to the fixer fork (which currently has none), populates the previously-empty `## Driver preamble` with a one-time shared-skill preload (#849), and fixes the catalog-facing `description` (#851). All four cards are sequential edits to the same file by the same implementer session — no other file is touched, no external interface changes, and there is no next batch (this plan has only one).

Card order matters here: the catalog-description card (Card 4) states the implementer's narrowed forked set in prose, so it must commit at or after the card that actually narrows that forked set (Card 1) — otherwise the file's frontmatter and body briefly contradict each other between commits.

There are no batch-local decisions beyond the two `## Shared Decisions` in `00-overview.md`.

## Cards

### Card 1: bookend implementer fork de-briefing; cold-dispatch the stuck-escalation self-resolve re-fire

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
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
    escalation applies; forking gets no marker. This logging fires at most
    once per batch: whichever trigger reaches it first switches the batch's
    remaining implementer dispatches to cold (per "Dispatch cold to escape a
    failed dispatch" above and step 5.5.2's own cold-only re-dispatch paths),
    so there is no second fork left in the batch for the other trigger to
    fail on and re-log against.
  ```

  Do not touch the `**Known limits.**` paragraph that follows, or anything above the `### fixer` section's `Risks:` paragraph.
- **Commit:** `fix(mill-go2): bookend implementer fork de-briefing, cold-dispatch the stuck-escalation self-resolve re-fire`

### Card 2: preload shared skills once via Driver preamble (#849)

- **Context:**
  - `plugins/mill/skills/workflow/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/unit_tests/test-mill-go-variants.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the `## Driver preamble` section's body. It currently reads just `(none)` on its own line below the heading. Replace `(none)` with the following preload instructions (keep the `## Driver preamble` heading itself unchanged):

  ```
  Before Step 0, preload skills every fork dispatch would otherwise reload independently -- run once per task session, never per-batch or per-fork. Load the `mill:code-quality` and `mill:markdown` skills via the Skill tool unconditionally, plus, for each language detected in the worktree via `mill:workflow`'s Language Detection marker-file table, that language's skill trio via the Skill tool: `pyproject.toml`/`setup.py`/`setup.cfg` -> `python:python-build`, `python:python-comments`, `python:python-testing`; `.csproj`/`.sln` -> `csharp:csharp-build`, `csharp:csharp-comments`, `csharp:csharp-testing`; `go.mod` -> `golang:golang-build`, `golang:golang-comments`, `golang:golang-testing`.
  ```

  Read `plugins/mill/skills/workflow/SKILL.md`'s "## Language Detection" table (listed in this card's `Context:`) to confirm the marker-file-to-skill-name mapping above matches it exactly before writing this text -- do not invent skill names.

  Do not add or remove any other heading in the file. This section is mill-go-base's documented "Override point B" extension point -- read `plugins/mill/skills/mill-go-base/SKILL.md`'s Entry section (listed in this card's `Context:`) before writing this card's edit and confirm it verbatim states: "Override point B: treat your variant's `## Driver preamble` text as if written here, ahead of everything below; if your variant declared no such section, halt ... A variant whose `## Driver preamble` section contains only `(none)` has declared the section and contributes no text; that is not a halt." This confirms the block runs before Step 0 of every mill-go2 session (ahead of Prepare and the Execute loop where forking happens), so no other wiring in `mill-go-base/SKILL.md` or elsewhere is needed to make this preload fire once, early, before any fork dispatch -- do not edit `mill-go-base/SKILL.md` itself.
- **Commit:** `feat(mill-go2): preload shared skills once before forking (#849)`

### Card 3: add bookended de-briefing text to fixer fork dispatch

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

### Card 4: fix mill-go2 catalog description to name both forked roles (#851)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the YAML frontmatter at the top of the file, replace the `description:` field's value. The current value reads (single line): `Experimental, opt-in variant of the mill-go orchestrator. Forks the fixer role instead of dispatching it cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator. Invoked only by an explicit /mill-go2.`

  Replace it with: `Experimental, opt-in variant of the mill-go orchestrator. Forks the implementer (every batch's initial dispatch and transient re-dispatch) and the first fixer dispatch per scope/round, instead of dispatching cold; otherwise identical to /mill-go, so fork-dispatch experiments never destabilise the production orchestrator. Invoked only by an explicit /mill-go2.`

  This wording must match Card 1's narrowed forked set exactly (initial dispatch and step 3(a)'s transient re-dispatch only -- the Stuck-escalation self-resolve re-fire no longer forks per Card 1, which commits before this card) rather than the plain "(every attempt)" phrasing originally proposed, which would misrepresent Card 1's own change and defeat the #851 catalog-accuracy goal this card exists to fix. This card is deliberately ordered last so the file's frontmatter and body are never briefly contradictory between commits.

  Do not change the `name:` field or anything else in the frontmatter.
- **Commit:** `docs(mill-go2): correct catalog description to name both forked roles (#851)`

## Scope Extension (post-approval)

`plugins/mill/unit_tests/test-mill-go-variants.py` was discovered mid-implementation to
directly exercise `plugins/mill/skills/mill-go2/SKILL.md`'s content -- contrary to this
batch's original "no existing test exercises this file's content" premise (see `## Batch
Tests` below). Specifically: `_check_variants_carry_no_machinery` enforces a 4096-byte
ceiling on the variant file (breached starting at Card 1's bookended de-briefing text), and
`_check_mill_go2_declares_fork_override` asserts `## Driver preamble`'s first non-blank line
is the literal `(none)` (contradicted by Card 2's preload text). Both assertions were locking
in the pre-task state of this same file as a regression guard, not asserting an unrelated
invariant -- they must be updated to match this task's intended end state: raise the byte
ceiling to accommodate the now-larger, intentionally thicker variant file, and assert the
`## Driver preamble` body contains the preload instructions (starting with "Before Step 0")
instead of `(none)`.

## Batch Tests

`verify:` runs the full unit-test suite (`run-all.py`, unbounded, no `--only` scoping) as a pure regression guard. This batch edits only `plugins/mill/skills/mill-go2/SKILL.md`, which is prose consumed by an LLM orchestrator session, not by any script under `plugins/mill/unit_tests/` -- no existing test exercises this file's content, so there is no scoped subset of tests to target with `--only`. The full suite confirms these edits introduce no incidental breakage (e.g. if any script happens to parse `SKILL.md` frontmatter) without claiming positive coverage of the prompt-text changes themselves, which (per `_mill/discussion.md`'s Testing section) cannot be verified synchronously -- efficacy against the non-deterministic identity-confusion failure is judged empirically by the absence of further GitHub issues over time, outside this task's scope. This is the documented `verify-full-suite` skip-check escape hatch's justification case; `mill-plan` applies `--skip-check verify-full-suite` when self-validating this plan.

Manual cross-reference review (also per the discussion's Testing section, not an automated check): confirm each card's replacement text keeps the `Agent()` call shape (`subagent_type`, omitted `model`, the `prompt` argument) consistent with `mill-go-base/SKILL.md`'s "## Agent-mode dispatch" → Override point A contract, and that Card 2's Driver-preamble text is read as "Override point B" content (runs before Step 0, ahead of everything else) rather than as a new independent phase.
