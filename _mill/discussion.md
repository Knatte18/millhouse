# Discussion: Add first-class Moves/Renames field to plan cards for rename-heavy batches

```yaml
task: Add first-class Moves/Renames field to plan cards for rename-heavy batches
slug: mill-plan-rename-moves
status: discussing
parent: main
```

## Problem

Rename/move-heavy refactors are a recurring class of mill work (GitHub issue
#572, closed; observed on loomyard's `cobra-cli-engine-sweep`, 7 of 8 batches
doing module renames + kernel extractions). On these, implementers
systematically produce noisy full-file-rewrite diffs: they read a card's
`Creates:` / `Deletes:` lists and interpret them as "write the new file from
scratch, then delete the old one." That loses git's rename/history detection,
balloons the diff, and wastes tokens. It was observed twice in a row on one
batch even after a mid-flight correction.

**Root cause — this belongs in the PLAN, not the brief.** The plan card is the
authoritative instruction the implementer reads. The implementer brief
(`implementer-brief.md`) is just an ad-hoc shim for Agent Dispatch — it points
at the batch file and is explicitly NOT the right home for move semantics. Two
concrete gaps in how plans express moves:

1. A move is expressed as `Creates:` + `Deletes:` (the END STATE), never as a
   move. There is no first-class representation of "this file is the same file,
   relocated."
2. mill-plan and mill-review-plan never require a rename-heavy card to state the
   `git mv` mechanic.

So implementers write-from-scratch-then-delete. The fix is to give plan cards a
first-class `Moves:` field of old→new path pairs and to make the `git mv` +
surgical-edit mechanic part of the generated plan (not the brief), then teach
the validator and reviewers about it.

**Why now:** the pattern is frequent enough (whole-module sweeps) that the
manual workaround — hand-writing a `## Rename mechanic` section into each
affected card — is being repeated by operators. The workaround confirms the
plan is the right place; mill-plan should generate it.

## Scope

**In:**

- A new first-class **`Moves:`** card field (old→new path pairs), parsed and
  validated alongside `Context:` / `Edits:` / `Creates:` / `Deletes:`.
- `Moves:` becomes a **required 7th card field** (`Moves: none` when empty),
  consistent with the existing six required fields.
- Card-field representation: **arrow-paired backtick sub-bullets** —
  `` - `old/path` -> `new/path` `` — or the literal `none` inline.
- The **`git mv` + surgical-edit mechanic lives in the generated plan**: a
  canonical `## Rename mechanic` section is rendered into any batch file that
  has at least one non-empty `Moves:` card. `implementer-brief.md` is NOT
  modified to carry the mechanic (the brief is an Agent-Dispatch shim, not part
  of mill proper).
- `_plan_validate.py` new checks: move-source existence, move-target collision,
  move-bullet format, and Moves/Creates/Deletes redundancy; plus feeding move
  endpoints into the existing checks (non-existent-path suppression, all-files-
  touched, parallel-overlap, batch-oversized context estimate).
- `_review_common.py` new parsing helpers (`parse_moves`, `compute_moves_union`)
  and wiring move endpoints into the plan-review and code-review source bulks.
- Plan-review templates (`review-plan-batch.md`, `review-plan-holistic.md`):
  criteria requiring well-formed `Moves:` and the stated git mv mechanic for
  rename-heavy batches; flag full-file-rewrite plans.
- Code-review: a **mechanical git rename-detection check** in the code-review
  backend (`_review_code.py`, per-batch scope only) that emits an **advisory
  NIT** when a planned Move did not land as a git-detected rename, using a
  **tunable low similarity threshold** (so legitimate rename+extraction/seam-
  split work is not false-flagged); plus a matching LLM criterion in
  `review-code-batch.md` that can escalate an actual full rewrite to BLOCKING.
- `mill-plan/SKILL.md`: instruct the planner to express renames as `Moves:`
  (never as `Creates:` + `Deletes:`), to emit the `## Rename mechanic` section,
  and to keep naming surgical edits in `Requirements:`; update the Step 1.5
  validator-fix table with the new checks.
- `_agent_dispatch.language_skills_directive`: include Move endpoints in
  language detection so a `.go -> .go` rename still pulls Go skills.
- Unit tests for all new parsing/validation; update existing plan fixtures to
  add `Moves: none` (required-field ripple); the mechanical rename check is
  designed dependency-injected so it is unit-testable without real git.

**Out:**

- The issue's "optional" item — a standalone heuristic detector that flags
  add+delete of near-identical content as a *likely forgotten* `git mv` outside
  of a planned Move. YAGNI: the planned-Move mechanical check (above) covers the
  practical need; an unplanned-rename heuristic is speculative and noisy.
- Any change to how renames are tracked in git itself (git does not record
  renames — see Technical context; this is by design and we work with it).
- Retroactively rewriting existing plans. Plans are per-task and regenerated;
  only test fixtures need updating.
- Changing `Creates:` / `Deletes:` semantics. They keep their meaning; a rename
  simply must not be double-expressed there (redundancy guard enforces this).

## Decisions

### moves-field-syntax

- Decision: Express each move as an **arrow-paired backtick sub-bullet** under a
  `- **Moves:**` header: `` - `old/path` -> `new/path` ``. Empty is the literal
  `none` inline (`- **Moves:** none`), matching the other fields. The separator
  is ASCII `->` (CLAUDE.md mandates ASCII-only generated output; no `→`).
- Rationale: fits the existing backtick-bullet card grammar; an operator reading
  a card sees moves expressed *as* moves. A dedicated regex handles the
  two-backticks-plus-arrow shape (see technical context).
- Rejected: frontmatter YAML list of `{from,to}` (splits the move out of the
  card body where the rest of the card's intent lives); single-line inline pairs
  (hard to read for multi-move batches).

### moves-required-field

- Decision: `Moves:` is a **required 7th card field**; write `Moves: none` when
  there are no moves. The `card-missing-field` validator check is extended to
  require it. **Field position:** `Moves:` sits **immediately after `Deletes:`**
  (semantic grouping with `Creates:` / `Deletes:`), before `Requirements:` and
  `Commit:`. The `plan-batch.md` template, its example card, and planner output
  all use this fixed order so card layout is consistent.
- Rationale: uniform with the existing six required fields; the validator stays
  simple (no conditional presence). The cost is a one-time fixture update.
- Rejected: optional field present only on rename-heavy cards — inconsistent
  with the other fields and complicates the card-missing-field check.

### mechanic-in-plan-not-brief

- Decision: The `git mv` + surgical-edit **mechanic is authored into the
  generated plan**. The canonical wording lives in the `plan-batch.md` template
  as a `## Rename mechanic` section; mill-plan renders this section into any
  batch file that contains at least one non-empty `Moves:` card. The
  implementer reads it from the batch file (already the authoritative input).
  `implementer-brief.md` is **not** modified to carry the mechanic.
- Rationale: the operator was explicit — the brief is an ad-hoc Agent-Dispatch
  shim and is not part of "real mill"; the rename mechanic MUST be in the plan.
  This also matches issue #572's root-cause analysis verbatim. Keeping the
  wording canonical in the template (rather than planner-improvised per card)
  keeps it consistent while still physically living in the plan files.
- Rejected: generic protocol in the brief (operator vetoed); per-card
  planner-written prose only (inconsistent wording, more planner burden) — the
  canonical-template approach gives consistency AND keeps it in the plan.
- Note: the "what moves" (the `Moves:` pairs) is per-card and authoritative; the
  "how" (the mechanic) is the fixed `## Rename mechanic` section. `Requirements:`
  still names the specific surgical edits (package decl, import retargeting,
  identifier renames, seam splits) using stable identifiers, as today.

### move-endpoints-feed-existing-checks

- Decision: Move endpoints participate in the existing path machinery, treating
  the **source like a Delete** (it disappears) and the **target like a Create**
  (it appears):
  - non-existent-path: a Move **target** is suppressed exactly like a
    `creates_union` member, so a later card editing the moved file's new path
    does not trip "does not exist on disk." A Move **source** must exist on disk
    (it is a real file being relocated) unless an earlier batch creates/moves it
    to that path first.
  - all-files-touched-mismatch: Move **targets** count toward the cards' touched
    set (end state); Move **sources** are excluded (mirrors the existing
    Deletes exclusion, issue #494).
  - parallel-modifies-overlap: both Move **source and target** count as
    "touched" for a batch, so two parallel batches relocating/editing the same
    file are flagged.
  - batch-oversized context estimate: Move **sources** count toward the context
    byte/token estimate (the implementer reads them); Move **targets** are
    excluded (they do not exist yet), mirroring Creates.
- Rationale: a rename is semantically a delete-of-old + create-of-new that
  preserves identity; reusing the established suppression/accounting rules keeps
  the validator coherent and avoids false "non-existent path" errors on
  downstream cards.
- Rejected: treating moves as opaque (would break downstream non-existent-path
  checks and under-count context).

### review-bulk-wiring

- Decision: Surface the relevant move file to each reviewer by adding move
  endpoints to the source bulk:
  - **Plan review** (`_review_plan.py`) bulks the existing `Context: ∪ Edits:`
    plus **Move sources** (they exist pre-implementation, so the reviewer sees
    what is being moved).
  - **Code review** (`_review_code.py`) bulks `Context: ∪ Edits: ∪ Creates:`
    plus **Move targets** (post-implementation they exist; sources are gone).
- Rationale: reviewers must see the file under discussion. The asymmetry mirrors
  the existing "plan reviewer sees existing files; code reviewer sees post-impl
  files" split documented in `plan-batch.md`.

### verification-scope

- Decision (operator delegated this call): build four verification layers,
  defer the speculative one.
  - **Plan-time, deterministic (`_plan_validate.py`):**
    - `move-source-missing` — a Move source does not exist on disk and is not a
      Creates/Moves target of any batch. (Suppressed like the Deletes check.)
    - `move-target-collision` — a Move target already exists on disk, or two
      cards target the same destination, or a target collides with a `Creates:`
      target.
    - `move-format` — a `Moves:` bullet is not exactly `` `src` -> `dst` ``
      (e.g. missing arrow, missing one backtick path, prose alongside).
    - `move-redundant` — a path appears both as a Move endpoint and in
      `Creates:` / `Deletes:` (a rename must be expressed in `Moves:` only).
  - **Plan-review (LLM criteria):** `Moves:` is well-formed; a rename-heavy
    batch states the git mv mechanic; plans that prescribe full-file rewrites of
    relocated files are flagged.
  - **Code-review (mechanical, in `_review_code.py`, per-batch scope ONLY):** for
    each planned Move pair, inspect `git diff --name-status --find-renames=<thr>
    <batch-base>..HEAD` with a **tunable low threshold** (`<thr>` default **30%**;
    surface it as a `pipeline.*` config knob, e.g. `pipeline.rename_detect_pct`).
    If the pair did NOT land as a detected rename (`R…`) — it shows as add +
    delete — emit an **advisory NIT** ("planned rename `<old>` -> `<new>` not
    detected as a git rename at <thr>% similarity; confirm it was done with
    `git mv` + surgical edits, not a full rewrite"). **Never auto-BLOCKING** —
    see the threshold gap below. The NIT is merged into the round's review so it
    flows through the existing receive-review loop. This check runs in **per-batch
    review only**; holistic-scope review has no per-batch base SHA, so the
    mechanical check is skipped there (the LLM criterion still applies).
  - **Code-review (LLM criterion, `review-code-batch.md`):** the judgment layer —
    the reviewer is told the planned moves and may **escalate to BLOCKING** when
    it sees an actual full rewrite of a relocated file (lost structure, mass
    reformat). This is where genuine "write-from-scratch" gets blocked; the
    mechanical NIT only flags candidates.
- Rationale: prevention (plan expresses the move + mechanic) is the primary fix.
  The mechanical check is deliberately **advisory, not deterministic-BLOCKING**,
  because git rename detection is similarity-based and the motivating workload
  (module renames + kernel/seam **extractions**) deliberately drops the moved
  file's surviving content below git's default 50% threshold — a correctly
  executed `git mv` + extraction would otherwise be false-flagged as a rewrite
  and falsely BLOCK the very work this task targets. A tunable low threshold
  (30% default) catches genuine relocations-with-edits; legitimate sub-threshold
  splits surface as a NIT for confirmation rather than a hard block. See
  Technical context for why `git diff -M` is a valid (similarity-based) proxy.
- Rejected: the issue's optional standalone "forgotten git mv" heuristic for
  *unplanned* renames — speculative and out of scope (see Scope/Out).

## Technical context

What mill-plan needs to know to write the plan:

**Card schema + parsing.**
- `plugins/mill/templates/plan-batch.md` documents the card fields and shows the
  example card. Today the required fields are Context, Edits, Creates, Deletes,
  Requirements, Commit. Add `Moves:` (7th) with format docs + an example, and
  add the canonical `## Rename mechanic` section text the template carries.
- `plugins/mill/scripts/_review_common.py`:
  - `_RE_REFS_HEADER` (line ~475) matches `(Context|Edits|Creates|Deletes)`.
    **Do NOT add `Moves` to this regex** — its sub-bullet grammar is a single
    backtick path, but a Move sub-bullet has *two* backtick paths plus `->`.
    Adding Moves here would make `reads-not-backtick-path` (which errors on
    sub-bullets with >1 backtick) reject every Move. Instead add a dedicated
    `_RE_MOVES_HEADER` and a `parse_moves(batch_path) -> list[tuple[str, str]]`
    helper, plus `compute_moves_union(plan_dir) -> tuple[set[str], set[str]]`
    returning `(sources, targets)`.
  - `parse_batch_refs(batch_path, fields=...)` (line ~482) is the shared
    field-token extractor used by plan review, code review, the validator, and
    `_agent_dispatch.language_skills_directive`. It must NOT pick up Move bullets
    (they are not single-path bullets); keep moves on the dedicated parser.
- `plugins/mill/scripts/_plan_validate.py`:
  - `_RE_REFS_HEADER` (line ~54) and the per-field helpers `_parse_edits_only` /
    `_parse_creates_only` / `_parse_deletes_only` follow the same single-path
    grammar — add a parallel `_parse_moves_only` (returns pairs) rather than
    extending the shared regex.
  - `_REQUIRED_CARD_FIELDS` (line ~65) — add `"Moves"`.
  - `run()` (line ~1010) wires checks; add the new move checks and thread
    `moves_union` into `_check_non_existent_path`, `_check_all_files_touched_
    mismatch`, `_check_parallel_modifies_overlap`, `_check_batch_oversized`.
  - The `verify-not-isolated` check (line ~808) keys off Python markers — this
    repo IS a Python project (`plugins/mill/pyproject.toml`), so generated
    `verify:` commands for THIS task's plan must start with `PYTHONPATH= ` and
    use `uv run --project plugins/mill python plugins/mill/unit_tests/...`.
- Review backends consuming the helpers: `_review_plan.py` (lines ~145, ~309,
  ~326, ~405, ~583, ~731), `_review_code.py` (lines ~254, ~256), and
  `_agent_dispatch.py` (line ~138). Each builds a bulk via `parse_batch_refs` +
  `compute_creates_union`/`compute_deletes_union`; the new
  `compute_moves_union` feeds the bulk per the review-bulk-wiring decision.

**Why `git diff -M` is a valid proxy (important nuance).**
Git does **not** store renames. `git mv old new` is exactly equivalent to
`mv old new; git add new; git rm old`. A "rename" is detected at *diff/log time*
purely by content similarity (`-M`). Therefore the distinction the issue cares
about is really *surgical edit vs full rewrite*: a `git mv` + surgical edit keeps
content similar → `git diff -M` reports `R###`; a write-from-scratch reorders/
reformats → similarity drops below threshold → reported as add + delete. So the
mechanical `git diff --name-status -M <base>..HEAD` check IS a sound proxy for
"was this done surgically." Document this in the check's comment so future
readers don't think git tracks renames.

**Mechanical check placement + testability.**
Put the check in `_review_code.py` (the code-review *backend* is ordinary
orchestration Python — it already reads `start_sha` around line ~240 and already
runs git via `bulk_files_with_diff` at line ~165; only the reviewer LLM is
read-only). Structure it so the pure logic (`given a name-status diff string +
planned move pairs + threshold, return NIT findings`) is a separate function
that takes the diff text as an argument; the caller runs
`git -C <worktree> diff --name-status --find-renames=<thr> <base>..HEAD` and
passes the output. This keeps the logic unit-testable without a real git repo
(unit tests are in-memory/tempfile per CLAUDE.md; real git lives in
`integration_tests/`). The check runs in **per-batch scope only** — gate it on
`scope != "holistic"` and on `start_sha` being available; skip silently
otherwise.

**Docstring invariant must be updated (`_review_code.py`).** The module
docstring opens with "v2 code review does NOT look at git diff... The reviewer
never scrapes git for files." That rule is about the **LLM reviewer**, and the
backend already partially contradicts it (`bulk_files_with_diff` at line ~165
diffs against `start_sha`). The plan MUST reword the docstring to scope the "no
git" rule to the LLM reviewer and document the backend's deterministic git usage
(both the existing diff-scoped bulking and the new rename-detection check), so a
future reader is not misled.

**Status of issue #572:** CLOSED. Treat its text as the spec, not a live ticket.

## Constraints

- No `CONSTRAINTS.md` at the hub root (none found during exploration).
- Generated/printed output must be **ASCII only** (CLAUDE.md): use `->` not `→`,
  ` -- ` not em-dash, in any code, template text, or `print()`/`_log()` output.
- Generated markdown uses fenced ` ```yaml ` for metadata, never `---`
  frontmatter (that is reserved for SKILL.md / plugin manifests).
- Unit tests: in-memory/tempfile fixtures, **no real git or LLM** — run via
  `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`.
  Real-git behavior (the rename-detection check end to end) belongs in
  `integration_tests/` if covered there at all; the unit layer tests the pure
  diff-parsing logic via injected diff text.
- Operational mill calls use the cache (`${CLAUDE_PLUGIN_ROOT}`); only tests run
  from the repo tree. (Not directly relevant to code edits, but relevant if the
  plan adds any operational invocation.)
- The `Moves:` required-field change is a breaking ripple for **every existing
  plan fixture** in the unit tests — they must each gain `Moves: none` on every
  card or `card-missing-field` will fire. This is expected; budget a fixture-
  update card.

## Testing

Per-area approach (all unit tests under `plugins/mill/unit_tests/`, `test-*.py`,
run through `run-all.py`; TDD-friendly because the logic is pure):

- **`_review_common` parsing** (`test-review-common.py`, plus new cases):
  - `parse_moves` — single pair, multiple pairs, `none`, mixed with other
    fields, malformed bullets (should be parsed leniently / surfaced by the
    validator, not crash).
  - `compute_moves_union` — sources/targets aggregated across batches; empty
    plan dir; `none` filtered.
  - Confirm `parse_batch_refs` does NOT absorb Move bullets (regression guard).
- **Validator** (`test-plan-validate.py`, `test-millpy-validate-plan.py`):
  - `card-missing-field` now fires when `Moves:` is absent (and passes with
    `Moves: none`).
  - `move-source-missing` — source absent on disk and not a Creates/Moves
    target → error; suppressed when an earlier batch creates/moves it.
  - `move-target-collision` — target exists on disk; two cards same target;
    target collides with a `Creates:` target.
  - `move-format` — missing arrow, single backtick, prose alongside.
  - `move-redundant` — endpoint also in Creates/Deletes.
  - Endpoint feeding: a downstream card editing a Move target does NOT raise
    `non-existent-path`; Move target appears in all-files-touched reconciliation;
    parallel batches touching the same Move endpoint raise
    `parallel-modifies-overlap`; Move source bytes count toward batch-oversized.
- **Review bulks** (`test-review-common.py` / `test-review-plan-flow.py` /
  `test-review-code-flow.py`): plan-review bulk includes Move sources; code-
  review bulk includes Move targets.
- **Mechanical rename check** (new `test-*.py`): the pure function, fed a crafted
  `git diff --name-status -M` string + planned pairs, returns a BLOCKING finding
  for an add+delete pair and no finding for an `R###` pair. No real git.
- **Language detection** (`test-language-skills-directive.py`): a `.go -> .go`
  Move pulls the Go skills even with empty Edits/Creates.
- **Fixture sweep:** update every existing plan fixture across the test files to
  add `Moves: none` so the new required-field check does not break unrelated
  tests. (Audit: `test-plan-validate.py`, `test-millpy-validate-plan.py`,
  `test-review-common.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`
  all contain batch-card fixtures.)

The plan should also confirm template/SKILL/markdown text edits don't need a
runnable test beyond the existing template-rendering tests (if any); a docs-only
batch may set `verify: null` with a stated justification.

## Q&A log

- **Q:** How should `Moves:` represent old→new pairs? **A:** Arrow-paired
  backtick sub-bullets (`` - `old` -> `new` ``); `none` inline when empty.
- **Q:** Required 7th field or optional? **A:** Required, with `Moves: none`
  default — consistent with the existing six fields.
- **Q:** Where does the `git mv` + surgical-edit mechanic live? **A:** In the
  PLAN, never the brief. The brief is an ad-hoc Agent-Dispatch shim, not part of
  real mill. Canonical `## Rename mechanic` wording lives in `plan-batch.md` and
  is rendered into batch files that contain moves.
- **Q:** Which automated verifications to build? **A:** Operator delegated the
  call. Decided: validator move-sanity + redundancy + format checks (plan-time),
  plan-review criteria, and a mechanical `git diff -M` rename-detection check in
  the code-review backend (BLOCKING on add+delete) plus a matching LLM criterion.
  Deferred the issue's optional unplanned-rename heuristic (YAGNI).
- **Q:** Does git actually track renames so the check is reliable? **A:** No —
  git detects renames by content similarity at diff time; the check is therefore
  a valid proxy for surgical-edit-vs-rewrite, which is exactly the failure mode.

Discussion-review round 1 gap/note resolutions (auto-resolved with recommended
fixes per operator instruction):

- **Q (GAP):** Does the default `-M` (50%) similarity false-BLOCK the motivating
  rename+extraction workload? **A:** Yes — extractions/seam-splits legitimately
  drop similarity below 50%. Resolved: the mechanical check is **advisory NIT,
  never auto-BLOCKING**, uses a **tunable low threshold (30% default, config
  knob)**, and the LLM reviewer is the layer that escalates an actual full
  rewrite to BLOCKING.
- **Q (NOTE):** The `_review_code.py` "does NOT look at git diff" docstring
  contradicts the new check (and existing `bulk_files_with_diff`). **A:** The
  plan must reword the docstring to scope the "no git" rule to the LLM reviewer
  and document the backend's deterministic git usage.
- **Q (NOTE):** Does the mechanical check run in holistic-scope review? **A:** No
  — per-batch scope only (no per-batch base SHA in holistic); gate on
  `scope != "holistic"` and on `start_sha` availability.
- **Q (NOTE):** Where does `Moves:` sit in the card? **A:** Immediately after
  `Deletes:`, before `Requirements:` / `Commit:` — fixed template order.
```
