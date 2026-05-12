# Batch: skills-and-docs

```yaml
task: (A) — Add /mill-fold skill with active-task guard
batch: skills-and-docs
number: 3
cards: 4
verify: null
depends-on: [2]
```

## Batch Scope

Adds the operator-facing surface for the fold subsystem: a new `mill-fold/SKILL.md` thin skill over `millpy-fold.py`, a retrofit of `mill-ghissues-to-tasks/SKILL.md` (Step 3 phase guard + Step 5 bullet alignment + Step 5 close-comment split + Rules bullets), a one-bullet "Backlog editing invariants" addition to project `CLAUDE.md`, and a regenerated repo-root `SKILLS.md` index. Pure documentation — no `verify:` command. The cards in this batch are independent (different files); the implementer may execute them in any order. SKILLS.md regen depends on the new SKILL.md existing, so card 12 runs last.

## Cards

### Card 6: Create `mill-fold/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-add/SKILL.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
  - `plugins/mill/scripts/millpy-fold.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/mill-fold/SKILL.md`
- **Deletes:** none
- **Requirements:**
  - Top-of-file `---`-fenced YAML frontmatter: `name: mill-fold` and `description: Fold a GitHub issue or scope item into an existing Home.md backlog task. Hard-refuses locked-phase targets ([active], [ready-to-merge], [pr-pending]) so a frozen plan is never invalidated by silent scope creep.`
  - Body sections (mirror `mill-add/SKILL.md`'s shape):
    - `# mill-fold` heading + one-paragraph overview that explains the two invocation forms and the close-comment behavior. Reference `_tasks_md.LOCKED_FOLD_PHASES` as the single source of truth for the locked-phase set.
    - `## When the user invokes me` — typical triggers: "fold #N into <slug>", "fold this issue into …", "legg det inn under …".
    - `## Preconditions` — `.millhouse/wiki` junction exists (if not, run `/mill-setup`); for the GH path, `gh auth status` must succeed.
    - `## Two invocation forms`:
      - `/mill-fold <target-slug> --issue <N>` — GH issue. The script fetches the issue, prompts to confirm a draft `Sources:` line, edits Home.md, commits/pushes, then closes the GH issue with comment `Folded into wiki task: <target-slug>`.
      - `/mill-fold <target-slug> --scope "<text>"` — scope item. The script appends `- Folded in: <text>` to the target body. No GH side-effect.
    - `## Locked-phase guard` — restate the rule verbatim: tasks marked `[active]`, `[ready-to-merge]`, or `[pr-pending]` reject the fold with `SystemExit(1)`. No `--force` flag. Explain why (plan is frozen post-spawn). Cite `_tasks_md.LOCKED_FOLD_PHASES` as the source of truth.
    - `## How to call the script` — show both the cache-form (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fold.py" <slug> --issue <N>`) and the source-tree form for testing. Include a PowerShell example matching `mill-add/SKILL.md`'s style.
    - `## Examples` — three short blocks: (a) fold GH issue #99 into `mill-misc-fixes-7`, (b) fold scope text into `cluster-reviewer`, (c) attempted fold into `[active]` task showing the error message verbatim so operators recognize it.
    - `## Error handling` — table mapping common script exits to operator-facing meanings (`Slug not in Home.md`, `Cannot fold into … task is […]`, `issue #N is CLOSED`, `gh issue view failed`).
    - `## Non-goals` — title/summary edits (use manual wiki edit or `mill-groom`), un-folding, multi-issue batch input.
  - The file uses `${CLAUDE_PLUGIN_ROOT}` everywhere, never `plugins/mill/...` (project CLAUDE.md `## Conventions worth carrying`).
- **Commit:** `feat(mill-fold): add SKILL.md`

### Card 7: Retrofit `mill-ghissues-to-tasks/SKILL.md` for phase guard, bullet alignment, and close-comment split

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - **Step 3 phase guard.** In the section "On selection 2 (Fold into existing):" (currently 3 bullets at SKILL.md line ~67 — implementer locates it by grep), add a new bullet between the "Validate against the parsed Home.md slug list" bullet and the "Record the decision" bullet:
    - `Phase check: parse Home.md via _tasks_md.parse() and inspect the target Task's phase. When the phase is in _tasks_md.LOCKED_FOLD_PHASES (i.e. one of "active", "ready-to-merge", "pr-pending"), refuse the fold for this issue: print "Cannot fold #<N> into <slug>: task is [<phase>]. Plan is frozen — scope additions silently invalidate it. Pick a different action for this issue." and re-present the decision menu with option 2 omitted (struck-through or disabled). Use _tasks_md.LOCKED_FOLD_PHASES as the source of truth — never duplicate the tuple in this SKILL.md or anywhere else.`
  - **Step 5 bullet alignment.** In Step 5 item 1 (currently: "Append new task entries using the mill-add format ... For each fold-in, leave existing task text unchanged unless the user asked to append a note."), replace the second sub-bullet with: `For each fold-in, call _tasks_md.append_to_body(home_text, target_slug, f"- Sources: #{N} — {issue_title}") to add a Sources: bullet to the target body. The append is unconditional — there is no longer a "leave unchanged" path. Each fold-in produces the same Home.md output as a /mill-fold #N <slug> invocation.`
  - **Step 5 close-comment split.** In Step 5 item 4 (currently: "For each consumed issue (new or fold-in), call ... `_gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>', git_root=...)`"), replace the single-string call with a per-decision branch in the prose:
    - `For each consumed New-task issue, call _gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>', git_root=...).`
    - `For each consumed Fold-in issue, call _gh_issues.close_with_comment(<N>, 'Folded into wiki task: <slug>', git_root=...). The Fold-in close-comment string MUST match /mill-fold's exactly — see plugins/mill/skills/mill-fold/SKILL.md.`
  - **Rules section bullets.** In `## Rules` (currently 4 bullets), add three new bullets at the end:
    - `Fold targets must be in an unlocked phase. _tasks_md.LOCKED_FOLD_PHASES is the source of truth — never duplicate the tuple.`
    - `Fold-in always appends a "- Sources: #N — <issue title>" bullet to the target body via _tasks_md.append_to_body. The Home.md output of a fold-in is identical between this skill and /mill-fold.`
    - `Close-comment strings: New-task → "Consolidated into wiki task: <slug>"; Fold-in → "Folded into wiki task: <slug>". The Fold-in string matches /mill-fold's comment verbatim.`
  - Do not change any other section of the SKILL.md — entry checks, Steps 1/2/4/6, and out-of-scope items remain as-is.
- **Commit:** `feat(ghissues): add phase guard, align fold-in bullet, split close-comment string`

### Card 8: Add "Backlog editing invariants" bullet to project `CLAUDE.md`

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Locate the existing `## Constraints` section. Append exactly one new bullet at the end of the existing bullet list (under "Working state is never written to the wiki."):
    - `Folding scope into a Home.md task entry — via /mill-fold or the fold-in branch of /mill-ghissues-to-tasks — is forbidden when the target's phase marker is [active], [ready-to-merge], or [pr-pending]. The plan was committed at spawn time and scope additions silently invalidate it. Phase tuple lives at _tasks_md.LOCKED_FOLD_PHASES; both skills import it. Personal memory is NOT a valid place for this rule — it must travel with the repo.`
  - Do not change any other section of `CLAUDE.md`. In particular, the `## Review terminology`, `## Path invariants`, and `## Wiki access` sections are unchanged.
- **Commit:** `docs(claude): add backlog-editing invariant against locked-phase folds`

### Card 9: Regenerate repo-root `SKILLS.md` via mill-skills-index

- **Context:**
  - `plugins/mill/skills/mill-fold/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Run the mill-skills-index regeneration command from the source-tree (this is a build-artifact card; the millhouse repo IS the worktree, so source-tree form is correct here):
    - `uv run --project plugins/mill plugins/mill/scripts/millpy-skills-index.py` (verify the exact CLI name by listing `plugins/mill/scripts/millpy-*` if `millpy-skills-index.py` is not present; the underlying skill is `mill:mill-skills-index`).
  - Confirm the regenerated `SKILLS.md` includes a `mill-fold` entry with the one-line description from card 6's frontmatter, in alphabetical order with the other `mill-*` entries.
  - Do NOT hand-edit `SKILLS.md`. The regen script is the single source of truth; manual edits drift the moment another skill is added.
- **Commit:** `chore(skills): regenerate SKILLS.md to include mill-fold`

## Batch Tests

Documentation batch — `verify: null`. The reviewer in plan-review and code-review reads the four files against the discussion and against the existing patterns (`mill-add/SKILL.md`, the project `CLAUDE.md`'s existing `## Constraints` bullets). Manual smoke-test after merge: invoke `/mill-fold mill-misc-fixes-7 --scope "test fold"` in a scratch branch against a throwaway Home.md to confirm the SKILL.md instructions land correctly; this is not part of the plan's automated verification.
