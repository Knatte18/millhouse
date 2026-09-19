# Batch: turn-reduction-audit-doc

```yaml
task: Audit mill-start/mill-plan/mill-go for turn reduction
batch: turn-reduction-audit-doc
number: 1
cards: 4
verify: null
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

This batch produces the task's entire deliverable: `doc/turn-reduction-audit.md`, a permanent,
git-tracked audit classifying every step of `mill-start/SKILL.md`, `mill-plan/SKILL.md`, and
`mill-go-base/SKILL.md` as Mechanical/collapsible, Borderline, or Excluded, per
`_mill/discussion.md`. Four cards build the same file incrementally, in file order (card 1 creates
it with a scaffold plus the mill-start section, cards 2-3 add the mill-plan and mill-go-base
sections, card 4 adds cross-cutting recommendations, the follow-up backlog list, and a coverage
self-check). There is no external interface for a next batch to consume — this is the only batch.
No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 1: Scaffold audit doc; classify mill-start; confirm mill-go/mill-go2

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
  - `doc/backlog.md`
  - `_mill/discussion.md`
- **Edits:** none
- **Creates:**
  - `doc/turn-reduction-audit.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create `doc/turn-reduction-audit.md` using the fenced-`yaml`-metadata-block convention shown at
  the top of `doc/backlog.md` (a `source:` key naming this task; never `---` frontmatter). Give it
  an H1 title and these top-level sections, in this order: `## Scope`, `## Methodology`,
  `## mill-start`, `## mill-plan`, `## mill-go-base`, `## Cross-cutting recommendations`,
  `## Follow-up backlog candidates`, `## Coverage check`. Fill only `## Scope`, `## Methodology`,
  and `## mill-start` in this card; leave the remaining four headings with a one-line placeholder
  such as "_Filled by card N._" for the later cards to replace.

  `## Scope` restates the audit's In/Out boundary from `_mill/discussion.md`'s own `## Scope`
  section: `mill-start/SKILL.md`, `mill-plan/SKILL.md`, `mill-go-base/SKILL.md` are the audit
  targets; `mill-go/SKILL.md` and `mill-go2/SKILL.md` are checked only for whether they add
  anything of their own beyond loading `mill-go-base`; `mill-merge`, `mill-finalize`, and every
  other skill are out of scope for this audit (cite this exclusion explicitly — a reader who only
  read the task's motivating background, which mentions `mill-merge`, could otherwise assume it is
  in scope).

  `## Methodology` restates the three-bucket scheme from `_mill/discussion.md`'s "Classification
  scheme" Decision — Mechanical/collapsible, Borderline, Excluded, with each bucket's definition —
  and names `plugins/mill/skills/workflow/SKILL.md`'s anti-pattern #2 by section reference for the
  Excluded bucket's round-by-round-loop criterion, without quoting or restating its content. State
  the four required fields for a Mechanical/collapsible entry (step range, current per-step
  behavior, already-scripted-per-step vs. un-scripted, rough turn-count saving) and the required
  shape for a Borderline entry (both a full-exclusion alternative and a scoped-partial-collapse
  alternative, each described, plus an explicit recommendation between them — never a single forced
  verdict, per `_mill/discussion.md`'s "Borderline treatment" Decision).

  `## mill-start` walks every `### Phase:` heading and every numbered step under `## Entry` in
  `mill-start/SKILL.md`, in file order, and classifies each into exactly one bucket, using the
  fields `## Methodology` just defined. Do not skip the `--auto`/`--orch` mode sections or the
  Tree-guard/Convergence-gate subsections — classify those too (most will be Excluded, since they
  are judgment/branching logic, but state that explicitly rather than omitting them). Immediately
  below the `## mill-start` heading, add one short paragraph confirming that `mill-go/SKILL.md` and
  `mill-go2/SKILL.md` add no mechanical step sequences of their own beyond loading
  `mill-go-base/SKILL.md` — `mill-go` is a bare load-and-follow wrapper, `mill-go2` only overrides
  dispatch calls with fork/cold-fallback branching logic (judgment, not mechanical) and preloads a
  fixed skill set once per session — per `_mill/discussion.md`'s "Technical context" section, which
  already confirmed this; re-verify against the current files rather than copying that confirmation
  on faith.
- **Commit:** `docs(turn-reduction-audit): scaffold audit doc, classify mill-start`

### Card 2: Classify mill-plan

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `_mill/discussion.md`
- **Edits:**
  - `doc/turn-reduction-audit.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the `## mill-plan` placeholder in `doc/turn-reduction-audit.md` (created by card 1).
  Walk every numbered step under `## Entry` and every phase/step under `## Phases` in
  `mill-plan/SKILL.md`, in file order, classifying each into exactly one bucket per `## Methodology`.
  Do not skip the `--revise`/`--approve` pre-checks, the "Entry-gate wait for upstream mill-start"
  and "Entry: resuming after a max-rounds block" subsections, or the Convergence-gate/tree-guard
  paragraphs — classify those too.

  Give special attention to Entry step 4's phase-table branch (the `_mill/discussion.md` "Borderline
  treatment" Decision's own worked example): record it as Borderline with both alternatives
  (full exclusion vs. a scoped partial collapse where a script call does only the deterministic
  `phase:`/`approved:`/`blocked_reason:` read-and-classify work, and the SKILL.md keeps every
  distinct halt message and the branch-selection decision itself) and a recommendation between
  them, plus the real line range this step currently spans in `mill-plan/SKILL.md` (re-derive it —
  do not copy `_mill/discussion.md`'s citation, which the discussion review round already found
  a drifted example of, without re-checking it against the current file).
- **Commit:** `docs(turn-reduction-audit): classify mill-plan`

### Card 3: Classify mill-go-base

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `_mill/discussion.md`
- **Edits:**
  - `doc/turn-reduction-audit.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the `## mill-go-base` placeholder in `doc/turn-reduction-audit.md`. Walk every numbered
  step and every `###`-level section under `## Prepare`, `## Execute — sequential loop`,
  `## Agent-mode dispatch`, `### Stuck escalation`, `### Blocked`, and every other top-level section
  in `mill-go-base/SKILL.md`, in file order, classifying each into exactly one bucket per
  `## Methodology`.

  Re-derive, from the current file, the `_status.append_phase` call-site count and the paired
  `_status.append_phase` + git-commit pattern's occurrences (do not copy `_mill/discussion.md`'s
  cited counts on faith — that document itself flags them as a starting point, not ground truth,
  and the discussion-review round already found one of them one off). Record the `## Prepare`
  section (`_status.init_batches` -> `_status.append_phase("implementing", ...)` -> one git commit)
  as a Mechanical/collapsible entry with its real current line range, current per-step behavior,
  and a rough turn-count saving, following the four required fields from `## Methodology`.
- **Commit:** `docs(turn-reduction-audit): classify mill-go-base`

### Card 4: Cross-cutting recommendations, follow-up backlog, coverage check

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `doc/turn-reduction-audit.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the three remaining placeholders in `doc/turn-reduction-audit.md`.

  `## Cross-cutting recommendations` carries forward, as recommendations for whoever implements the
  accepted candidates (not as new decisions made by this task), the two design questions
  `_mill/discussion.md` already resolved: (1) the "Helper-function home for the `append_phase` +
  git-commit pattern" Decision — a new, separate module (e.g. `_status_commit.py`) composing
  `_status.append_phase` with the existing `_subprocess_util.git_commit`, not an addition to
  `_status.py` itself, to preserve `_status.py`'s current git-free, unit-testable-with-no-real-git
  nature; (2) the "Borderline treatment: partial collapse over all-or-nothing" Decision — every
  Borderline entry records both alternatives with a recommendation, never one forced verdict.

  `## Follow-up backlog candidates` lists one bullet per accepted Mechanical/collapsible candidate
  found across the three `## mill-start`/`## mill-plan`/`## mill-go-base` sections, and one bullet
  per Borderline candidate whose recommendation in this doc favors the scoped-partial-collapse
  alternative — each bullet phrased as a ready-to-file wiki-task one-liner (a short title plus one
  sentence of scope), since the task body states each accepted candidate becomes its own follow-up
  backlog task once this audit is reviewed. Do not include Excluded items or a Borderline candidate
  whose recommendation favors full exclusion.

  `## Coverage check` records a completeness self-check, run ad hoc during this card (not as a new
  persisted script — no new tooling ships in this task): for each of `mill-start/SKILL.md`,
  `mill-plan/SKILL.md`, `mill-go-base/SKILL.md`, enumerate every `###`-level heading and every
  top-level numbered step, and confirm each one is classified somewhere in the corresponding
  section of `doc/turn-reduction-audit.md` — no step silently dropped, none double-counted. State
  the check's outcome in this section (e.g. counts matched, or name any heading that needed a
  second look and how it was resolved).
- **Commit:** `docs(turn-reduction-audit): add recommendations, backlog list, coverage check`

## Batch Tests

`verify: null` — this is a pure-docs batch with no runnable surface: the only file this batch
touches is `doc/turn-reduction-audit.md`, a markdown document, per
`plugins/mill/templates/plan-batch.md`'s own documented example for this field. The substitute for
an automated test is: (1) card 4's own inline coverage self-check, recorded in the doc's
`## Coverage check` section; (2) the Code Review loop's reviewer applying the manual completeness
criteria from `_mill/discussion.md`'s `## Testing` section (every step assigned to exactly one
bucket; every Mechanical/collapsible entry carries its four required fields; every Borderline entry
carries both alternatives plus a recommendation; no implementation of any candidate leaks into the
doc or elsewhere in the diff; `mill-merge`/`mill-finalize`/other skills stay out of scope).
