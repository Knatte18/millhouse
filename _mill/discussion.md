# Discussion: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
task: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3
slug: plan-validate-context-completeness-round3-gaps
status: discussing
parent: main
```

## Problem

`_plan_validate.py`'s `context-completeness` check (`_check_context_completeness`, `_symbol_candidate_shape`,
`_resolve_symbol_files` in `plugins/mill/scripts/_plan_validate.py`) validates that a plan card's
`Requirements:` prose doesn't cite a file or symbol absent from that card's own
`Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` fields — the allowlist a bulk-mode implementer/reviewer
actually reads. Three prior patch rounds have already landed on this exact check (see `git log --oneline
-- plugins/mill/scripts/_plan_validate.py`), each adding more shape heuristics and exemptions. Six new
bug reports arrived after those rounds:

- **#1131** / **#1129** — bare symbol / BCL type names (`Seed`, `Register`, `Advance`, `Sync`,
  `CellLength`, `InnerRadius`, `OuterRadius`, `InvalidOperationException`, …) resolve to unrelated files
  anywhere in a large repo and get demanded in `Context:`. Observed in one real mill-plan run: 80
  validator findings, 79 of them `context-completeness`, the large majority false positives.
- **#1122** — a bare file-path citation used as evidentiary support for a mechanism claim isn't checked.
- **#1119** — a card's own not-yet-existing constant, declared inline (not in a paren/brace-shaped
  backtick span), gets misresolved to an unrelated file elsewhere in the repo.
- **#1116** — the "3+ literal backtick tokens on one line, at least one non-path/non-symbol-shaped"
  exemption is line-wide, so a single incidental literal sharing a line with a genuine dependency
  suppresses the real finding.
- **#1115** — an assignment-expression backtick span (`` `x = mod.func(args)` ``) is invisible to
  `_symbol_candidate_shape`, which only strips a *trailing* call/generic suffix, never a *leading*
  assignment-target prefix.

Why now: the false-positive volume in #1131/#1129 is severe enough that plan authors were forced to strip
backticks from ordinary prose to pass the check — degrading plan readability to satisfy the checker,
exactly the failure mode `_plan_validate.py`'s exemptions exist to prevent. The task brief explicitly asks
whether another patch round is still the right call, or whether the check needs a structural change.

## Scope

**In:**

- A structural change to the symbol branch's resolution scope (see Decision `resolution-scope-rework`):
  `_resolve_symbol_files` stops walking the whole repo tree for a bare/dotted symbol candidate and
  instead resolves only within the plan's own already-cited files (union of every card's
  `_card_own_reference_set` — `Context:`/`Edits:`/`Creates:`/`Deletes:` tokens plus BOTH halves of every
  `Moves:` pair, source and target — across every card in the plan). No repo-wide fallback when the
  narrowed search finds nothing — treat as unresolvable, don't flag.
- A refactor of `_check_context_completeness`'s Requirements-text tokenization from per-physical-line to a
  single pass over the fence/blockquote-filtered text, joined into one continuous string (see Decision
  `line-join-refactor`; `_compute_declared_symbols_union` already scans its Requirements body in one pass
  with no per-line loop, so it is untouched by this refactor). This fixes a previously undocumented
  bug I traced during exploration (see below); it does NOT close `_is_prohibition_exempt`'s own documented
  "multi-line prohibition phrasing not detected" limitation — that remains open and out of scope (see the
  Decision for why).
- `_symbol_candidate_shape`: strip a leading `identifier(: Type)? = ` assignment-target prefix before the
  `_RE_SYMBOL_SHAPE` match, mirroring the existing trailing-suffix stripping (fixes #1115).
- `_compute_declared_symbols_union`: also capture a `modifier+ identifier = value` inline declaration form
  — one OR MORE modifier/type-annotation tokens required before the `=` (e.g.
  `` `private const double StepDurationS = 10.0` ``), not just the current paren/brace-shaped extraction
  (fixes #1119). The modifier requirement is not optional/zero-or-more: a bare `` `identifier = value` ``
  span with no modifier/type token in front is ordinary prose citing an EXISTING symbol's current value
  (e.g. `` `timeout = 30` ``), not a new inline declaration — matching that bare form too would silently
  add an existing repo symbol's name to the plan-wide declared-symbols set and wrongly exempt a genuine
  later citation of that same symbol anywhere else in the plan (caught in discussion-review round 4).
- `_is_literal_enumeration_exempt`: change the trigger from "at least one non-shaped sibling token" to
  "non-shaped tokens are a majority of the line's backtick tokens" (fixes #1116 and #1122 — see Decision
  `literal-enumeration-majority`).
- New/extended unit test coverage in `plugins/mill/unit_tests/test-plan-validate.py` for every fix above,
  including regression tests reproducing each of the 6 issues' own repro cases plus the traced
  backtick-line-wrap incident.

**Out:**

- `_filter_matches_by_qualifier`, the declaration-form regexes inside `_resolve_symbol_files`
  (`go_top_level_re`, `cs_member_re`, etc.), and any other context-completeness machinery not implicated
  by one of the 6 issues, my own traced finding, or the resolution-scope rework. No speculative
  hardening beyond what a concrete failure demonstrates.
- Any check in `_plan_validate.py` other than `context-completeness` (e.g. `verify-not-isolated`,
  `move-format`, `batch-oversized`) — untouched.
- Splitting `test-plan-validate.py` into a dedicated context-completeness test module — left to the
  plan-writer's discretion if the file's size makes that clearly better; not a discussion-level decision.

## Decisions

### resolution-scope-rework

- Decision: `_resolve_symbol_files` resolves a symbol-branch candidate only against the plan-wide union
  of files already cited somewhere in the plan — built by calling the existing `_card_own_reference_set`
  helper on every card and unioning the results, unchanged (computed once per `run()` call, mirroring the
  existing plan-wide `creates_union`/`deletes_union`/`moves_sources`/`moves_targets` pattern already
  threaded through this same function). This means a `Moves:` pair contributes BOTH its source and target
  token to the set, exactly as `_card_own_reference_set` already does for its own existing callers — no
  Moves-target carve-out. A not-yet-existing `Moves:`-target token cannot resolve to an existing file
  anyway (the narrowed search only ever matches real on-disk declaration content — see the resolution
  step below), so including it changes nothing behaviorally; excluding it would be extra filtering logic
  bought for zero behavioral difference, and reusing `_card_own_reference_set` unchanged is simpler.
  When the narrowed search finds zero matches, the token is treated as unresolvable and never flagged —
  no fallback to a repo-wide walk.
- Rationale: #1131's own false-positive list (`CellLength`, `InnerRadius`, `OuterRadius`, …) shows the
  failure mode is not shape-dependent — these are well-formed, multi-word, legitimately-cased
  identifiers that still collided with an unrelated file purely because the repo is large enough that
  "resolves to exactly one file anywhere in the tree" stops being a meaningful confidence signal. Three
  rounds of shape/exemption patches have not closed this class and cannot, by construction: no amount of
  identifier-shape filtering can distinguish "this is the project's own symbol" from "this coincidentally
  collides with an unrelated file's symbol of the same name" without narrowing *where* the search looks.
  Scoping to the plan's own already-cited files makes a coincidental collision with a totally unrelated
  file structurally impossible, since a repo-wide-common word essentially never happens to also be
  declared in a file the plan itself already references.
- Rejected: another patch round of shape heuristics only (a BCL/exception denylist, stricter casing
  rules) — doesn't address the root cause, is language-specific and permanently incomplete (the report
  itself notes inconsistent behavior — `ArgumentException` didn't fire on the same line
  `InvalidOperationException` did). Dropping the symbol branch entirely — too blunt; #1115's own working
  example (`` `_run_verify_gates` `` correctly flagged) shows the branch has genuine value when scoped
  correctly.
- Accepted cost: a symbol cited as a dependency for the very first time anywhere in the plan (no other
  card's `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` names its file yet) is no longer caught by the
  symbol branch. This is the same blind spot that existed before the symbol branch was added at all
  (#742's original path-only check), not a regression — and a far smaller cost than a check that
  currently produces 79 false positives out of 80 findings in a real run.

### line-join-refactor

- Decision: `_check_context_completeness` stops restarting `_BACKTICK_RE.finditer` fresh on each physical
  line of the Requirements body (`_compute_declared_symbols_union` is untouched — it already runs
  `_BACKTICK_RE.finditer` once over its whole Requirements body with no per-line loop, so it never had
  this bug). Instead, build the
  fence/blockquote-filtered text (skipping quoted lines exactly as today) as one continuous joined string
  (physical lines joined in order), with a line-start-offset lookup table recording which original
  physical line each character position falls in.
  Token EXTRACTION (`_BACKTICK_RE.finditer`) always runs against this joined text — this is what fixes
  the backtick-line-wrap corruption bug. Which text an EXEMPTION helper is checked against then splits
  by helper, not uniformly:
  - `_is_non_dependency_negation_exempt` and `_is_contrast_citation_exempt` (both via `_clause_bounds`)
    run against the joined text, but `_clause_bounds`'s own boundary search is capped from crossing an
    original physical-line/bullet break: in addition to the existing comma/semicolon/colon/period
    (`_RE_CLAUSE_BOUNDARY`), the line-start-offset table's own line-break positions count as clause
    boundaries when computing bounds over the joined text. Without this cap, a "clause" could span two
    physical lines/bullets with no punctuation between them at all (e.g. one bullet ending "...`x.py`"
    and the next starting "without needing it") — reproducing, at clause scope, the exact new
    cross-line false-negative class the four unconditional exemptions below are being kept away from.
    With the cap, these two helpers effectively keep the same per-physical-line reach they have today for
    any token whose own backtick span doesn't itself cross a line break, while still correctly handling
    the case that actually motivated the join: a single token whose own backtick span crosses a line
    break (the corrected-extraction case) still gets a well-defined clause, bounded by whichever comes
    first — real punctuation or the line break.
  - `_is_prohibition_exempt`, `_is_literal_enumeration_exempt`, `_is_cross_card_ownership_exempt`, and
    `_is_illustrative_output_exempt` are each an unconditional, unbounded substring/pattern-presence match
    with no clause or position scoping at all — the "any negation+verb pair", "any output verb", or "any
    ownership phrase" fires anywhere the check looks, and `_is_literal_enumeration_exempt`'s trigger counts
    every backtick token the check looks at. All four keep running against ONLY the physical line(s) that
    the tested token's own backtick match spans — normally exactly one line, identical to today; for the
    rare token whose own span crosses a line break (the corrected-extraction case), the two-or-more lines
    it spans, joined, so the helper can still see a negation/verb pair or sibling token that happens to
    straddle that same span — never the whole joined Requirements body. `_is_prohibition_exempt`'s own
    docstring documents a broader "Nested-bullet/multi-line prohibitions (negation on a parent bullet, path
    on a child bullet)" gap as known-but-unhandled; that gap is NOT closed by this task — closing it would
    require bullet-parent-relative scoping this task has no filed issue demanding, and discussion-review
    round 4 confirmed naively widening it to whole-body scope (this decision's own original draft)
    reproduces the exact unbounded false-negative class the other three unconditional exemptions are
    being deliberately kept away from, just via a fourth helper. `_is_literal_enumeration_exempt` is the
    one of these four that takes explicit `token_start`/`token_end` position parameters (used to skip the
    tested occurrence via `m.start(1) == token_start and m.end(1) == token_end` when scanning for a
    disqualifying sibling); since token extraction now runs on the joined text, `token_start`/`token_end`
    arrive as joined-text-global offsets and MUST be translated to offsets local to the token's own
    spanned line(s) (subtract that span's own start offset, from the offset table, before the call) —
    passing global offsets against a call that internally re-scans only the local text would make the
    self-skip comparison fail for every occurrence past the first physical line, corrupting the
    `literal-enumeration-majority` tally by double-counting the tested token as its own sibling. The other
    three take no position parameters, so no offset translation applies to them. Each of these four
    helpers' own docstring explicitly calibrates its accepted false-positive/negative tradeoff assuming
    single-physical-line scope (`_is_literal_enumeration_exempt`: "3+ backtick tokens... on the same
    line"; `_is_cross_card_ownership_exempt`: accepts its line-wide tradeoff explicitly for "an unusually
    long Requirements: line"; `_is_illustrative_output_exempt`: scans "anywhere on the line") — widening
    any of them to the whole joined Requirements body would let one sentence's prohibition/literal-
    enumeration/ownership/output-verb phrase exempt every backtick token elsewhere in that card's
    Requirements text, including an unrelated genuine dependency several sentences away — a new
    false-negative class this task's own goal (fixing #1131's false positives without regressing coverage)
    does not want.
  The emitted error dict's `"line"` field switches from "the physical line's stripped text" to "the
  physical line containing the token match's start offset" (via the same offset table), preserving today's
  error-message granularity.
- Rationale: during exploration I traced #1122 back to its real source plan
  (`hanf/mill-go-merge-in-orchestration-robustness-r2`, batch 1 card 2) and found the automated check
  missed `millpy-fix.py` for a reason *not* stated in the issue report: a single-backtick inline-code span
  that happens to wrap across a markdown physical-line boundary (`` `start_sha is not\nNone` ``) leaves an
  odd/shifted backtick count on the line where it closes. `_BACKTICK_RE`'s left-to-right greedy pairing,
  restarted fresh on that line, then pairs the leftover close-marker with the *next* real backtick it
  finds — silently swallowing every genuine token after it on that line into garbage, non-path/non-symbol
  captures that are never flagged. This is a distinct bug from #1122's filed hypothesis ("no mechanism for
  a bare file-path citation") — the check *does* have that mechanism; the token extraction itself was
  corrupted before the citation ever reached it. This bug is invisible to any per-line patch, since it can
  recur at any future multi-line-spanning inline-code span. Joining lines before tokenizing is the only
  fix that closes the class rather than the one instance found. (An earlier draft of this decision also
  claimed this refactor incidentally closes `_is_prohibition_exempt`'s own documented "Nested-bullet/
  multi-line prohibitions" limitation — discussion-review round 4 caught that this was wrong: naively
  widening that helper's own reach to whole-body scope reproduces the same unbounded false-negative class
  the other unconditional exemptions are deliberately kept away from. That documented limitation remains
  open and out of scope for this task; see the EXEMPTION-helper enumeration above.)
- Rejected: detect-and-suppress (treat an odd-backtick-count line as a continuation and skip further
  matches on it) — stops the corruption from spreading past that line, but doesn't recover the swallowed
  token, so the exact `millpy-fix.py` incident traced above would still go undetected. Also rejected:
  running every exemption helper uniformly against the whole joined body (this discussion's own original
  draft) — flagged in discussion-review round 1 as silently widening three deliberately line-scoped,
  unconditional exemptions (`_is_literal_enumeration_exempt`, `_is_cross_card_ownership_exempt`,
  `_is_illustrative_output_exempt`) to whole-Requirements-field scope, a new false-negative class with no
  test coverage; the per-helper split above (joined text for extraction, `_is_prohibition_exempt`, and the
  already clause-scoped helpers; originating-physical-line only for the three unconditional line-wide ones)
  is the fix.

### literal-enumeration-majority

- Decision: `_is_literal_enumeration_exempt` (the "3+ backtick tokens on a line, ≥1 not path/symbol
  shaped" exemption) changes its trigger to "non-shaped tokens are a STRICT majority (non-shaped count >
  shaped count) of the line's backtick tokens," instead of "at least one non-shaped sibling." The tested
  occurrence itself counts toward both the total and its own shape classification — the tally is over
  every backtick token on the line, including the one currently being evaluated, exactly like the
  existing "3 or more backtick tokens total" count already does (today's code only excludes the tested
  occurrence from the separate "at least one OTHER token" sibling search, not from the total count; the
  new rule keeps that same self-inclusive total and simply changes what's compared against it — there is
  no separate "siblings only" tally to keep track of). An exact tie (non-shaped count == shaped count) is
  NOT a majority and does not exempt — ties resolve toward flagging/checking, matching this task's
  overall bias toward not suppressing a genuine dependency.
- Rationale: verified against both real-world repro lines. #1116's own line
  (`` construct `WellboreCases.CaseHydraulic(includeCirculationSub: true)`, seed it with a converged
  `SteadyStateHydraulicSolver` at `EpsForConvergence = DefaultSolverScalings.Pressure * 10` `` — 3
  tokens: 2 symbol-shaped, 1 not) has a minority of non-shaped tokens under the new rule, so the exemption
  no longer swallows the genuine `SteadyStateHydraulicSolver` dependency. #1122's traced line 99
  (`` `millpy-merge-in-subagent.py`'s `verify-fix` mode never calls `finalize_from_output`/ `` — 3
  tokens: 2 shaped (a path, a bare identifier), 1 not — the CLI-mode literal `verify-fix`) gets the same
  correct outcome. A genuine literal-value enumeration (e.g. `` `"a"`, `"b"`, `42` ``) stays exempt since
  it's all or mostly non-shaped.
- Rejected: clause-scoping the exemption (reusing `_clause_bounds`, the same mechanism
  `_is_contrast_citation_exempt` already uses) — checked against #1122's line 99 specifically. The line
  does contain one clause-boundary character (the period inside `millpy-merge-in-subagent.py`'s own `.py`
  extension), but that period sits BEFORE that token's own end offset, not after it — and
  `_clause_bounds` computes a token's clause end by searching for the next boundary character starting
  FROM that token's own end. For `millpy-merge-in-subagent.py` specifically (the token that actually needs
  to be flagged), that forward search finds no further boundary punctuation anywhere else on the line, so
  its own computed clause still spans the whole line, still including `verify-fix` and
  `finalize_from_output` — the pre-existing "≥1 non-shaped sibling" trigger still (wrongly) fires for it.
  (Clause-scoping would correctly isolate `verify-fix`/`finalize_from_output` into their own tighter
  clause when evaluating THOSE two tokens, but that's immaterial: `millpy-merge-in-subagent.py` is the
  token needing the fix, and its own clause-bounds computation is unaffected by a boundary that sits
  inside its own already-consumed span.) The majority-based rule fixes this regardless of where any
  boundary punctuation happens to sit, since it doesn't depend on clause position at all.

## Technical context

- Everything lives in `plugins/mill/scripts/_plan_validate.py`. Key functions (line numbers as of this
  discussion; will drift — use `grep -n 'def _check_context_completeness\|def _symbol_candidate_shape\|def _resolve_symbol_files\|def _compute_declared_symbols_union\|def _is_literal_enumeration_exempt\|def _requirements_fence_aware_body'` to relocate):
  - `_check_context_completeness` — the check's entry point, called from `run()`.
  - `_symbol_candidate_shape` — gates whether a non-path-shaped backtick token is symbol-shaped at all.
  - `_resolve_symbol_files` — the repo-walk resolver being narrowed by `resolution-scope-rework`; already
    memoized per `run()` call via a `cache` dict keyed by search key.
  - `_compute_declared_symbols_union` — plan-wide union of symbols the plan itself declares (exemption
    14); already calls `_BACKTICK_RE.finditer` once over the whole `_requirements_fence_aware_body`
    output with no per-physical-line loop, so it does NOT have the backtick-line-wrap corruption bug and
    is untouched by `line-join-refactor` — that decision is `_check_context_completeness`-only. This
    function is touched only by the separate `modifier+ identifier = value` capture widening (#1119, see
    Scope).
  - `_is_literal_enumeration_exempt`, `_is_prohibition_exempt`, `_is_non_dependency_negation_exempt`,
    `_is_contrast_citation_exempt`, `_is_cross_card_ownership_exempt`, `_is_illustrative_output_exempt`,
    `_clause_bounds` — the exemption helpers `line-join-refactor` re-targets onto joined text.
  - `_requirements_fence_aware_body` — already produces the fence/blockquote-aware Requirements body;
    both the existing per-line loop and the new joined-text approach start from its output.
  - `resolve_existing_paths` (in `plugins/mill/scripts/_review_common.py`) — the path-branch resolver;
    reuse its root-precedence pattern when resolving the plan-wide cited-files set's raw tokens
    (`Context:`/`Edits:`/etc. entries are typically already relative-path-shaped, matching the canonical
    form `_resolve_symbol_files` currently returns via `matches[0].relative_to(producing_root).as_posix()`)
    to real files for `resolution-scope-rework`'s narrowed declaration-form search.
  - `_card_own_reference_set` — already extracts one card's own Context/Edits/Creates/Deletes/Moves
    backtick tokens; the plan-wide cited-files set for `resolution-scope-rework` is the union of this
    across every card in the plan (mirrors how `compute_creates_union`/`compute_deletes_union`/
    `compute_moves_union` already build their own plan-wide unions — grep those names to find the
    existing pattern to follow).
  - `run()` (~line 4430) — wires `creates_union`, `deletes_union`, `moves_sources`, `moves_targets`,
    `creates_declaring_card_map`, and `declared_symbols` as plan-wide precomputed values passed into
    `_check_context_completeness`; the new plan-wide cited-files set follows the same wiring pattern.
- Existing coverage: `plugins/mill/unit_tests/test-plan-validate.py` already has ~147 tests touching
  context-completeness/symbol-resolution — follow its existing per-check naming/fixture conventions for
  new tests.
- The two real-world incidents this discussion cites (#1122's source plan, and #1116's own reported line)
  are useful ground truth for regression tests; #1122's source plan is on branch
  `hanf/mill-go-merge-in-orchestration-robustness-r2` (already merged — read via
  `git show hanf/mill-go-merge-in-orchestration-robustness-r2:_mill/plan/01-finalize-completeness-and-baseline-robustness.md`
  for the exact card 2 text, batch-file name may drift if that branch is ever pruned).

## Testing

- TDD candidates: `_symbol_candidate_shape`'s new leading-prefix stripping (#1115), the widened
  `_compute_declared_symbols_union` extraction (#1119), and `_is_literal_enumeration_exempt`'s majority
  rule (#1116/#1122) are all pure functions with no filesystem/git dependency — write these test-first.
- `resolution-scope-rework` needs fixture-based tests (in-memory/tempfile plan dirs, per this repo's
  existing integration-test convention of no real git/LLM for unit tests) covering: (a) a symbol resolving
  within the plan-wide cited-files set but not the current card's own refs → still flagged; (b) a symbol
  matching a file NOT in the plan-wide cited-files set (the #1131/#1129 false-positive shape) → no longer
  flagged; (c) the existing qualifier-disambiguation and single-letter-qualifier behavior is unaffected by
  the scope narrowing (that logic runs on whatever match list `_resolve_symbol_files` returns, regardless
  of scope); (d) a fully empty plan-wide cited-files set — a fixture plan where no card anywhere has any
  `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` entry at all, so the whole-plan union (built once per
  `run()` call over every card, per Decision `resolution-scope-rework`) is empty regardless of card order
  — assert no crash and that the symbol branch simply resolves nothing and never flags (caught as a NIT
  in discussion-review round 4; wording corrected in round 6 — the set is not order-/position-dependent,
  so "first card before accumulation" was a misleading frame for this boundary case).
- `line-join-refactor` needs a regression test reproducing the exact traced incident: a Requirements body
  where one inline-code span opens on one physical line and closes on the next, followed by a genuine
  path-shaped dependency later on the closing line — must now be flagged. (The already-documented
  `_is_prohibition_exempt` multi-line-prohibition limitation is NOT fixed by this refactor — see Decision
  `line-join-refactor` — so it needs no test here; this bullet's earlier draft wrongly claimed otherwise,
  corrected in discussion-review round 7.)
- `line-join-refactor` also needs a negative-direction test proving the per-helper split holds: a card
  whose Requirements text has a genuine unlisted dependency on one physical line and, on a *different*
  physical line elsewhere in the same field, an unrelated phrase that would trigger
  `_is_literal_enumeration_exempt`, `_is_cross_card_ownership_exempt`, or `_is_illustrative_output_exempt`
  — the genuine dependency must still be flagged, proving the whole-body-join scope change didn't silently
  widen these three exemptions' reach past their own originating line (discussion-review round 1 finding).
- Each of the 6 filed issues should get at least one regression test using that issue's own reported repro
  text (adapted to this repo's fixture conventions), not just a synthetic minimal case — several of these
  bugs (especially #1122) only manifested with the exact surrounding prose shape.

## Q&A log

- **Q:** Structural rework of the symbol branch's resolution scope, plus targeted patches for the
  line-local bugs, vs. another patch round only, vs. dropping the symbol branch entirely? **A:**
  [auto-pick] Structural rework (narrow `_resolve_symbol_files` to the plan's own already-cited files, no
  repo-wide fallback) plus targeted patches for #1119/#1115/#1116/#1122 and the newly-traced
  backtick-line-wrap bug. **Why:** #1131's false positives (`CellLength`, `InnerRadius`, `OuterRadius`)
  are well-formed identifiers, proving the failure is about resolution scope (repo-wide walk), not
  identifier shape — no amount of shape-heuristic patching (3 rounds already tried) can close that class.
- **Q:** Should the plan-wide "already-cited files" set for the resolution-scope rework be built from the
  whole plan, or scoped to the current/same batch only? **A:** [auto-pick] Whole-plan union. **Why:**
  mirrors the existing `creates_union`/`deletes_union`/`moves_sources` plan-wide pattern already used
  elsewhere in this exact function; no reason a cross-batch dependency should be treated differently.
- **Q:** How to fix the newly-traced backtick-line-wrap-corruption bug? **A:** [auto-pick] Refactor
  `_check_context_completeness`'s Requirements-text tokenization to operate on the fence/blockquote-
  filtered text joined into one continuous string, rather than a narrower per-line odd-backtick-count
  suppression. **Why:** the narrower fix stops corruption spreading but doesn't recover the swallowed
  token — the exact `millpy-fix.py` incident traced from #1122's source plan would still go undetected.
  (`_compute_declared_symbols_union` already tokenizes in one pass with no per-line loop, so it never had
  this bug and is untouched — caught in discussion-review round 6, corrected from this entry's original,
  now-inaccurate draft. The draft's other claim — that this refactor also closes
  `_is_prohibition_exempt`'s documented multi-line-prohibition limitation "for free" — was separately
  corrected in round 4: naively widening that helper's scope reproduces the same unbounded false-negative
  class three other exemptions are deliberately kept away from, so that limitation remains open and out
  of scope; see Decision `line-join-refactor`.)
- **Q:** Add leading-prefix stripping to `_symbol_candidate_shape` for #1115's assignment-expression
  backtick spans, or leave it as a documented limitation? **A:** [auto-pick] Add the stripping. **Why:**
  direct, symmetric fix (mirrors existing trailing-suffix stripping) matching the issue's own suggested
  direction; this task exists specifically to close these gaps, not document more of them.
- **Q:** Widen `_compute_declared_symbols_union` to capture inline `modifier* identifier = value`
  declarations for #1119, or leave the rephrase-to-avoid-bare-token workaround in place? **A:** [auto-pick]
  Widen the extraction. **Why:** matches the issue's exact repro; the workaround has the same
  "degrade the plan to satisfy the checker" cost #1131 already flagged as unacceptable.
- **Q:** Fix #1116/#1122's literal-enumeration exemption via a majority-non-shaped-tokens rule, or by
  clause-scoping the existing trigger? **A:** [auto-pick] Majority-non-shaped-tokens rule. **Why:** verified
  against both real repro lines (#1116's own line and #1122's traced line 99) — the majority rule fixes
  both; clause-scoping only fixes #1116's (no clause-splitting punctuation exists on #1122's line, so
  clause-scoping leaves all 3 tokens in one clause and the exemption still wrongly fires).
- **Q:** New test coverage location — extend `test-plan-validate.py`, or split into a dedicated
  context-completeness test module? **A:** [auto-pick] Extend `test-plan-validate.py`. **Why:** keeps all
  context-completeness coverage discoverable in one place, consistent with how the prior 3 patch rounds
  already extended it; splitting is left to the plan-writer's discretion if size makes it clearly better.
- **Q:** Should this task also proactively audit adjacent context-completeness machinery
  (`_filter_matches_by_qualifier`, the declaration-form regexes) not implicated by any filed issue? **A:**
  [auto-pick] No — scope strictly to the 6 filed issues, the resolution-scope rework, and the traced
  backtick-line-wrap bug. **Why:** YAGNI; no concrete failure drives auditing anything beyond this set.
