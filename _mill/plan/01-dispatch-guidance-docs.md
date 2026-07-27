# Batch: dispatch-guidance-docs

```yaml
task: 'Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output'
batch: dispatch-guidance-docs
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch adds two independent guidance notes surfaced by GitHub issues #711 and #710 — both are prose-only edits to existing documentation files, with no runnable surface. Card 1 adds a hard-constraint bullet to `CLAUDE.md` distinguishing "read source via `${CLAUDE_PLUGIN_ROOT}` for script invocation" from "read/verify actual source code via the task-worktree path" (per `_mill/discussion.md`'s "cache-vs-worktree guidance location" Decision). Card 2 adds a caution note to `mill-start/SKILL.md`'s existing "Sub-investigation guidance" paragraph about fork directive-echo (per `_mill/discussion.md`'s "fork directive-echo mitigation" Decision). Neither card produces an external interface for a later batch to consume — both are terminal documentation edits. No batch-local decisions beyond the two Shared Decisions in the overview.

## Cards

### Card 1: Add cache-vs-worktree source-read hard constraint to CLAUDE.md

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `CLAUDE.md`'s `## Hard constraints` section, add a new bullet immediately after the existing `**\${CLAUDE_PLUGIN_ROOT}\` for all intra-plugin paths.**` bullet (the one reading "Never `plugins/mill/…` — external repos have no millhouse checkout. Write `${CLAUDE_PLUGIN_ROOT}` literally in Bash tool calls — do NOT read or memorize its value; let the shell expand it at runtime."). The new bullet must: (1) open with a bolded short label analogous to the existing bullets' style (e.g. `**Task-worktree path for source verification, not \`${CLAUDE_PLUGIN_ROOT}\`.**`); (2) state that reading actual source code to verify plan/discussion accuracy — the code a plan is about to edit, as distinct from invoking a script — must target the task-worktree path, never the plugin cache; (3) state that in this self-hosted repo (millhouse developing millhouse) the cache and the worktree can silently diverge, and that reading stale cache content during plan-writing has previously produced an incorrect conclusion requiring mid-plan rework; (4) explicitly note that `${CLAUDE_PLUGIN_ROOT}` remains correct for script invocation — this bullet narrows only the source-code-verification case, it does not revise the existing bullet above it. Do not edit any other bullet in `## Hard constraints`.
- **Commit:** `docs(claude-md): distinguish worktree source reads from CLAUDE_PLUGIN_ROOT script invocation`

### Card 2: Add fork-echo caution note to mill-start/SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-start/SKILL.md`'s `### Phase: Explore` section, Step 3 ("Explore the codebase"), add a new paragraph immediately after the existing "**Sub-investigation guidance (not a mandate).**" paragraph — the one whose final sentence reads "...which is exactly why none of the three fork disqualifiers (see \"Why not fork?\" in `mill-go/SKILL.md`'s \"## Agent-mode dispatch\") apply here." The new paragraph must: (1) open with a bolded label, e.g. `**Fork echo caution.**`; (2) warn that a fork dispatched via `Agent(subagent_type: "fork")` shortly after the parent has just produced a similarly-shaped text block (e.g. the Step 2 scope digest) may, on its first turn, echo/restate that block instead of executing the assigned investigation directive; (3) instruct the orchestrator to check the fork's first response for grounded findings (specific file:line citations, quoted code) before trusting it as complete; (4) instruct that if the response is a restatement rather than grounded findings, the orchestrator should `SendMessage` the same fork an explicit corrective directive (e.g. telling it to stop restating context and perform the investigation) rather than accepting the echoed response. Do not modify the existing "Sub-investigation guidance" paragraph's bullet list or its final sentence — only insert the new paragraph after it.
- **Commit:** `docs(mill-start): warn about fork echoing parent context instead of executing its directive`

## Batch Tests

`verify: null` — both cards are documentation-only edits (Markdown prose) with no executable behavior to assert against; there is no runnable surface for this batch.
