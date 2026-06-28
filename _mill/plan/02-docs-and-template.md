# Batch: Docs and Template

```yaml
task: 'Fix implement finalize correctness: mid-batch stop recovery, commit-count guard, and empty-commit detection'
batch: Docs and Template
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

This batch updates two documentation files that contribute to the bugs being fixed: `implementer-brief.md` (the template rendered at prepare time for each implementer session) and `mill-go/SKILL.md` (the orchestrator instructions that govern how finalize output is routed). Both changes are pure text edits with no runnable test surface; verification is via plan review. Depends on Batch 1 because the SKILL.md addition references `commits_made` behavior introduced there.

## Cards

### Card 4: Update `implementer-brief.md` — shared-file combined-commit guidance

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `## Implementation discipline`, find the bullet that currently reads:
  ```
     - One commit per card.
  ```
  (line 54, the first bullet under that heading). Replace it with:
  ```
     - One commit per card is the norm. For cards that necessarily touch the same file(s), one combined commit covering both cards is acceptable — do NOT create empty commits to satisfy a per-card count. If you choose a combined commit, name it using the later card's `Commit:` message.
  ```
  Do not change any other text in the file. The leading spaces before the dash must match the original indentation exactly.
- **Commit:** `docs(brief): permit combined commits for shared-file cards; ban empty commits`

---

### Card 5: Update `mill-go/SKILL.md` — document clean mid-work-stop path in step 4

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `## Agent-mode dispatch`, find step 4. Its current text starts with `4. **Recover from raw API errors and interruptions:**`. After the entire existing step-4 paragraph (which ends with `...before escalating.`), insert the following new paragraph as a continuation of step 4 (same indentation level, separated by a blank line):

  ```
  **Clean mid-work stop (implementer only):** When the implementer notification is a non-error non-JSON message — meaning the payload contains neither an `API Error` / `Internal server error` marker nor a valid `status` JSON block (clean turn exhaustion: the implementer ran out of budget and stopped before emitting the required JSON report) — do NOT re-dispatch fresh immediately. Instead, write the notification to the `.out.md` file as normal and invoke the `--stage finalize` step (step 6). Finalize will either infer success (if commits were made and the tree is clean) or emit `stuck_type: transient` with a `commits_made` field. If finalize returns `stuck_type: transient` with `commits_made > 0`, route directly to the Stuck escalation `commits_made > 0` path (one retry, then skip to cleanliness gate) — do NOT treat it as the raw-API-error one-retry path. Re-dispatching fresh with a new `start_sha` would discard the partial commit count context and risk a second completeness-gate loop even when partial work exists.
  ```

  The exact location to insert is immediately after the paragraph that begins `4. **Recover from raw API errors and interruptions:**` and before step 5 (whatever heading follows). Preserve the surrounding blank lines and indentation so the new paragraph renders as part of the step-4 block in markdown.
- **Commit:** `docs(mill-go): document clean mid-work stop routing in agent-mode dispatch step 4`

## Batch Tests

`verify: null` — both cards are documentation edits. The brief template has no direct test coverage (it is rendered at runtime by `_render.render`). The SKILL.md is read by the orchestrator at session start. Review is the validation mechanism for both files.
