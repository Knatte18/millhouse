# Discussion: 50 (A) — Bug-fix batch 5 (post-44 triage)

```yaml
task: 50 (A) — Bug-fix batch 5 (post-44 triage)
slug: mill-misc-fixes-5
status: discussing
parent: main
```

## Problem

Triage of the 2026-05-11 bug intake — issues identified after task 44 had already
locked its scope, plus a handful of follow-ups discovered while spawning 44 —
collects nine concrete defects that each block or degrade specific code paths in
mill-start, mill-plan, mill-go, and the review CLIs. None individually justify a
dedicated task; together they form Bug-fix batch 5.

The bugs span four classes:

1. **Config-schema migration tail** (#237): the task-34 rename from `review.*` →
   `roles.*` left stale doc strings and an auto-generated CLI help dump.
2. **Auto-mode plumbing gaps** (#238, #247, #249): mill-start and mill-plan
   auto-mode paths cannot reliably record `blocked_reason`, do not handle
   APPROVE-with-NIT review verdicts, and run Handoff with `approved: false` when
   the configured reviewer is null.
3. **Path / quoting / encoding correctness** (#239, #248, #251, #254): SKILL.md
   path typo (`<worktree_root>/reviews/` vs `task/reviews/`), `append_phase`
   writing unquoted timestamps while `render_initial` writes quoted ones,
   Windows cp1252 UnicodeEncodeError from `→` in test prints, mill-merge-in
   calling `sync_pull` without the now-required `slug=` kwarg.
4. **Implementer JSON-report robustness** (#243): long Sonnet sessions
   occasionally truncate their final stdout, losing the structured JSON report
   that `_implementer_common._forward_output` requires; mill-go then escalates a
   completed batch as `stuck_type: logic`.

#237 was partially fixed in commit `560bed8` (mill-start / mill-plan SKILL.md
files migrated to `roles.*`). What remains is documentation tail. #246 from the
proposal was the same SKILL.md change and is already complete; this task only
re-verifies it.

**Why now:** every auto-mode path through mill-start / mill-plan currently
crashes on the documented escape route (#238 cascades into an unreviewable
`status.md` edit attempt), and #243 keeps re-firing as user-visible "stuck"
reports for batches that actually succeeded. Both undermine the autonomous-mode
guarantees the v2 rewrite is built around.

## Scope

**In:**

- **#237 (doc tail):** Update `_review_plan.py` line 280 docstring from
  `cfg.review.plan.holistic` to `cfg["roles"]["plan-review"]["holistic"]`.
  Regenerate `plugins/mill/SCRIPTS.md` so `--max-rounds` help strings reflect
  the new `roles.*` keys.
- **#238:** Introduce `_status.set_blocked(status_path, reason, *, timestamp)`
  in `plugins/mill/scripts/_status.py`. It rewrites `phase: blocked`, appends a
  `blocked  <timestamp>` timeline row, and writes a `blocked_reason: <reason>`
  key inside the top yaml block — adding the key when absent. Replace the four
  call sites currently using
  `_status.update_field(status_path, "blocked_reason", …)` (mill-start auto
  block-on-gaps; mill-plan non-progress block in autonomous mode; mill-plan
  max-rounds block in autonomous mode; any other site grep finds) with
  `_status.set_blocked(...)`. Add `read_status` coverage in the existing
  `test-status.py` for the new helper.
- **#239:** Edit `plugins/mill/skills/mill-start/SKILL.md` line 111 — replace
  `<worktree_root>/reviews/` with `task/reviews/`. Code unaffected (reviewer
  already writes there via `paths.reviews_dir`).
- **#246 (verify-only):** Confirm `plugins/mill/skills/mill-start/SKILL.md`
  contains zero references to `review.discussion.*`. No edit expected.
- **#247:** Split mill-plan SKILL.md step 4a into:
  - 4a — `APPROVE` with zero `[NIT]` findings → set `approved: true`,
    append `plan-review-r<N>`, commit, push, break loop → Handoff.
  - 4b — `APPROVE` with one or more `[NIT]` findings → load
    `mill-receiving-review`, apply each NIT (or push back per the decision
    tree), write `task/reviews/<ts>-plan-fix-r<N>.md` with `## Fixed` /
    `## Pushed Back` sections, append `plan-fix-r<N>` to the timeline, set
    `approved: true`, single commit covering plan + reviews + status, break →
    Handoff. Round counter NOT advanced (same convention mill-start uses).
  - Renumber the existing 4b (`REQUEST_CHANGES + blocking_count == 0`) and 4c
    accordingly. The existing semantics carry forward — only the substep label
    shifts.
- **#248:** In `_status.append_phase`, change `new_row = f"{phase}  {timestamp}\n"`
  to `new_row = f"{phase}  {quote_scalar(timestamp)}\n"`. Existing `status.md`
  files in active worktrees mix quoted (from `render_initial`) and unquoted
  rows; do NOT back-rewrite history, but add a unit test asserting newly
  appended rows are quoted.
- **#249:** Add a skip block to mill-plan SKILL.md (mirroring mill-start
  line 98) at the head of Phase: Plan Review:
  > Two skip conditions: `roles.plan-review.holistic.rounds == 0` OR
  > `roles.plan-review.holistic.reviewer is None`. When either holds: set
  > overview frontmatter `approved: true` via direct Edit, commit
  > (`mill-plan: skip plan review (reviewer null or rounds 0) for {slug}`),
  > push, proceed straight to Handoff.
- **#251:** In `plugins/mill/unit_tests/test-review-common.py` and any other
  unit-test print() lines that contain U+2192 `→`, replace with ASCII `->`.
  Add a grep-style regression guard in `run-all.py` (or a tiny dedicated test)
  that asserts no `→` characters exist in any `test-*.py` file's source —
  prevents future regressions.
- **#254:** In `plugins/mill/skills/mill-merge-in/SKILL.md` line 12, change
  `_wiki.sync_pull(<WIKI_PATH>)` to
  `_wiki.sync_pull(<WIKI_PATH>, slug="mill-merge-in")`.
- **#243:** Two complementary changes:
  - **Brief hardening**: extend `plugins/mill/templates/implementer-brief.md`
    `## Report` section with an explicit "Long-session reminder" — for sessions
    that span many tool calls, the implementer is instructed to emit the JSON
    report once it has finished implementation and BEFORE running any
    open-ended `Bash` exploration that might produce long output. Already-present
    "last line of output MUST be JSON" stays, but is reinforced with a
    second-paragraph: "if you have produced a lot of output earlier in this
    session, your final JSON line may be truncated by the orchestrator. Re-emit
    the JSON on its own line at the start of your final assistant turn before
    any further tool calls."
  - **Fallback in `_implementer_common._forward_output`**: when the regex finds
    no JSON object, before emitting the `stuck_type: logic` sentinel, check
    *new* dirt since batch start using the existing snapshot:
    `compute_new_dirt(project_root, snapshot_path)` (from `_cleanliness.py`)
    returns `[]` iff the implementer left no uncommitted changes beyond what
    was already present at batch start. AND `git rev-parse HEAD` differs from
    the brief's `start_sha` (proving the implementer committed work). If both
    hold: emit
    `{"status":"success","commit_sha":"<HEAD>","session_id":"<unknown>","inferred":true}`
    instead. Otherwise emit the existing stuck-logic sentinel.
    The `snapshot_path` is the same path mill-go's batch-start commit wrote
    via `capture_snapshot` — `millpy-implement.py` already resolves it for
    the initial-dispatch path; pass it through to `_forward_output` as a new
    keyword argument (`snapshot_path: Path | None = None`). When
    `snapshot_path` is None or missing on disk, the fallback degrades to the
    existing stuck-logic sentinel (no inference attempted) — matches the
    existing `compute_new_dirt` "treat pre-batch as empty + stderr warning"
    behaviour, but for `_forward_output` we refuse to infer success without a
    real baseline.

**Out:**

- The brief change is a wording / placement tweak — it does NOT add any new
  template tokens, and does NOT change `_render.render`.
- Back-rewriting existing `status.md` timeline rows to quote timestamps is
  out of scope — the inconsistency stays until the next mutation.
- `_implementer_common.py`'s broader regex robustness (e.g. matching nested
  JSON) is out of scope; the fallback path handles the truncation failure mode.
  The current `\{[^{}]*"status"[^{}]*\}` regex stays — implementer JSON shape is
  flat by template contract.
- Renaming `set_blocked` to anything broader; this helper is purpose-built for
  the blocked-reason flow. Callers that want generic `update_field` semantics
  still use `update_field`.
- The "stale wts/-katalog audit" bonus strand from the proposal — it's covered
  by task 46's teardown-split and not actionable here.
- No changes to `wiki/config.yaml` or `wiki-config.yaml` template (no schema
  changes).

## Decisions

### D1: `_status.set_blocked` helper (over template field or update_field flag)

- **Decision:** Add a new helper `_status.set_blocked(status_path, reason, *, timestamp)`
  rather than (a) seeding `blocked_reason: null` in the status template or
  (b) loosening `update_field` with `add_if_missing=True`.
- **Signature:** `set_blocked(status_path: Path, reason: str, *, timestamp: str) -> None`.
  Mutations in order:
  1. Rewrite `phase: blocked` in the top yaml block (same logic as
     `append_phase`).
  2. Insert `blocked_reason: <quoted reason>` immediately after the existing
     `phase:` row if absent; otherwise rewrite the existing row.
  3. Append `blocked  <quoted timestamp>` to the `## Timeline` text block.
  All three mutations are written in one `write_text` call (consistent with
  `append_phase`).
- **Rationale:** Templates should reflect the *initial* shape of the file;
  `blocked_reason` is conditional state that only ~5 % of tasks ever set.
  Loosening `update_field` would silently mask typos in the seven other call
  sites that rely on strict-key validation (the integration tests for
  `update_field` explicitly cover this guard). A targeted helper keeps both
  contracts intact.
- **Rejected:**
  - (a) Adding `blocked_reason: null` to `status-discussing.md` —
    "templates own data they don't always populate" is the same anti-pattern
    that prompted the v1→v2 rewrite of status handling.
  - (b) `update_field(..., add_if_missing=True)` — generic but hides genuine
    typo bugs; would force every caller that wants strict semantics to pass
    `add_if_missing=False` defensively.

### D2: Quote timestamps in `append_phase` (canonical-form quoted)

- **Decision:** `append_phase` runs the timestamp through `_yaml_writer.quote_scalar`
  before appending to the timeline. The canonical form for *all*
  timeline-row timestamps is quoted (single-quoted, matching
  `render_initial`).
- **Rationale:** `render_initial` already writes quoted timestamps. Two writers
  producing the same logical column with different shapes is a per-file
  inconsistency that diff tooling and the eventual `read_full` consumer either
  has to tolerate or normalise. Quoting is YAML-safe for ISO-8601 strings, and
  the cost is one extra single-quote pair.
- **Rejected:** Stripping quotes from `render_initial` — would require a
  cross-cutting edit to every existing `status.md` to maintain the round-trip
  property; quoting is the cheaper convergence path.

### D3: Skip-review path mirrors mill-start exactly (#249)

- **Decision:** When either `roles.plan-review.holistic.reviewer is None` OR
  `roles.plan-review.holistic.rounds == 0`, mill-plan skips the review loop,
  sets overview frontmatter `approved: true` via direct Edit, commits with
  message `mill-plan: skip plan review (reviewer null or rounds 0) for {slug}`,
  pushes, and proceeds to Handoff. The skip block is added at the top of
  Phase: Plan Review, identical in shape to mill-start SKILL.md line 98.
- **Rationale:** mill-start already documents and enforces this pattern.
  Without it, callers who disable plan review (e.g. cheap-iteration profiles)
  end up with `approved: false` plans that mill-go then refuses to execute.
  This is the same trust-the-config behaviour as mill-start; consistency is
  the design.
- **Rejected:**
  - Run at least one round even when reviewer is null — wastes the
    operator's explicit opt-out.
  - Set `approved: true` unconditionally at Handoff — breaks the audit trail.
    The skip-block records the skip in commit history; an unconditional
    Handoff flip would hide it.

### D4: mill-plan 4a/4b split (#247) mirrors mill-start, not the existing 4c

- **Decision:** Step 4a handles APPROVE-no-NITs; new step 4b handles
  APPROVE-with-NITs (apply per mill-receiving-review, write fixer report,
  break loop). The existing 4b (`REQUEST_CHANGES + blocking_count == 0`) and
  4c (`REQUEST_CHANGES + blocking_count > 0`) renumber to 4c and 4d
  respectively. Step 4.5 (ERROR-only-aggregate retry) stays at its numeric
  position.
- **Rationale:** The reviewer schema permits `APPROVE` with `[NIT]` findings
  (`review-output.schema.md` line 120). The current 4a treats every APPROVE as
  no-NITs; the assistant skips the fixer-report write and the audit trail
  loses the NIT history. Mirroring mill-start exactly keeps cognitive load
  low for skill maintainers.
- **Rejected:** Keep current 4a and rely on 4c (REQUEST_CHANGES + 0 blocking)
  for NIT-only rounds — only fires when the reviewer chose `REQUEST_CHANGES`
  for a NIT-only round, which conflicts with the schema's APPROVE-with-NITs
  contract.

### D5: #243 dual fix (template + fallback inference)

- **Decision:** Both the implementer-brief reinforcement AND the
  `_forward_output` fallback ship together. The fallback path is guarded by
  *three* conditions: (1) `_cleanliness.compute_new_dirt(project_root,
  snapshot_path)` returns `[]` (no new uncommitted changes since batch
  start), (2) `git rev-parse HEAD` differs from a known `start_sha`, AND
  (3) `snapshot_path` exists on disk (we refuse to infer success without a
  real baseline). The `start_sha` source is mill-go's existing
  `status.md` `batches[].start_sha` — `millpy-implement.py` already has the
  batch name in argv; it reads `start_sha` and `snapshot_path` via
  `_status.read_batches(status_path)` and passes both to `_forward_output`
  as new keyword arguments (`start_sha: str | None`, `snapshot_path: Path |
  None`). If either argument is None or the snapshot file is missing, the
  fallback degrades to the existing stuck-logic sentinel — no false
  positives on a fresh batch with no prior commit or no snapshot.
- **Rationale:** Template alone leaves already-stuck runs in their broken
  state and only helps future sessions. Fallback alone weakens the brief
  contract — a brief that doesn't insist on JSON tells the implementer the
  JSON is optional. Together they tighten the contract AND recover the
  already-degraded case. The guard (clean + new commits since start_sha)
  rules out the *real* `stuck_type: logic` cases where the implementer
  produced no output AND made no commits.
- **Rejected:**
  - Brief-only — does not retro-help in-flight runs.
  - Fallback-only — fails closed when the brief itself drifts further over
    time.
  - Skip — keeps a high-rate user-visible false-positive ("stuck logic" on
    successful batches) in place indefinitely.

### D6: Test regression guards (#251 + #248)

- **Decision:** Two small additions to the existing unit-test suite:
  - `test-status.py`: add a case asserting that a row appended via
    `append_phase` has the timestamp wrapped in single quotes
    (`re.search(r"^\w+\s+'[^']+'$", row)`).
  - `run-all.py` (or `test-encoding.py` if a clearer home is preferred):
    scan every `plugins/mill/unit_tests/test-*.py` file for the literal
    character `→` (`→`). Any hit fails the suite with a one-line
    message naming the file. Cost: one `Path.glob` + one `in` check per
    file.
- **Rationale:** Both bugs are simple to reintroduce by reflex. A grep-style
  guard is cheap and catches regressions at PR time rather than during
  Windows-CI runs.
- **Rejected:** Forcing UTF-8 stdout in `run-all.py` — masks the bug instead
  of fixing it, and the broader convention across mill scripts is ASCII for
  cross-platform.

## Technical context

### Source-of-truth files

- **`plugins/mill/scripts/_status.py`** — owns `update_field`, `append_phase`,
  the batch helpers, and the top-yaml-block / timeline-block readers. The new
  `set_blocked` helper lives here. The `_BATCH_ALLOWED_KEYS` set already
  includes `blocked_reason` (batch-level); the top-yaml-block key is new and
  needs no allowlist (yaml-block writes are not strict-set-validated).
- **`plugins/mill/scripts/_implementer_common.py`** — owns
  `_forward_output`. The fallback path lives here. Calls
  `_subprocess_util.run` for `git rev-parse`; will additionally call
  `_cleanliness.compute_new_dirt` and `_status.read_batches`.
- **`plugins/mill/scripts/_cleanliness.py`** — already exposes
  `capture_snapshot(worktree, snapshot_path)` and
  `compute_new_dirt(worktree, snapshot_path) -> list[str]`. No new function
  added in this task. The fallback uses `compute_new_dirt(...) == []` as
  the "no new dirt since batch start" predicate. `compute_new_dirt`'s
  existing behaviour when the snapshot file is missing (warn + treat pre-batch
  as empty) does NOT carry over — `_forward_output` refuses to infer success
  when `snapshot_path` does not exist on disk and falls back to the
  stuck-logic sentinel instead.
- **`plugins/mill/scripts/_review_plan.py`** — docstring at line 280 mentions
  `cfg.review.plan.holistic`. Edit-only; no logic change.
- **`plugins/mill/SCRIPTS.md`** — auto-generated. Look at the top of the file
  for the regen command; if absent, regenerate by running each `millpy-*.py`
  with `--help` and pasting the output (or, if a generator script exists,
  invoke it).
- **`plugins/mill/skills/mill-start/SKILL.md`** — line 111 path typo (#239).
  Already migrated for #237 / #246; verify by grep.
- **`plugins/mill/skills/mill-plan/SKILL.md`** — needs the new 4a/4b split
  (#247) AND the skip-review block at top of Phase: Plan Review (#249).
- **`plugins/mill/skills/mill-merge-in/SKILL.md`** — line 12 missing
  `slug=` kwarg (#254).
- **`plugins/mill/templates/implementer-brief.md`** — append long-session
  reminder paragraph (#243 brief-half).
- **`plugins/mill/unit_tests/test-review-common.py`** — replace `→` with `->`
  in print() strings (#251). Grep for `→` to enumerate hits.
- **`plugins/mill/unit_tests/test-status.py`** — add quoted-timestamp guard
  (#248 regression test) and `set_blocked` coverage (#238 happy path +
  add-key-if-missing path).

### Shared helpers already in place

- `_yaml_writer.quote_scalar` — public API used by both `append_phase` and
  the new `set_blocked` helper.
- `_status._split_fences` — module-private; the new helper reuses it via
  call. Mark it explicit if pylint complains about private access; it's
  already used cross-function inside `_status.py`.
- `_subprocess_util.run` — public CompletedProcess wrapper.
- `_cleanliness.compute_new_dirt` — public; returns the line-set diff of
  current `git status --porcelain` against the per-batch snapshot.
- `_status.read_batches` — public; needed by `_forward_output` to look up
  `start_sha` for the current batch.

### Things that look fragile but aren't

- `_status.update_field`'s strict-key behaviour stays — many callers
  (`plan:`, `branch:`) rely on the typo-protection it gives them. The new
  `set_blocked` is purpose-built; that's the only key whose semantics
  require add-if-missing.
- The `_review_plan.py` docstring is the only stale `cfg.review.*` reference
  in source files (everything else is in argparse `help=` strings that
  were already migrated). Grep confirms.

## Constraints

No `CONSTRAINTS.md` at the worktree root (`_constraints.read_if_exists()`
returns empty). Repo-level constraints from CLAUDE.md apply unchanged:

- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths** — no edit touches
  this rule; SKILL.md examples in this batch all stay parameterised.
- **Working state in `task/` on the task branch** — every commit in this
  task targets `task/...` or `plugins/...`. No wiki mutations.
- **Wiki access via helpers, never `cd`** — none of the bug fixes require
  wiki I/O.
- **Junctions are IDE convenience** — no path resolves through `.wiki` /
  `.active`. All resolution stays in `_paths.py`.

## Testing

### Per-file approach

- **`_status.py` (new `set_blocked`)** — add three cases to
  `test-status.py`:
  1. Happy path: call on a fresh `render_initial` output; assert
     `read_status()["blocked_reason"] == "<reason>"`, `phase == "blocked"`,
     and the timeline row is appended with quoted timestamp.
  2. Add-key-if-missing: same fixture, no pre-existing `blocked_reason:`
     row; assert the new key is inserted right after `phase:`.
  3. Rewrite existing: pre-seed the yaml block with a `blocked_reason: foo`
     row, call `set_blocked(..., "bar", ...)`; assert the row is rewritten
     in place, no duplication.
- **`_status.append_phase` quoting (#248)** — add one assertion: append a
  phase, read the resulting file's last timeline row, regex-match
  `^\w+\s+'[^']+'$`.
- **`_implementer_common._forward_output` fallback (#243)** — four cases in
  `test-implementer-common.py` (file may need creating; check first):
  1. Snapshot file exists + `compute_new_dirt == []` + new commits since
     `start_sha` + no JSON in stdout → emits success-inferred JSON with
     `"inferred": true`.
  2. Snapshot file exists + `compute_new_dirt == []` + zero new commits
     since `start_sha` + no JSON in stdout → emits the existing
     stuck-logic sentinel.
  3. Snapshot file exists + `compute_new_dirt` returns non-empty (dirty) +
     new commits since `start_sha` + no JSON in stdout → emits the
     existing stuck-logic sentinel.
  4. Snapshot file missing (or `snapshot_path is None`) + everything else
     fine → emits the existing stuck-logic sentinel (no inference
     attempted).
  Use `tempfile.TemporaryDirectory` + `git init` for the fixture, same
  pattern as `test-review-common.py`. Use `capture_snapshot` to seed the
  baseline file in each case.
- **Encoding guard (#251)** — add `test-no-unicode-arrow.py` (or a function
  inside `run-all.py`) that scans every `test-*.py` for `→`. Hit →
  print the file path and exit non-zero.
- **SKILL.md path / kwarg fixes (#239, #254, #246 verify, #247, #249)** —
  no executable test; covered by the existing `test-skill-anti-patterns.py`
  if it picks up these patterns, otherwise reviewer-eyes-on-diff.
- **SCRIPTS.md regen (#237 tail)** — no test; reviewer verifies the regen
  output matches current help strings.

### TDD candidates

- **`set_blocked`** — strong TDD candidate: small surface, three
  enumerable cases, no I/O beyond the temp file. Write the three test
  cases first, watch them fail, implement.
- **`_forward_output` fallback** — TDD candidate, but the fixture cost is
  higher (needs `git init` + commit). Write the three cases first
  anyway; the fixture pays off across the run.
- **`append_phase` quoting regression** — single-assertion test; write
  before the one-line fix.

### Scenarios that must be covered

- A task whose configured plan review is disabled (`reviewer: null`) flows
  cleanly from mill-plan to mill-go without a manual `approved: true` flip.
- A task whose configured discussion review hits max-rounds in auto mode
  blocks cleanly with `phase: blocked`, `blocked_reason: <reason>`, and a
  timeline row — and is restorable with one `set_blocked` call once the
  operator resolves whatever's outstanding.
- An implementer that ran 728s+, produced N commits, and emitted only
  truncated output is recovered as success-inferred rather than escalated
  as stuck.
- A Windows operator running `python plugins/mill/unit_tests/run-all.py`
  in PowerShell 5 (cp1252 default) sees the full test suite green —
  no UnicodeEncodeError anywhere in print().

## Q&A log

- **Q:** Bundle all 9 bug strands in this task, or split? **A:** [auto-pick]
  All 9 strands (Recommended). **Why:** Each strand is small (~1–60 lines);
  splitting would multiply task-spawn overhead with no isolation benefit.
- **Q:** #237 doc tail — update both `_review_plan.py:280` docstring and
  `SCRIPTS.md`, or skip the autogen? **A:** [auto-pick] Update both
  (Recommended). **Why:** Stale doc is a confusion vector when grepping; the
  regen is cheap.
- **Q:** #238 — `_status.set_blocked` helper vs template default vs
  `update_field` flag? **A:** [auto-pick] New helper `_status.set_blocked`
  (Recommended). **Why:** Proposal recommendation (c); preserves
  `update_field` strict-key guarantee everywhere else; templates stay
  data-shape-only.
- **Q:** #248 — quote timestamps in `append_phase` or strip quotes from
  `render_initial`? **A:** [auto-pick] Quote in `append_phase`
  (Recommended). **Why:** Cheaper convergence; existing files don't need
  back-rewriting.
- **Q:** #251 — replace `→` with `->`, or force UTF-8 stdout? **A:**
  [auto-pick] Replace with `->` (Recommended). **Why:** Cross-platform-safe;
  matches the ASCII convention used elsewhere in mill scripts.
- **Q:** #247 — split mill-plan 4a (APPROVE+NIT split) or rely on existing
  paths? **A:** [auto-pick] Split 4a/4b mirroring mill-start (Recommended).
  **Why:** The reviewer schema explicitly permits APPROVE with NIT findings;
  current 4a treats them as no-fix.
- **Q:** #249 — add explicit skip-review block to mill-plan, or accept
  `approved: false` Handoff? **A:** [auto-pick] Add explicit skip block
  mirroring mill-start (Recommended). **Why:** mill-plan and mill-start
  should behave identically on the skip-review opt-out; an `approved:
  false` Handoff is downstream-incompatible with mill-go's gate.
- **Q:** #243 — implementer-brief hardening, `_forward_output` fallback,
  or both? **A:** [auto-pick] Both (Recommended). **Why:** Brief tightens
  the contract for future sessions; fallback recovers the already-in-flight
  case. Either alone leaves half the regression class open.
- **Q:** Bundle #239 / #246 / #254 / #237-tail as one docs batch in the
  plan? **A:** [auto-pick] One docs batch (Recommended). **Why:** Single
  reviewer pass on doc-only diffs; minimal cross-batch noise.
