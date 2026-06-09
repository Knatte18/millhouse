# Batch: SKILL.md updates: Agent-mode dispatch pattern

```yaml
task: Fix agent-pipeline reliability gaps in finalize/success contract
batch: "'SKILL.md updates: Agent-mode dispatch pattern'"
number: 3
cards: 2
verify: null
depends-on: [1, 2]
```

## Batch Scope

This batch updates two SKILL.md files to document the new prepare->finalize contract established by Batches 1 and 2. Mill-go's Agent-mode dispatch pattern (the generic 6-step procedure) needs two amendments: step 2 must document extracting `session_id`, `round`, and `start_sha` from the prepare envelope, and step 5 must document threading those values into the finalize call. Mill-start's two discussion-review call sites must be updated to explicitly state that `--round` from the prepare envelope is threaded into finalize.

Both changes are documentation-only. `verify: null` because there is no runnable surface for SKILL.md edits.

## Cards

### Card 6: Amend mill-go/SKILL.md Agent-mode dispatch pattern (steps 2 and 5)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In the "## Agent-mode dispatch" section, find step 2 ("**Run prepare stage:**"). After the existing three bullet points listing `brief_path`, `subagent_type`, and `model`, add the following sentence: "Also extract from the envelope: `session_id` (string or null), `round` (integer), and `start_sha` (string or null -- present only when the CLI emits it, e.g. fix and implementer CLIs)."
  - In the "## Agent-mode dispatch" section, find step 5 ("**Run finalize stage:**"). After the existing text ending with "Parse the returned JSON envelope.", add the following paragraph: "Additionally thread any applicable prepare-envelope fields into the finalize call: for fix and implementer CLIs, pass `--session-id <session_id>` and `--start-sha <start_sha>` (when `start_sha` is not null in the envelope); for review CLIs, pass `--round <round>`."
  - No other sections of mill-go/SKILL.md are changed. The per-batch and holistic dispatch subsections that say "follow the Agent-mode dispatch pattern with `<cli> = millpy-fix.py`" already inherit the step 2 and step 5 amendments above. Do not add per-call-site notes.
  - All Bash tool calls must keep `${CLAUDE_PLUGIN_ROOT}` as a literal reference; do not expand to an absolute path.
- **Commit:** `docs(skill): amend mill-go Agent-mode dispatch steps 2 and 5 for prepare-envelope fields`

### Card 7: Update mill-start/SKILL.md discussion-review finalize call sites

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In "Phase: Discussion Review", step 2 (the loop body's dispatch step), find the agent-mode line that reads (approximately): "follow the Agent-mode dispatch pattern (see '## Agent-mode dispatch' in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-discussion.py` and no additional standard arguments." Change "and no additional standard arguments" to "with no additional prepare arguments; thread `--round <round>` from the prepare envelope into the finalize invocation."
  - In step 3.5 ("ERROR-only-aggregate retry"), find the agent-mode line that reads: "follow the Agent-mode dispatch pattern (see '## Agent-mode dispatch' in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-review-discussion.py` and no additional standard arguments." Apply the same change: "with no additional prepare arguments; thread `--round <round>` from the prepare envelope into the finalize invocation."
  - These are the only two changes in mill-start/SKILL.md. No other lines are touched.
- **Commit:** `docs(skill): thread --round into discussion-review finalize at mill-start call sites`

## Batch Tests

`verify: null` -- pure documentation batch. No test runner applies to SKILL.md files. Correctness is verified by reading the updated text against the discussion's specification (both amendments described in "Technical context" section of `_mill/discussion.md`).
