# Batch: handoff-skill-doc-fix

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: handoff-skill-doc-fix
number: 6
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes #1095: `handoff/SKILL.md` has no explicit ban on a "Done this session" commit changelog, and a
handoff that overwrites a prior handoff inherits that prior document's outline rather than being
re-derived from the skill's own rules — so one generation's violation reproduces in every later one.
Pure documentation edit, no runnable surface.

## Cards

### Card 15: add explicit anti-pattern ban, positive job statement, and overwrite-case handling

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/skills/handoff/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Rewrite `plugins/mill/skills/handoff/SKILL.md` to add the following four elements, per
  `_mill/discussion.md`'s `handoff-no-session-changelog` Decision:
  1. An explicit prohibition the author cannot read past: the handoff must not contain a session
     changelog under any heading — name "Done this session", "Changes made", "Completed work", and
     "Recent commits" as anti-pattern headings to reject on sight. State plainly: work already
     committed is described by its commit; work already merged is described by its PR — never
     restated in the handoff.
  2. A one-line positive statement of the document's job: it carries current state and durable
     facts, not history. Give the author a per-line test: "would a fresh agent act differently if
     this line were missing? If not, cut it." State explicitly that this test removes passing test
     counts, timings, and descriptions of already-finished edits, while keeping open PRs, in-flight
     work, and constraints.
  3. Explicit handling of the overwrite case: when the handoff replaces an existing handoff document,
     the author re-derives every section from this skill's own rules and treats the previous file
     only as a source of facts (e.g. "PR #183 is still open"), never as a section template or outline
     to inherit.
  4. A short anti-pattern example list under item 1's prohibition, each with a one-line "why not": a
     committed refactor (already captured by its commit), a green test run with its duration
     (not durable, doesn't change what a fresh agent does), a merged PR's contents (already captured
     by the PR), a review whose file is already committed at a known path (reference the path
     instead of restating findings).
  Keep the existing rule ("Do not duplicate content already captured in other artifacts... Reference
  them by path or URL instead.") — the new prohibition sharpens it for the commit/PR/review case
  specifically, it does not replace it.
- **Commit:** `docs(handoff): ban session changelogs and fix the overwrite-inheritance propagation (#1095)`

## Batch Tests

Documentation-only — no runnable surface. Verified by re-reading the rewritten `handoff/SKILL.md`
and confirming all four elements are present as distinct, locatable statements (not folded into
vague prose), and that none of the four named anti-pattern headings ("Done this session", "Changes
made", "Completed work", "Recent commits") appear anywhere else in the file as an implied allowed
pattern.
