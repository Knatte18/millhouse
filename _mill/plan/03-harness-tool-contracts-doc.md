# Batch: harness-tool-contracts-doc

```yaml
task: Self-discovered mill-go/mill-plan skill-doc and behavior gaps
batch: harness-tool-contracts-doc
number: 3
cards: 4
verify: null
depends-on: [1, 2]
```

## Batch Scope

Closes #755: creates a new standalone reference doc, `plugins/mill/docs/harness-tool-contracts.md`, recording the confirmed `Agent` vs `Monitor` notification/return-shape contracts that are currently documented only as scattered inline prose across four files, and adds a one-line pointer to the new doc from each of those four locations. None of the four inline copies are replaced or deleted — each remains load-bearing for its own skill's logic; the new doc only consolidates and cross-references them. Depends on Batch 1 and Batch 2 because two of the four pointer edits land in files those batches also edit (`mill-plan/SKILL.md`, `mill-go/SKILL.md`) — see the overview's "sequential ordering" Shared Decision. Documentation only; no runnable surface.

## Cards

### Card 5: Create the harness-tool-contracts.md reference doc

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/cli/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/templates/review-output.schema.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Create `plugins/mill/docs/harness-tool-contracts.md` (creating the `plugins/mill/docs/` directory) with this exact content:

  ```
  # Harness Tool Contracts

  This file records confirmed return/notification shapes for harness
  tools used by mill orchestrator skills (mill-plan, mill-go). These
  shapes were confirmed via live spikes and are not documented by the
  harness itself. Four skill files already carry inline copies of this
  material, load-bearing for each one's own logic — this doc
  consolidates and cross-references them; it does not replace any of
  them.

  ---

  ## Agent tool

  A background subagent dispatched via `Agent(subagent_type: ...,
  model: ..., prompt: ...)`:

  - Returns immediately with a launch acknowledgement carrying an
    `agentId` — the harness runtime handle for the live subagent.
    Retain it: it is what `SendMessage`/`TaskOutput` address to
    warm-resume or probe the same session.
  - Delivers exactly ONE combined-result `<task-notification>` when the
    subagent finishes, is stopped, or is interrupted — the
    notification payload carries the subagent's final message text.
  - A background agent IS a detached worker and CAN be stopped or
    interrupted independently of the orchestrator; a stopped/
    interrupted notification can be stale (an agent reported "killed"
    can still be running and deliver a real completion notification
    later). Probe with `TaskOutput(task_id: <agentId>, block: false)`
    before trusting a stop/interrupt notification as terminal.
  - `agentId` is distinct from any LLM-conversation `session_id` /
    `implementer_session` recorded in `status.md` — the former is the
    harness worker handle, the latter identifies the LLM conversation
    for finalize/cleanup purposes.

  See `mill-go/SKILL.md`'s "## Agent-mode dispatch" section for the
  full dispatch/recovery pattern built on this contract.

  ## Monitor tool

  A poll script run via `Monitor(command: ..., persistent: true, ...)`:

  - Delivers ONE `<task-notification>` PER stdout line the script
    emits, each carrying that line's content in an `<event>` tag.
  - Followed by a SEPARATE, terminal `<status>completed</status>`
    notification once the script's process actually exits — this one
    carries no `<event>` tag and no further information.
  - This two-notification shape (one-per-line, then a separate
    event-less terminal notification) is NOT the same shape as
    `Agent`'s single combined-result notification. Do not conflate the
    two when writing a new entry-gate wait or similar poll-and-notify
    pattern.
  - Runs bash, not PowerShell, regardless of the operator's terminal —
    see `cli/SKILL.md`.

  See `mill-go/SKILL.md`'s "### Entry-gate wait for upstream mill-plan"
  section and `mill-plan/SKILL.md`'s "### Entry-gate wait for upstream
  mill-start" section for two independent consumers of this contract.
  ```

  Follow the plain-markdown, `---`-divided reference-doc style of
  `plugins/mill/templates/review-output.schema.md` (H1 title, no
  frontmatter — this is a reference doc, not a task-state or template
  file).

- **Commit:** `docs(mill): add harness-tool-contracts.md reference doc (#755)`

### Card 6: Add a pointer to the new doc from cli/SKILL.md

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/cli/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In the `## PowerShell` section, locate the bullet beginning "**Commands CC executes via the Monitor tool:**" (currently ending "...PS syntax in a Monitor command yields exit 127 with no warning."). Append one sentence to the end of that same bullet: " See `plugins/mill/docs/harness-tool-contracts.md` for the confirmed `Agent`/`Monitor` notification-shape contract." Do not otherwise change the bullet or any other line in the file.

- **Commit:** `docs(cli): point to harness-tool-contracts.md (#755)`

### Card 7: Add pointers to the new doc from mill-go/SKILL.md

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Two separate insertions in this file, both one-line pointers to the new `plugins/mill/docs/harness-tool-contracts.md`:

  1. Immediately after the `## Agent-mode dispatch` heading (and before the existing sentence "When `dispatch == agent`, follow this three-step pattern at each dispatch point:"), insert a new blockquote line reading exactly: "> See `plugins/mill/docs/harness-tool-contracts.md` for the confirmed `Agent` tool notification/return-shape contract this section is built on." followed by a blank line.
  2. In the `### Entry-gate wait for upstream mill-plan` subsection, locate the sentence ending "...the same `task_id` carries no further information and needs no separate branch." (immediately before "Branch on the `<event>` content:"). Insert one new sentence between them: "See `plugins/mill/docs/harness-tool-contracts.md` for this contract's canonical write-up." — so the paragraph now reads "...needs no separate branch. See `plugins/mill/docs/harness-tool-contracts.md` for this contract's canonical write-up. Branch on the `<event>` content:".

  Do not change the load-bearing inline contract prose itself in either location — only insert the pointer.

- **Commit:** `docs(mill-go): point to harness-tool-contracts.md (#755)`

### Card 8: Add a pointer to the new doc from mill-plan/SKILL.md

- **Context:**
  - `plugins/mill/docs/harness-tool-contracts.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In the `### Entry-gate wait for upstream mill-start` section, locate the sentence ending "...the same `task_id` carries no further information and needs no separate branch." (immediately before "Branch on the `<event>` content:" — this is the near-verbatim duplicate of `mill-go/SKILL.md`'s own two-notification-shape paragraph). Insert one new sentence between them: "See `plugins/mill/docs/harness-tool-contracts.md` for this contract's canonical write-up." — so the paragraph now reads "...needs no separate branch. See `plugins/mill/docs/harness-tool-contracts.md` for this contract's canonical write-up. Branch on the `<event>` content:". Do not change the load-bearing inline contract prose itself — only insert the pointer.

- **Commit:** `docs(mill-plan): point to harness-tool-contracts.md (#755)`

## Batch Tests

Documentation only — no runnable surface. Correctness gate is plan review (does the plan describe faithful consolidation with no new claims) and code review of the actual diff (does the new doc's content match what's already stated inline in the four source locations).
