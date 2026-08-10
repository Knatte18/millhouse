# Batch: mill-plan-portable-cross-refs

```yaml
task: 'mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references'
batch: mill-plan-portable-cross-refs
number: 2
cards: 1
verify: PYTHONPATH= sh -c '[ "$(grep -c "plugins/mill/skills/mill-go\|plugins/mill/skills/mill-receiving-review\|plugins/mill/docs" plugins/mill/skills/mill-plan/SKILL.md)" = "0" ]'
depends-on: []
```

## Batch Scope

This batch delivers the #806 fix: converting all 6 non-portable `plugins/mill/...`-rooted cross-references in `plugins/mill/skills/mill-plan/SKILL.md` to skill-base-relative form, so they resolve correctly in any consuming repo (where the plugin lives under a versioned cache path, not at a `plugins/mill/` repo-relative path). This is a single-file, single-card batch, independent of batch 1 (different file, no shared edits, no ordering dependency) -- there is no external interface this batch produces for another batch to consume.

## Cards

### Card 4: #806 -- convert 6 non-portable plugins/mill cross-refs to skill-relative form

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
  - `plugins/mill/docs/harness-tool-contracts.md`
  - `plugins/mill/templates/plan-batch.md`
  - `plugins/mill/.claude-plugin/plugin.json`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `plugins/mill/skills/mill-plan/SKILL.md`, replace 6 non-portable `plugins/mill/...`-rooted cross-references with skill-base-relative forms. Each replacement is a like-for-like substring swap inside its existing sentence -- the surrounding prose (backtick-quoting, section-name suffixes such as `'s "## Agent-mode dispatch" section`) is unchanged. Line numbers are current as of this plan's writing (verified against the worktree source):

  | Line | Current substring | Replacement substring |
  |---|---|---|
  | 94 | `plugins/mill/docs/harness-tool-contracts.md` | `../../docs/harness-tool-contracts.md` |
  | 118 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |
  | 347 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |
  | 366 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |
  | 402 | `plugins/mill/skills/mill-receiving-review/SKILL.md` | `mill-receiving-review/SKILL.md` |
  | 432 | `plugins/mill/skills/mill-go/SKILL.md` | `mill-go/SKILL.md` |

  Use the file's own existing line-381 reference to `mill-go/SKILL.md` (already correct, bare skill-relative form, describing the same "## Agent-mode dispatch" section -- do not modify that line) as the exact phrasing/backtick-style template for the four `mill-go/SKILL.md` replacements above. The harness injects a "Base directory for this skill" path when a skill loads, so a sibling-relative reference like `mill-go/SKILL.md` resolves correctly under any skill's base directory regardless of whether that base directory is a plugin-cache path or a dev-tree path; the docs file is not under `skills/`, so its replacement needs one extra `../` hop -- from `plugins/mill/skills/mill-plan/` up two levels reaches `plugins/mill/`, then into `docs/harness-tool-contracts.md`.

  Do **not** touch: the `plugins/mill/templates/...` references (lines 166, 171), the `plugins/mill/unit_tests/...` references (lines 195, 196), the `plugins/mill/.claude-plugin/plugin.json` reference (line 319), or the `plugins/mill/templates/plan-batch.md` mention (line 317) -- these are legitimate repo-relative paths used inside `verify:` commands and render/file-creation instructions that execute from `git_root` in this self-hosting repo, not orchestrator-navigation cross-references into another skill's doc, per `_mill/discussion.md`'s `806-portable-cross-refs` Decision.

- **Commit:** `docs(mill-plan): convert 6 non-portable plugins/mill cross-refs to skill-relative form (#806)`

## Batch Tests

Pure documentation edit to one `SKILL.md` file -- no application/script code changes, so no unit tests apply. `verify:` above is the mechanical grep gate specified by `_mill/discussion.md`'s Testing section: zero remaining matches of `plugins/mill/skills/mill-go`, `plugins/mill/skills/mill-receiving-review`, or `plugins/mill/docs` in `plugins/mill/skills/mill-plan/SKILL.md`, confirming all 6 sites converted and that the intentionally-untouched `plugins/mill/templates/...`, `plugins/mill/unit_tests/...`, and `plugins/mill/.claude-plugin/plugin.json` references (which match none of those three grep alternatives) are unaffected.
