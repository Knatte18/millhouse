# Batch: extract-cold-path

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'extract-cold-path'
number: 4
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [3]
```

## Batch Scope

Moves the three cold-path sections — `## Resume`, `## Holistic code review`, `## Handoff` — out of `SKILL.md` into three companion files in the same directory, leaves a pointer-only reference site at each extraction point, appends the `## History` restore note, repairs cross-references in both directions, and extends `test-skill-helper-drift.py` so its two guarantees follow the relocated content.
This is the batch that turns the regression guard written in batch 1 green; from here on it is part of every `verify:`.

The interface batch 5 consumes is the five-file surface its renumbering sweep must cover: `SKILL.md`, the three companion files created here, and `mill-go2/SKILL.md`.

Batch-local decisions: none beyond the overview's `companion-files-carry-no-wiki-access-banner` and `no-renames-in-this-task`.
Cards 14 through 16 create the companion files; card 17 removes the extracted prose and installs the pointers; card 18 repairs cross-references once both ends exist; card 19 restores test coverage over the relocated content.

## Cards

### Card 14: Create resume.md

- **Context:**
  - `_mill/discussion.md`
  - `SKILLS.md`
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:**
  - `plugins/mill/skills/mill-go-base/resume.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create the file with an H1 `# mill-go-base: Resume` and, beneath it, the full body of `SKILL.md`'s `## Resume` section exactly as batch 2 and batch 3 left it — the opening paragraph beginning "When mill-go's Entry-step 5 phase gate routes here", numbered steps 1 through 4, and every sub-branch of step 2.
  Copy the prose verbatim; this card relocates content and does not reword, compress, or re-order it.
  Do not add YAML frontmatter.
  The skills-index generator collects its inputs with `skills_dir.rglob("SKILL.md")`, an exact-filename match, so this file is excluded from `SKILLS.md` by its filename alone and frontmatter would not change that.
  The rule stands anyway for a different reason: a `name:`/`description:` block is the marker of an invocable skill, and this file is a fragment of one.
  Do not add the `> Wiki access: never cd .wiki/ …` banner line.
  Keep `<VARIANT_LABEL>` tokens as literal `<VARIANT_LABEL>` — the variant binding substitutes them at read time in the companion file exactly as it does in `SKILL.md`.
  Edit `SKILL.md` in this card only to the extent of reading it as the source; leave its `## Resume` section in place for card 17 to remove, so that a failure between these two cards leaves the content present rather than lost.
- **Commit:** `docs(mill-go-base): extract the Resume section to resume.md`

### Card 15: Create holistic-review.md

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create the file with an H1 `# mill-go-base: Holistic code review` and, beneath it, the full body of `SKILL.md`'s `## Holistic code review` section exactly as batches 2 and 3 left it: the `**Guard:**` paragraph, the `max_holistic_rounds`/`min_holistic_rounds` bindings, the `**Convergence gate (min_rounds + demoted predicate).**` block, and numbered steps 0 through 7 including sub-steps 2.5, 3.5, and 3.6.
  Copy verbatim, with the same no-frontmatter, no-wiki-banner, and literal-`<VARIANT_LABEL>` rules as card 14.
  The line `reviews_dir = hub / '_mill/reviews'` inside step 1's inline-Python helper must survive this move byte-for-byte; card 19 re-points the test that locks it.
  Leave the section in place in `SKILL.md` for card 17 to remove.
- **Commit:** `docs(mill-go-base): extract the Holistic code review section to holistic-review.md`

### Card 16: Create handoff.md

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create the file with an H1 `# mill-go-base: Handoff` and, beneath it, the full body of `SKILL.md`'s `## Handoff` section exactly as batch 2 left it: `**Nit-enforcement gate.**`, `**Prior-blocking digest.**`, `**Manual recovery note.**`, `**Terminal cleanliness gate.**`, `**Scope violations cleanup gate.**`, `**Scope violations handling note.**`, the `**0. Pre-done gate.**` block, and numbered steps 1 through 6.
  Copy verbatim, with the same no-frontmatter, no-wiki-banner, and literal-`<VARIANT_LABEL>` rules as card 14.
  Note that this section's `**0. Pre-done gate.**` fenced Python contains `subprocess.run(...)`; that is the Python standard library, unrelated to the dispatch mode this task removes, and must be preserved exactly.
  Leave the section in place in `SKILL.md` for card 17 to remove.
- **Commit:** `docs(mill-go-base): extract the Handoff section to handoff.md`

### Card 17: Install pointer-only reference sites and the History note

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Delete the bodies of `## Resume`, `## Holistic code review`, and `## Handoff` from `SKILL.md`, keeping each `##` heading, and replace each body with a mandatory-read directive and nothing else.
  Before deleting, diff each section against the companion file created in cards 14 through 16 and confirm the content is identical, so nothing is lost.
  Each reference site must contain the literal read instruction `` Read `plugins/mill/skills/mill-go-base/<name>.md` now `` in bold, followed by a statement that all of the phase's behaviour lives in that file and that the reader must not proceed from the heading without reading it — the shape the discussion's `pointer-only-reference-sites-force-the-read` Decision specifies.
  Each site must carry **no** summary of the companion's content, no restatement of its steps, and no list of what it covers.
  This is the enforcement mechanism: with nothing actionable at the reference site there is no path forward except the read.
  Then append a `## History` section at the bottom of the file, after `## Board discipline`, with this exact content:

```markdown
## History

Pre-strip version (1483 lines, with subprocess/psmux dispatch branches and the Resume /
Holistic / Handoff sections inline) is at commit `356da5e5`. Restore with:
`git show 356da5e5:plugins/mill/skills/mill-go-base/SKILL.md`.
```

  That SHA is verified: `git diff 356da5e5 HEAD -- plugins/` is empty at the time this plan was written, so the commit is a faithful pre-strip snapshot even though the branch has advanced past it.
  Before writing the note, re-derive the line count mechanically rather than trusting the literal above: run `git show 356da5e5:plugins/mill/skills/mill-go-base/SKILL.md | wc -l`.
  It returned `1483` when this plan was written, which is why the note says 1483; if it returns anything else at execution time, use that number instead and leave the rest of the wording untouched.
  Note that a line-counting tool that reports 1484 is counting the empty string after the file's single trailing newline — `wc -l` and `git show | wc -l` are the arbiters here.
- **Commit:** `docs(mill-go-base): replace the three cold-path sections with mandatory-read pointers`

### Card 18: Repair cross-references in both directions

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Every reference that relied on the four files being one file must now name its target explicitly.
  Work both directions:
  1. **Companion into SKILL.md.** In each companion file, find every positional reference — "see `## Agent-mode dispatch` above", "the Agent-mode dispatch pattern above", "continue at Execute step 2b", "continue at Execute step 3 sub-step 3", "see Principles below", "as per the per-batch section above", "mirrors the per-batch APPROVE branch", "see `## Execute` step 4", "the `**Tree-guard checkpoint block**`", "see `## Board discipline`" — and rewrite it to name `plugins/mill/skills/mill-go-base/SKILL.md` plus the target section.
     Delete the words "above" and "below" from any such reference: neither holds across a file boundary.
  2. **Companion into companion.** `handoff.md` references `## Holistic code review` step 4's NIT-fix shape, and `holistic-review.md` ends by proceeding to Handoff.
     Rewrite both to name the other companion file by its repo-relative path.
  3. **SKILL.md into companion.** Find every forward reference in `SKILL.md` into the three extracted sections — including `## Entry`'s phase-table rows and the `### Mid-execution phase-gate widening` routing bullets, which route to `## Resume`, `## Holistic code review`, and `## Handoff` by section name; `### Blocked`'s "Do not proceed to Handoff."; `### 0.55`'s comparison against the Handoff-time pre-done gate; and `## Entry` step 3's note that auto-report fires at "Handoff step 6" — and make each name the companion file's repo-relative path alongside the section name.
     The routing bullets are the highest-value ones: they are the only instruction that gets a resumed run into the right phase.
  Do not reword any operational content while doing this; the edit is confined to reference targets.
  After this card, no reference in any of the four files may locate a target by relative position alone.
- **Commit:** `docs(mill-go-base): repair cross-references across the skill and its companions`

### Card 19: Follow the extracted content with drift-test coverage

- **Context:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two changes, both because content this test guards has left `SKILL.md`:
  1. **Widen the helper-reference scan.** The scan currently builds its file list as `skill_files = sorted(SKILLS.rglob("SKILL.md"))`.
     Extend it so the `mill-go-base` companion files are scanned too, by unioning that list with the `mill-go-base` directory's other `*.md` files and de-duplicating.
     Without this, every `_<module>.<fn>(` reference in the 524 relocated lines silently drops out of drift coverage.
     Keep the scan's existing per-file reporting so a failure still names the file it came from.
  2. **Re-point the `#496` lock.** The check currently reads `mill-go-base/SKILL.md` and fails if the literal `reviews_dir = hub / '_mill/reviews'` is absent.
     That literal now lives in the holistic crash-recovery helper, which moved to `holistic-review.md`.
     Change the lock to search `SKILL.md` and the `mill-go-base` companion files, passing when the literal is found in any one of them, and keep the failure message naming `#496` and the reason so a real regression stays diagnosable.
     Do not weaken the assertion to a substring match on a shorter fragment and do not delete it.
  Update the module docstring's description of Card 1's scan so it says the scan covers the `mill-go-base` companion files as well as every SKILL.md.
  Use only ASCII and no U+2192 arrow character, per `test-guards.py`'s own checks over `test-*.py`.
- **Commit:** `test(drift): follow mill-go-base companion files in the helper-drift scan`

## Batch Tests

`verify:` adds `test-mill-go-base-agent-only.py` to the `--only` list alongside the three existing tests, and it stays there for the rest of the task.
This is the batch where the TDD guard written in batch 1 goes green: cards 14 through 16 create the three companion files it asserts exist, and card 17 installs the repo-relative path reference and mandatory-read directive at each of the three sites it checks.
Its banned-literal check already passed as of batch 2 for `SKILL.md`, and cards 14 through 16 keep it passing for the companion files because they copy content batch 2 already stripped.

`test-skill-helper-drift.py` is exercised twice over by this batch: card 19 edits it, and cards 14 through 18 change the file set and the helper references it scans.
`test-guards.py` covers the `companion-files-carry-no-wiki-access-banner` decision — its `no_wiki_cwd` check walks every `*.md` under `plugins/mill/skills/` and the three new files are not allowlisted, so a copied banner line fails the batch immediately rather than silently.
`test-mill-go-variants.py` stays in the list because its `MACHINERY_LITERALS` tuple includes `## Holistic code review`, which card 17 keeps as a heading in `SKILL.md` and which must not appear in either variant file.
