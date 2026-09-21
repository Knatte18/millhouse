# Batch: skill-cross-reference-fix

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: skill-cross-reference-fix
number: 8
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes #1092: `mill-plan/SKILL.md` and `mill-start/SKILL.md` cross-reference `mill-go-base/SKILL.md`'s
"## Agent-mode dispatch" section with no absolute path, inviting the natural-but-cwd-corrupting
`cd <plugin-cache>/skills/mill-go-base && awk ...` reading (mill-go-base is documented as "not
invocable directly" via the Skill tool, so an orchestrator reading its content must resolve the file
path itself). Pure documentation edit — a mechanical text substitution in two files, no runnable
surface.

Exact occurrence counts, verified via `grep -c 'mill-go-base/SKILL.md' <file>` and `grep -c
'plugins/mill/skills/mill-go-base/SKILL.md' <file>` immediately before writing this plan:
`mill-plan/SKILL.md` has **12** occurrences, all bare (`mill-go-base/SKILL.md`, no path prefix).
`mill-start/SKILL.md` has **10** occurrences total — **4 bare** (lines 198, 264, 300, 320) and **6**
already qualified with the repo-relative `plugins/mill/skills/mill-go-base/SKILL.md` prefix (lines
262, 265, 275, 302, 318, 324). Re-verify these line numbers against the file on disk before editing
(a prior edit elsewhere in either file during this same task could have shifted them) — match by the
`mill-go-base/SKILL.md` substring itself, not by the stated line numbers.

## Cards

### Card 17: rewrite every cross-reference to the `${CLAUDE_PLUGIN_ROOT}`-qualified form

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In both files, replace every occurrence of the substring `mill-go-base/SKILL.md` — whether bare
  (`` `mill-go-base/SKILL.md` ``) or repo-relative-qualified (`` `plugins/mill/skills/mill-go-base/SKILL.md` ``) —
  with `` `${CLAUDE_PLUGIN_ROOT}/skills/mill-go-base/SKILL.md` ``, per this repo's own `CLAUDE.md`
  convention ("`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths ... Write `${CLAUDE_PLUGIN_ROOT}`
  literally in Bash tool calls"). Do this as a mechanical find-and-replace across every occurrence in
  both files — do not selectively rewrite only the bare ones, since the repo-relative form still
  implicitly assumes cwd is the git root and still isn't the established convention. Preserve
  surrounding prose and backtick/quote formatting exactly as it already appears at each site — only
  the path text inside changes. Do not touch any other cross-reference in either file that names a
  different skill file (e.g. `mill-receiving-review/SKILL.md`) — this card is scoped to
  `mill-go-base/SKILL.md` references only, per `_mill/discussion.md`'s scope note ruling out a
  repo-wide sweep.
- **Commit:** `docs: qualify mill-go-base/SKILL.md cross-references with CLAUDE_PLUGIN_ROOT (#1092)`

## Batch Tests

Documentation-only — no runnable surface. Verified by a grep self-check after editing: `grep -n
"mill-go-base/SKILL.md" plugins/mill/skills/mill-plan/SKILL.md plugins/mill/skills/mill-start/SKILL.md`
must show every remaining occurrence already prefixed with `` `${CLAUDE_PLUGIN_ROOT}/skills/` `` — no
bare or bare-repo-relative form left in either file.
