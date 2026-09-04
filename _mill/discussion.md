# Discussion: code-comments skill: prohibit enumerating current consumers/writers of a shared resource

```yaml
task: 'code-comments skill: prohibit enumerating current consumers/writers of a shared resource'
slug: code-comments-skill-consumer-enumeration-rule
status: discussing
parent: main
```

## Problem

A comment that explains a shared resource often names every subsystem that currently touches it, as illustration.
The loomyard repo carried exactly this pattern in `internal/fabricengine/junction.go`, mirrored verbatim into `docs/overview.md` and `manifest/designs/fabric-unified-view.md`: the comment explaining that `.lyx/` is lyx's own machine-local scratch directory said "content under it is always lyx's own machine-local scratch (the logger, reed, shuttle, scout and burler all write it unconditionally)".

The comment's point -- `.lyx` is always lyx's own scratch, never user content, therefore safe to auto-adopt -- does not depend on *which* subsystems write there.
But the enumeration made the comment stale the moment `scout` was extracted out of the repo: an unrelated module removal forced edits to comments in three files that have nothing to do with that module, purely because they listed it as an example.

**Why now:** the pattern was flagged during the loomyard `scout-extract-standalone-repo` work (GitHub issue #907, 2026-08-20) and the fix there was applied by hand in three files.
The `mill:code-comments` skill is the shared, language-agnostic rulebook that both authors and reviewers load, so encoding the rule there is what stops the pattern recurring across every repo that uses mill.

## Scope

**In:**

- One new bullet added to the `## Prohibited patterns` section of `plugins/mill/skills/code-comments/SKILL.md`.

**Out:**

- No change to `plugins/golang/skills/golang-comments/SKILL.md`, `plugins/csharp/skills/csharp-comments/SKILL.md`, or `plugins/python/skills/python-comments/SKILL.md`.
  Of the three, only `golang-comments` has a `## Prohibited patterns` section at all (line 220), and its single bullet is a language *syntax/mechanics* rule ("No `/* block comments */` inside function bodies");
  `csharp-comments` and `python-comments` have no such section to extend.
  A language-agnostic content rule belongs in `code-comments` -- which those skills explicitly layer on top of -- and duplicating it into any of them would drift.
- No change to `SKILLS.md` -- the root index renders each skill's frontmatter `description:`, and the frontmatter is untouched.
  No `/mill-skills-index` run is required.
- No change to the review-prompt templates under `plugins/mill/templates/` (`review-code-batch.md`, `review-code-holistic.md`).
  Reviewers load the `code-comments` skill itself; the templates do not restate individual comment rules.
- No sweep of existing comments in the millhouse repo for violations of the new rule.
  This task ships the rule, not a codebase-wide remediation.
- No new unit test.
  See "## Testing".

## Decisions

### Placement -- `code-comments` only, as a `## Prohibited patterns` bullet

- Decision: add exactly one bullet to `plugins/mill/skills/code-comments/SKILL.md`'s `## Prohibited patterns` list, appended after the existing final bullet ("No measured-result or design-rationale narrative").
- Rationale: the rule is language-agnostic and concerns comment *content*, which is precisely what `code-comments` owns ("Language-agnostic -- each language's own `{lang}-comments` skill covers syntax and mechanics on top of this").
  The existing prohibited-pattern bullets are the closest siblings in both form and intent: `No edit-history comments` and `No measured-result or design-rationale narrative` are also "don't put volatile/incidental facts in a comment" rules.
- Note: of the per-language comment skills, only `golang-comments` has a `## Prohibited patterns` section (its one bullet is syntax-only); `csharp-comments` and `python-comments` have none.
  Either way there is no language-agnostic content rule in any of them to extend or duplicate.
- Rejected: a new top-level `##` section of its own -- overweight for a single rule, and it would separate the rule from the sibling anti-staleness bullets it belongs with.
  Also rejected: mirroring the bullet into each per-language comment skill -- duplication that would drift.

### Rule breadth -- consumers of any shared symbol or resource, not just directories

- Decision: phrase the rule to cover naming the *current set* of callers, writers, consumers, or implementers of a shared symbol or resource, not narrowly "writers of a scratch directory".
- Rationale: the staleness mechanism is identical whether the enumerated list is of directory writers, callers of a function, implementers of an interface, or subscribers to an event.
  Narrowing to the loomyard specifics would leave the same defect reachable through every other shape.
- Rejected: transcribing issue #907's example verbatim as the rule text -- it would read as a directory-specific rule and under-cover.

### Escape hatch -- keep "unless the specific names are load-bearing"

- Decision: retain the issue's proposed exception clause: the enumeration is permitted when the specific names are themselves load-bearing to the point the comment is making.
- Rationale: some comments genuinely turn on identity -- e.g. "only the migration runner may write this table; every other subsystem reads it" is a constraint statement whose whole content is *which* component is named.
  A blanket ban would force those comments to become vaguer and less useful.
- Rejected: an unconditional ban (over-broad, and would generate false-positive review findings).
  Also rejected: a softer "prefer not to" phrasing -- the surrounding bullets are all hard prohibitions and a hedge would read as optional.

### Suggested replacement wording included in the bullet

- Decision: the bullet includes the concrete rewrite guidance from the issue -- say "several of `<component>`'s own subsystems" (or similar) instead of enumerating by name -- plus the loomyard example as the illustrative parenthetical.
- Rationale: the existing bullets in this section all carry a short quoted example of the banned form (e.g. `"added in v2", "removed old logic"`), so an example matches house style; and giving the positive replacement makes the rule actionable rather than only prohibitive.
- Rejected: rule text with no example -- the pattern is easy to misread as banning all mention of callers, which it does not.

### Correction to the brief's premise

- Decision: do not add cross-references to a pre-existing "current task/fix/callers" rule.
- Rationale: the wiki brief asserts "same rationale already applied to comments referencing 'the current task/fix/callers'", but no such bullet exists in the skill today.
  Verified by reading `plugins/mill/skills/code-comments/SKILL.md` in this worktree in full: `## Prohibited patterns` has exactly four bullets (commented-out code, edit-history, mechanical restatements, measured-result/design-rationale narrative), and a repo-wide grep for staleness-rationale wording in the comment/quality/markdown skills returns nothing relevant.
  The nearest genuine sibling is the edit-history bullet, which shares the anti-staleness rationale but not the subject matter.
- Rejected: writing the bullet as an extension of a rule that does not exist -- it would produce a dangling reference.

### No sweep of existing millhouse comments

- Decision: ship the rule only; do not audit or rewrite existing comments in this repo.
- Rationale: issue #907's fix was already applied in loomyard.
  A millhouse-wide comment audit is unbounded work with a different review shape, and mixing it into a one-bullet skill change would obscure the diff.
- Rejected: a combined rule-plus-sweep task -- if a sweep is wanted it is a separate backlog item.

## Technical context

**The single file to edit:** `plugins/mill/skills/code-comments/SKILL.md`.

Current structure (top to bottom): YAML frontmatter (`name: code-comments`, `description: ...`), `# Code Comments Skill`, then sections `## Purpose, not mechanism` (with `### Corollary: many comments needed is a refactoring signal`), `## Length ceiling`, `## File/module header`, `## No end-of-line comments`, `## Line-wrap style -- semantic line breaks, not fixed-column wrapping`, and finally `## Prohibited patterns` at the end of the file.

`## Prohibited patterns` currently holds four bullets, in this order:

1. `**Never** comment out code.` (multi-line bullet: "Delete it." / "Version control handles history." on their own continuation lines)
2. `**No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").`
3. `**No mechanical restatements** -- ...` (two continuation lines)
4. `**No measured-result or design-rationale narrative** -- ...` (one continuation line)

The new bullet is appended as item 5, at the end of the file.

**Formatting the edit must follow** (from `plugins/mill/skills/markdown/SKILL.md` and the file's own existing style):

- Semantic line breaks -- one sentence per line; continuation lines of a bullet are indented two spaces to match the existing bullets 1, 3, and 4.
- Em dashes in the source file are written as the literal `—` character (the existing bullets use it); this file is markdown, not `print()` output, so the ASCII-only rule in CLAUDE.md does not apply here.
- No trailing whitespace; file ends with a single newline.

**Nothing else in the repo references this section.** Verified: `grep -rn "Prohibited patterns"` across `*.md` returns only `code-comments/SKILL.md:58` and `golang-comments/SKILL.md:220`; `grep -n "code-comments" plugins/mill/unit_tests/*.py` returns nothing.
`SKILLS.md:35` links the skill by path and quotes its frontmatter description only.

**Proposed bullet text** (mill-plan may refine wording, but must preserve: the prohibition, the staleness rationale, the concrete replacement phrasing, and the load-bearing escape hatch):

```markdown
- **No enumerated-consumer lists** — don't name every current caller, writer, consumer, or implementer of a shared symbol or resource when the comment's point doesn't depend on which ones currently do
  (e.g. "the logger, reed, shuttle, and burler all write it").
  That list goes stale whenever a subsystem is added or removed, turning an unrelated change elsewhere in the codebase into a forced edit here.
  Write "several of `<component>`'s own subsystems" or similar instead, unless the specific names are themselves load-bearing to the point being made.
```

## Testing

No new automated test.
Skill content is prose consumed by an LLM at load time; the repo has no harness that asserts on `SKILL.md` body text, and `plugins/mill/unit_tests/` contains no test referencing `code-comments`.
Adding one would mean pinning prose to a string literal, which is a brittle test that fails on every future wording tweak without catching a real defect.

Regression check instead -- the change must not break the two suites that *do* read skill files structurally:

- `plugins/mill/unit_tests/test-skills-index.py` (asserts `SKILLS.md` matches skill frontmatter; frontmatter is untouched, so this must stay green).
- `plugins/mill/unit_tests/test-skill-writer.py` and `test-skill-helper-drift.py` (structural skill checks).

**Verify command for the plan** (Python project -- the `PYTHONPATH=` prefix is mandatory per CLAUDE.md `## Verify command shape`):

```
PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

Plus a manual read-back of the rendered section confirming: the bullet is the fifth and final item under `## Prohibited patterns`, uses semantic line breaks with two-space continuation indent, and states all four required elements (prohibition, staleness rationale, replacement phrasing, load-bearing exception).

## Q&A log

- **Q:** Where should the rule live -- a new bullet under `## Prohibited patterns` in `code-comments/SKILL.md`, or a new top-level section? **A:** [auto-pick] One new bullet in `## Prohibited patterns` of `plugins/mill/skills/code-comments/SKILL.md` only. **Why:** it sits with its sibling anti-staleness rules (edit-history, measured-result narrative) and a single rule does not justify its own `##` section.
- **Q:** Should the bullet be mirrored into `golang-comments` / `csharp-comments` / `python-comments`? **A:** [auto-pick] No mirror bullet in the per-language comment skills. **Why:** those `## Prohibited patterns` sections carry syntax/mechanics only; `code-comments` is explicitly the language-agnostic layer, and duplicating would drift.
- **Q:** How broadly should the rule be phrased -- directory writers specifically, or consumers generally? **A:** [auto-pick] General: any comment naming the current set of callers, writers, consumers, or implementers of a shared symbol or resource. **Why:** the staleness mechanism is identical across all those shapes; narrowing to the loomyard case would under-cover.
- **Q:** Keep issue #907's escape hatch, or make the prohibition unconditional? **A:** [auto-pick] Keep "unless the specific names are themselves load-bearing to the point being made". **Why:** some comments turn on identity (e.g. "only the migration runner writes this table"); a blanket ban would make them vaguer and would generate false-positive review findings.
- **Q:** Should this task also sweep existing millhouse comments for the pattern? **A:** [auto-pick] Rule-only; no sweep. **Why:** the loomyard instance is already fixed; a repo-wide comment audit is unbounded and would obscure a one-bullet diff.
- **Q:** What verification does a prose-only skill change get? **A:** [auto-pick] Existing unit suite as a no-regression check, plus manual read-back; no new test. **Why:** no harness asserts on `SKILL.md` body prose, and pinning prose to a string literal is brittle without catching real defects.
- **Q:** The wiki brief claims this rationale was "already applied to comments referencing the current task/fix/callers" -- should the bullet cross-reference that rule? **A:** [auto-pick] No; record the correction in Decisions instead. **Why:** verification against the worktree file shows no such bullet exists; the nearest sibling is the edit-history bullet, and referencing a non-existent rule would leave a dangling pointer.
