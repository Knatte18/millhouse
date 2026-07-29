# Batch: skill-doc-gaps

```yaml
task: "mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push"
batch: "skill-doc-gaps"
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

This batch resolves two small, mechanical documentation gaps in mill-v2's orchestrator-tier `SKILL.md` files, self-discovered during an autonomous `/mill-plan` run and filed as GitHub issues #747/#748 (both closed, consolidated into task `mill-plan-skill-doc-gaps`). Card 1 edits `plugins/mill/skills/mill-plan/SKILL.md`: inserts a new `Step 0` in `## Entry` that loads `mill:conversation` (mirroring `mill-start/SKILL.md`'s own `Step 0`), adds/normalizes "Push." + `-C <worktree>` wording across five commit-producing steps (Phase: Plan's commit, the plan-review-skip branch, both Step 1.5 validator-fix branches, and step 4d's commit bullet), and reformats the max-rounds-escape prompt into `mill:conversation`'s numbered/recommended-first format. Card 2 edits `plugins/mill/skills/mill-go/SKILL.md`: inserts a new `Step 0b` immediately after the existing `Step 0`, loading `mill:conversation` (mirroring mill-go's own `4.5.` decimal-substep-in-Entry precedent). Both cards are pure prose edits with no executable code path and no external interface for a downstream batch to consume — this is the only batch in the plan. No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 1: mill-plan/SKILL.md — Step 0 load, push wording, max-rounds prompt reformat

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/conversation/SKILL.md`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Make the following seven surgical text replacements in `plugins/mill/skills/mill-plan/SKILL.md`. Each is given as an exact old block to find and the exact new block to replace it with. Every "Find:" block below is copied byte-for-byte from the current source file (no extra indentation added for this plan's own list nesting) — use it verbatim to locate the target text. Every "Replace with:" block is new authored text (not present in source today) to paste in as-given. Do not touch any other text in the file.

  **1. Insert Step 0 at the top of `## Entry`** (before the existing step 1). Find:
```
## Entry

1. Resolve and bind the path variables:
```
  Replace with:
```
## Entry

**Step 0: Load `mill:conversation`.** Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately — before any other Entry step or phase. Phase: Plan Review's max-rounds-escape prompt (step 6) is an operator-facing prompt that depends on `mill:conversation`'s numbered-options rule (banning `AskUserQuestion`) being active, so it must be loaded before that prompt can be built.

1. Resolve and bind the path variables:
```
  This mirrors `mill-start/SKILL.md`'s own `**Step 0: Load \`mill:conversation\`.**` Entry step in phrasing style (imperative, one short paragraph, names why this file's prompts depend on it). It is a bolded-label paragraph, not a numbered list item — the existing numbered steps 1-4 in this Entry section are NOT renumbered (this exactly matches how `mill-go/SKILL.md`'s own `**Step 0: Verify \`CLAUDE_PLUGIN_ROOT\`.**` already precedes its numbered steps 1-4 without being part of that numbering).

  **2. Phase: Plan's commit step — add push, normalize `-C <worktree>`.** Find:
```
**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git commit -m "mill-plan: write plan for {slug}"`.
```
  Replace with:
```
**Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: write plan for {slug}"`. Push.
```

  **3. Plan-review-skip branch commit — normalize `-C <worktree>` only** (this branch already says "push"; do not add a second "push" word). Find:
```
set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff.
```
  Replace with:
```
set overview frontmatter `approved: true` via direct Edit, commit on the task branch (`git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: skip plan review (reviewer null or rounds 0) for {slug}"`), push, and proceed straight to Handoff.
```

  **4. Step 1.5 subprocess/psmux branch validator-fix commit — add push.** The find/replace text below has the source's own 3-space indent (it sits inside the "1.5." sub-section) — preserve those 3 leading spaces exactly, they are not this plan's list-nesting. Find:
```
   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"` and re-runs the CLI. The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).
```
  Replace with:
```
   After applying mechanical fixes for every error in the JSON, mill-plan commits the fix(es) on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`. Push. Then re-runs the CLI. The commit message uses `validator-fix` to distinguish it from `plan-fix-r{N}` commits (which are LLM-fix-pass commits).
```

  **5. Step 1.5 Agent-mode branch validator-fix commit — add push.** Same 3-space source indent as edit 4 above (a nested bullet under "Agent-mode prepare-envelope handling:"). Find:
```
   - **If `errors` key is present** (validator failure): The envelope contains `{"errors": [...], "summary": "..."}`. Parse the JSON and apply one mechanical fix per error dict, using the fix table in Step 1.5 below as the source of truth for all fix semantics. After fixes, commit on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`. Then re-invoke the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize; the same cycle repeats). Use the two-pass cap: if the second prepare invocation also fails validator, halt with `BLOCKED: plan-validate non-progress` and write the unresolved errors to the user.
```
  Replace with:
```
   - **If `errors` key is present** (validator failure): The envelope contains `{"errors": [...], "summary": "..."}`. Parse the JSON and apply one mechanical fix per error dict, using the fix table in Step 1.5 below as the source of truth for all fix semantics. After fixes, commit on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`. Push. Then re-invoke the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize; the same cycle repeats). Use the two-pass cap: if the second prepare invocation also fails validator, halt with `BLOCKED: plan-validate non-progress` and write the unresolved errors to the user.
```

  **6. Step 4d's commit bullet — add push, normalize `-C <worktree>`.** Same 3-space source indent (a nested bullet under step 4d). Find:
```
   - Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.
```
  Replace with:
```
   - Commit on the task branch: `git -C <worktree> add <plan_dir> <reviews_dir> <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-plan: plan-fix round {N} for {slug}"`. Push.
```

  **7. Max-rounds-escape prompt (step 6) — reformat from lettered `A)/B)/C)` + trailing `Recommended:` line into `mill:conversation`'s numbered/recommended-first format.** Same 3-space source indent (a nested blockquote under step 6). Find:
```
   > After {N} rounds, {M} BLOCKING findings remain unresolved (blocking_count from latest round's review JSON). Options:
   > A) Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > B) Shallow — one more review round. Invoke: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
   > C) Override — accept findings and proceed to mill-go anyway.
   > Recommended: {A/B/C} based on {analysis of remaining findings}.

   Wait for the user's choice. A → halt and tell user to check out fresh after they revise. B → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max). C → set `approved: true` and proceed to Handoff.
```
  Replace with:
```
   > After {N} rounds, {M} BLOCKING findings remain unresolved (blocking_count from latest round's review JSON). Present these three as a numbered list per `mill:conversation`'s convention: determine the recommended option from {analysis of remaining findings}, list it first as `1)` with `(Recommended)` appended to its label, then list the remaining two as `2)` and `3)` in their order below.
   > - Deep problems — rethink approach. Go back to mill-start and revise discussion.
   > - Shallow — one more review round. Invoke: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-plan.py" --max-rounds {N+1}` (the `--max-rounds` flag overrides the configured cap; without it the script re-reads config and exits at the same cap again).
   > - Override — accept findings and proceed to mill-go anyway.

   Wait for the user's choice. Deep problems → halt and tell user to check out fresh after they revise. Shallow → invoke `millpy-review-plan.py --max-rounds {N+1}` where `{N}` is the round count just reported (one extra round beyond the configured max). Override → set `approved: true` and proceed to Handoff.
```
  Preserve the prompt's content verbatim in substance (same three choices, same `{N}`/`{M}` computed values, same invoke-command text, same routing) — only the presentation format changes, per `_mill/discussion.md`'s `max-rounds-prompt-format-conformance` Decision. The follow-up sentence routes by option label ("Deep problems → ...", "Shallow → ...", "Override → ...") rather than by the Decision's literal "1 → / 2 → / 3 →" wording: this is an intentional deviation, because which choice is numbered `1)` is recomputed each round (whichever option the analysis recommends), so a fixed number-to-outcome mapping would be misleading — the label-based routing stays correct regardless of which option gets `(Recommended)` in a given round.

  After all seven edits, confirm the file's frontmatter (`---\nname: mill-plan\ndescription: ...\n---`) is untouched and still the first thing in the file.

- **Commit:** `docs(mill-plan): load mill:conversation, fix push wording, reformat max-rounds prompt`

### Card 2: mill-go/SKILL.md — Step 0b load

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/conversation/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Insert a new **Step 0b** in `## Entry`, immediately after the existing `**Step 0: Verify \`CLAUDE_PLUGIN_ROOT\`.**` block (including its bash snippet and the "Path variable rule" paragraph) and before the existing numbered step 1. The "Find:" block below is copied byte-for-byte from the current source file (0 leading spaces — both quoted lines sit at column 0 in the source) — use it verbatim to locate the target text. The "Replace with:" block is new authored text (not present in source today) to paste in as-given. Find:
```
**Path variable rule:** All Bash tool calls in this skill use `${CLAUDE_PLUGIN_ROOT}` directly — it is an environment variable already present in the shell. Do NOT read or memorize its value. Write the variable reference; the shell expands it at runtime. The full absolute path must never appear in a command string.

1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
```
  Replace with:
```
**Path variable rule:** All Bash tool calls in this skill use `${CLAUDE_PLUGIN_ROOT}` directly — it is an environment variable already present in the shell. Do NOT read or memorize its value. Write the variable reference; the shell expands it at runtime. The full absolute path must never appear in a command string.

**Step 0b: Load `mill:conversation`.** Load the `mill:conversation` skill via the Skill tool, unconditionally, immediately after Step 0 and before any other Entry step or phase. This file's `### Stuck escalation` prompts (in `## Agent-mode dispatch`) and the holistic-rounds-exhausted prompt (in `## Holistic code review`) are operator-facing prompts that depend on `mill:conversation`'s numbered-options rule (banning `AskUserQuestion`) being active, so it must be loaded before any of those prompts can be built.

1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
```
  `Step 0b` is a letter suffix, NOT `Step 0.5` — `0.5`/`0.55` are already bound elsewhere in this same file to unrelated `### 0.5. Baseline pre-flight` / `### 0.55. Done-gate baseline pre-flight` headings inside `## Agent-mode dispatch`'s per-batch dispatch loop, a different numbering namespace from `## Entry`. `0b` avoids that collision. It is a bolded-label paragraph between Step 0 and numbered step 1, mirroring this same file's own `4.5.` decimal-substep-in-Entry precedent (**Path Setup**, between numbered steps 4 and 5) in shape, even though the label itself uses a letter, not a decimal, to sidestep the `0.5`/`0.55` collision.

  After the edit, confirm the file's frontmatter (`---\nname: mill-go\ndescription: ...\n---`) is untouched and still the first thing in the file, and confirm no other text in the file changed (this card's edit is confined to the single insertion above).

- **Commit:** `docs(mill-go): load mill:conversation at Entry Step 0b`

## Batch Tests

`verify: null` — this is a pure docs batch with no runnable surface: two `SKILL.md` prose edits with no executable code path. Manual read-back verification (per `_mill/discussion.md`'s `## Testing` section):
- `mill-plan/SKILL.md`'s new Step 0 appears before the existing step 1 in `## Entry`.
- Phase: Plan's commit step, step 4d's commit bullet, and both Step 1.5 validator-fix commit branches each now include an explicit "Push." instruction; Phase: Plan's and step 4d's `git commit` now carry `-C <worktree>`.
- `mill-plan/SKILL.md`'s plan-review-skip branch commit now carries `-C <worktree>` on `git commit`.
- `mill-plan/SKILL.md`'s max-rounds-escape prompt now uses numbered `1)/2)/3)` with `(Recommended)` on the recommended option's label (computed, listed first), and the "Wait for the user's choice" follow-up sentence references the option labels (Deep problems / Shallow / Override) consistent with the reformatted prompt.
- `mill-go/SKILL.md` has a new Step 0b (distinct from Step 0, not labeled `0.5`) that loads `mill:conversation`, positioned immediately after the existing `CLAUDE_PLUGIN_ROOT` check block and before numbered step 1, and correctly cites `## Agent-mode dispatch` for Stuck escalation and `## Holistic code review` for the rounds-exhausted prompt.
- Neither file's frontmatter was disturbed.
