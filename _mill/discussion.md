# Discussion: mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit

```yaml
task: mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit
slug: mill-plan-entry-gate-wait-trigger-gaps
status: discussing
parent: main
```

## Problem

`mill-plan/SKILL.md`'s "Entry-gate wait for upstream mill-start" lets a bare `/mill-plan` block on a `Monitor` wait until mill-start reaches `phase: discussed`, instead of halting and telling the operator to babysit mill-start manually. Two bugs undermine that wait, bundled from three source issues:

1. **Trigger gap (#1041, #1028, duplicates).** The wait's trigger call, `_phase_wait.matches_wait_trigger(phase, {"discussing"}, [r"^discussion-fix-r\d+$"])`, omits `^discussion-gap-fix-r\d+$`. mill-start's Phase: Discussion Review step 5 (the plain-interactive gap-resolution path — under `--auto`/`--orch`, step 5 is skipped entirely per `mill-start/SKILL.md:390`, so this phase value never appears in that mode; not step 4b's NIT-fix path either) writes, commits, and pushes `discussion-gap-fix-r{N}` as its own standalone phase before continuing to round N+1 — confirmed at `mill-start/SKILL.md:406`. Since that phase value matches neither the exact set nor the regex, `mill-plan`'s wait falls through to the narrowed catch-all Entry row and halts, even though mill-start is actively running and will reach `discussed` shortly. `mill-go-base/SKILL.md`'s own copy of this exact wait pattern (mill-go waiting on mill-plan) already carries the widened 4-pattern list including `discussion-gap-fix-r{N}` — this is the same one-phase-short gap issue #821 already fixed for `discussion-fix-r{N}`, just never carried over to mill-plan's own copy for the sibling phase.

2. **Pinning race (#1029).** The wait polls `status_path` **on disk**, but mill-start writes `<discussion_path>` and appends the `discussed`/`discussion-fix-r{N}`/`discussion-gap-fix-r{N}` phase to `status_path` *before* its single `git commit` call lands (see e.g. `mill-start/SKILL.md`'s step-5 gap-fix path: "write `<discussion_path>`, call `_status.append_phase(...)`, commit..."). If the `Monitor` poll's `grep` catches `status_path` in that window — phase already written, commit not yet run — it reports `READY` while both files are still dirty in the working tree. `mill-plan`'s Phase: Plan then reads `_mill/discussion.md` fresh off disk (the new content) but pins `discussion_sha = git rev-parse HEAD:_mill/discussion.md` (the *previous* round's committed blob, since the new commit hasn't landed yet) — a mismatch baked in at the moment of capture, not a later drift.

## Scope

**In:**
- Widen mill-plan's own Entry-gate wait trigger regex list to also match `discussion-gap-fix-r{N}`, mirroring `mill-go-base/SKILL.md`'s already-correct 4-pattern list.
- Close the pinning race by making the wait's `READY` condition require a clean git tree for `status_path` and `discussion_path`, not just the phase-value match — i.e. only report `READY` once mill-start's commit has actually landed.
- Update `plugins/mill/skills/mill-plan/SKILL.md`'s Entry-gate wait section (phase-table row, trigger call, and its explanatory prose) and `plugins/mill/scripts/_phase_wait.py`'s `build_wait_command`.
- Unit test coverage for both changes in `plugins/mill/unit_tests/test-phase-wait.py`.

**Out:**
- `mill-go-base/SKILL.md`'s analogous Entry-gate wait (mill-go waiting on mill-plan's `phase: planned`) is architecturally exposed to the same pinning-race class — mill-plan's own Phase: Handoff/4b-style commit sequencing writes files then commits, same as mill-start's. None of the three source issues report it there, and it is not touched by this task. See Decisions below for why the fix is opt-in per call site rather than a blanket behavior change.
- The existing `discussion_sha` drift-guard machinery (capture at Phase: Plan entry, pre-commit re-check, per-dispatch-site re-check in Phase: Plan Review — added by a prior task, commits `b805007d`/`1e8ec476`) is not modified. It remains as defense-in-depth against a genuinely concurrent edit to `discussion.md` *after* Phase: Plan has already started; this task's fix eliminates the specific stale-initial-capture case that guard cannot see, it doesn't replace the guard.
- No change to `mill-start/SKILL.md`'s phase-writing/commit sequencing itself — the fix lives entirely on the waiting side (mill-plan), not the writing side (mill-start).

## Decisions

### Widen the trigger regex list

- Decision: add `r"^discussion-gap-fix-r\d+$"` to the `regex_patterns` list in mill-plan's Entry-gate wait `matches_wait_trigger` call (`mill-plan/SKILL.md:87`), and update the phase-table row (`:77`) and the explanatory paragraph (`:89`–`90`) to name both `discussion-fix-r{N}` and `discussion-gap-fix-r{N}`.
- Rationale: like-for-like parity with `mill-go-base/SKILL.md`'s already-widened, already-tested 4-pattern list (`plugins/mill/unit_tests/test-phase-wait.py`'s Case 15 already exercises `discussion-gap-fix-r{N}` matching against that list) — this is the same class of gap #821 fixed for `discussion-fix-r{N}`, left uncarried for the sibling phase in mill-plan's own copy.
- Rejected: leaving it unmatched — the current, broken behavior: mill-plan halts and tells the operator to run mill-start, even while mill-start is actively mid-run. (#1041's reporter had to work around this manually in-session.)

### Gate `READY` on a clean tree, not just phase value

- Decision: extend `_phase_wait.build_wait_command` with two new optional keyword-only parameters, `clean_tree_root: Path | None = None` and `clean_tree_paths: list[Path] | None = None`. When both are supplied, the rendered poll script only echoes `READY` when the phase-value grep matches **and** `git -C <clean_tree_root> status --porcelain -- <path...>` is empty for every path in `clean_tree_paths`; otherwise it keeps polling (the `elapsed`/`giveup_s` timeout accounting is unaffected — a dirty-tree iteration just doesn't echo `READY` yet, same as a non-matching phase value today). Raise `ValueError` if exactly one of the two parameters is given (a caller bug, not a valid partial configuration) — mirrors this module's existing fail-fast style. Omitting both parameters (as every existing call site does today) reproduces today's script byte-for-byte — this is purely additive.
  mill-plan's Entry-gate wait call site becomes:
  ```python
  discussion_path = _paths.resolve_task_path(worktree_root, cfg['paths']['discussion_file'])
  cmd = _phase_wait.build_wait_command(
      status_path, "discussed", 10, giveup_s,
      clean_tree_root=git_root, clean_tree_paths=[status_path, discussion_path],
  )
  ```
  (`discussion_path` is not otherwise bound this early in mill-plan's Entry section today — the same `resolve_task_path` pattern `Path Setup` already uses for `status_path` derives it here, locally, for this call.)
- Rationale: this closes the race at its source instead of downstream. It mirrors #1029's reporter's own manual workaround exactly (“arming a second ad-hoc `Monitor` polling `git status --porcelain -- <discussion.md> <status.md>` until empty, then entering Phase: Plan”) but makes it structural, in one poll script, instead of a second ad-hoc wait bolted on after the first. It also composes cleanly with the existing drift-guard: that guard can only detect a blob-sha *change* between two of its own reads, so it cannot tell "the read I started with was already stale" from "nothing has changed" — gating `READY` on a clean tree prevents mill-plan from ever starting Phase: Plan with a stale initial read in the first place, restoring the drift-guard to catching only genuine concurrent edits during planning.
- Rejected:
  - Making Phase: Plan itself poll for a clean tree before capturing `discussion_sha` — this would duplicate the poll/timeout machinery `_phase_wait.py` already owns, for no benefit over gating the existing wait.
  - Making the clean-tree check unconditional in `build_wait_command` (always-on, no opt-in) — this would silently change `mill-go-base/SKILL.md`'s existing wait behavior too, which is out of scope for this task's three source issues (all specifically about mill-plan waiting on mill-start). An additive, opt-in pair of keyword parameters keeps today's other call site byte-for-byte unchanged. **This is a judgment call, made autonomously in the absence of an operator** — a follow-up task could evaluate applying the same `clean_tree_root`/`clean_tree_paths` gating to mill-go-base's own wait for `phase: planned` (mill-go waiting on mill-plan's Handoff/Phase: Plan Review commit), which is architecturally exposed to the identical race, but it has not been reported and is left as a candidate future issue rather than folded in here.

## Technical context

- `plugins/mill/scripts/_phase_wait.py` — pure string-building/predicate module, no file I/O of its own (`build_wait_command`, `matches_wait_trigger`). Both source issues' fixes land here plus in `mill-plan/SKILL.md`'s prose.
- `plugins/mill/skills/mill-plan/SKILL.md` — "Entry-gate wait for upstream mill-start" section (lines ~81–116 as of this writing): the phase-table row at line 77, the `matches_wait_trigger` call at line 87, and its explanatory prose at 89–90 all need the parity update. `git_root` is already bound at Entry step 1; `discussion_path` needs a one-line local derivation at this call site (see Decisions above) since it isn't otherwise bound until Phase: Plan.
- `plugins/mill/skills/mill-go-base/SKILL.md` — read-only reference for this task: its own Entry-gate wait (lines ~120–193) already carries the widened `discussion-gap-fix-r{N}` pattern and is the parity target for the trigger-list fix; leave this file untouched.
- `plugins/mill/skills/mill-start/SKILL.md:406` — confirms `discussion-gap-fix-r{N}` is committed standalone; confirms the write-then-commit ordering that produces the pinning race. Read-only reference, not edited by this task.
- `plugins/mill/skills/mill-plan/SKILL.md:147,290,301,314` — the existing `discussion_sha` drift-guard (capture, persist, pre-commit check, per-dispatch-site check). Not modified; described in Scope/Decisions as defense-in-depth this task's fix complements rather than replaces.
- `plugins/mill/unit_tests/test-phase-wait.py` — existing Case 15 already tests `matches_wait_trigger` against the widened 4-pattern set (documented there as "mill-go-base/SKILL.md's Entry-gate wait for upstream mill-plan"); mill-plan's own trigger list has no equivalent up-to-date case today and needs one. `build_wait_command`'s existing cases (1–7-ish, covering the ready-phase grep, `tr -d '\r'`, timeout, poll/sleep, space-quoting, trailing-`$` anchoring) all assume the two-argument-only, no-clean-tree-check call shape and must keep passing unmodified — new cases are additive, not replacements.

## Constraints

None beyond this repo's own conventions (no `CONSTRAINTS.md` at hub root).

## Testing

- `matches_wait_trigger`: add a case mirroring existing Case 15 but scoped to mill-plan's own (now-widened) 2-pattern list (`[r"^discussion-fix-r\d+$", r"^discussion-gap-fix-r\d+$"]` against `exact={"discussing"}`) — asserts `discussion-gap-fix-r12` matches, `discussion-fix-r3` still matches, and a near-miss like `discussion-fixed-r3` does not.
- `build_wait_command`:
  - Regression: every existing case (no `clean_tree_*` kwargs) must still produce byte-identical output to before this change — confirms the extension is additive.
  - New: with `clean_tree_root`/`clean_tree_paths` supplied, the rendered script contains a `git -C <root> status --porcelain -- <path...>` (or equivalent) guard gating the `echo "READY"` line — assert by string content, consistent with this test file's existing string-content-assertion style (it never executes the rendered bash).
  - New: `ValueError` when exactly one of `clean_tree_root`/`clean_tree_paths` is supplied and the other is `None`.
  - New, required (not optional): actually execute the rendered script in a tempdir git repo, exercising the dirty-then-clean transition, to confirm `READY` is genuinely withheld while the tree is dirty and fires once committed. `test-phase-wait.py`'s own Case 13 (lines 115–146) already establishes real `subprocess.run(["bash", "-c", ...])` execution as this file's convention for exactly this kind of race/timing behavior — the dirty-then-clean case follows that established pattern, it is not an optional addition gated on a "purely string-content assertions" premise that doesn't hold.
- No test changes needed for `mill-start/SKILL.md` or `mill-go-base/SKILL.md` — neither is modified by this task.

## Q&A log

- **Q:** Should the pinning-race fix (#1029) gate `READY` on a clean git tree (mirroring the reporter's own manual workaround), or instead make Phase: Plan itself wait for/verify the commit before capturing `discussion_sha`? 1) Gate `READY` on a clean git tree via new opt-in `clean_tree_root`/`clean_tree_paths` params on `_phase_wait.build_wait_command`, scoped to mill-plan's call site only (Recommended) 2) Add a separate clean-tree wait/poll inside mill-plan's Phase: Plan, ahead of the `discussion_sha` capture. **A:** [auto-pick] Option 1. **Why:** it fixes the race at its source in the one shared wait-building module instead of duplicating poll/timeout logic a second time inside Phase: Plan, and it composes cleanly with the existing (already-shipped) `discussion_sha` drift-guard as defense-in-depth rather than overlapping with it.
- **Q:** Should the clean-tree gating also apply to `mill-go-base/SKILL.md`'s analogous wait (mill-go waiting on mill-plan's `phase: planned`), which is exposed to the same race class but wasn't reported? 1) Leave it untouched — out of scope for this task's three source issues; flag it as a candidate follow-up (Recommended) 2) Fix it too in the same task, since it's the same bug pattern. **A:** [auto-pick] Option 1. **Why:** none of the three source issues report a problem there, so folding it in here would widen this task's diff past what was actually triaged; the opt-in parameter shape means doing it later is a small, independent follow-up, not a rework.
