# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success.
Do NOT commit.
Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Task intent

These excerpts describe what THIS branch is trying to accomplish.
When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent.
In particular: if a file appears under a batch's `Deletes:` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides).
Stage the deletion with `git -C /home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability rm <file>`.

### From discussion.md

# Discussion: mill-implementer: commit_sha transcription/truncation and final-status-line reliability

```yaml
task: mill-implementer: commit_sha transcription/truncation and final-status-line reliability
slug: implementer-commit-sha-and-status-line-reliability
status: discussing
parent: main
```

## Problem

Five self-reported GitHub issues (#978, #932, #944, #953, #923) converge on the same
failure family: the implementer's self-reported `commit_sha` and its final JSON status
line are not fully trustworthy, and one adjacent script shares the same
misleading-field pattern. Exploration during this discussion round established that
two of the five are **already structurally fixed** by prior commits and need no code
change; the remaining three are genuinely open. This task closes the three open gaps
and documents (without re-doing) the two that are already resolved, so the underlying
GitHub issues can stay closed against this task with an accurate paper trail.

## Scope

**In:**
- `plugins/mill/templates/implementer-brief.md`: stop instructing/allowing prose
  restatement of `commit_sha` (#978), and reinforce the "nothing after the JSON
  line" rule with a concrete anti-pattern example (#944).
- `plugins/mill/scripts/_implementer_common.py` (`_forward_output` /
  `finalize_from_output`) and `plugins/mill/scripts/millpy-merge-in-subagent.py`
  (`--mode conflicts`, both the `--stage finalize` branch and `_run_conflicts`'s
  full-mode return): stop emitting a `commit_sha` field before a merge commit
  actually exists (#953).
- `plugins/mill/skills/git-commit/SKILL.md`: add a mandatory post-stage
  verification step that catches the add/edit staging race for moved or
  just-edited files (#923).
- Adding a new regression test to `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
  pinning the renamed field's behavior (no existing test in that file asserts
  `commit_sha` on output today — see Decisions > rename-conflicts-finalize-field
  for why no existing test needs editing).
- Documenting, in this file, why #932 and part of #978's risk are already closed
  by prior work — no code change for those.

**Out:**
- Any change to `verify-fix` mode's finalize path in `millpy-merge-in-subagent.py`
  — that mode's `commit_sha` is reported *after* a real commit exists (post-fixer or
  clean-verify), so its field name is already accurate. Confirmed by reading
  `_run_verify_fix` and the `--stage finalize` verify-fix branch.
- Any change to the batch/card success path in `_implementer_common.py`'s main
  `_forward_output` branch (the one used by `millpy-implement.py`) — that path's
  `commit_sha` already refers to a real, already-created commit and is not
  misleading. Only the two conflicts-mode call sites (finalize-stage and
  full-mode, both reaching the same generic fallback with no verify/card args)
  produce a misleading value. Do not generalize the field-rename to the
  batch/card success path.
- Rewriting or re-architecting `_forward_output`'s branching structure. This task
  adds one optional parameter, not a refactor.
- Any change to `mill-go`'s `inferred: true` recovery path — it already handles a
  missing/prose-only final line correctly; this task only reduces how often that
  recovery has to fire.
- Any change to `git-commit`'s lint/codeguide pre-commit steps, or to
  `git-workflow`'s general commit rules — only a new staging-verification step is
  added, inserted after existing `git add`.

## Decisions

### no-prose-commit-sha (#978)

- Decision: The implementer brief's Report section gets an explicit rule: the
  free-text turn summary must never restate the `commit_sha` value (in full or
  abbreviated form). It may say the work is committed, but the SHA itself is
  carried exactly once, in the final JSON line.
- Rationale: The JSON line's `commit_sha` is already discarded and overwritten by
  `_forward_output` with a freshly computed `git rev-parse HEAD` on every
  self-reported success (see `_implementer_common.py` ~line 1879-1885, added in
  commit `6d92c82d`) — so a prose restatement is never load-bearing. Nothing in
  the current `implementer-brief.md` `## Report` section actually instructs the
  implementer to restate `commit_sha` in prose today (confirmed by reading the
  section in full during this discussion round) — the restatement is
  spontaneous model behavior, not brief-directed. Adding an explicit prohibition
  closes off that spontaneous behavior at its only observed error site (per
  #978's own report, the JSON line was correct both times; the prose was not).
- Rejected: Instructing the implementer to copy-paste the SHA from `git
  rev-parse HEAD` output when restating it in prose (issue's alternative
  suggestion (b)). Rejected because it still permits a manual-retype failure
  mode for something the JSON line already reports authoritatively — no reason
  to keep it in prose at all.

### reinforce-json-line-discipline (#944)

- Decision: Add a short, explicit anti-pattern block to the brief's `## Report`
  section, immediately after the existing "Long-session reminder": name the
  observed failure shape directly (ending the turn on a `Note:`/`Summary:`-style
  wrap-up paragraph after finishing implementation) and state plainly that nothing
  — no notes, caveats, or explanations — may follow the JSON line; if such text
  has already been started, it must be deleted before the turn ends.
- Rationale: The existing "Long-session reminder" instruction (added May 2026,
  well before #944 was filed in August) already asks for JSON-first,
  re-emitted-at-end — and #944 still happened despite it, so the existing wording
  is an insufficient deterrent on its own. `mill-go`'s `inferred: true` recovery
  already prevents this from blocking a batch (confirmed still present in
  `_implementer_common.py`), so this decision is a belt-and-suspenders reduction
  in how often that recovery has to fire, not a claim that the current behavior is
  unsafe.
- Rejected: Leaving the brief unchanged and relying solely on `inferred: true`
  recovery. Rejected because the task explicitly calls this out as a target
  issue, and the recovery path, while safe, still costs the orchestrator an extra
  git-log reconciliation step every time it fires.

### rename-conflicts-finalize-field (#953)

- Decision: `millpy-merge-in-subagent.py`'s conflicts-mode success path emits
  `pre_merge_head` instead of `commit_sha` in its JSON envelope, at **both**
  call sites that reach the generic fallback: the `--stage finalize` branch
  (~line 397-424) and `_run_conflicts`'s own full-mode return (~line 490,
  `return _forward_output(output, project_root)`) — both funnel through the
  same unconditional `git rev-parse HEAD` fallback before any merge commit
  exists, so both are misleading in the same way and both are in scope; this
  is not a "re-check during planning" item. Implementation: add an optional
  keyword parameter (e.g.
  `commit_sha_field_name: str = "commit_sha"`) to `_forward_output` /
  `finalize_from_output`, used only where the generic fallback branch attaches the
  freshly-computed `git rev-parse HEAD` value to the success envelope (the
  block that currently does `parsed["commit_sha"] = result.stdout.strip()` at
  the unconditional end of `_forward_output` when no verify/card args are
  supplied). The conflicts-mode call site in `millpy-merge-in-subagent.py` passes
  `commit_sha_field_name="pre_merge_head"`; every other caller keeps the default
  and is unaffected. A grep of `plugins/mill/skills/` for `commit_sha` found no
  file that documents consuming this specific conflicts-finalize field by name
  (confirmed during this discussion round — see Technical context), so there is
  no doc line to update for this rename. A grep of
  `test-millpy-merge-in-subagent.py` for `commit_sha` likewise found no existing
  test that asserts the field on *output* (every occurrence is in an input
  fixture's self-reported JSON, which `_forward_output` already discards
  regardless of field name) — so no existing test needs editing either; only the
  new regression test named in Testing below is required.
- Rationale: Root-caused by reading `millpy-merge-in-subagent.py`'s
  `--stage finalize`/`--mode conflicts` branch (~line 397-424): on a
  self-reported success that passes the conflict-marker gate, it falls through
  to `finalize_from_output(..., start_sha=None, snapshot_path=None,
  session_id=None)`, which reaches `_forward_output`'s generic fallback (no
  verify_cmd/card_ids supplied) and does an unconditional `git rev-parse HEAD` —
  at that point in the documented mill-merge-in flow, `git merge --continue` has
  not yet run, so `HEAD` is still the pre-merge commit, not a merge commit. The
  field name `commit_sha` strongly implies a completed commit reference,
  which cost real investigation time in the reported incident. Renaming (rather
  than omitting) preserves the value's diagnostic use — it is a legitimate,
  correct answer to "what was HEAD before I ran merge --continue".
- Rejected: Omitting the field entirely for this path (issue's other suggested
  fix). Rejected because the value is genuinely useful for the orchestrator/human
  to see what pre-merge HEAD was, and the misleading part is the name, not the
  presence, of the field.
- Rejected: A broader refactor of `_forward_output`'s fallback branch to
  distinguish "real commit" vs "no commit yet" callers structurally (e.g. a
  separate function). Rejected as disproportionate to the fix — one parameter on
  the existing function is sufficient and keeps the diff reviewable.

### staging-verification-gate (#923)

- Decision: `git-commit/SKILL.md` gets a new mandatory step, inserted
  immediately after `git add <files>` and before `git commit`: run `git diff
  --quiet -- <the same files just staged>`. A non-zero exit means the working
  tree still has changes beyond what was staged for those paths (the race
  condition observed in #923 — a `git mv`/edit not yet reflected in the index at
  commit time). On a non-zero exit, re-run `git add` for those exact paths once
  and re-check; if the second check is still non-zero, halt and report the
  mismatch rather than committing — do not proceed to `git commit` with an
  unresolved diff.
- Rationale: #923's own investigation concluded the implementer's own
  `git diff --cached` self-check caught the mismatch by luck, and asked
  specifically whether "a `git diff --cached --quiet` (or equivalent) check
  should be a mandatory pre-commit gate in that flow rather than left to
  implementer self-discipline." `git diff --quiet -- <files>` (unstaged, not
  `--cached`) is the more precise check for this race: it asserts the staged
  snapshot already equals the current working-tree content for exactly the
  files being committed, which is what a `git mv`/edit-then-stage race breaks.
  `git diff --cached --quiet` only confirms *something* is staged, not that it
  matches the working tree, so it would not have caught the reported incident.
  This is a general `git-commit` skill change (not implementer-only) since the
  skill is shared by every commit path in the repo, including but not limited to
  the implementer's per-card commits.
- Rejected: `git diff --cached --quiet` as suggested literally in the issue.
  Rejected per the rationale above — it checks the wrong thing for this specific
  race.
- Rejected: Leaving this to implementer self-discipline (status quo). Rejected
  because the task explicitly lists #923 as in scope, and the whole point of the
  observed incident is that self-discipline caught it by luck, not by
  guarantee.

### no-change-truncation (#932) — documented, not re-fixed

- Decision: No code or brief change for the literal truncated-SHA report in
  #932.
- Rationale: `_implementer_common.py`'s `_forward_output` already validates and
  overwrites `commit_sha` unconditionally on every self-reported success with a
  freshly computed, regex-validated (`_is_valid_commit_sha`, 40 or 64 lowercase
  hex chars) `git rev-parse HEAD` result — added in commit `6d92c82d` (dated
  2026-07-29), which predates #932's report (2026-08-24). #932's own report
  confirms this: "`millpy-implement.py --stage finalize` recomputes/validates
  the real SHA independently from git state, so no downstream damage occurred in
  this run." The implementer's *self-reported* truncated value is provably never
  consumed downstream of finalize. The brief's existing instruction ("`commit_sha`
  MUST be the full SHA from `git rev-parse HEAD`") plus the no-prose-restatement
  change above (#978) further reduce any residual noise from a malformed
  self-reported value, without needing dedicated new work.
- Rejected: Adding redundant validation/tests for a path that is already
  provably covered. Rejected as make-work — see Testing below for the one
  targeted addition that IS worth it (a regression test pinning this behavior
  down explicitly, since none currently names #932 directly).

## Technical context

- `plugins/mill/scripts/_implementer_common.py` is the shared finalize engine.
  The relevant fallback block is the unconditional tail of `_forward_output`
  (search `parsed["commit_sha"] = result.stdout.strip()` near the function's
  end) — this is the block both the normal batch success path *and* the
  conflicts-mode merge-in path funnel through when no verify/card gates fire.
  The new `commit_sha_field_name` parameter's implementation should reuse the
  existing `_is_valid_commit_sha` / `_COMMIT_SHA_RE` regex (40 or 64 lowercase
  hex) that already gates this block. `_attach_commit_sha` is a separate helper
  used only by unrelated stuck-envelope call sites (retiering/completeness/
  incomplete, all out of scope for this task) — it is not called by the block
  being parameterized here and must not be touched.
- `plugins/mill/scripts/millpy-merge-in-subagent.py`: `_run_conflicts` (full-mode,
  ~line 490, `return _forward_output(output, project_root)`) and the
  `--stage finalize` / `args.mode == "conflicts"` branch (~line 397-424) are the
  two places conflicts-mode reaches a success envelope, and both are in scope
  for the field-rename per the Decision above — both funnel through the same
  generic fallback and produce the same misleading value.
- A grep of `plugins/mill/skills/` for `commit_sha` (run during this discussion
  round) found no file that documents consuming the conflicts-finalize
  envelope's SHA field by name — `mill-merge-in`'s skill file mentions the
  `merge --continue` follow-up step but not this field. There is no confirmed
  doc-update target for the rename; do not add a doc-update line item to the
  plan on spec, and drop it unless planning turns up a target this discussion
  round missed.
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`: grepped for
  `commit_sha` during this discussion round — every occurrence is inside an
  input fixture's self-reported JSON string (e.g. `test_15_stage_finalize_conflicts`,
  `test_19_finalize_conflicts_accepts_parity_flags`); none of them assert
  `commit_sha` on the *output* JSON. No existing test needs editing for the
  field-rename — only the new regression test named in Testing below is
  required.
- `plugins/mill/templates/implementer-brief.md`'s `## Report` section is
  the single edit site for both #978 and #944 — they're adjacent paragraphs in
  the same section, so this can likely be one focused edit pass rather than two
  separate diffs.
- `plugins/mill/skills/git-commit/SKILL.md`'s `## Pre-commit steps` section
  currently has two numbered steps (Lint, Codeguide sync) that run *before*
  staging. The new staging-verification step is conceptually a **post-stage,
  pre-commit** step and belongs in a new subsection (or the `## Rules` list,
  wherever staging is first mentioned: "Stage files individually: `git add
  file1 file2`") — placed structurally after that staging instruction, not
  folded into the existing pre-commit numbered list which the heading text
  scopes to "before staging."

## Constraints

No `CONSTRAINTS.md` present at the hub root (checked via `_constraints.read_if_exists()`
during exploration — file does not exist). No project-specific constraints beyond
the repo-wide conventions already in `CLAUDE.md` (ASCII-only `print()`/`_log()`
output, no `sed`, verify-command `PYTHONPATH=` prefix for Python projects).

## Testing

- `_implementer_common.py`: add a unit test to `test-implementer-common.py`
  covering the new `commit_sha_field_name` parameter — when passed a non-default
  name, the fallback success path's SHA appears under that key and NOT under
  `commit_sha`; when omitted, behavior is unchanged (existing tests as
  regression coverage for the default case).
- `test-millpy-merge-in-subagent.py`: no existing test needs editing (see
  Decisions > rename-conflicts-finalize-field and Technical context — grepped
  during this discussion round, none assert `commit_sha` on output). Add one
  new test asserting the conflicts-mode success envelope carries
  `pre_merge_head` (not `commit_sha`) for both the full-mode and finalize-mode
  call sites, specifically when `merge --continue` has NOT yet been run (i.e.,
  `.git/MERGE_HEAD` still present, or HEAD unchanged from a pre-recorded
  pre-merge value) — this is the regression test that directly pins down
  #953's reported scenario.
- `_implementer_common.py` / `_is_valid_commit_sha`: add one small regression
  test to `test-implementer-common.py` that feeds a 39-char self-reported
  `commit_sha` through `_forward_output` on a success path and asserts the
  output's `commit_sha` is the full 40-char `git rev-parse HEAD` value, not the
  self-reported 39-char one — this is the one targeted addition named in the
  #932 Decision above; it exists to pin the already-correct behavior down
  explicitly since no current test names #932's exact scenario.
- `implementer-brief.md` changes (#978, #944) and `git-commit/SKILL.md`
  changes (#923) are prose/instruction edits with no executable surface — no
  automated test applies. Their correctness is verified by the discussion/plan
  review loop and, longer-term, by whether the corresponding failure patterns
  stop recurring in future mill-go runs (not verifiable synchronously in this
  task).

## Q&A log

- **Q:** Which of the five source issues need code changes vs. documentation-only
  closure? **A:** [auto-pick] Code changes for #953 (conflicts-mode field rename)
  and #923 (staging-verification gate); brief-wording changes for #978 (no prose
  SHA restatement) and #944 (reinforced JSON-line discipline); #932 documented as
  already fixed by commit `6d92c82d`, no further change. **Why:** exploration of
  `_implementer_common.py` and `millpy-merge-in-subagent.py` showed #932's fix
  already predates its own bug report and is provably in effect on every
  success path, while #953 and #923 are confirmed still live in current code.
- **Q:** For #978, should the brief stop prose SHA restatement entirely, or just
  make restatement safer (copy-paste instruction)? **A:** [auto-pick] Stop it
  entirely — never restate `commit_sha` in prose. **Why:** the JSON line's SHA
  is already authoritative and independently recomputed downstream; prose
  restatement serves no consumer and was the sole observed error site.
- **Q:** For #944, is the existing "Long-session reminder" wording sufficient, or
  does it need reinforcement? **A:** [auto-pick] Reinforce with an explicit
  anti-pattern example naming the observed "Note:"-paragraph failure shape.
  **Why:** the existing wording predates #944's report and evidently did not
  prevent it; `inferred: true` recovery already makes this safe, so the change
  is a frequency reduction, not a safety fix.
- **Q:** For #953, rename or omit the misleading `commit_sha` field in
  conflicts-mode finalize? **A:** [auto-pick] Rename to `pre_merge_head`, applied
  to both the finalize-stage and full-mode conflicts call sites. **Why:** the
  value itself (pre-merge HEAD) is legitimate and useful; only the name implies
  a completed merge commit that doesn't exist yet at that point in the
  documented flow.
- **Q:** For #923, what check specifically closes the staging race — `git diff
  --cached --quiet` (as literally suggested in the issue) or something else?
  **A:** [auto-pick] `git diff --quiet -- <staged files>` (unstaged diff against
  the just-staged paths), with one re-stage-and-recheck retry before halting.
  **Why:** `--cached --quiet` only confirms something is staged, not that it
  matches the working tree — it would not have caught the reported incident,
  where content was staged but stale relative to the just-written edit.


### From _mill/plan/00-overview.md


```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
slug: implementer-commit-sha-and-status-line-reliability
approved: true
started: 20260904-100640
parent: main
root: ""
verify: null
```

### From _mill/plan/01-brief-instruction-hardening.md


```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
batch: brief-instruction-hardening
number: 1
cards: 1
verify: null
depends-on: []
```



- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/02-git-commit-staging-verification.md


```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
batch: git-commit-staging-verification
number: 2
cards: 1
verify: null
depends-on: []
```



- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/03-commit-sha-field-rename-and-regression-tests.md


```yaml
task: 'mill-implementer: commit_sha transcription/truncation and final-status-line reliability'
batch: commit-sha-field-rename-and-regression-tests
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-merge-in-subagent.py
depends-on: []
```



- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none

## Conflicting files

- `plugins/mill/scripts/_implementer_common.py`

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
5. Run `git -C /home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability add <file>` to stage the resolved file.
6. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's `Deletes:`, run `git -C /home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability rm <file>` instead of editing;
   that stages the intentional deletion.
7. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification.
   Instead: a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent. b. Run `git show <deletion-commit>` to inspect context. c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"),
   or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C /home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability rm <file>`. d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt.
   Do NOT silently keep the modification.
8. Before reporting `{"status":"success"}` (with or without `discarded`), re-read each file listed in Conflicting files in full and explicitly verify no contradictory losing-side claims survive the resolution — e.g. a stale value from one side of the conflict left alongside the correct value from the other side, or a claim that only made sense before the other side's edit was applied.
   If you find a contradiction you missed, fix it before reporting.
   If you find a contradiction you cannot confidently resolve, report `{"status":"stuck","stuck_type":"logic","reason":"self-verification found an unresolved contradiction in <file>: <description>"}` instead of `{"status":"success"}`.

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
Use `git -C /home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability` for any git commands;
do not `cd`.
Worktree cwd is `/home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability`.
