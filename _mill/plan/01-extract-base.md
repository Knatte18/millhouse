# Batch: extract-base

```yaml
task: 'mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)'
batch: 'extract-base'
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-skill-helper-drift.py
depends-on: []
```

## Rename mechanic

For the `Moves:` pair in this batch the implementer MUST:

1. Run `git mv plugins/mill/skills/mill-go/SKILL.md plugins/mill/skills/mill-go-base/SKILL.md`
   FIRST, before making any other change to the moved file. Create the
   `plugins/mill/skills/mill-go-base/` directory as part of that `git mv`.
2. Make ONLY surgical edits afterwards — touch only the lines cards 1-4 name.
   The remaining ~1400 lines are moved byte-for-byte.
3. Never write the relocated file from scratch and delete the original — that breaks git rename
   history and inflates the review diff to 1424 added plus 1424 removed lines.
4. After the move, confirm rename detection with
   `git -C <worktree> diff --cached -M --stat` and check the entry reads as a rename, not as a
   delete plus an add.

## Batch Scope

This batch relocates the whole of today's `plugins/mill/skills/mill-go/SKILL.md` to
`plugins/mill/skills/mill-go-base/SKILL.md`, parameterizes the three variant-specific literal
families inside it, adds the two override-point directives the variant contract depends on, and
retargets the two existing test locks that name the old path. It delivers the single copy of the
machinery that both orchestrator variants will load.

The external interface this batch publishes, and that batch 2 consumes, is the variant contract: a
variant file declares `VARIANT_LABEL` under a `## Variant binding` heading, a `## Driver preamble`
section, and a `## Dispatch overrides` section; the base reads all three.

Batch-local note: at the end of this batch the `plugins/mill/skills/mill-go/` directory does not
exist. That is deliberate — see the `intermediate-missing-mill-go` Shared Decision. Batch 2 creates
the thin `mill-go/SKILL.md` in its place.

## Cards

### Card 1: Relocate mill-go/SKILL.md to mill-go-base and rewrite its identity block

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:**
  - `plugins/mill/skills/mill-go/SKILL.md` -> `plugins/mill/skills/mill-go-base/SKILL.md`
- **Requirements:** Perform the `git mv` per the `## Rename mechanic` section above. Then make
  exactly three surgical edits to the relocated file, and no others in this card.
  (1) In the `---` frontmatter, change `name: mill-go` to `name: mill-go-base`.
  (2) In the same frontmatter, replace the `description:` value with text that states the skill is
  internal and not invocable directly, naming `/mill-go` and `/mill-go2` as the skills that load it —
  this description is what appears in the operator's skill list and in the generated root skills
  index, so it must not read as an invocable orchestrator.
  (3) Change the H1 title line `# mill-go` to `# mill-go-base`.
  Everything else in the file — the `> Wiki access:` banner, the "You are the **Builder** — a lean
  orchestrator" role paragraph, and every section from `## Entry` through `## Board discipline` —
  moves unchanged in this card. The banner and the role paragraph are machinery-level instructions
  to whoever drives the batch loop, which is the base, so they belong here and are NOT reproduced in
  either thin variant.
- **Commit:** `refactor(mill-go): relocate SKILL.md machinery to mill-go-base`

### Card 2: Add the variant-binding and driver-preamble directives at the top of Entry

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Insert a new `**Step 0a: Variant binding and driver preamble.**` block
  immediately after the `## Entry` heading and immediately BEFORE the existing
  `**Step 0: Verify \`CLAUDE_PLUGIN_ROOT\`.**` block. Step 0a must run first because the existing
  Step 0 halt string is one of the `[mill-go]` prefixes card 4 parameterizes, so `VARIANT_LABEL` has
  to be bound before it is reached.

  Step 0a must state all of the following:
  - This skill is never invoked directly. A variant skill loads it and binds `VARIANT_LABEL` in that
    variant's own `## Variant binding` block.
  - Read the variant's `## Variant binding` block, bind `VARIANT_LABEL` to the value declared there,
    and substitute that value for every `<VARIANT_LABEL>` token in this file.
  - If no variant loaded this skill, or the loading variant declares no `VARIANT_LABEL`, halt with
    the literal message
    `[mill-go-base] HALT: mill-go-base is not invocable directly -- run /mill-go or /mill-go2.`
    Use `[mill-go-base]` here, not `[<VARIANT_LABEL>]` — at this point no label is bound, and the
    prefix must not be parameterized.
  - Override point B, worded exactly as: *treat your variant's `## Driver preamble` text as if
    written here, ahead of everything below; if your variant declared no such section, halt — this
    skill is not invocable directly.*
  - A variant whose `## Driver preamble` section contains only `(none)` has declared the section and
    contributes no text; that is not a halt.

  Do not use the word `hook` anywhere in this block — see the `no-hook-terminology` Shared Decision.
  Do not renumber the existing `Step 0`, `Step 0b`, or numbered Entry steps.
- **Commit:** `feat(mill-go-base): add variant-binding and driver-preamble override point`

### Card 3: Add the dispatch-overrides directive at Agent-mode dispatch step 3

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Agent-mode dispatch` section, insert override point A at the head of
  numbered step 3 (`**Call Agent tool:**`), before the existing "Invoke the Agent tool with:" line
  and its `subagent_type` / `model` / `prompt` sub-bullets. This is the only attachment point for
  override point A in the whole file — all twelve dispatch call sites already funnel through this
  one section, so no per-call-site directive is added anywhere else.

  The inserted text must state:
  - Override point A, worded exactly as: *consult your variant's `## Dispatch overrides` for this
    role; if it declares one, follow it instead of the default `Agent()` call below.*
  - The role for the current dispatch is the one named by the calling subsection (implementer,
    fixer, reviewer, or merge-in).
  - A variant whose `## Dispatch overrides` section contains only `(none)` declares no override for
    any role, and the default `Agent()` call below applies unchanged.

  Leave the existing "Why not fork?" paragraph in this section unchanged — it remains accurate for
  both variants, since neither forks as of this task.
  Do not use the word `hook` anywhere in this block.
- **Commit:** `feat(mill-go-base): add dispatch-overrides override point at Agent-mode step 3`

### Card 4: Parameterize the three variant-specific literal families

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Regenerate the work inventory with grep against the relocated file rather than
  working from any hand-copied line list, then replace the literal `mill-go` with the token
  `<VARIANT_LABEL>` at every site the three greps return:

  ````bash
  F=plugins/mill/skills/mill-go-base/SKILL.md
  grep -n 'commit -m "mill-go: ' "$F"
  grep -n '_notify\.notify("mill-go\.'  "$F"
  grep -n '\[mill-go\]' "$F"
  ````

  Expected counts, verified at plan time against commit `6442a688`: 26, 8, and 10 respectively. A
  differing count means `mill-go/SKILL.md` changed after planning — parameterize what grep actually
  returns and record the delta in this card's commit message.

  Resulting shapes: `commit -m "<VARIANT_LABEL>: approve batch {batch_name}"`,
  `_notify.notify("<VARIANT_LABEL>.done", ...)`, `echo "[<VARIANT_LABEL>] HALT: ..."`.

  Exclusions, all mandatory:
  - The `[mill-go-base]` halt string added by card 2 is not parameterized and is not matched by the
    `\[mill-go\]` grep.
  - Every other occurrence of the string `mill-go` in this file — narrative prose, section
    cross-references, `millpy-bg` slug arguments, `[mill-bg]` markers — is left byte-for-byte
    unchanged.
  - The commit subjects written by Python scripts (`mill-go: start batch`,
    `mill-go: fixing batch`, `mill-go: holistic fix round`) are produced by scripts under
    `plugins/mill/scripts/`, not by this file, and are out of scope for this plan entirely. Do not
    edit any Python script in this card.

  After the replacements, re-run all three greps and confirm each returns zero matches.
- **Commit:** `feat(mill-go-base): parameterize commit, notify, and echo prefixes as VARIANT_LABEL`

### Card 5: Retarget the two test locks that name the old mill-go path

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-guards.py`
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two edits.

  (1) In `test-guards.py`, in the `_WIKI_CWD_ALLOWLIST` set: replace the entry
  `"plugins/mill/skills/mill-go/SKILL.md"` with `"plugins/mill/skills/mill-go-base/SKILL.md"`.
  The `> Wiki access:` banner is the only line in the moved file matching `_WIKI_CWD_PATTERNS`, and
  card 1 moved that banner to the base, so the allowlist entry follows it. Removing the `mill-go`
  entry is required, not optional bookkeeping — a stale entry would mask a future reintroduction of
  a wiki-cwd pattern into the thin variant. Do NOT add a `mill-go2` entry: the thin variants contain
  no wiki-cwd pattern and must stay unallowlisted.

  (2) In `test-skill-helper-drift.py`, in the `#496 lock` block: change the `mill_go_skill_path`
  assignment from `SKILLS / "mill-go" / "SKILL.md"` to `SKILLS / "mill-go-base" / "SKILL.md"`.
  The literal it asserts on, `reviews_dir = hub / '_mill/reviews'`, moved to the base with the rest
  of the machinery. Leave the variable name `mill_go_skill_path` and the assertion string unchanged;
  only the path changes. Every failure message in that block already interpolates
  `{mill_go_skill_path}`, so no message text needs editing.
- **Commit:** `test: retarget wiki-cwd allowlist and #496 lock at mill-go-base`

## Batch Tests

`verify:` runs `run-all.py --only test-guards.py test-skill-helper-drift.py` — the two test files
this batch edits, and the only two tests that name the relocated path.

`test-guards.py` covers the retargeted `_WIKI_CWD_ALLOWLIST` entry and, through its generic
`_WALK_ROOTS` scan of `plugins/mill/skills/`, proves the relocated banner is allowlisted at its new
path and that no other skill file gained a wiki-cwd pattern. `test-skill-helper-drift.py` covers the
retargeted `#496` lock and, through its generic drift scan of every mill SKILL.md, proves every
`_<module>.<fn>(` helper reference in the relocated file still resolves after the move — which is
the check that would catch a truncated or mangled relocation.

The scope is deliberately narrow rather than a full `run-all.py`: this batch touches only two test
files plus one relocated SKILL.md. Batch 3 runs the unbounded suite as the plan's cross-cutting gate.
