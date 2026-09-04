# Batch: enumerated-consumer-rule

```yaml
task: 'code-comments skill: prohibit enumerating current consumers/writers of a shared resource'
batch: 'enumerated-consumer-rule'
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-skills-index.py test-skill-writer.py test-skill-helper-drift.py
depends-on: []
```

## Batch Scope

This batch delivers the whole task: one new bullet appended to the `## Prohibited patterns` section of `plugins/mill/skills/code-comments/SKILL.md`, banning comments that enumerate a shared resource's current callers/writers/consumers by name.
It is one batch because the task touches exactly one file and one section of it, with no runtime surface and no dependent work.
There is no external interface for a following batch to consume.
No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 1: Add the enumerated-consumer-list prohibition to code-comments

- **Context:**
  - `plugins/mill/skills/markdown/SKILL.md`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/code-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append one new bullet to the end of the `## Prohibited patterns` section of `plugins/mill/skills/code-comments/SKILL.md`, immediately after the existing final bullet whose label is `**No measured-result or design-rationale narrative**`.
  Do not modify, reorder, or reword any of the four existing bullets in that section (`**Never** comment out code.`, `**No edit-history comments**`, `**No mechanical restatements**`, `**No measured-result or design-rationale narrative**`).
  Do not modify the file's YAML frontmatter (`name: code-comments`, `description:`), and do not modify any other section of the file.
  Do not edit `plugins/golang/skills/golang-comments/SKILL.md`, `plugins/csharp/skills/csharp-comments/SKILL.md`, `plugins/python/skills/python-comments/SKILL.md`, or `SKILLS.md`.
  The new bullet's text is exactly:

  ```markdown
  - **No enumerated-consumer lists** — don't name every current caller, writer, consumer, or implementer of a shared symbol or resource when the comment's point doesn't depend on which ones currently do
    (e.g. "the logger, reed, shuttle, and burler all write it").
    That list goes stale whenever a subsystem is added or removed, turning an unrelated change elsewhere in the codebase into a forced edit here.
    Write "several of `<component>`'s own subsystems" or similar instead, unless the specific names are themselves load-bearing to the point being made.
  ```

  Reproduce that block byte-for-byte: the four physical lines, the two-space continuation indent on lines two through four, and the literal `—` em-dash character (matching the sibling bullets, which use the same character).
  The file must end with a single trailing newline and carry no trailing whitespace on any line.
- **Commit:** `docs(code-comments): prohibit enumerating a shared resource's current consumers`

## Batch Tests

`verify:` runs the three structural skill-file tests named in `_mill/discussion.md`'s `## Testing` section: `plugins/mill/unit_tests/test-skills-index.py`, `plugins/mill/unit_tests/test-skill-writer.py`, and `plugins/mill/unit_tests/test-skill-helper-drift.py`.
Together they cover every machine-checked invariant a `SKILL.md` edit can break -- `SKILLS.md` consistency with each skill's YAML frontmatter, skill-file structure, and skill/helper drift -- and the three run in ~0.1s combined, so the `--only` scoping costs nothing in coverage relative to the full suite.
No other unit test reads `code-comments/SKILL.md`;
`grep -n "code-comments" plugins/mill/unit_tests/*.py` returns nothing.

No new test is added.
As recorded in `_mill/discussion.md`'s `## Testing` section, the repo has no harness that asserts on `SKILL.md` body prose, and pinning prose to a string literal would fail on every future wording tweak without catching a real defect.
The substantive check is a manual read-back of the rendered section, confirming the bullet is the fifth and final item under `## Prohibited patterns` and states all four required elements: the prohibition, the staleness rationale, the replacement phrasing, and the load-bearing exception.
