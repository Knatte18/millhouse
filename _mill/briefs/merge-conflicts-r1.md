# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success.
Do NOT commit.
Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Task intent

These excerpts describe what THIS branch is trying to accomplish.
When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent.
In particular: if a file appears under a batch's `Deletes:` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides).
Stage the deletion with `git -C /home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only rm <file>`.

### From discussion.md

# Discussion: mill-go-base: remove subprocess/psmux dispatch branches

```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
slug: mill-go-base-agent-dispatch-only
status: discussing
parent: main
```

## Problem

`plugins/mill/skills/mill-go-base/SKILL.md` is 1483 lines (146 KB). It is the single
largest skill in the repo and it is loaded in full, unconditionally, by both `/mill-go`
and `/mill-go2` at the start of every orchestration run.

Two things make it longer than it needs to be.

First, it documents two parallel dispatch mechanisms at every dispatch point: Agent-mode
(the live path) and subprocess/psmux (dead). The hub `mill-config.yaml` has pinned
`dispatch: agent` for some time, so every `If dispatch == subprocess or psmux:` branch —
twelve of them, each carrying a full `millpy-bg` invocation, a poll loop, and a liveness
check — is unreachable prose that the orchestrator reads and must mentally discard on
every run.

Second, roughly a third of the file describes phases that are never entered on the hot
path. `## Resume` (71 lines) fires only when status.md shows an in-flight batch.
`## Holistic code review` (299 lines) fires only after every batch is complete.
`## Handoff` (154 lines) fires only at the very end. All 524 lines are read on every
session regardless.

**Why now:** the dead path has no remaining consumer, and the file's size is a live cost
paid on every mill-go and mill-go2 invocation.

## Scope

**In:**

- `plugins/mill/skills/mill-go-base/SKILL.md` — delete the entire subprocess/psmux
  dispatch surface; extract three cold-path sections to companion files; de-duplicate the
  repeated tree-guard checkpoint paragraphs; add a short `## History` note recording the
  pre-strip commit.
- Three new companion files in the same directory: `resume.md`, `holistic-review.md`,
  `handoff.md`.
- `plugins/mill/skills/mill-go2/SKILL.md` — one-line correction of the now-false
  "Known limits" claim about subprocess/psmux (line 70), plus its base-coverage
  enumeration if the extraction falsifies it.
- `plugins/mill/skills/mill-go/SKILL.md` — its base-coverage enumeration, same reason.

**Out:**

- All Python. `_agent_dispatch.resolve_dispatch_mode`, `_llm_claude.py`'s psmux routing,
  `_psmux.py`, `_psmux_capture.py`, `millpy-claude-sub.py`, `millpy-bg.py` and every unit
  test covering them are untouched.
- `mill-config.yaml` (hub and template). The `dispatch:` key and the `psmux:` block stay.
- `mill-plan`, `mill-start`, `mill-merge-in` SKILLs. They still carry their own
  subprocess/psmux dispatch prose — `grep -cE 'psmux|subprocess'` gives 10, 9, and 2 lines
  respectively as of commit `356da5e5`. (These counts are cited only to convey that the
  sibling surface is non-trivial; nothing in this task's plan depends on them, and none of the
  three uses the `If \`dispatch == subprocess\`` branch form that `mill-go-base` does, so their
  strip is shaped differently and is deliberately deferred.) Stripping those is a follow-up
  task, not this one.
- Any rewriting or compression of surviving Agent-mode operational prose. Content is
  deleted (dead path) or relocated (cold path) — never reworded to save lines.
- The `## Agent-mode dispatch` section stays inline in SKILL.md. It is the hot path,
  referenced twelve times per run.

## Decisions

### scope-limited-to-mill-go-base

- Decision: touch `mill-go-base/SKILL.md` only (plus the two one-line corrections in
  `mill-go`/`mill-go2` that this task's own changes falsify). No Python, no config, no
  sibling-SKILL strip.
- Rationale: smallest blast radius on a file that every orchestration run depends on. The
  sibling SKILLs and the Python psmux layer are independently removable later and nothing
  in this task depends on their removal.
- Rejected: stripping all five SKILLs; stripping the Python layer as well. Both expand the
  change well beyond the brief and couple a documentation cleanup to a code change.

### keep-dispatch-config-and-resolver

- Decision: leave `cfg["llm"]["claude"]["dispatch"]`, the `psmux:` config block, and
  `_agent_dispatch.resolve_dispatch_mode` exactly as they are. `mill-go-base` simply stops
  branching on the resolved value.
- Rationale: `resolve_dispatch_mode` has three live Python consumers (`_llm_claude.py:111`,
  `_llm_claude.py:540`, `millpy-implement.py:519`) and four other SKILLs still branch on it.
  Removing the key or the function would break them, which is out of scope. The function
  already defaults to `"agent"` when the key is absent, so nothing here is load-bearing for
  correctness — it is simply not this task's to remove.
- Rejected: narrowing `VALID_DISPATCH_MODES` to `{"agent"}`; deleting the key from config;
  deleting the resolver. All are Python/config changes outside the agreed scope.

### remove-subprocess-fallback-in-agent-error-recovery

- Decision: delete the Agent-mode error-recovery fallback at SKILL.md line 275 — the rule
  that a read-only reviewer dispatch, after two consecutive Agent errors, falls back to the
  subprocess `--stage full` path via `millpy-bg`. Replace it with escalation to the existing
  stuck/operator path on the second consecutive error.
- Rationale: this is the last thing that keeps the subprocess path reachable from
  `mill-go-base`. Leaving it means the path is not actually removed, only mostly removed,
  and the file must keep documenting enough of `millpy-bg` for the fallback to be
  executable.
- Rejected: keeping the fallback. It would preserve one live subprocess reference and the
  supporting prose, defeating the point of the task.

### remove-psmux-cleanup-block

- Decision: delete **both** psmux cleanup blocks and **all** of their invocation sites.
  - **Per-batch cleanup block** — definition at SKILL.md 403–421 (the `**Per-batch session
    cleanup.**` prose at 403–406, the `The per-batch cleanup block:` lead-in at 408, and the
    fenced Python block at 410–421 ending in `_llm_claude.cleanup_session(sid)` at line 419),
    and its invocation sites at lines 404, 624, 628, 659, 662, 685, 807, 876, 883, 885, 886,
    897, 902, 908.
  - **Holistic cleanup block** — definition at SKILL.md 994–1007 (the `**Holistic session
    cleanup.**` prose at 994–996, the `The holistic cleanup block:` lead-in at 998, and the
    fenced Python block at 1000–1007 ending in
    `_llm_claude.cleanup_session('${holistic_sid}')` at line 1005), and its twelve invocation
    sites at lines 996, 1027, 1198, 1218, 1220, 1255, 1261, 1271, 1272, 1275, 1280, 1287. The
    holistic block and every one of its call sites move into `holistic-review.md` as part of
    the extraction, so they must be stripped *there*, not left behind in `SKILL.md`.
  - The holistic block receives exactly the same treatment as the per-batch block: block and
    call sites both deleted. Neither is left as an empty stub or a no-op call.
- Rationale: `_llm_claude.cleanup_session` returns early when the resolved dispatch mode is
  not `psmux`, so under `dispatch: agent` every one of these ~26 calls is a no-op. The Python
  function itself stays (see `keep-dispatch-config-and-resolver`); only the SKILL's
  instructions to call it go away. Symmetry between the two blocks matters: leaving the
  holistic one while deleting the per-batch one would be an arbitrary inconsistency and would
  keep `_llm_claude` imported in a file that otherwise no longer needs it.
- Rejected: keeping either block as a harmless no-op (~40 lines plus ~26 call-site references
  for zero effect); deleting the per-batch block but leaving the holistic one as a no-op stub
  (inconsistent, and the stub would be the only surviving psmux reference in
  `holistic-review.md`).

### remove-subprocess-poll-loop-maxwait

- Decision: delete the `**Subprocess/psmux poll-loop max-wait.**` section, SKILL.md
  **395–422**, in full. The section starts at line 395 and ends at 422; `**Why not fork?**`
  begins at 423 and is unrelated and retained. Note that this range *contains* the per-batch
  cleanup block (403–421) covered by `remove-psmux-cleanup-block` above — the two decisions
  overlap by design, they are not two separate ranges to delete twice.
- Rationale: it governs only `[mill-bg] EXIT` poll loops, which exist only in the
  subprocess/psmux branches being deleted. With no poll loops left there is nothing to
  bound.
- Rejected: nothing — this is unconditionally dead once the twelve branches are gone.

### renumber-agent-mode-steps-with-namespace-scoped-sweep

- Decision: deleting step 1 ("Resolve dispatch mode") from `## Agent-mode dispatch` renumbers
  the remaining steps 2–7 down to 1–6 (and sub-labels with them: 4(a)/(b)/(c) -> 3(a)/(b)/(c),
  6.5 -> 5.5). Every reference to an Agent-mode step is updated across all five affected files:
  `SKILL.md`, the three new companion files (`resume.md`, `holistic-review.md`, `handoff.md`),
  and `mill-go2/SKILL.md`.
- **Critical hazard — the sweep must be namespace-scoped, never a blind find/replace.**
  `SKILL.md` contains at least four independent numbered-step namespaces, and only the first
  is being renumbered:
  1. **Agent-mode dispatch steps 1–7** (plus 4(a)/(b)/(c), 6.5, 6.5.1/6.5.2) — *renumbered*.
  2. **The batch loop's own sections** `### 0.`, `### 0.5`, `### 0.55`, `### 0.6`, `### 1.
     Implement`, `### 2. Parse implementer report`, `### 2b. Cleanliness gate`, `### 3. Code
     Review loop` — *untouched*.
  3. **The Code Review loop's internal steps** 1, 1.5, 2, 3, 3.5, 4, 4.5, 5 — *untouched*.
  4. **The Holistic loop's internal sub-steps** 3, 3.5, 3.6 — *untouched*.
  Confirmed cross-namespace references that must NOT be shifted include: line 332's "see step 3
  of \"Code Review loop\"" (namespace 3), line 404's "immediately after step 2 parse, before
  step 2b cleanliness gate" (namespace 2), line 641's "Inline Python (in step 2b …)"
  (namespace 2), line 662's "the cold-start fixer used in step 4 REQUEST_CHANGES" (namespace 3),
  line 872's "mirrors mill-plan's existing step 4.5" (a *different SKILL's* namespace),
  line 947's "continue at Execute step 2b" (namespace 2), and lines 1159/1197/1199/1205's
  "sub-step 3.5"/"sub-step 3.6" (namespace 4).
- **Reference inventory to work from** (counts in current `SKILL.md`, all namespaces combined,
  so each occurrence must be classified before being changed): `step 4` ×23, `step 3` ×17,
  `step 2` ×16, `step 6` ×13, `step 5` ×10, `step 1` ×6, `step 4(b)` ×5, `step 6.5` ×4,
  `step 2b` ×3, `step 7` ×2, `step 3.6` ×2, `step 3.5` ×2, `step 4.5` ×1, `step 4(c)` ×1.
  In `mill-go2/SKILL.md`: `step 4` ×2, `step 3` ×1, `step 4(a)` ×1, `step 6.5` ×1 — all four
  are Agent-mode-namespace references and all four shift.
- Rationale: the operator chose clean numbering over reference-stability. Within a single skill
  this is a bounded mechanical edit, and the numbered list reading "2, 3, 4, 5, 6, 7" with no
  step 1 would be a permanent readability wart in a file an orchestrator executes from.
- Rejected: leaving the numbering at 2–7 with an explanatory note (zero edit risk, but ships a
  list that starts at 2 forever); converting to named steps (`prepare`/`dispatch`/`recover`/
  `capture`/`finalize`) — most robust against future shifts, but restructures the section well
  beyond a deletion task.

### extract-cold-path-sections-to-companion-files

- Decision: move three sections out of `SKILL.md` into companion files in the same
  directory:
  - `## Resume` (71 lines) -> `plugins/mill/skills/mill-go-base/resume.md`
  - `## Holistic code review` (299 lines) -> `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `## Handoff` (154 lines) -> `plugins/mill/skills/mill-go-base/handoff.md`
- Rationale: these three are the only sections that are never needed on the hot path —
  Resume applies only when status.md shows an in-flight batch, Holistic only after all
  batches are complete, Handoff only at the very end. Together they are 524 lines read on
  every session for nothing. Every other large section (`## Agent-mode dispatch` 217,
  `### 3. Code Review loop` 212, `## Entry` 106) is either hot-path or entered on a
  condition the orchestrator cannot evaluate before reading it.
- Rejected: extracting `## Agent-mode dispatch` (hot path, referenced twelve times per run —
  externalising it would cost more reads than it saves); extracting `### Entry-gate wait for
  upstream mill-plan` and `### Mid-execution phase-gate widening` (would reach ~550 lines but
  adds two more conditional read-points inside `## Entry`, where a missed read is hardest to
  notice); extracting only `## Holistic code review` (too little gain).

### companion-files-live-in-the-skill-directory

- Decision: companion files live at `plugins/mill/skills/mill-go-base/<name>.md`, referenced
  from `SKILL.md` by repo-relative path.
- Rationale: co-located with the skill they belong to, so they travel with it and are
  obviously part of it rather than reference material.
- Rejected: `plugins/mill/docs/mill-go-base-*.md` alongside `harness-tool-contracts.md`.
  That directory holds reference material about external contracts; these files are
  operational instructions and belong with the skill.

### pointer-only-reference-sites-force-the-read

- Decision: at each of the three extraction points, `SKILL.md` retains the `##` heading and
  exactly one mandatory-read directive, modelled on the existing proven
  "Load `mill-receiving-review` unconditionally" pattern. For example:

  ```markdown
  ## Holistic code review

  **Read `plugins/mill/skills/mill-go-base/holistic-review.md` now, before any other action
  in this phase.** All of this phase's behaviour lives in that file. Do not proceed from
  this heading without reading it.
  ```

  The reference site carries **no summary** of what the companion file contains, and no
  partial restatement of its steps.
- Rationale: the enforcement mechanism is the absence of information, not the strength of
  the wording. If the reference site described what the phase does, the orchestrator could
  plausibly act on that description and skip the read. Because the pointer contains nothing
  actionable, there is no path forward except reading the file.
- Rejected: adding a one-line content summary at each site (invites acting on the summary);
  promoting each companion file to its own `mill:` skill loaded via the Skill tool (strongest
  loading guarantee, but these are fragments of one skill, not three skills, and it would add
  three misleading entries to `SKILLS.md`).

### deduplicate-tree-guard-checkpoint-paragraphs

- Decision: define the tree-guard checkpoint once in `SKILL.md` as a named block (pre-dispatch
  and post-dispatch forms), and replace each of the ten current occurrences with a one-line
  reference to it.
- Rationale: the ten paragraphs are near-verbatim copies of the same two instructions. Part of
  each copy — the "this does not apply to the subprocess/psmux branch" sentence — dies with the
  strip anyway, and what remains is mechanically identical. Note that four of the ten
  occurrences live inside sections being extracted (two in Holistic review, and the
  Handoff/Resume vicinity), so the named block must be reachable from the companion files:
  the companion files reference it by the same name and path.
- Rejected: leaving the ten copies inline (~40 lines of pure duplication); moving the block to
  a companion file (it is needed on the hot path).

### git-history-is-the-backup

- Decision: the pre-strip version is preserved by git history at commit
  `356da5e549c89a2f7374fb716cb8fc0f6be11176` (the current HEAD of
  `hanf/mill-go-base-agent-dispatch-only`). No backup copy is committed into the repo. A short
  `## History` section is appended at the bottom of the stripped `SKILL.md` recording the SHA
  and the exact restore command.
- Rationale: the operator asked for a safety net in case the stripped skill does not work
  immediately, and for a plain-text note in the repo saying where the old version is. Git
  history satisfies the first; the `## History` note satisfies the second and is discoverable
  by anyone reading the skill. Committing a `SKILL.md.bak` would put a second SKILL-shaped file
  in a skills directory, where it risks being indexed or loaded.
- Rejected: `.scratch/mill-go-base-SKILL-prestrip.md` (gitignored, so it does not survive a
  fresh clone and cannot carry the note); a committed `SKILL.md.bak` (indexing risk).
- The note's exact wording:

  ```markdown
  ## History

  Pre-strip version (1483 lines, with subprocess/psmux dispatch branches and the Resume /
  Holistic / Handoff sections inline) is at commit `356da5e5`. Restore with:
  `git show 356da5e5:plugins/mill/skills/mill-go-base/SKILL.md`.
  ```

### fix-only-falsified-sibling-references

- Decision: correct only the sibling-SKILL statements that this task's own changes make false —
  `mill-go2/SKILL.md` line 70's "Engages under `dispatch: agent` only (cold under
  `subprocess`/`psmux`)", and the base-coverage enumerations in both `mill-go/SKILL.md` and
  `mill-go2/SKILL.md` that list "Resume, holistic code review, and Handoff" as living in
  `mill-go-base` (they now live in its companion files).
- Rationale: leaving a documented distinction that no longer exists is a correctness defect
  introduced by this task, so fixing it is in scope; stripping the siblings' own
  subprocess/psmux branches is not.
- Rejected: leaving all siblings untouched (ships a known-false statement); stripping all four
  siblings (that is the rejected wider scope).

### line-count-is-an-outcome-not-a-gate

- Decision: the expected result is roughly 630 lines in `SKILL.md` (1483 minus ~370 lines of
  subprocess/psmux, minus ~455 lines of extracted cold-path content, minus ~30 lines of
  tree-guard de-duplication). This is an expectation to sanity-check against, not a threshold
  that gates the task.
- Rationale: the brief's original 500–600 target was set before anyone measured the branches.
  Measurement shows deletion alone yields ~1113; the extraction is what closes most of the
  remaining gap. Making a number the gate would create pressure to compress live prose, which
  is explicitly out of scope.
- Rejected: treating 500–600 as a hard requirement (would force compression of load-bearing
  Agent-mode prose in a file mill-go depends on at runtime).

## Technical context

**Target file:** `plugins/mill/skills/mill-go-base/SKILL.md`, 1483 lines. Loaded via the Skill
tool by `mill-go/SKILL.md` (28 lines) and `mill-go2/SKILL.md` (82 lines), which bind a
`VARIANT_LABEL` and then defer wholesale to the base skill from its `## Entry` onward.

**The twelve subprocess/psmux branches** begin at these lines and each run to the start of the
next step or subsection:

| Line | Dispatch point |
|---|---|
| 582 | Step 1 Implement — `millpy-implement.py` |
| 736 | Step 3 Code Review loop — `millpy-review-code.py` |
| 795 | Step 3 NIT-fix — `millpy-fix.py --nits-only` |
| 817 | Step 3 REQUEST_CHANGES fix — `millpy-fix.py` |
| 851 | Step 3 ERROR-retry — `millpy-review-code.py` |
| 937 | Resume — implementer re-dispatch |
| 955 | Resume — reviewer re-dispatch |
| 973 | Resume — fixer re-dispatch |
| 1127 | Holistic review — `millpy-review-code.py` |
| 1178 | Holistic review ERROR-retry |
| 1243 | Holistic NIT-fix — `millpy-fix.py --nits-only` |
| 1265 | Holistic REQUEST_CHANGES fix — `millpy-fix.py` |

Each branch carries a `millpy-bg.py` invocation, a `> **Before invoking millpy-bg**` cwd
warning, a `cat <log-path>` poll loop, a `_bg.check_bg_status` liveness check, and JSON
extraction via `grep '^{' <log> | tail -1`. All of it goes. Line numbers will shift as
deletions are applied top-down; anchor on the `If \`dispatch == subprocess\` or \`psmux\``
literal text rather than on line numbers.

**Also removed** (none of these are inside the twelve branches above, so each must be deleted
explicitly — this list and the table together are the complete deletion set):

- **Lines 555–559, the `### 1. Implement` preamble.** The `Background via millpy-bg:` heading
  (557) and the `> **Before invoking millpy-bg**` cwd warning (559) sit *above* the
  `If dispatch == agent` / `If dispatch == subprocess` split at 574/582, unlike every other
  occurrence of that same warning (738, 819, 939, 957, 975, …), each of which sits *inside* its
  subprocess branch and dies with it. Left alone, these two lines survive the strip and fail the
  regression guard's "the literal string `millpy-bg` does not appear" assertion. Delete them;
  the surviving Agent-mode branch at 574 needs neither, since Agent-mode dispatch does not
  invoke `millpy-bg` and has no cwd sensitivity of this kind.
- `**Subprocess/psmux poll-loop max-wait.**` section, lines **395–422** (this range contains
  the per-batch cleanup block at 402–421 — see `remove-psmux-cleanup-block`, which covers the
  same lines; do not treat them as two separate deletions).
- Line 275's subprocess `--stage full` fallback inside Agent-mode error recovery ("read-only
  reviewer dispatches (which write no review file) fall back to the subprocess `--stage full`
  path via `millpy-bg` before escalating") — replaced by escalation per the
  `### Stuck escalation` section, identical to the implementer/fixer treatment in the same
  sentence.
- The holistic cleanup block (996–1005) and its twelve invocation sites — see
  `remove-psmux-cleanup-block`. These live in the extracted `holistic-review.md`, so they are
  stripped there.
- Line 224–225's dispatch-mode preamble in `## Agent-mode dispatch`: "This reads
  `cfg["llm"]["claude"]["dispatch"]` and returns one of `"subprocess"`, `"psmux"`, or
  `"agent"`. If the mode is not `agent`, skip this entire section…", i.e. all of step 1
  ("Resolve dispatch mode"). The seven-step pattern becomes six steps; renumber per
  `renumber-agent-mode-steps-with-namespace-scoped-sweep`, which carries the full reference
  inventory and the namespace-collision hazard.
- Line 518's "see the Agent-mode and subprocess/psmux dispatch branches there" in
  `### 0.6. Per-batch baseline recapture` — reword to name only the Agent-mode branch.
- Line 255's parenthetical "`effort` remains present in the envelope for `subprocess`/`psmux`
  dispatch parity…" — reword to keep the audit-visibility rationale, drop the parity clause.
- Line 627's "`status: stuck, stuck_type: incomplete` (subprocess/psmux mode)" case in the
  batch loop's `### 2. Parse implementer report`, and line 900's
  "`millpy-implement.py <batch_name> --resume-incomplete` in subprocess/psmux mode" half of the
  warm-resume sentence in `### Stuck escalation`.
- Line 379's "branch identically to the existing `subprocess`/`psmux` flow" — reword; the
  verdict-branching description must survive on its own terms.

**Left in place deliberately:** `millpy-bg.py` and `_bg.py` are not deleted and remain
available; this task only removes `mill-go-base`'s instructions to use them. Other SKILLs
(`mill-plan`, `mill-start`, `mill-merge-in`) still invoke `millpy-bg`.

**Python consumers of `resolve_dispatch_mode`** (all untouched, listed so mill-plan does not
mistake them for orphans): `plugins/mill/scripts/_llm_claude.py:111` (`_get_via_psmux_flag`),
`plugins/mill/scripts/_llm_claude.py:540` (`cleanup_session`'s early return),
`plugins/mill/scripts/millpy-implement.py:519`.

**mill-go2 interaction:** mill-go2's fork dispatch is a variant overlay on the Agent-mode
pattern — it replaces the `Agent()` call at specified steps with
`Agent(subagent_type: "fork")`. It is not governed by the `dispatch:` key and is unaffected by
this strip, except that its "Known limits" sentence at line 70 references the modes being
removed. Its step references into the base skill ("base step 4", "step 6.5.2", "step 3")
must still resolve after the Agent-mode section is renumbered — verify these explicitly.

**Companion-file cross-references:** the extracted sections contain internal references back
into `SKILL.md` (e.g. Holistic review references "the Agent-mode dispatch pattern above",
Resume references the batch-loop steps, Handoff references the done-gate marker written by the
NIT-fix pass). "Above" no longer holds once the content is in a separate file — every such
reference must be rewritten to name `plugins/mill/skills/mill-go-base/SKILL.md` and the target
section explicitly. Symmetrically, `SKILL.md` contains forward references into the extracted
sections that must name the companion file.

**Existing precedent for path-referenced companion docs:** `plugins/mill/docs/harness-tool-contracts.md`,
referenced from `mill-go-base/SKILL.md:184` and `:219`, `mill-plan/SKILL.md:95`, and
`cli/SKILL.md:37`. Those references are informational ("see X for the contract"); the three new
ones are mandatory-read, which is why they need the stronger wording from
`pointer-only-reference-sites-force-the-read`.

**Skills index:** `SKILLS.md` at the repo root is generated from SKILL.md frontmatter by
`/mill-skills-index`. The companion files have no frontmatter and must not be picked up as
skills — confirm the generator globs `*/SKILL.md` specifically and not `*.md`, and regenerate
the index after the change.

## Testing

There is no automated test for SKILL.md content, and this task adds no production code, so
"testing" here means regression guards plus a live verification run.

**Regression guard (TDD candidate, and the only new test):**
a unit test under `plugins/mill/unit_tests/` — suggested name
`test-mill-go-base-agent-only.py`, run via `run-all.py` — asserting against
`plugins/mill/skills/mill-go-base/SKILL.md`:

- The literal strings `psmux`, `millpy-bg`, and `dispatch == subprocess` do not appear.
- The three companion files exist and each is referenced from `SKILL.md` by its repo-relative
  path.
- Each of the three reference sites contains a mandatory-read directive (assert on the
  presence of the read instruction, not on exact prose).

Write this test first, watch it fail against the current file, then strip. It is the guard
against the dead path being reintroduced later by a copy-paste from another SKILL.

**Scenarios to cover beyond the guard:**

- The generated `SKILLS.md` is unchanged by the addition of the three companion files (they
  must not be indexed as skills).
- No dangling references: no surviving "see … above" pointing into an extracted section, and
  no reference in a companion file to a `SKILL.md` section by relative position alone.
- **Agent-mode step renumbering — the highest-risk scenario in this task.** Two distinct
  failure modes must both be covered:
  - *Under-shift:* an Agent-mode-namespace reference that still names its old number (e.g. a
    surviving "step 6.5" that should now read "step 5.5"). Catch by enumerating every
    `step N` occurrence in the five affected files after the edit and classifying each against
    the four namespaces listed in
    `renumber-agent-mode-steps-with-namespace-scoped-sweep`.
  - *Over-shift:* a reference belonging to one of the three untouched namespaces that got
    shifted anyway. The named collision sites (lines 332, 404, 641, 662, 872, 947, 1159, 1197,
    1199, 1205 in the pre-edit file) are the specific ones to re-read by hand after the sweep —
    each must still name the same number it names today.
  - Neither failure mode is mechanically detectable by string matching alone, because the
    namespaces share identical surface text. This check is a deliberate manual read-through,
    not an assertion.

**Verification sequence:**

1. Full unit-test suite via `plugins/mill/unit_tests/run-all.py`.
2. `/mill-skills-index` regeneration; confirm `SKILLS.md` diff is empty.
3. A real `/mill-go2` run on the next available task as the live end-to-end test. SKILL.md has
   no automated behavioural test, so a real orchestration run is the only honest verification
   that the stripped skill and its three companion files still drive a complete task. The git
   backup at `356da5e5` covers failure.

Steps 1 and 2 gate the merge; step 3 happens on the next task and is the reason the `## History`
restore note exists.

## Q&A log

- **Q:** How far does the removal reach — mill-go-base only, all five SKILLs, or the Python layer too? **A:** mill-go-base only, but take a backup — the stripped version may not work immediately.
- **Q:** Does the `dispatch:` config key and `resolve_dispatch_mode` survive? **A:** Initially leaned toward removing it, then confirmed: keep it. (mill-go2's forking is a separate mechanism and does not depend on it.)
- **Q:** What happens to the Agent-mode subprocess fallback at line 275? **A:** Remove it; escalate to stuck/operator on the second consecutive Agent error instead.
- **Q:** The psmux per-batch cleanup block? **A:** Delete the block and all its invocation points.
- **Q:** Is the ~500–600 line target binding? **A:** No — but 1100 is far more than expected. The point of the task is to shorten the skill; it is too long and contains too much that is not needed.
- **Q:** Rather than compressing prose, can duplicated/reusable content be extracted into separate files that are loaded on demand? **A:** Yes — extract duplicated content into external files that do not need to be read every time.
- **Q:** Backup mechanism? **A:** Git history, plus a plain-text note somewhere in the repo saying "the old version is here: …".
- **Q:** Where do the companion files live? **A:** In the skill directory, `plugins/mill/skills/mill-go-base/*.md`.
- **Q:** Which sections get extracted? **A:** Whichever ones make sense — resolved to Resume, Holistic code review, and Handoff (the three cold-path sections).
- **Q:** How do we guarantee the orchestrator reads a companion file at the right moment? **A:** The operator's own reasoning settled it: if the essential information lives only in the .md file, the LLM cannot know what to do without reading it. Hence pointer-only reference sites with no summary.
- **Q:** Stale references in sibling SKILLs? **A:** Fix only mill-go2's falsified line; leave mill-plan/mill-start/mill-merge-in for a follow-up.
- **Q:** How do we verify the stripped SKILL still works? **A:** Unit tests + `/mill-skills-index`, then a real `/mill-go2` run as the live test.
- **Q:** Removing Agent-mode step 1 shifts the step numbering — don't renumber (zero edit risk), renumber with an exhaustive sweep, or convert to named steps? **A:** Renumber with the exhaustive sweep — within a single skill this is not a large job. (Recorded hazard: the sweep must be namespace-scoped, since SKILL.md has four independent numbered-step namespaces that share identical surface text.)


### From _mill/plan/00-overview.md


```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
slug: 'mill-go-base-agent-dispatch-only'
approved: true
started: '20260812-083517'
parent: 'main'
root: ""
verify: null
```

### From _mill/plan/01-regression-guard.md


```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'regression-guard'
number: 1
cards: 1
verify: null
depends-on: []
```



- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-mill-go-base-agent-only.py`
- **Deletes:** none

### From _mill/plan/02-strip-subprocess-dispatch.md


```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'strip-subprocess-dispatch'
number: 2
cards: 10
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [1]
```



- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/03-treeguard-dedup.md


```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'treeguard-dedup'
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [2]
```



- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/04-extract-cold-path.md


```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'extract-cold-path'
number: 4
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [3]
```



- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:**
  - `plugins/mill/skills/mill-go-base/resume.md`
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:**
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:**
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/05-renumber-and-siblings.md


```yaml
task: 'mill-go-base: remove subprocess/psmux dispatch branches'
batch: 'renumber-and-siblings'
number: 5
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-mill-go-base-agent-only.py test-guards.py test-mill-go-variants.py test-skill-helper-drift.py
depends-on: [4]
```



- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/resume.md`
  - `plugins/mill/skills/mill-go-base/holistic-review.md`
  - `plugins/mill/skills/mill-go-base/handoff.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-go2/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none

## Conflicting files

- `plugins/mill/skills/mill-go-base/SKILL.md`

## Instructions

For each file listed above:

1. Read the file and locate every conflict block (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides of the conflict — what each branch intended.
3. Write a resolution that preserves the intent of both sides.
   When both sides modify **different, non-overlapping parts** of the same conflict region — for example, different columns of one table row, different keys of one object, or disjoint lines of a prose block — **combine both edits** into a single resolved structure.
   Do NOT pick one side wholesale just because the region overlaps syntactically;
   picking one side wholesale is correct only when the two changes are genuinely mutually exclusive (e.g. the same key is renamed to two different values).
   Worked example: if `ours` changes column A and `theirs` changes column B of the same table row, the resolution keeps both column changes in a single row — it does not discard either.
4. Before keeping content from either side inside a conflict hunk, search the rest of the file (outside the hunk) for that same content.
   This judgment call is scoped narrowly — it applies only when a hunk's content might be a moved duplicate of content living elsewhere in the file;
   it does NOT apply to every ordinary step-3 disjoint-region combine (e.g. the column-A/column-B worked example above), which remains today's silent, high-confidence success path.
   Two branches:
   - **Confident case:** if the content clearly already exists elsewhere and the surrounding context makes it unambiguous that this is the same item having been moved (not two independent, separately-intended copies) — do not re-add it in the hunk;
     keep only the other side's unrelated edit.
     Worked example: one side moves a roadmap item from `## Planned` to `## Done`, while the other side makes an unrelated edit elsewhere in the file.
     The resolution keeps the item only under `## Done`;
     it is not re-added under `## Planned`.
   - **Ambiguous case:** if you cannot confidently tell whether this is the same moved content or a legitimate independent duplication — fall back to step 3's default (keep both) rather than guessing, and report the ambiguity via the `discarded` field (see Report section) with the description `"kept both sides of a conflict, ambiguous move-vs-duplicate"`.
     Worked example: a similarly-worded item appears in two different sections and you cannot tell whether it is the same item moved or a legitimate second, independently-added item.
     The resolution keeps both occurrences and reports the ambiguity via `discarded`.
5. Run `git -C /home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only add <file>` to stage the resolved file.
6. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's `Deletes:`, run `git -C /home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only rm <file>` instead of editing;
   that stages the intentional deletion.
7. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification.
   Instead: a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent. b. Run `git show <deletion-commit>` to inspect context. c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"),
   or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C /home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only rm <file>`. d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt.
   Do NOT silently keep the modification.

Never use `git checkout --ours` or `git checkout --theirs` — they silently discard one side of the conflict.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

On success (nothing discarded):

{"status":"success"}

On success with discarded content — if you had to drop content from one side (e.g. two sides made mutually exclusive changes and only one could survive), list each dropped item:

{"status":"success","discarded":["<short description of what was dropped from which side>"]}

An empty or absent `discarded` field means nothing was lost.
If anything was discarded, you MUST list it;
an empty list when content was actually dropped is a protocol violation. `discarded` also carries the step 4 ambiguous-case entry `"kept both sides of a conflict, ambiguous move-vs-duplicate"` — even though nothing was technically dropped in that case, the field's purpose is to surface anything the operator should double-check before `git merge --continue`, which covers both a genuine drop and a kept-both ambiguity.
The `mill-merge-in` frontend reads this field and surfaces any losses (or ambiguities) to the operator before continuing, rather than silently running `git merge --continue`.

If you cannot resolve one or more conflicts:

{"status":"stuck","stuck_type":"logic","reason":"<one-line description of what you could not resolve>"}

Anything other than this JSON object on the last line is a protocol violation;
the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost.
Do not wrap the JSON in a code fence;
do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob.
Use `git -C /home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only` for any git commands;
do not `cd`.
Worktree cwd is `/home/hanf/Code/millhouse/wts/mill-go-base-agent-dispatch-only`.
