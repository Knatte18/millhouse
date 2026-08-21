# Discussion: mill-go-base/mill-merge: documented step behavior diverges from underlying script capability

```yaml
task: mill-go-base/mill-merge: documented step behavior diverges from underlying script capability
slug: mill-go-base-documented-behavior-gaps
status: discussing
parent: main
```

## Problem

This task bundles 5 GitHub issues (#847, #842, #850, #856, #873), each reporting a mismatch
between what a mill SKILL.md file documents about an orchestrator step and what the underlying
Python helper actually does. Two of the five (#847, #842) turned out, on investigation against
this worktree's dev-tree source, to be false reports caused by a stale deployed plugin cache — the
underlying code was already fixed before the issue was even filed. The other three (#850, #856,
#873) are confirmed live gaps as of this discussion.

Why now: these were filed independently against the mill plugin over 2026-08-12, discovered live
during real mill-go/mill-merge/mill-start runs in other repos, and folded into this single task per
mill's issue-bundling convention.

## Scope

**In:**
- #850 — `_marker.slug_from_branch`/`_pygit2_util` gains detached-HEAD-matches-a-local-branch
  detection; `MarkerError`'s message is enriched when a match is found; mill-go-base/SKILL.md's
  Entry Step 1 halt handler surfaces `str(e)` verbatim instead of a blanket fixed string.
- #856 — `_preflight.missing_helpers`/`check_helpers` gains an optional attribute-level check (see
  `#856-attribute-level-guard` Decision below); mill-merge/SKILL.md Step 4 and
  mill-merge-in/SKILL.md's own duplicate liveness-check call site (line 21, not 23) each gain
  `_preflight.check_helpers(['_parent_branch:check_liveness'])` immediately before their
  `_parent_branch.check_liveness(...)` call, mirroring the existing Step 5.5
  `_preflight.check_helpers(['_archive_tag'])` guard-placement precedent but targeting the
  function, not just the file.
- #873 — add `r"^discussion-fix-r\d+$"` and `r"^discussion-gap-fix-r\d+$"` to both
  mill-go-base/SKILL.md trigger-set literals: the phase table row (~line 119) and the
  `_phase_wait.matches_wait_trigger` call in the "Entry-gate wait for upstream mill-plan" section
  (~lines 171-173). Both sites change together.
- #847, #842 — closed as no-action. No code or doc change; recorded here so mill-plan doesn't
  re-investigate them.

**Out:**
- No change to `_status.update_field`'s strict-key behavior (#847) — it stays strict by design;
  no defensive doc note added (would be speculative hardening against a hypothetical future
  misuse, not a real gap).
- No change to `millpy-review-code.py`'s `--duration-s` handling (#842) — already correct.
- No auto-checkout or any other repo-state mutation added to mill-go-base's Entry Step 1 (#850) —
  it stays a read-only identification check; remediation is message-only.
- No remote-tracking-branch (`origin/*`) matching for #850 — local branches only.
- No new exception subtype or structured fields on `MarkerError` for #850 — richer message text
  only.

## Decisions

### #850-detection-layer

- Decision: Detect the "detached HEAD, but the commit is still a local branch tip" case inside
  the script layer (`_pygit2_util.py` / `_marker.py`), not as an inline Bash/Python snippet in
  mill-go-base/SKILL.md.
- Rationale: Git plumbing (enumerating branches, comparing OIDs) belongs where the existing
  branch-reading logic already lives (`_pygit2_util.current_branch`, `_pygit2_util.head_sha`), and
  is unit-testable via the existing real-git-tempdir pattern in `unit_tests/test-marker.py`. This
  matches the project's general "logic in scripts, skills orchestrate" convention (see CLAUDE.md
  `## Path invariants`, which applies the same principle to path resolution).
- Rejected: Doc-layer-only detection (catch `MarkerError` in the SKILL.md halt handler, inspect
  `str(e)`, and do ad-hoc branch-matching inline) — would duplicate git plumbing in a markdown
  file with no test coverage.

### #850-remediation

- Decision: Message-only. `mill-go-base`'s Entry Step 1 still halts on the detached-HEAD case, but
  when the commit matches one or more local branch tips, the message names them and suggests next
  steps: `"HEAD is detached at a commit matching branch <name(s)> -- run 'git checkout <name>', or
  use /mill-resume if this worktree was copied from another machine."` When no local branch
  matches, the message stays the original generic text ("this worktree was not created by
  mill-spawn" / detached-HEAD explanation).
- Rationale: Entry Step 1 is a read-only identification check, consistent with every other
  mill-go-base Entry step. Auto-checkout would mutate repo state on the operator's behalf inside
  what's supposed to be inspection-only, and the worktree-copied-from-another-machine scenario
  already has a dedicated recovery flow (`/mill-resume`) that owns worktree recreation — this
  decision points the operator at it instead of re-implementing a subset of it inline.
- Rejected: Auto-checkout the matching branch and continue past Entry Step 1 — bigger blast radius
  than needed, and blurs the identification-check/mutation boundary the rest of Entry keeps.

### #850-branch-matching-scope

- Decision: Check local branches only for a SHA match against detached `HEAD`. If more than one
  local branch matches, list all of them in the message (no arbitrary first-match tie-break).
- Rationale: mill worktrees are always created attached to a local branch by `mill-spawn`; the
  detached-HEAD-with-valid-branch case here means something (rebase artifact, manual `git checkout
  <sha>`) left HEAD pointing at a commit that is still a local branch tip in the *same* worktree.
  Remote-tracking matches would target the different scenario (worktree copied from another
  machine) that's already covered by the `/mill-resume` pointer in the message text, so detecting
  it too would be redundant. Listing all matches avoids an arbitrary ordering decision.
- Rejected: Also matching remote-tracking branches; reporting only the first local match.

### #850-exception-shape

- Decision: Reuse `MarkerError` with richer formatted message text only — no new exception
  subtype, no structured fields (e.g. no `candidate_branches: list[str]` attribute). The
  mill-go-base/SKILL.md Entry Step 1 halt handler is changed to surface `str(e)` verbatim to the
  operator instead of the current blanket fixed string, regardless of which `MarkerError` variant
  was raised.
- Rationale: Given the message-only remediation decision above, the handler never needs to branch
  programmatically on this condition — it only needs to display it. Structured fields would be
  unused plumbing.
- Rejected: A new exception subtype or structured `candidate_branches` field.

### #850-test-coverage

- Decision: Extend `unit_tests/test-marker.py`. Keep `test_slug_from_branch_detached_head` as-is
  in structure (real git repo in a tempdir via `_test_helpers._make_task_worktree`, HEAD checked
  out to its own current SHA) but additionally assert the raised `MarkerError`'s message names
  branch `hanf/foo` — not bare `foo` — since the fixture calls `_make_task_worktree(tmp, "foo",
  ..., branch_prefix="hanf/", ...)`, which checks out `f"{branch_prefix}{slug}"` =
  `"hanf/foo"` (`_test_helpers.py` lines 183-214); the branch-matching code reads git's actual
  branch name, so `hanf/foo` is what it will find and report. Add one new test for the negative
  case: detached HEAD at a commit that is not any local branch's tip, asserting the message falls
  back to the current generic text with no branch name.
- Rationale: `test-marker.py` already exercises exactly the fixture shape needed; extending it is
  near-zero marginal cost versus writing a new test file.
- Rejected: No new test coverage, relying on manual verification.

### #856-attribute-level-guard

- Decision: `_preflight.missing_helpers`/`check_helpers` gains an optional attribute-level check.
  Accept required-helper entries in `"module"` (file-presence only, unchanged/backward-compatible)
  or `"module:attr"` form (file-presence AND `hasattr(imported_module, attr)`); on the `:attr`
  form, missing the attribute is reported the same way as a missing file. Both new call sites
  (mill-merge/SKILL.md Step 4, mill-merge-in/SKILL.md line 21) use
  `_preflight.check_helpers(['_parent_branch:check_liveness'])`. Step 5.5's existing
  `_preflight.check_helpers(['_archive_tag'])` call is left as a bare module name — unchanged.
- Rationale: `check_liveness` (#817) lives inside `_parent_branch.py`, the same file as the
  long-established `resolve()` function. A stale plugin cache with a pre-#817 `_parent_branch.py`
  (has `resolve()`, lacks `check_liveness`) passes a file-existence-only guard and still crashes
  with `AttributeError` at the exact call the guard exists to protect — the precise failure mode
  #856 was filed to prevent. Step 5.5's `_archive_tag` guard protects a different failure class
  (whole-file `ModuleNotFoundError` from a module absent from the cache entirely), where
  file-presence is sufficient and an attribute check would add nothing — so it's left unchanged
  rather than migrated to the new syntax.
- Rejected: Leaving `check_helpers(['_parent_branch'])` as a bare file-presence check (per the
  original Step 5.5 mirror) — confirmed by discussion-review round 1 to not detect #856's actual
  failure mode, since the file exists in the stale-cache case that matters here.

### #847-#842-disposition

- Decision: Close both as no-action against current dev-tree source. No code change, no defensive
  doc note.
- Rationale: #847's offending call site (`_status.update_field(status_path, "blocked_reason",
  ...)`) does not exist in current source — `plugins/mill/skills/mill-go-base/holistic-review.md`
  already calls `_status.set_blocked(...)` instead, which explicitly handles the absent-key case;
  this fix landed in commit `4b3ce636`, before the issue was filed. #842's `--duration-s` flag is
  already declared in `millpy-review-code.py`'s argparse and threaded through to the finalize
  stage, added in commit `479f806b`, over 3 hours before the issue was filed. Both issues were
  filed from external consumer repos against a deployed plugin cache that had not yet picked up
  those commits — the same underlying class of drift that #856 proposes to guard against for
  mill-merge's liveness check.
- Rejected: Adding a defensive doc note to `_status.update_field` warning future callers it's
  strict-key-only — speculative hardening against a hypothetical future misuse; none of the 3
  remaining call sites (mill-merge/SKILL.md, mill-merge-in/SKILL.md, mill-plan/SKILL.md) target a
  non-pre-seeded key, so there's no live pattern to guard against today.

## Technical context

- `_marker.py` (`plugins/mill/scripts/_marker.py`): `slug_from_branch` (lines 56-98) raises
  `MarkerError("detached HEAD or non-branch state")` at line 75 when
  `_pygit2_util.current_branch` returns `None`. This is the raise site to enrich.
- `_pygit2_util.py`: `current_branch` (lines 103-124) returns `None` on `repo.head_is_detached`.
  `head_sha` (lines 83-100) returns `str(repo.head.target)` — usable to get the detached commit's
  SHA. No existing helper enumerates local branches by target SHA; one needs to be added (e.g.
  `local_branches_at_sha(path: Path, sha: str) -> list[str]`, iterating `repo.branches.local` and
  comparing each branch's `.target` to the given SHA — follow the existing `open_repo`/error-wrapping
  pattern used by `current_branch` and `head_sha`).
- `mill-go-base/SKILL.md` line 52: current halt text is a blanket fixed string — `On MarkerError ->
  halt with "this worktree was not created by mill-spawn"` — regardless of the exception's actual
  message. Change to surface `str(e)`.
- `mill-go-base/SKILL.md` phase table (~line 119) and the "Entry-gate wait for upstream mill-plan"
  section's `_phase_wait.matches_wait_trigger` call (~lines 171-173): both currently list
  `discussed`/`discussing`/`planning` plus `^plan-review-r\d+$` / `^plan-fix-r\d+$` only. Add the
  two new discussion-phase patterns to both call sites — see #873 in Scope above.
- `mill-merge/SKILL.md` Step 4 "Liveness check (#817)" (lines 81-111) calls
  `_parent_branch.check_liveness('<parent_branch>', git_root)` (line 88) with no
  `_preflight.check_helpers` guard. Step 5.5 (lines 415-416) is the placement precedent: `import
  _preflight; exit(_preflight.check_helpers(['_archive_tag']))` before the `_archive_tag` import at
  Step 6. `mill-merge-in/SKILL.md` **line 21** (not line 23 — line 23 is the `resolve_dead_parent`
  call in the dead-parent branch) has its own duplicate `check_liveness` call with the same gap —
  needs the same guard.
- `_preflight.missing_helpers`/`check_helpers` (`plugins/mill/scripts/_preflight.py`, lines 25-73
  in current source): takes a list of required helper module names, resolves the active
  `CLAUDE_PLUGIN_ROOT` scripts dir, and returns non-zero with an actionable stderr message if any
  listed module is missing — today, file-presence only (`(scripts_dir / f"{name}.py").exists()`,
  line 38), no attribute check. Per the `#856-attribute-level-guard` Decision above, this needs
  extending to accept a `"module:attr"` form that additionally checks `hasattr` on the imported
  module. Call with `['_parent_branch:check_liveness']` at both new call sites; Step 5.5's existing
  `['_archive_tag']` call stays a bare module name.
- `unit_tests/test-preflight.py` already exists and covers `_preflight.py` — extend it for the new
  attribute-check form (see Testing below).
- Full per-issue investigation detail (issue bodies, exact commit hashes, line-cited current
  behavior) is preserved at `.scratch/issue-detail-report.md` in this worktree for mill-plan's
  reference, though this discussion file is self-contained without it.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- `_marker.py` / `_pygit2_util.py` (TDD candidate): extend `unit_tests/test-marker.py` per the
  `#850-test-coverage` decision above — positive case (detached HEAD matching a local branch tip,
  message names the branch) and negative case (detached HEAD matching no local branch, message
  stays generic). Add a focused unit test for the new `_pygit2_util` branch-enumeration helper
  itself if it's added as a standalone function (e.g. `unit_tests/test-pygit2-util.py` if that file
  exists, otherwise colocate in `test-marker.py`).
- `_preflight.py` (TDD candidate, #856): extend `unit_tests/test-preflight.py` with cases for the
  new `"module:attr"` form — module present with the attribute (passes), module present without
  the attribute (reported missing), and confirm the bare `"module"` form's existing behavior is
  unchanged. `mill-merge` / `mill-merge-in` SKILL.md step text itself has no automated test harness
  (prose-driven orchestration, not executable code) — verify manually that both new
  `_preflight.check_helpers(['_parent_branch:check_liveness'])` lines are placed immediately
  before their respective `check_liveness` calls, matching Step 5.5's exact placement-before-import
  pattern.
- `mill-go-base` phase-table / `matches_wait_trigger` (#873): if `_phase_wait.py` has unit tests
  (check `unit_tests/` for a `test-phase-wait.py` or similar), add cases asserting
  `discussion-fix-r3` and `discussion-gap-fix-r12`-shaped strings match the wait trigger. Otherwise
  verify the two new regex patterns are syntactically consistent with the existing
  `^plan-review-r\d+$` / `^plan-fix-r\d+$` patterns (same `\d+` group, same anchoring).
- #847, #842: no test changes — no-action dispositions.

## Q&A log

- **Q:** #847 (`_status.update_field` ValueError vs mill-go docs) — close as no-action, or also add
  a defensive doc/code note? **A:** [auto-pick] Close as no-action; the offending call site was
  already replaced with `_status.set_blocked` before the issue was filed — stale plugin-cache
  artifact, not a live gap. **Why:** the 3 remaining call sites all target pre-seeded keys; a
  hardening note would be speculative documentation for a hypothetical future misuse.
- **Q:** #842 (`--duration-s` rejected by finalize) — close as no-action, or add a regression test?
  **A:** [auto-pick] Close as no-action; the flag was added to argparse (and threaded through) over
  3 hours before the issue was filed — stale plugin-cache artifact. **Why:** mill-go-base/SKILL.md's
  documented contract already matches the CLI's current flags exactly; no live mismatch to guard
  against.
- **Q:** Include #856 + #873 mechanical fixes in this task's scope? **A:** [auto-pick] Yes — fix
  both. **Why:** both are already bundled in this task's brief, both are confirmed live gaps, and
  both fixes mirror an existing precedent already in the same file.
- **Q:** #850 — where to detect the detached-HEAD-with-valid-branch case: script layer vs. doc
  layer? **A:** [auto-pick] Script layer (`_marker.slug_from_branch`/`_pygit2_util`). **Why:** git
  plumbing belongs where existing branch-reading logic already lives and is unit-testable;
  duplicating it as an inline skill-markdown snippet breaks the "logic in scripts, skills
  orchestrate" convention.
- **Q:** #850 — what should happen once the recoverable case is detected: message-only or
  auto-checkout? **A:** [auto-pick] Message-only; still halt, with an actionable message pointing
  at `git checkout <name>` or `/mill-resume`. **Why:** Entry Step 1 is read-only elsewhere in
  mill-go-base; auto-checkout would mutate repo state on the operator's behalf, and `/mill-resume`
  already owns the worktree-copied-from-another-machine recovery flow.
- **Q:** #850 — branch-matching scope: local only, or local + remote-tracking? **A:** [auto-pick]
  Local branches only. **Why:** mill worktrees are always created attached to a local branch by
  mill-spawn; the remote-tracking scenario is a different case already covered by the
  `/mill-resume` pointer in the message text.
- **Q:** #850 — multiple matching local branches: list all, or report first match only? **A:**
  [auto-pick] List all. **Why:** "first match" is an arbitrary tie-break with no defined ordering;
  listing all candidates is unambiguous and equally cheap.
- **Q:** #850 — exception shape: richer `MarkerError` text only, or a new subtype/structured
  fields? **A:** [auto-pick] Richer text only, no new fields. **Why:** given the message-only
  remediation decision, the halt handler never needs to branch programmatically on this condition,
  only display it — structured fields would be unused plumbing.
- **Q:** #850 — add unit test coverage for the new branch-matching path? **A:** [auto-pick] Yes —
  extend `test-marker.py`'s existing detached-HEAD test plus one new negative-case test. **Why:**
  the existing fixture (real git tempdir, HEAD checked out to its own SHA) already *is* the
  positive case; extending it is near-zero marginal cost.
- **Q:** (discussion-review round 1, BLOCKING) `_preflight.check_helpers(['_parent_branch'])` is a
  file-presence-only check, but #856's actual failure mode is a stale cache with `_parent_branch.py`
  present yet missing the `check_liveness` function — should the guard gain an attribute-level
  check, or is file-presence documented as intentionally sufficient? **A:** [auto-resolved] Extend
  `_preflight.missing_helpers`/`check_helpers` to accept an optional `"module:attr"` form that also
  checks `hasattr`; use `['_parent_branch:check_liveness']` at both new #856 call sites. **Why:**
  file-presence alone does not catch the specific stale-cache scenario #856 was filed to guard
  against, since `_parent_branch.py` already exists in that scenario — only the function is
  missing. Step 5.5's `_archive_tag` guard is left as a bare module name since its failure mode
  (whole-file absence) is genuinely caught by file-presence alone.
