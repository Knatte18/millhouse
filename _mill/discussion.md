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
  subprocess/psmux branches (7, 6, and 2 references respectively). Stripping those is a
  follow-up task, not this one.
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

- Decision: delete the per-batch psmux cleanup block (SKILL.md ~404–432, which calls
  `_llm_claude.cleanup_session`) and all of its invocation points — after every implementer
  `success`, at every review-loop terminus (APPROVE, max-rounds blocked, cleanliness-blocked,
  stuck-blocked), and before every transient implementer re-dispatch. Also delete the
  equivalent holistic-review cleanup call (~1004–1005).
- Rationale: `_llm_claude.cleanup_session` returns early when the resolved dispatch mode is
  not `psmux`, so under `dispatch: agent` every one of these calls is a no-op. The Python
  function itself stays (see `keep-dispatch-config-and-resolver`); only the SKILL's
  instructions to call it go away.
- Rejected: keeping the block as a harmless no-op. It costs ~30 lines plus five call-site
  references for zero effect.

### remove-subprocess-poll-loop-maxwait

- Decision: delete the `**Subprocess/psmux poll-loop max-wait.**` section (SKILL.md
  395–432) in full.
- Rationale: it governs only `[mill-bg] EXIT` poll loops, which exist only in the
  subprocess/psmux branches being deleted. With no poll loops left there is nothing to
  bound.
- Rejected: nothing — this is unconditionally dead once the twelve branches are gone.

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

**Also removed:**

- `**Subprocess/psmux poll-loop max-wait.**` section, lines 395–432 (includes the psmux
  per-batch cleanup block).
- Line 275's subprocess `--stage full` fallback inside Agent-mode error recovery.
- Lines 1004–1005's `_llm_claude.cleanup_session` call in Holistic review (which moves to
  `holistic-review.md`, minus this call).
- Line 224–225's dispatch-mode preamble in `## Agent-mode dispatch`: "This reads
  `cfg["llm"]["claude"]["dispatch"]` and returns one of `"subprocess"`, `"psmux"`, or
  `"agent"`. If the mode is not `agent`, skip this entire section…". Step 1 of that section
  ("Resolve dispatch mode") becomes unnecessary and the section's three-step pattern becomes a
  two-step pattern; renumber accordingly, and check for stale "step 3"/"step 6"/"step 6.5"
  cross-references elsewhere in the file after renumbering.
- Line 255's parenthetical "`effort` remains present in the envelope for `subprocess`/`psmux`
  dispatch parity…" — reword to keep the audit-visibility rationale, drop the parity clause.
- Line 627's `status: stuck, stuck_type: incomplete` (subprocess/psmux mode)` case in step 2,
  and line 900's `millpy-implement.py <batch_name> --resume-incomplete` in-subprocess-mode
  half of the warm-resume sentence.
- Line 518's "see the Agent-mode and subprocess/psmux dispatch branches there".
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
- Agent-mode step renumbering leaves no stale numeric cross-reference, in `SKILL.md`,
  in the companion files, or in `mill-go2/SKILL.md`.

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
