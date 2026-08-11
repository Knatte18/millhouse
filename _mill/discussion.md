# Discussion: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)

```yaml
task: 'mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet)'
slug: mill-go2-scaffold
status: discussing
parent: main
```

## Problem

Two planned experiments — `mill-go2-fork-implementer` and `mill-go2-fork-fixer` — want to swap
mill-go's implementer and fixer dispatch from a cold `Agent(subagent_type: "mill:mill-implementer")`
call to `Agent(subagent_type: "fork")`, so each batch inherits the driver's already-loaded plan and
codebase context instead of re-reading it cold. Neither experiment should be run against `/mill-go`
itself: mill-go is the production orchestrator, and a fork experiment that destabilises it stops all
real work.

So both experiments need a second, independently-invocable orchestrator that behaves identically to
mill-go today. This task builds exactly that and nothing more — no fork behaviour is introduced here.

**Why now:** the original `mill-go2-fork-implementer` proposal was flagged as too large for one pass
and split into three tasks on 2026-08-11. This is step 1; the other two depend on it.

The naive way to build it is to copy `plugins/mill/skills/mill-go/SKILL.md` (1424 lines) to
`mill-go2/SKILL.md`. That creates a second copy of machinery that is under active development, and
the copy silently rots as mill-go evolves. The proposal explicitly asked this task to decide how that
drift is prevented rather than defaulting to accept-drift. The operator's answer, taken during
discussion, is to remove the duplication instead of policing it: extract the shared machinery into a
base skill that both orchestrators load.

## Scope

**In:**

- New `plugins/mill/skills/mill-go-base/SKILL.md` — the whole of today's `mill-go/SKILL.md` machinery,
  moved verbatim, with two parameterizations: a `VARIANT_LABEL` token, and two declared override
  points (see Decisions).
- `plugins/mill/skills/mill-go/SKILL.md` rewritten as a thin variant file (~25 lines) that binds
  `VARIANT_LABEL: mill-go`, declares both override-point sections as `(none)`, and loads the base.
- New `plugins/mill/skills/mill-go2/SKILL.md` — same thin shape, `VARIANT_LABEL: mill-go2`, both
  override-point sections `(none)` today.
- Repoint every existing cross-reference that names `mill-go/SKILL.md` as the location of machinery
  that has moved to the base, and add `mill-go2` to the two prose orchestrator-lists that name
  `mill-go` without citing its path (full enumeration under Technical context).
- Update `plugins/mill/unit_tests/test-guards.py`'s `_WIKI_CWD_ALLOWLIST` and
  `plugins/mill/unit_tests/test-skill-helper-drift.py`'s `mill_go_skill_path` locks to target the
  base file.
- New unit test asserting the variant contract holds: both variant files declare `VARIANT_LABEL`,
  both declare the two override-point sections, and the base halts when loaded without a variant.
- Regenerate `SKILLS.md` (via `/mill-skills-index`) so all three skills are indexed.

**Out:**

- **Any fork behaviour.** No `Agent(subagent_type: "fork")` call is introduced anywhere. Both
  variants dispatch every role via the base's existing cold `Agent()` path. mill-go2 is functionally
  identical to mill-go at the end of this task; only the invocation name differs.
- **Renaming `/mill-go`.** It keeps its name; no `mill-go1` is created.
- **New config keys.** No `roles.mill-go2.*` section in `mill-config.yaml` or the plugin template.
- **Script changes.** No Python under `plugins/mill/scripts/` changes behaviour. In particular
  `millpy-implement.py`, `millpy-fix.py`, and `_implementer_common.py` are untouched.
- **Wiring mill-go2 into any automatic path.** mill-plan's handoff text still names `/mill-go` only;
  mill-autofix, mill-resume, mill-status, and mill-pause are not taught about mill-go2.
- **Extracting SKILL.md prose into new `_*.py` helpers.**
- **A `variant:` field in `status.md`'s yaml block.**
- **Webster's own mechanisms** — the foreground `await-batch` poll loop, the two-tier
  warm-refork-then-cold-strand recovery, and the minimal 3-field report contract. These belong to the
  two follow-on fork tasks, and two of the three are already superseded by mill-go's harness-native
  equivalents (see Technical context).

## Decisions

### three-file-split

- Decision: `mill-go-base` (all machinery) + `mill-go` (thin variant) + `mill-go2` (thin variant).
  The base is not directly invocable by the operator; its Entry halts if no variant bound a
  `VARIANT_LABEL`.
- Rationale: there is then exactly one copy of the machinery, so there is nothing to drift. This
  also makes the two follow-on fork tasks edit one small file each instead of re-forking 1424 lines.
  The split is cheap because every dispatch in mill-go already funnels through one section — see
  `single-dispatch-funnel` below.
- Rejected: verbatim clone of `mill-go/SKILL.md` to `mill-go2/SKILL.md` (the proposal's default) —
  two copies of an actively-developed 1424-line file, drift guaranteed. Also rejected: a delta/patch
  file describing edits against mill-go — would force the fork tasks to write fragile
  "replace step N of section X" prose.

### keep-mill-go-name

- Decision: the v1 variant keeps the skill name `mill-go` and the invocation `/mill-go`. No
  `mill-go1` is introduced.
- Rationale: `/mill-go` appears in mill-plan's handoff message, mill-status's phase table,
  mill-resume, mill-pause, mill-autofix, README, and operator muscle memory. Renaming buys symmetry
  and costs churn across all of those.
- Rejected: renaming to `mill-go1` for symmetry with `mill-go2`.

### override-point-terminology

- Decision: the two variant-fillable sections are called **override points**. The word **hook** must
  not be introduced to describe them anywhere — in the SKILL files, the plan, commit messages, or
  code comments. This is a ban on *new* usage naming the override mechanism, not a global ban on the
  English word: `mill-go/SKILL.md` already contains two incidental occurrences that move to the base
  unchanged under the byte-for-byte rule ("At the hook point, run all of:" in the per-batch baseline
  recapture section, and "this mode has no separate finalize call to hook before" in the Implement
  section). Neither refers to an override point, and neither is reworded.
- Rationale: `hook` already means Claude Code's `settings.json` hook mechanism (`PreToolUse`,
  `UserPromptSubmit`, …). Overloading it in mill's own docs would make both meanings ambiguous.
  Scoping the ban to new override-point usage keeps it from colliding with the byte-for-byte move
  guarantee — a blanket textual ban would force a silent reword of source text this task promises
  not to touch.
- Rejected: "hook", "extension point", "slot" as the term. Also rejected: a blanket
  no-`hook`-anywhere rule, for the collision described above.

### preamble-to-base

- Decision: the pre-`## Entry` preamble of today's `mill-go/SKILL.md` — the `> Wiki access:` banner
  and the "You are the **Builder** — a lean orchestrator" role paragraph — moves to `mill-go-base`.
  It is not reproduced in either thin variant. Each of the three files carries its own `---`
  frontmatter and its own `# <name>` title.
- Rationale: both are machinery-level instructions to whoever is driving the batch loop, and the
  driver is the base. Reproducing them per variant would recreate exactly the duplication
  `three-file-split` exists to remove. This also settles the `test-guards.py` allowlist concretely:
  the banner is the only line in the entire file matching `_WIKI_CWD_PATTERNS`, so the allowlist
  entry follows it to the base — `mill-go-base/SKILL.md` is added, `mill-go/SKILL.md` is removed,
  and `mill-go2/SKILL.md` is never added.
- Rejected: reproducing the preamble in each thin variant; leaving its destination unstated.

### two-override-points

- Decision: the variant contract declares exactly two override points, both present and both filled
  with `(none)` in both variants as of this task:
  - **A — `## Dispatch overrides`.** Consulted by the base at step 3 of `## Agent-mode dispatch`
    (the `Agent()` tool call itself). A variant may declare a per-role replacement for that call. The
    base's directive reads: *consult your variant's `## Dispatch overrides` for this role; if it
    declares one, follow it instead of the default `Agent()` call below.*
  - **B — `## Driver preamble`.** Consulted by the base at the top of Entry. Text the variant
    contributes ahead of the base's own instructions, which every subagent forked from the driver
    would inherit. The base's directive reads: *treat your variant's `## Driver preamble` text as if
    written here, ahead of everything below; if your variant declared no such section, halt — this
    skill is not invocable directly.*
- Rationale: A alone is not sufficient for the follow-on fork tasks. A fork inherits the driver's
  entire context, which under this design includes the whole of `mill-go-base` — the batch loop, the
  phase gate, the commit verbs. Loomyard's Webster module treats an implementer that misidentifies
  itself as the driver as a run-fatal failure and mitigates it with a disambiguation block at the
  top of the *driver's own* prompt (`master-template.md:12-15`), not at the dispatch site. Under
  override point A alone, `mill-go2-fork-implementer` could not express that and would have to
  reopen the base — which is the coupling this task exists to remove. Declaring B now costs two lines
  of `(none)` per variant plus one directive in the base.
- Rejected: declaring only A and letting the fork task add B later. Also rejected: a third
  wait/poll override point mirroring Webster's `await-batch` loop — unnecessary, see
  `no-wait-override` below.

### no-wait-override

- Decision: no override point for the post-dispatch wait. The base's existing `<task-notification>`
  wait plus `TaskOutput(task_id: <agentId>, block: false)` liveness probe stays the single mechanism
  for every variant.
- Rationale: Webster's short foreground `await-batch` poll loop exists because `lyx` is a Go CLI
  driving Claude Code from outside the harness, so it has no notification channel. mill-go is
  in-harness and already receives a completion notification with an `agentId` handle. A fork is also
  a backgrounded agent with an `agentId`, so the same wait and the same liveness probe apply to it
  unchanged.
- Rejected: adding a wait/poll override point for symmetry with Webster.

### variant-label-in-logs

- Decision: `VARIANT_LABEL` replaces the literal `mill-go` in **all three** literal families inside
  the base — the SKILL-authored `commit -m "mill-go: …"` subjects, the `_notify.notify("mill-go.…")`
  event names, and the `[mill-go]` operator-facing echo/halt prefixes. Counts and the exact grep
  commands that regenerate the site list live in the "What is parameterized in the base" table under
  Technical context; that table is the single source of truth for the inventory, and this Decision
  deliberately restates no numbers of its own. A mill-go2 run therefore writes
  `mill-go2: approve batch <name>`, emits `mill-go2.done`, and echoes `[mill-go2]`; a mill-go run is
  unchanged from today.
- Rationale: the operator wants git history and desktop notifications to record which variant did
  the work, so the fork experiment's runs are distinguishable after the fact.
- Rejected: keeping `mill-go:` in both variants (no way to tell the runs apart). Also rejected:
  adding a `variant:` field to `status.md`'s yaml block — that schema is read by `millpy-cleanup.py`,
  mill-status, and several tests, and the commit prefix plus notify event already carry the signal.

### script-side-prefixes-unchanged

- Decision: the commit subjects written by Python scripts keep the literal `mill-go` prefix under
  both variants — `mill-go: start batch <name>` (`millpy-implement.py`), `mill-go: fixing batch …`
  and `mill-go: holistic fix round …` (`millpy-fix.py`). No `--variant-label` flag is threaded
  through, and `_implementer_common.py`'s prefix matching is not widened.
- Rationale: `_implementer_common.py` parses the literal string `"mill-go: start batch"` at three
  sites (lines 35, 55, 103) as part of the Bug #557 commit-recount logic. Touching that parser to
  gain cosmetic consistency risks the batch-completeness detection. A mill-go2 run's history mixing
  `mill-go: start batch X` with `mill-go2: approve batch X` still identifies the variant on every run.
- Rejected: threading `--variant-label` through `millpy-implement.py` / `millpy-fix.py` and widening
  the parser to accept either prefix.

### config-reuse

- Decision: mill-go2 reads the existing `roles.implementer.*`, `roles.fixer.*`, `roles.code-review.*`,
  and `pipeline.*` config unchanged. No new keys in the hub `mill-config.yaml` or the plugin template.
- Rationale: mill-go2 is behaviourally identical to mill-go in this task, and the config keys are
  read by the Python CLIs (`millpy-implement.py`, `millpy-fix.py`, the three review CLIs), not by
  the SKILL prose — so a parallel `roles.mill-go2.*` section would require script changes for zero
  behavioural gain. The follow-on fork tasks can add keys if their dispatch genuinely needs to
  diverge; the sibling proposal already lists that as an open question it owns.
- Rejected: adding a `roles.mill-go2.*` section now.

### no-python-extraction

- Decision: no SKILL.md prose is extracted into new `_*.py` helpers as part of this task.
- Rationale: the mechanisable parts are already factored — `_phase_gate.py`, `_phase_wait.py`,
  `_plan_dag.py`, `_status.py`, `_treeguard.py`, `_agent_dispatch.py`, `_builder_lock.py`. What
  remains in the SKILL is orchestration narrative addressed to the model, which has no Python
  equivalent to extract into.
- Rejected: identifying and extracting further helpers as part of this task (scope inflation).

### opt-in-only

- Decision: mill-go2 is invoked only by an explicit operator `/mill-go2`. mill-plan's handoff text is
  unchanged and still names `/mill-go` alone.
- Rationale: the proposal requires it, and an experimental orchestrator must not become reachable by
  default.
- Rejected: mentioning `/mill-go2` in mill-plan's handoff as an alternative.

### verification-approach

- Decision: unit tests for the variant contract, plus **one live `/mill-go` run on a real task** to
  prove the base survived extraction. A live `/mill-go2` run is desirable but not a gate for this
  task.
- Rationale: the base extraction is a refactor of the production orchestrator. File-level assertions
  can prove the sections exist but prove nothing about the batch loop, phase gate, review loop, or
  handoff still working end-to-end. Only a real run does that, and v1 is the variant whose breakage
  would matter most.
- Rejected: file-level assertions only. Also rejected: gating the task on live runs of *both*
  variants.

### single-dispatch-funnel

- Decision: override point A attaches at step 3 of `## Agent-mode dispatch` in the base, and nowhere
  else.
- Rationale: mill-go already routes every dispatch through that one section. All twelve call sites
  read identically — *"follow the Agent-mode dispatch pattern (see `## Agent-mode dispatch` above)
  with `<cli> = X` and `<args> = …`"* — at `mill-go/SKILL.md` lines 548, 708, 757, 779, 811, 899,
  917, 935, 1088, 1138, 1195, 1217. So a single attachment point covers implementer, fixer, reviewer,
  and merge-in dispatch, in both the per-batch loop and the holistic loop, including the resume paths.
- Rejected: per-section override points at each of the twelve call sites.

## Technical context

### The file being split

`plugins/mill/skills/mill-go/SKILL.md` — 1424 lines. Top-level sections: `## Entry` (with
`### Mid-execution phase-gate widening` and `### Entry-gate wait for upstream mill-plan`),
`## Prepare`, `## Execute — sequential loop`, `## Agent-mode dispatch`, the numbered execute
subsections `### 0.` through `### 3.` plus `### Stuck escalation` / `### Blocked`, `## Resume`,
`## Holistic code review`, `## Handoff`, `## Principles`, `## Board discipline`. All of it moves to
the base.

The pre-`## Entry` preamble — the `> Wiki access:` banner and the "You are the **Builder** — a lean
orchestrator" role paragraph — also moves to the base; see the `preamble-to-base` Decision. Each of
the three files keeps its own `---` frontmatter and its own `# <name>` title line, which is the only
text that is necessarily per-file rather than moved.

### What is parameterized in the base

Three literal families become `VARIANT_LABEL`. **Do not work from a hand-copied line list** — this
repo is self-hosting and `mill-go/SKILL.md` is under active development, so line numbers will have
shifted by the time the plan is written and again by the time it is implemented. Regenerate the work
inventory with these commands, run from the task worktree:

```bash
F=plugins/mill/skills/mill-go/SKILL.md
grep -n 'commit -m "mill-go: ' "$F"          # SKILL-authored commit subjects
grep -n '_notify\.notify("mill-go\.'  "$F"   # notify event names
grep -n '\[mill-go\]' "$F"                   # operator-facing echo/halt prefixes
```

Counts as of commit `6442a688` (2026-08-11), for sanity-checking the grep output — a mismatch means
mill-go changed since this discussion, which is information, not an error:

| Family | Sites | Notes |
| --- | --- | --- |
| `commit -m "mill-go: …"` | 26 | |
| `_notify.notify("mill-go.…")` | 8 call sites | 5 distinct event names: `blocked` (×4), `done`, `holistic-fallback`, `review-exhausted`, `review-need-context` |
| `[mill-go]` echo/halt prefix | 10 | |

Every one of these sites must be parameterized. A missed site silently keeps a `mill-go:` prefix
under mill-go2, defeating `variant-label-in-logs`.

Everything else is moved byte-for-byte, with one narrow exception recorded under
`preamble-to-base` below (each file necessarily carries its own frontmatter and `# <name>` title).

### Cross-references that must be repointed

These name `mill-go/SKILL.md` as the home of machinery that moves to the base. All must be checked
and repointed to `mill-go-base/SKILL.md`:

- `plugins/mill/skills/mill-start/SKILL.md` — lines 179, 239, 241, 251, 276, 290, 292
- `plugins/mill/skills/mill-plan/SKILL.md` — lines 119, 362, 381, 396, 452
- `plugins/mill/skills/mill-merge-in/SKILL.md` — lines 87, 139
- `plugins/mill/skills/mill-quick/SKILL.md` — line 23 (references mill-go's "0.55" block)
- `plugins/mill/docs/harness-tool-contracts.md` — lines 22, 34
- `plugins/mill/scripts/millpy-implement.py` — lines 517, 523 (comment plus a **user-facing error
  string**), 720 (comment)
- `plugins/mill/unit_tests/test-phase-wait.py` — line 153 (comment)
- `plugins/mill/skills/mill-go/SKILL.md` — line 321 self-reference

Two further sites name `mill-go` in prose *without* citing its file path, so they fall outside the
enumeration above and would go stale silently once a second orchestrator exists. Both list the
orchestrators a Bash-convention rule applies to, and both must gain `mill-go2`:

- `plugins/mill/skills/cli/SKILL.md:40` — "Autonomous agents (mill-plan, mill-go) constructing new
  Bash commands must use the resolved path verbatim …"
- `plugins/mill/skills/conversation/SKILL.md:74` — "Applies to every Bash call made directly by the
  orchestrator (mill-start, mill-plan, mill-go, …)"

Neither is a behaviour gap — the underlying rules are enforced by the base's own Step 0 and by the
`mill:conversation` load that every variant inherits — so this is accuracy maintenance, not a
correctness fix. Add `mill-go2` to both lists. Do **not** add `mill-go-base`: these lists name what an
operator invokes, and the base is never invoked directly.

Note the "Why not fork?" paragraph at `mill-go/SKILL.md:399-406` is referenced by both
`mill-start/SKILL.md:179` and `mill-plan/SKILL.md:119`. It moves to the base with everything else.
Its content stays accurate for both variants as of this task, since neither forks yet.

### Test locks that must be updated

- `plugins/mill/unit_tests/test-guards.py:141` — `_WIKI_CWD_ALLOWLIST` contains
  `"plugins/mill/skills/mill-go/SKILL.md"`. Exactly one line in the whole file matches
  `_WIKI_CWD_PATTERNS`: the `> Wiki access:` banner in the pre-Entry preamble. Per `preamble-to-base`
  that banner moves to the base, so: add `"plugins/mill/skills/mill-go-base/SKILL.md"`, remove the
  `mill-go` entry, and do not add `mill-go2`. The removal is not optional bookkeeping — leaving a
  stale allowlist entry would mask a future reintroduction of a wiki-cwd pattern into the thin
  variant.
- `plugins/mill/unit_tests/test-skill-helper-drift.py:178,185` — reads `mill-go/SKILL.md` and asserts
  the literal `reviews_dir = hub / '_mill/reviews'` is present (the #496 regression lock). That
  string moves to the base; the test must follow it.

### Skill registration

`plugins/mill/.claude-plugin/plugin.json` lists only `agents`, not skills — skills are discovered
from `plugins/mill/skills/<name>/SKILL.md`. Creating the two new directories is sufficient to
register `mill:mill-go-base` and `mill:mill-go2`; no manifest edit. `SKILLS.md` at the repo root is
generated from SKILL.md frontmatter and is regenerated via `/mill-skills-index`.

### Loading the base from a variant

Loading one skill from another via the Skill tool is an established pattern in this codebase:
`mill-start/SKILL.md` Step 0 and `mill-go/SKILL.md` Step 0b both load `mill:conversation`
unconditionally as their first action. The variant files use the same mechanism to load
`mill:mill-go-base`.

Because `mill-go-base` appears in the skill list like any other skill, its frontmatter `description`
must state that it is internal and invoked by `/mill-go` or `/mill-go2` rather than directly, and its
Entry must halt when no variant has bound a `VARIANT_LABEL`.

### Shared state between the two variants

`_builder_lock.py` is a per-worktree mutex keyed on the slug, not on the orchestrator. mill-go and
mill-go2 therefore already exclude each other within one worktree, which is the desired behaviour and
requires no change.

`status.md`'s phase strings (`implementing`, `reviewing-<batch>-r<N>`, `holistic-reviewing`, …) are
identical under both variants, so a task started under one and resumed under the other resumes
correctly. This is a consequence of the shared base, not a separate design goal.

### Webster background (context for the follow-on tasks, not work for this one)

Read during discussion: `/home/knatte/Code/loomyard/wts/loomyard/internal/websterengine/`
(`master-template.md`, `fork-prefix.md`, `recovery-prefix.md`, `implementer-body.md`,
`integration-template.md`) and `docs/reference/webster-contract.md`.

Three points that shaped decisions above:

1. Webster's Master spawns each implementer with the prompt `"Read this file and follow it exactly:
   <path>"` so the prompt text never enters the driver's context. mill-go's Agent-mode dispatch step 3
   (`mill-go/SKILL.md:223`) already uses the same form — `"Read this file and follow the instructions
   exactly: <brief_path>"`. The two designs converge here, which is why override point A is a clean
   swap of one call.
2. Webster's Master prompt opens with a self-disambiguation block (`master-template.md:12-15`) because
   the prompt is inherited by every fork, and a fork that concludes it is the Master forges
   driver-only actions and fails the run's audit. This motivated override point B.
3. Webster's foreground `await-batch` polling and its cold recovery strand exist because `lyx` drives
   Claude Code from outside the harness. mill-go's in-harness notification plus `TaskOutput` liveness
   probe is the equivalent, so no wait override point is needed.

## Constraints

No `CONSTRAINTS.md` at the hub root and no `_codeguide/` in this repo. Repo-wide constraints from
`CLAUDE.md` that bear on this task:

- `${CLAUDE_PLUGIN_ROOT}` is written literally in Bash tool calls for all intra-plugin paths; its
  value is never read or memorized. The base inherits this rule verbatim from mill-go.
- Source-code verification during planning and implementation targets the task-worktree path
  (`/home/knatte/Code/millhouse/wts/mill-go2-scaffold/...`), never the plugin cache — this repo is
  self-hosting and the two can diverge.
- `print()` / `_log()` output is ASCII only.
- Generated markdown uses fenced ` ```yaml ` metadata blocks, except SKILL.md and plugin manifests,
  which use `---` frontmatter. All three skill files here use `---` frontmatter.
- Never use `sed` — in this repo or in any prompt generated for a dispatched sub-agent.
- `verify:` commands in plan files must start with a literal empty `PYTHONPATH=` prefix, since this
  is a Python project (`plugins/mill/pyproject.toml` is present).

## Testing

Unit tests live in `plugins/mill/unit_tests/test-<name>.py` and run via `run-all.py`; they use
in-memory and tempfile fixtures with no real git or LLM.

**TDD candidate — the variant contract test.** A new `test-mill-go-variants.py` is the one genuinely
new test surface, and it is worth writing before the split so it drives the shape of the contract.
Scenarios it must cover:

- Both `mill-go/SKILL.md` and `mill-go2/SKILL.md` declare a `VARIANT_LABEL`, and the two values are
  distinct.
- Both declare a `## Dispatch overrides` section and a `## Driver preamble` section, so a variant
  cannot silently omit one and leave the base consulting a section that does not exist.
- Both instruct loading `mill:mill-go-base`.
- `mill-go-base/SKILL.md` contains the directive that halts when no variant bound a `VARIANT_LABEL`.
- Neither variant file contains the machinery — a size or marker assertion catching a future
  regression where someone re-inlines the base into a variant.
- The override points are never described as "hooks": the assertion is scoped to the two override
  point section headers and the base's two directives that consult them, **not** a global search for
  the word in the file. A blanket search would fail immediately on the two incidental pre-existing
  occurrences the base inherits byte-for-byte — see `override-point-terminology`. Asserting the
  scoped form and asserting the absence of those two known strings are different tests; only the
  scoped one is wanted.

**Updated existing tests.** `test-guards.py` and `test-skill-helper-drift.py` must pass with their
locks retargeted at the base. These are updates to existing assertions, not new scenarios.

**Full suite.** `run-all.py` must pass — the split touches strings that several tests reference
indirectly, so a green full run is the signal that no lock was missed.

**Live verification (the real gate).** One `/mill-go` run against a real task, exercised end to end:
entry phase gate, prepare, at least one batch through implement → code review → approve, holistic
review, and handoff. This is what proves the base survived extraction; no file-level test can. A
`/mill-go2` run on the same shape is a strong follow-up but is not a gate for marking this task done.

## Q&A log

- **Q:** Full verbatim clone of mill-go/SKILL.md into mill-go2, or a delta file? **A:** Neither as posed — a three-file split, base + two thin variants, once it was confirmed the override surface is a single funnel point.
- **Q:** How does mill-go2 avoid silently drifting out of sync with mill-go? **A:** By sharing one base file, so there is no second copy to drift. No provenance-SHA or normalized-diff test needed.
- **Q:** Does the v1 variant keep the name `/mill-go` or become `/mill-go1`? **A:** Keeps `/mill-go`; no mill-go1.
- **Q:** Do the script-authored commit prefixes (`mill-go: start batch`) get a variant label too? **A:** No — `_implementer_common.py` parses that literal at three sites; not worth the risk for cosmetic consistency.
- **Q:** How deep does variant logging go — commit prefixes and notify events only, or also a `variant:` field in status.md? **A:** Commit prefixes and notify events only.
- **Q:** How is the refactor verified? **A:** Unit tests plus one live `/mill-go` run on a real task; a live mill-go2 run is not a gate.
- **Q:** Is mill-go2 mentioned anywhere automatic? **A:** No — purely opt-in, mill-plan's handoff is untouched.
- **Q:** Where does mill-go2's config live? **A:** Operator delegated the call; decided to reuse existing `roles.*` / `pipeline.*` unchanged, since the keys are read by the Python CLIs and behaviour is identical.
- **Q:** Should anything currently inline in mill-go's prose be extracted into a `_*.py` helper first? **A:** No.
- **Q:** Had the Webster module in Loomyard been read in detail? **A:** Not until asked; reading it produced the second override point, since a fork inheriting the base's driver instructions can misidentify itself as the driver — Webster treats that as run-fatal and guards it in the driver's own prompt, which override point A alone cannot express.
- **Q:** Declare the driver-preamble override point now, or let the fork task add it? **A:** Now — deferring it would force the fork task to reopen the base, which is the coupling this task exists to remove.
- **Q:** Terminology for the two variant-fillable sections? **A:** "Override point". "Hook" is banned as a *new* name for the mechanism — it already means Claude Code's settings.json hook mechanism — but the ban does not extend to two incidental pre-existing occurrences of the English word that the base inherits byte-for-byte.
- **Q:** Should the parameterization inventory be hand-enumerated line numbers, or regenerated by grep at implementation time? **A:** Grep commands, with the verified counts kept only as an as-of-commit sanity check. Line numbers in a self-hosting repo go stale between discussion, plan, and implementation.
- **Q:** Where does the pre-Entry preamble (wiki-access banner, Builder role paragraph) go? **A:** To the base, not reproduced per variant — which also settles the test-guards allowlist as base-added / mill-go-removed / mill-go2-never-added.
- **Q:** How should the remaining review rounds be handled? **A:** Operator delegated all of them: apply the recommended resolution to every gap and every NIT without prompting, for all rounds.
