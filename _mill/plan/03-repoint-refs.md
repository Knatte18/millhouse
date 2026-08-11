# Batch: repoint-refs

```yaml
task: 'mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)'
batch: 'repoint-refs'
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-skill-helper-drift.py test-phase-wait.py test-mill-go-variants.py
depends-on: [2]
```

## Batch Scope

Every remaining cross-reference in the repo that names `plugins/mill/skills/mill-go/SKILL.md` as the
home of machinery batch 1 moved is repointed at `plugins/mill/skills/mill-go-base/SKILL.md`, the two
prose orchestrator-lists that name `mill-go` without citing a path gain `mill-go2`, and `SKILLS.md`
is regenerated so all three skills are indexed. This batch closes the plan: after it, no file in the
repo points a reader at a section that no longer lives where it says.

This is documentation and index accuracy, not a behaviour change — every rule the two prose lists
state is already enforced by the base's own Step 0 and by the `mill:conversation` load every variant
inherits. No Python behaviour changes: the only script edited is `millpy-implement.py`, and only in a
comment and a user-facing error string's cited path.

Batch-local decision: `plugins/mill/skills/mill-go-base/SKILL.md` appears in several cards' Context
purely as the repoint *target path*. The implementer does not need to read that 141 KB file to
perform these edits and should not load it.

## Cards

### Card 9: Repoint the skill-to-skill cross-references

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In each of the four files, replace every occurrence of the path substring
  `mill-go/SKILL.md` with `mill-go-base/SKILL.md`, preserving whatever prefix each citation already
  carries — some are written bare as `mill-go/SKILL.md` and some fully qualified as
  `plugins/mill/skills/mill-go/SKILL.md`; both forms keep their existing shape and only the
  directory segment changes.

  Regenerate the site list with `grep -rn 'mill-go/SKILL\.md' plugins/mill/skills/` rather than
  working from a line-number list. Sites verified at plan time against commit `6442a688`:
  `mill-start/SKILL.md` lines 179, 239, 241, 251, 276, 290, 292; `mill-plan/SKILL.md` lines 119, 362,
  381, 396, 452; `mill-merge-in/SKILL.md` lines 87, 139; `mill-quick/SKILL.md` line 23. A differing
  set means those files changed after planning — repoint what grep actually returns.

  Two references need a sanity check beyond the mechanical substitution, because they name a section
  rather than just a file: `mill-quick/SKILL.md`'s citation of mill-go's "0.55" block, and
  `mill-start/SKILL.md` line 179 plus `mill-plan/SKILL.md` line 119, which both cite the "Why not
  fork?" paragraph inside `## Agent-mode dispatch`. All three sections moved to the base intact, so
  the section names stay correct; only the file path changes.

  Do not touch `mill-plan/SKILL.md`'s Handoff message — it still names `/mill-go` alone, and
  mill-go2 stays opt-in.
- **Commit:** `docs(skills): repoint mill-go/SKILL.md cross-references at mill-go-base`

### Card 10: Repoint the doc, script, and test cross-references

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/docs/harness-tool-contracts.md`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-phase-wait.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Same mechanical substitution as card 9 — `mill-go/SKILL.md` becomes
  `mill-go-base/SKILL.md` — across three non-skill files. Regenerate the site list with
  `grep -rn 'mill-go/SKILL\.md' plugins/mill/docs/ plugins/mill/scripts/ plugins/mill/unit_tests/`.
  Sites verified at plan time: `harness-tool-contracts.md` lines 22 and 34;
  `millpy-implement.py` lines 517 (comment), 523 (a **user-facing error string** — the path inside
  the quoted message is what a hub operator reads when agent-mode is misconfigured, so it must be
  correct), and 720 (comment); `test-phase-wait.py` line 153 (comment).

  In `millpy-implement.py` this is a string- and comment-only edit. Do not change any control flow,
  any function signature, or the literal prefix `mill-go: start batch` that
  `_implementer_common.py` parses — see the `script-side-prefixes-unchanged` Shared Decision.

  `harness-tool-contracts.md` line 34 additionally names mill-go's
  "### Entry-gate wait for upstream mill-plan" subsection; that subsection moved to the base intact,
  so only the file path changes.
- **Commit:** `docs: repoint mill-go/SKILL.md references in docs, scripts, and tests`

### Card 11: Add mill-go2 to the two prose orchestrator lists

- **Context:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/cli/SKILL.md`
  - `plugins/mill/skills/conversation/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Both files list the orchestrators a Bash-convention rule applies to, by name and
  without citing a file path, so card 9's path-based repoint does not reach them and they would go
  stale silently now that a second orchestrator exists.

  In `plugins/mill/skills/cli/SKILL.md`, the sentence beginning "Autonomous agents (mill-plan,
  mill-go) constructing new Bash commands must use the resolved path verbatim" (line 40 as of commit
  `6442a688`): add `mill-go2` to the parenthesised list.

  In `plugins/mill/skills/conversation/SKILL.md`, the sentence "Applies to every Bash call made
  directly by the orchestrator (mill-start, mill-plan, mill-go, ...)" (line 74 as of the same
  commit): add `mill-go2` to that list.

  Do NOT add `mill-go-base` to either list. Both lists name what an operator invokes, and the base is
  never invoked directly. Change nothing else in either sentence — the underlying rules are unchanged
  and this is accuracy maintenance, not a correctness fix.
- **Commit:** `docs(skills): add mill-go2 to the orchestrator name lists`

### Card 12: Regenerate SKILLS.md

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Regenerate the index rather than hand-editing it — `SKILLS.md` is a generated
  view of every SKILL.md's frontmatter, and the file's own header says not to edit it by hand. Run,
  from the task worktree:

  ````bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"
  ````

  The script resolves its scan root from `git rev-parse --show-toplevel` in the current working
  directory, so it indexes the task worktree, not the plugin cache. Write
  `${CLAUDE_PLUGIN_ROOT}` literally — do not resolve or memorize its value.

  Then confirm the regenerated table: the `mill-go` row's description is unchanged from before this
  task, and two new rows are present — `mill-go-base` and `mill-go2` — carrying the descriptions
  cards 1 and 8 wrote. If any of the three rows is missing or carries a stale description, the
  frontmatter is the defect; fix the SKILL.md and re-run the script rather than editing `SKILLS.md`.
- **Commit:** `chore: regenerate SKILLS.md`

## Batch Tests

`verify:` runs `run-all.py --only test-guards.py test-skill-helper-drift.py test-phase-wait.py
test-mill-go-variants.py` — the four tests that can observe anything this plan changed, run together
as the closing gate.

Why these four and no others: `test-phase-wait.py` is edited by card 10. `test-guards.py` walks
`plugins/mill/scripts/` and `plugins/mill/skills/` for five anti-patterns, so it re-checks the
retargeted wiki-cwd allowlist against the post-repoint tree. `test-skill-helper-drift.py` walks every
mill SKILL.md for `_<module>.<fn>(` helper references and holds the `#496` lock retargeted in batch 1
— it is the check that would catch a mangled or truncated relocation surviving into this batch.
`test-mill-go-variants.py` re-confirms the variant contract still holds after the cross-reference
edits, including the parameterization lock.

No other test in the suite reads a SKILL.md, a doc, or the two `millpy-implement.py` strings this
batch touches, so a wider scope would add minutes of runtime for no additional signal. The live
`/mill-go` run named in the discussion's `verification-approach` Decision is the real end-to-end
gate for the base extraction and is exercised outside this plan.
