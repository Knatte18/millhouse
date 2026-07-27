# Discussion: mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases

```yaml
task: mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases
slug: mill-go-verify-gate-misclassification
status: discussing
parent: main
```

## Problem

Two independent, unrelated misclassification bugs in mill's own gate/cleanup
logic, both filed as closed GitHub issues (#715, #716) and folded into this
one task.

**Bug 1 (#715).** `_implementer_common.py`'s `_go_build_tag_retiering_stuck`
(fixes #642) detects `//go:build` constraint transitions between batch start
and HEAD and runs a `go build` compile check against the affected package
directory. When a batch does a whole-directory deletion (e.g. `git rm -r
internal/warpcli`) and one of the deleted files carried a `//go:build` tag,
the diff shows that tag's line disappearing — indistinguishable, to the
current parser, from a same-directory detagging edit. The gate schedules a
compile check (`go build -tags <tag> ./<dir>/...`) against a directory that
no longer exists, which fails with `lstat: no such file or directory`, and
mill-go reports a spurious `stuck_type:verify` even though the batch's real
verify command passed cleanly. A user hit this on branch `fabric-cutover`
and had to manually bypass the finalize gate.

**Bug 2 (#716).** `millpy-cleanup.py`'s `_LIVE_PHASES` set only lists the
base pipeline phases (`discussing`, `discussed`, `planning`, `planned`,
`implementing`, `reviewing`, `fixing`, `blocked`). `_status.append_phase` is
routinely called with round-suffixed and batch-name-embedded phase values —
`discussion-fix-rN`, `plan-review-rN`, `plan-fix-rN`, `reviewing-{batch}-rN`,
`fixing-{batch}-rN`, `approved-{batch}`, `nits-fixed-{scope}`,
`holistic-reviewing`, `holistic-fixing`, `holistic-approved` — none of which
match the fixed set, so any task sitting on one of these phases (i.e. any
task mid-plan-review, mid-batch-review, or mid-holistic-review) is reported
as `"unknown phase '<phase>', skipping"` on every cleanup run. This is a
false positive: the task is live and mid-pipeline, not actually broken.
Note: the base set's bare `"reviewing"` and `"fixing"` entries are dead —
`append_phase` never writes those bare values, only the batch-suffixed or
`holistic-` prefixed forms.

**Why now:** both are real false-positive reports discovered during actual
mill-go/mill-cleanup runs on other repos (`loomyard`), filed as bugs against
millhouse itself, and both root-caused with a concrete suggested fix already
in the issue text.

## Scope

**In:**
- Fix `_go_build_tag_retiering_stuck` in `plugins/mill/scripts/_implementer_common.py`
  to skip the compile check (with a stderr log line) when the target
  directory no longer exists on disk, for both `added_dirs` and
  `removed_dirs` transitions.
- Fix live-phase classification in `plugins/mill/scripts/millpy-cleanup.py`
  (`build_plan`, around the `_LIVE_PHASES` set / line 179 `elif phase in
  _LIVE_PHASES`) to recognize the full real phase vocabulary written by
  mill-start/mill-plan/mill-go via `_status.append_phase`, not just the
  three round-suffixed phases literally named in issue #716.
- Unit tests for both fixes, following each file's existing test
  conventions.

**Out:**
- No change to `_go_build_tag_retiering_stuck`'s transition-classification
  logic itself (added/removed/value-only detection, `_is_qualifying_custom_tag`,
  GOOS/GOARCH handling) — only the missing existence check before the
  compile-check step.
- No change to `_parse_go_build_tag_diff`'s diff-parsing approach (e.g. no
  switch to `git diff --name-status` based deletion detection) — the
  directory-existence check is the chosen mechanism (see Decisions).
- No change to any other `millpy-cleanup.py` classification branch (`done`,
  `abandoned`, `pr-pending`, orphan-worktree detection, `status.md`-unreadable
  handling) — only the `_LIVE_PHASES` live-phase branch.
- No change to how/when `_status.append_phase` writes phase values — this
  task only changes how the reader (`millpy-cleanup.py`) classifies them.
- No retroactive audit of already-reported "unknown phase" tasks in any
  live repo.

## Decisions

### bug1-detection-mechanism

- Decision: Before running the `go build` compile check for a given
  `dir_str` (in both the `added_dirs` loop and the `removed_dirs` loop),
  check `(project_root / dir_str).is_dir()`. If the directory does not
  exist, skip the compile check for it and print a stderr log line
  matching the existing skip-logging style used elsewhere in this
  function (e.g. the `tag_mismatch` / non-qualifying-tag skip branches):
  `f"[go-build-tag-retiering] skip: {dir_str} no longer exists on disk (directory deleted)"`.
- Rationale: This is the issue's own suggested minimal fix. It is
  symmetric (applies to both transition directions, since a directory
  deletion could in principle coincide with either an added-tag or
  removed-tag classification, even though the reported repro is the
  removed-tag case) and requires no change to the diff-parsing stage.
  `dir_str == "."` (repo root) is never deleted by construing a batch that
  deletes the whole repo, so no special-case is needed for that value —
  `Path(project_root).is_dir()` is trivially true.
- Rejected: Detecting deletion via `git diff --name-status` and excluding
  deleted files from `_parse_go_build_tag_diff` entirely. Rejected because
  it requires a second git subprocess call, duplicates information the
  existence check gets for free from the filesystem, and doesn't cover a
  file that still exists in the diff's `a/`/`b/` history but whose parent
  directory was removed by a later step within the same batch (e.g. file
  moved out then directory removed) — the isdir check is a strictly
  simpler and more robust guard at the point the compile check is about to
  run.

### bug2-live-phase-detection

- Decision: Replace the flat `_LIVE_PHASES` set-membership check
  (`millpy-cleanup.py`, `elif phase in _LIVE_PHASES: pass`) with a helper
  function `_is_live_phase(phase: str) -> bool` defined next to
  `_read_phase` in the same file. It returns `True` for:
  - Exact matches: `discussing`, `discussed`, `planning`, `planned`,
    `implementing`, `blocked`, `holistic-reviewing`, `holistic-fixing`,
    `holistic-approved`.
  - Regex matches (compiled at module scope alongside the exact set):
    - `^discussion-fix-r\d+$`
    - `^plan-review-r\d+$`
    - `^plan-fix-r\d+$`
    - `^reviewing-.+-r\d+$` (matches `reviewing-{batch_name}-r{N}`)
    - `^fixing-.+-r\d+$` (matches `fixing-{batch_name}-r{N}`)
    - `^approved-.+$` (matches `approved-{batch_name}`)
    - `^nits-fixed-.+$` (matches `nits-fixed-{scope}`, scope = batch name or `"holistic"`)
  - The bare `"reviewing"` and `"fixing"` entries are dropped from the
    exact-match set — `_status.append_phase` never writes those literal
    values (grep across `plugins/mill/skills/*/SKILL.md` and
    `plugins/mill/scripts/*.py` for `append_phase(` call sites confirms
    every reviewing/fixing phase is either batch-suffixed or
    `holistic-`-prefixed). Caveat: this grep only covers current source,
    not whether any already-registered active worktree's `status.md` has
    `phase:` frozen at a bare `reviewing`/`fixing` value from before
    round-suffixing existed — such a task would flip from silently-live to
    newly-reported by `millpy-cleanup`. This is a bounded, low-severity
    residual risk (a diagnostic report line only, never a mutation) and
    falls under the same "no retroactive audit of live repos" carve-out
    already listed under Scope > Out.
  - `done`, `abandoned`, `pr-pending` are unaffected — they're handled by
    earlier `elif` branches in `build_plan` before the live-phase check is
    ever reached, and are NOT part of `_is_live_phase`.
- Rationale: The issue's own suggested fix names only 3 phases, but is
  explicitly qualified with "or a regex over the phase vocabulary" as an
  acceptable alternative. Grepping every `_status.append_phase(` call site
  across `plugins/mill/scripts/` and `plugins/mill/skills/*/SKILL.md`
  shows the real vocabulary is much larger than the 3 phases named in
  #716 — it includes batch-name-embedded phases (`reviewing-<batch>-rN`,
  `fixing-<batch>-rN`, `approved-<batch>`, `nits-fixed-<scope>`) that a
  fixed prefix list can't enumerate (batch names are arbitrary plan-DAG
  identifiers). The narrow 3-phase fix would leave the bug effectively
  unfixed for the common case — any task mid-batch-review, mid-batch-fix,
  or mid-holistic-review would still misreport as "unknown phase" on every
  cleanup run. The comprehensive regex-based fix covers every phase value
  `_status.append_phase` is ever called with anywhere in the current
  codebase.
- Rejected: Narrow fix (prefix-match only the 3 phases literally named in
  #716). Rejected per Rationale above — doesn't actually close the false-
  positive gap for the majority of real mid-pipeline states.
- Rejected: Moving `_is_live_phase` into `_status.py` as a shared helper.
  Rejected because phase-vocabulary classification for cleanup-reporting
  purposes is specific to `millpy-cleanup.py`'s use case (deciding what to
  silently skip vs. report); no other script currently needs this
  classification, and `_status.py` is the phase-writer, not a phase-
  vocabulary registry — keeping the reader-side helper local avoids
  implying `_status.py` owns the full enumerated vocabulary of every
  caller's round/batch-naming scheme.

## Technical context

**Bug 1 files:**
- `plugins/mill/scripts/_implementer_common.py`:
  - `_go_build_tag_retiering_stuck` (~line 1004-1137): the gate function
    itself. The `added_dirs`/`removed_dirs` loops needing the isdir guard
    are at ~line 1097-1131.
  - `_parse_go_build_tag_diff` (~line 903): diff parser, unchanged.
  - `_go_build_tag_dir` (~line 941): returns the POSIX parent directory of
    a diff-reported file path — this is the `dir_str` value to check with
    `is_dir()`.
  - `_go_build_pattern` (~line 953), `_is_qualifying_custom_tag` (~line
    958), `_go_build_tag_stuck_dict` (~line 984): unchanged, referenced for
    context only.
  - Existing skip-logging style to match (both at ~line 1109 and ~1117):
    `print(f"[go-build-tag-retiering] skip: ...", file=sys.stderr)`.

**Bug 2 files:**
- `plugins/mill/scripts/millpy-cleanup.py`:
  - `build_plan` (~line 89 onward): the function containing `_LIVE_PHASES`
    (~line 115-118) and the `elif phase in _LIVE_PHASES: pass` branch
    (~line 179).
  - `_read_phase` (~line 53): reads the `phase:` scalar from `status.md`'s
    yaml block — unchanged, this is what feeds the classification.
- `plugins/mill/scripts/_status.py`:
  - `append_phase` (~line 444): the single writer of the `phase:` field.
    Docstring confirms phase names come from an open-ended "closed v2 set"
    plus "per-round variants" — i.e. round-suffixing is an expected,
    ongoing pattern, not a one-off.
  - Call sites across `plugins/mill/skills/*/SKILL.md` (including
    `mill-plan`, `mill-go`, `mill-start`, and also `mill-finalize`/
    `mill-merge` for the `pr-pending` phase, which is handled by an
    earlier `elif` branch in `build_plan` and is intentionally excluded
    from `_is_live_phase`) are the authoritative list of phase values in
    current use (see Decisions for the full enumerated set derived from
    these).

## Constraints

No `CONSTRAINTS.md` present at the hub root — none apply beyond the
codebase conventions already captured in Decisions/Technical context
(ASCII-only stderr logging per project CLAUDE.md, existing skip-log style).

## Testing

**Bug 1 — `_go_build_tag_retiering_stuck` (test file:
`plugins/mill/unit_tests/test-implementer-common.py`, follows the existing
"case 66*" convention — real git repo in a `tempfile.TemporaryDirectory()`,
`unittest.mock.patch.object(_subprocess_util, "run", side_effect=...)` via
the existing `_go_gate_mock` helper so only `go build` calls are mocked and
git operations run for real):**

- New case (append after case 66c or wherever the next free case letter
  is): create a package directory with a `//go:build <custom-tag>`-tagged
  file, commit (`start_sha`), then `git rm -r` the whole directory and
  commit again. Call `_go_build_tag_retiering_stuck(project_root, start_sha,
  session_id)` and assert: `result is None`, zero `go build` calls
  recorded (`calls == []`), and a skip line appears on stderr (matching
  the `"skip"` substring check pattern used in case 66c) mentioning the
  directory no longer existing.
- Also cover the added-tag-transition case for symmetry with the "apply
  to both loops" decision. Note: an added-tag transition (added=1,
  removed=0) can only be classified for a file that still exists at HEAD
  — `git diff` reports a deleted file's original lines purely as
  removals, never additions — so a directory that is truly gone on disk
  can never surface via `added_dirs` through git history alone; only
  `removed_dirs` can arise from an actual directory deletion. To exercise
  the `added_dirs` isdir-skip path anyway (both loops must be covered by
  the fix, per Decisions), construct the test by physically removing the
  directory from disk without committing: reuse case 66a's git setup (tag
  added, directory present and committed in git), then `shutil.rmtree` the
  directory before calling `_go_build_tag_retiering_stuck` — the diff
  still classifies it as an added-tag transition from git's perspective,
  but the isdir() check now correctly skips it since the directory is
  physically absent, exactly as the gate itself observes the filesystem.
- TDD candidate: yes — write the failing case first (currently the isdir
  check doesn't exist, so this new case should reproduce the
  `lstat`-style failure via a real `go build` if not mocked, or simply
  assert the (currently wrong) call happens against a `dir_str` argument
  for the deleted directory before the fix lands).

**Bug 2 — `_is_live_phase` (test file: `plugins/mill/unit_tests/test-cleanup.py`,
follows the existing `_make_status_md(phase, parent)` + `build_plan(...)`
+ `plan.to_report` assertion convention seen in the `"implementing"`/
`"abandoned"`/`"done"` phase tests):**

- Unit-test `_is_live_phase` directly (if exported/importable the same way
  `build_plan`/`_resolve_inplace_mode` already are via `importlib.util`) for
  each of the exact and regex cases listed in the Decisions section:
  `discussing`, `holistic-reviewing`, `holistic-fixing`, `holistic-approved`,
  `discussion-fix-r1`, `plan-review-r3`, `plan-fix-r2`,
  `reviewing-batch-a-r1`, `fixing-batch-a-r2`, `approved-batch-a`,
  `nits-fixed-holistic`, `nits-fixed-batch-a` → all `True`. And confirm
  bare `"reviewing"` / `"fixing"` (now dropped) plus a genuinely unknown
  value (e.g. `"frobnicating"`) → `False`.
- Integration-level: at least one `build_plan(...)` test using a
  round-suffixed or batch-embedded phase value (e.g. `plan-review-r2` or
  `reviewing-batch-a-r1`) via `_make_status_md`, structured like the
  existing `"implementing"` phase test at ~line 276 (same fixture/call
  pattern), but with a new `plan.to_report == []` assertion — that
  existing test itself only asserts `to_remove_done`/`to_remove_abandoned`/
  `to_reset_home` are empty (lines 267-285), not `to_report`, so the
  `to_report == []` check here is new, not literally carried over.
- TDD candidate: yes for `_is_live_phase` itself (pure function, easy to
  drive test-first); the `build_plan` integration case can follow once the
  helper exists.

## Q&A log

- **Q:** How should the gate detect a deleted directory before compile-checking it? **A:** [auto-pick] Check `os.path.isdir(project_root / dir_str)` before each compile check (both loops); skip with a stderr log line if missing. **Why:** matches the issue's own suggested minimal fix; symmetric across transition types; needs no change to diff parsing.
- **Q:** Apply the directory-existence check to which loop(s) — `added_dirs`, `removed_dirs`, or both? **A:** [auto-pick] Both, uniformly. **Why:** directory deletion is a general precondition failure for any compile check, not specific to the removed-tag repro path; symmetric handling is simpler to reason about than a special case.
- **Q:** What should the skip-log line say? **A:** [auto-pick] `[go-build-tag-retiering] skip: {dir} no longer exists on disk (directory deleted)` to stderr. **Why:** matches the existing `[go-build-tag-retiering] skip: ...` convention used by the tag-mismatch and non-qualifying-tag skip branches in the same function.
- **Q:** Should the millpy-cleanup fix cover only the 3 phases literally named in issue #716, or the full round-suffixed/batch-embedded phase vocabulary mill-go actually writes? **A:** [auto-pick] Comprehensive — a regex/prefix-based `_is_live_phase()` helper covering every phase value `_status.append_phase` is called with anywhere in the current codebase (batch-name-embedded phases included). **Why:** the narrow fix leaves the bug effectively unfixed for the common case (any task mid-batch-review or mid-holistic-review still misreports as unknown); the issue text itself allows "a regex over the phase vocabulary" as an acceptable alternative to the literal 3-phase list.
- **Q:** Should the dead bare `"reviewing"`/`"fixing"` entries in the base `_LIVE_PHASES` set be removed? **A:** [auto-pick] Yes, remove them. **Why:** `_status.append_phase` never writes those literal bare values (confirmed by grepping every `append_phase(` call site) — they are unreachable and misleading; the regex forms correctly cover the real values that replace them.
- **Q:** Where should the new phase-classification helper live — `millpy-cleanup.py` or `_status.py`? **A:** [auto-pick] `millpy-cleanup.py`, next to `_read_phase`. **Why:** this classification is specific to cleanup's report-vs-skip decision; `_status.py` is the phase writer, not a registry of every caller's round/batch-naming scheme, and no other script currently needs this helper.
- **Q:** (discussion-review r1 GAP) The Testing section proposed exercising the `added_dirs` isdir-skip path via "a two-file directory where one file gains a tag and the whole directory is deleted in the same batch" — is this construction buildable? **A:** [auto-pick] No — fixed. `git diff` only reports a deleted file's original lines as removals, so an added-tag classification (added=1, removed=0) requires the file to still exist at HEAD, meaning its directory necessarily still exists too; a real directory deletion can only ever surface via `removed_dirs`. The `added_dirs` case must instead be tested by physically `shutil.rmtree`-ing a directory that's still present in git history (reusing case 66a's setup) before calling the gate, so the isdir() check fires against the live filesystem rather than git history. **Why:** confirmed against `_go_build_tag_retiering_stuck`/`_parse_go_build_tag_diff`'s actual diff-parsing logic during discussion review round 1 (2026-07-27).
