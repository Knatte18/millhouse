# Batch: mill-go-skill-update

```yaml
task: Fix millpy-bg EXIT marker and implementer reliability
batch: mill-go-skill-update
number: 4
cards: 2
verify: null
depends-on: [1, 2]
```

## Batch Scope

Updates `mill-go SKILL.md` to reflect the new behaviour introduced by batches 1 and 2:
(1) every polling block's `"dead"` branch gains a note that "dead" now only fires when the
log contains no parseable JSON result line (the JSON fallback in `check_bg_status` silently
promotes dead+JSON to `("exit", 0)`); (2) the Stuck escalation section gains a new branch
for `stuck_type: transient` + `commits_made > 0` — the implementer timed out after committing
some work, so re-implementation can be skipped in favour of proceeding straight to the
cleanliness gate. Depends on batches 1 and 2 so the SKILL accurately describes code that is
already landed.

## Cards

### Card 9: Clarify "dead" semantics in all polling blocks

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Find every occurrence of the pattern `"dead" -> classify as \`stuck_type: infrastructure\` and route to Stuck escalation` (the exact phrase appears in the implementer poll, per-batch reviewer poll, per-batch fixer poll, holistic reviewer poll, holistic fixer poll, and resume-path polls — approximately 8 occurrences).
  - Append to each occurrence: ` Note: \`"dead"\` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, \`check_bg_status\` returns \`("exit", 0)\` instead (see \`_bg.py\` JSON fallback).`
  - The appended note must be on the same prose line as the existing `"dead" -> ...` sentence (i.e., no new heading or bullet, just extended sentence).
  - Do not change any other text in the polling blocks.
- **Commit:** `docs(mill-go): clarify "dead" means no-JSON, not just missing EXIT sentinel`

### Card 10: Add commits_made routing for timeout-stuck

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Locate the Stuck escalation subsection for `**transient** (LLM-layer failure or timeout)` in `mill-go SKILL.md`.
  - Within that subsection, after the existing re-fire instruction, add a new conditional branch:
    ```
    **If `commits_made > 0` in the stuck JSON** (the implementer timed out after committing some work):
    - Interactive mode: present options:
      1) Skip to cleanliness gate (Recommended) — commits were made before the timeout; proceed directly to the cleanliness gate then code review
      2) Retry from scratch — re-fire the implementer as a fresh batch start
    - On option 1: skip re-invocation of the implementer; proceed to the per-batch cleanliness gate (scope violations check) then code review as if the implementer had reported success.
    - `autonomous_mode: true`: auto-pick option 1 (skip to cleanliness gate).
    - If `commits_made == 0` or the field is absent: use the existing re-fire path.
    ```
  - The routing options must follow the mill:conversation rule: numbered list, option 1 is the recommendation.
  - This applies to the implementer step only (not the reviewer or fixer stuck paths — those do not emit `commits_made`).
- **Commit:** `docs(mill-go): add commits_made>0 skip-to-cleanliness routing for timeout-stuck`

## Batch Tests

`verify: null` — pure SKILL.md documentation change with no runnable test surface.
