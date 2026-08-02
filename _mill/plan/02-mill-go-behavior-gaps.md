# Batch: mill-go-behavior-gaps

```yaml
task: Self-discovered mill-go/mill-plan skill-doc and behavior gaps
batch: mill-go-behavior-gaps
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py
depends-on: []
```

## Batch Scope

Fixes two independent behavior gaps in `plugins/mill/skills/mill-go/SKILL.md` (closes #757 and #758), plus the test coverage #757 calls for in `plugins/mill/unit_tests/test-phase-wait.py`. Both gaps live in the same file — the Entry step 5 phase-gate table doesn't recognize batch-scoped `phase:` values as resumable (#757), and the `verify`/`logic` stuck-escalation self-resolve step only conditionally records its failure reason before re-firing (#758) — so they are grouped into one batch to avoid a same-file `parallel-modifies-overlap` finding between two otherwise-independent batches. Card 3 (#758) touches a different section of the file than Cards 1-2 (#757), so there is no overlap risk within the batch itself.

## Cards

### Card 2: Widen the Entry step 5 phase-gate table to recognize batch-scoped phase values

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In the `## Entry` section's Entry step 5 phase-gate table (the markdown table whose rows include `planned`, `implementing` / `reviewing` / `fixing`, `blocked`, `discussed` / `discussing` / `planning`, `done`, `any other`), replace the row whose left cell reads `implementing` / `reviewing` / `fixing` (three separate backtick-wrapped words) and whose right cell reads "resume (see *Resume*)" so that:

  - the left cell instead reads: `implementing` / `reviewing` / `fixing`, or matching the widened batch-scoped set (see "### Mid-execution phase-gate widening" below)
  - the right cell instead reads: resume or routed continuation — see subsection

  Immediately after the table (before the existing `### Entry-gate wait for upstream mill-plan` subsection), insert a new subsection:

  `````
  ### Mid-execution phase-gate widening

  Whenever the phase-table lookup above lands on the widened
  `implementing`/`reviewing`/`fixing` row, compute the match to determine
  which of the seven branches fired:

  ```python
  matched = _phase_wait.matches_wait_trigger(
      phase,
      {"implementing", "reviewing", "fixing", "self-resolved-verify-logic", "holistic-approved"},
      [r"^approved-.*$", r"^reviewing-.*-r\d+$", r"^fixing-.*-r\d+$", r"^holistic-reviewing$"],
  )
  ```

  `matched` is always `True` here — the table row above is defined by this
  same predicate, so this call only distinguishes which branch fired. Route
  on the current `phase` value:

  - `implementing` / `reviewing` / `fixing` (bare, unsuffixed) — route to
    `## Resume`, unchanged from today.
  - `reviewing-{batch_name}-rN` / `fixing-{batch_name}-rN` — route to
    `## Resume`. That batch's `state` in `## Batches` genuinely is
    `reviewing`/`fixing`, so Resume's step 1 (locate the entry whose
    `state` is non-terminal: `running`, `reviewing`, or `fixing`) matches
    it unchanged.
  - `approved-{batch_name}` — fires *between* batches: the just-finished
    batch is `state: approved`, every other batch is either already
    `approved` or still `pending`, so no batch entry is
    `running`/`reviewing`/`fixing` and `## Resume`'s step 1 has nothing to
    match. Route instead to `## Execute — sequential loop`, continuing
    from the next `pending` batch in `order` — the same continuation the
    normal in-flow path already takes after a batch approves. **Edge
    case:** if the just-approved batch was the last one in `order` (zero
    `pending` batches remain), route to `## Holistic code review` instead,
    mirroring the normal in-flow transition from the end of the Execute
    loop into that section.
  - `holistic-reviewing` — fires *after all* batches are `approved`,
    entirely outside the per-batch `## Batches` state machine. Route
    directly to `## Holistic code review`; its own step 1 crash-recovery
    scan already handles resuming a specific round. Do not route through
    `## Resume` at all.
  - `self-resolved-verify-logic` — this literal phase string is appended at two call sites with identical text: the per-batch Stuck escalation section's verify/logic branch, and the Holistic code review section's own verify/logic branch. So `phase` alone cannot disambiguate which occurrence fired. Read `_status.read_batches(status_path)`: if any entry's `state` is `running`, `reviewing`, or `fixing`, this is the per-batch occurrence — route to `## Resume` (the self-resolve step only edits plan/batch files and records an audit-trail phase; it never changes `state`, so Resume's step 1 still finds the batch). If every entry's `state` is `approved`, this is the holistic occurrence (holistic self-resolve only happens after every batch is already approved) — route directly to `## Holistic code review`, mirroring the `holistic-reviewing` row's routing.
  - `holistic-approved` — fires immediately before "Proceed to Handoff", after all holistic-review/NIT-fix work is already complete. Route directly to `## Handoff` — re-entering Handoff is idempotent (flip Home.md, invoke mill-finalize, invoke mill-self-report), whereas
    routing to `## Resume` would find no non-terminal batch to act on.
  `````

  (The 5-backtick fence markers above are literal delimiters used only to safely nest the inner fenced ` ```python ` block inside this Requirements field — the inserted subsection itself is plain markdown containing one ordinary ` ```python ` fence, exactly as shown between the two 5-backtick lines.)

- **Commit:** `docs(mill-go): widen Entry step 5 phase gate for batch-scoped phase values (#757)`

### Card 3: Extend test-phase-wait.py with cases for the six widened phase-gate values

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-phase-wait.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `plugins/mill/unit_tests/test-phase-wait.py`, add a new numbered case block ("Case 14") immediately after the existing "Case 13" block (the CRLF end-to-end `with tempfile.TemporaryDirectory()` block) and before the line `print("All _phase_wait unit tests passed.")`. The new block must exercise the exact `exact` set and `regex_patterns` list Card 2 added to `mill-go/SKILL.md`'s new "### Mid-execution phase-gate widening" subsection: `{"implementing", "reviewing", "fixing", "self-resolved-verify-logic", "holistic-approved"}` and `[r"^approved-.*$", r"^reviewing-.*-r\d+$", r"^fixing-.*-r\d+$", r"^holistic-reviewing$"]`.

  Assert `matches_wait_trigger` returns `True` for: `"approved-foo"`, `"reviewing-foo-r1"`, `"fixing-foo-r3"`, `"holistic-reviewing"`, `"self-resolved-verify-logic"`, `"holistic-approved"`. Assert it returns `False` for: `"blocked"`, `"done"`, and one near-miss that should NOT accidentally match the new regexes, e.g. `"approved"` (no trailing `-{name}`, must not full-match `^approved-.*$`). Print one `PASS:` line per assertion group (matching the file's existing per-case style), and end the block the same way every other case does (asserting, then a `print("PASS: ...")` line — no bare `assert` without a following print). Do not modify `main()`'s `try`/`except`/`return` structure outside inserting this new block.

- **Commit:** `test(phase-wait): cover the six widened Entry-gate phase values (#757)`

### Card 4: Make the stuck-escalation verify/logic self-resolve step's failure-reason annotation mandatory (both branches)

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  This file has two occurrences of an identical conditional hedge — "edit the plan file(s) if the failure traces to an ambiguous or incorrect card" — inside a `verify`/`logic` self-resolve branch. Both occurrences get the identical fix: keep the existing investigate-and-maybe-edit-the-plan sentence unchanged, but insert one new sentence immediately after it that makes recording the failure reason mandatory regardless of whether a plan edit was made.

  **Occurrence 1 — per-batch `### Stuck escalation` section**, in the bullet whose text begins `verify` / `logic` (first occurrence): immediately after the existing sentence ending "...edit the plan file(s) if the failure traces to an ambiguous or incorrect card." and before the existing sentence beginning "Before re-firing, record the self-resolve:", insert this new sentence: "**Regardless of whether a plan edit was made**, append a `## Prior failure` section to the affected batch file (`<plan_dir>/NN-<batch_name>.md`, placed immediately after its frontmatter, before `## Rename mechanic`/`## Batch Scope` — create the section if it is not already present) with one new bullet stating the round and the verbatim stuck-JSON `reason` text."

  **Occurrence 2 — `## Holistic code review` section**, in the bullet whose text begins `stuck_type: verify` or `logic` (first occurrence): immediately after the existing sentence ending "...edit the plan file(s) if the failure traces to an ambiguous or incorrect card." and before the existing sentence beginning "Before re-invoking, record the self-resolve:", insert this new sentence: "**Regardless of whether a plan edit was made**, append a `## Prior failure` section to `00-overview.md` (placed immediately after its frontmatter, before `## Batch Index` — create the section if it is not already present) with one new bullet stating the round and the verbatim stuck-JSON `reason` text, regardless of whether the reason names a specific batch, spans several, or names none at all."

  Do not change anything else in either bullet — the existing `_status.append_phase(status_path, "self-resolved-verify-logic", ...)` + commit + re-fire-fresh mechanism, and the repeat-failure escalation-to-blocked sentence that follows, are unchanged in both locations.

- **Commit:** `docs(mill-go): make verify/logic self-resolve failure-reason annotation mandatory (#758)`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-phase-wait.py` directly — the single file Card 3 extends. This is the only runnable surface in the batch: Cards 2 and 4 are `mill-go/SKILL.md` prose interpreted by the orchestrating LLM at runtime, with no Python function backing the routing table or the annotation-mandatory wording (same rationale as the discussion's Testing section for #757's routing logic and #758) — Card 3's coverage of `_phase_wait.matches_wait_trigger` with the exact pattern set Card 2 introduces is the correctness gate for the *predicate* those two cards' prose leans on; the prose itself is gated by plan review and code review of the actual diff.
