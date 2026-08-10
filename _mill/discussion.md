# Discussion: _plan_validate.py: path-reference heuristic false positives (round 3) + run() docstring drift

```yaml
task: _plan_validate.py: path-reference heuristic false positives (round 3) + run() docstring drift
slug: mill-plan-validate-heuristic-gaps-3
status: discussing
parent: main
```

## Problem

`plugins/mill/scripts/_plan_validate.py`'s `context-completeness` check (introduced #742, previously
tuned in mill-plan-validate-false-positives and mill-plan-validate-heuristic-gaps-2) still has five
open gaps, filed as GitHub issues #807, #805, #793, #789, #796 and folded into this single task. Four
are false-positive/message-accuracy gaps in the `context-completeness` heuristic; the fifth (#796) is
an unrelated docstring-drift fix on the same file's `run()` function, folded in because it touches the
same module.

Why now: this is the third round of tuning this heuristic against real `mill-plan` sessions across the
`loomyard` and `millhouse` repos — each issue is a concrete false-positive (or message-inaccuracy)
reproduction captured during an actual plan-writing session, not a hypothetical.

## Scope

**In:**
- #807 — exempt backtick-quoted filenames that appear in prose citing them as an example/write-target
  (not a read dependency), via a new `_CITATION_MARKERS` substring-exemption tuple, mirroring the
  existing `_PROHIBITION_MARKERS` pattern.
- #805 — thread the already-computed `moves_sources` (from `compute_moves_union`, currently discarded
  by `run()`) into `_check_context_completeness` as a third exemption dimension: a path that is a
  `Moves:` source anywhere earlier in the plan is exempt in *any* later card's `Requirements:`, not
  just the declaring card's own.
- #793 — qualify the `context-completeness` error message's field list from `Context:/Edits:/Creates:/
  Deletes:/Moves:` to `Context:/Edits:/Creates:/Deletes:/Moves:-source` (the module docstring already
  says this correctly; only the emitted message string and mill-plan's fix-table row are stale).
- #789 — extend `_PROHIBITION_MARKERS` with `"never change"`, `"not change"`, `"never modify"`,
  `"not modify"` to catch `"do not change X"` / `"must not modify X"` phrasing (currently only
  `"forbid"`/`"never touch"`/`"must not touch"`/`"do not touch"`/`"not touch"` are covered).
- #796 — update the module docstring's `run(...)` public-API summary line (top of file, ~line 9) to
  match the real signature, which additionally takes `max_cards_per_batch`, `max_batch_context_tokens`,
  `parent_branch`.
- Update `plugins/mill/skills/mill-plan/SKILL.md`'s `context-completeness` fix-table row wording to say
  `Moves:-source` instead of bare `Moves:`, matching #793's explicit ask.
- Unit tests for each of the five fixes in `plugins/mill/unit_tests/test-plan-validate.py`, following
  the file's existing one-test-per-scenario convention.

**Out:**
- #789's broader original repro set (card 41 "this task adds no module", card 30 "a list of files a
  later batch owns", card 37 "this card declares no Edits:") — these are not negation-of-touching
  phrasing and are not part of this round's brief, which narrows specifically to
  `"do not change X"`/`"must not modify X"` wording. Not addressed here.
- Any new plan-format field (e.g. a `Mentions:`/`NoRead:` marker) for declaring a citation as
  non-consuming — rejected as disproportionate to a heuristic-tuning task; see Decisions.
- Rewriting `context-completeness` to use verb-construction detection instead of markers — rejected;
  see Decisions.
- Any change to `_check_context_completeness`'s resolvability logic (the `existing_files` /
  `creates_union` / `deletes_union` / `moves_targets` disjunction) — out of scope; only the exemption
  logic downstream of resolvability changes.

## Decisions

### citation-exemption-via-markers (#807)

- Decision: add a new module-level tuple `_CITATION_MARKERS` (separate from `_PROHIBITION_MARKERS`,
  since it exempts a different semantic class — "named as an example/citation" vs "must not act on")
  containing `"as an example"`, `"as examples"`, `"for example"`, `"e.g."`, `"such as"`, `"cited as"`,
  `"citing"`. Checked the same way as `_PROHIBITION_MARKERS` — substring match against the lowered
  `Requirements:` line — and exempts the token from flagging when matched.
- Rationale: matches the two concrete #807 repro sentences ("naming README.md, CLAUDE.md... as
  examples of files whose outgoing links are checked by nobody"; "_mill/discussion.md, cited as the
  source of a decision"). Consistent with the existing marker-substring architecture and its accepted
  false-negative risk tolerance (a real dependency phrased with "for example" would also get exempted
  — same trade-off already made for `_PROHIBITION_MARKERS`).
- Rejected: allowlist-of-consuming-verbs rewrite (too high a blast radius against existing passing
  tests using "See X"/"Follow the pattern in X"); new plan-format annotation field (disproportionate
  scope — template + SKILL.md changes, and doesn't retroactively fix without planner adoption).

### moves-sources-plan-wide-exemption (#805)

- Decision: add a `moves_sources: set[str]` parameter to `_check_context_completeness`, threaded from
  `run()`'s already-computed (but currently discarded) `moves_sources` local (see
  `_plan_validate.py:2677`). Exempt a token when `stripped_token in moves_sources`, alongside the
  existing per-card `own_refs` check.
- Rationale: root cause is exactly `run()` computing `moves_sources` via `compute_moves_union` and
  never passing it to the one check that needs it — `moves_targets` already makes the equivalent trip.
  This is a plan-wide exemption (mirrors how `creates_union`/`deletes_union` are already plan-wide),
  not a per-card one, because the whole point is a *later* card referencing an *earlier* card's Move.
- Rejected: none considered — this is a direct wiring fix matching the bug report's own root-cause
  diagnosis, with no meaningful alternative design.

### moves-source-message-qualifier (#793)

- Decision: change the error message at `_check_context_completeness`'s error-emission site (currently
  `"...which is not in this card's Context:/Edits:/Creates:/Deletes:/Moves:"`) to append `-source`
  after `Moves:`. Update `mill-plan/SKILL.md`'s `context-completeness` fix-table row (line ~320) the
  same way — but that row is only **partially** stale: its first clause ("the card's own
  `Edits:`/`Creates:`/`Deletes:`/`Moves:` already covers it") is unqualified and needs the `-source`
  suffix, while a later clause in the same row ("a token that legitimately belongs to
  `Deletes:`/`Moves:`-source means the check should not have fired at all") is already correctly
  qualified. Fix only the first occurrence — a blind find/replace across the row would turn the
  already-correct clause into `Moves:-source-source`.
- Rationale: the module docstring (top of `_plan_validate.py`, line ~46-47) already documents the
  check correctly as `Moves:-source`; only the runtime message and the SKILL.md prose lagged. Issue
  explicitly names both sites.
- Rejected: message-only fix without touching SKILL.md — rejected because the issue explicitly flags
  the fix-table row as part of what misdirects the mechanical fixer.

### prohibition-marker-change-modify (#789)

- Decision: add `"never change"`, `"not change"`, `"never modify"`, `"not modify"` to
  `_PROHIBITION_MARKERS`.
- Rationale: mirrors the existing "touch" coverage pattern — `"never touch"` plus a catch-all
  `"not touch"` (which already subsumes `"do not touch"`/`"must not touch"`/`"should not touch"` as
  substrings) — applied to the two verbs (`change`, `modify`) the brief names.
- Rejected: also adding `"edit"` variants — the brief's literal wording only names "change"/"modify"
  phrasing; adding "edit" would be scope creep beyond what was reported in this round. Full semantic
  negation-detection (parsing "do NOT X" generically) — rejected as disproportionate; the existing
  architecture is deliberately a flat substring list.

### run-docstring-signature-sync (#796)

- Decision: update the module docstring's `run(...)` one-line signature summary (currently
  `run(plan_dir, project_root, *, root=None, wiki_root=None, git_root=None, skip_checks=frozenset())
  -> list[dict]`) to add `max_cards_per_batch=10, max_batch_context_tokens=120000,
  parent_branch=None`.
- Rationale: the real `def run(...)` (line ~2615) already has all three params with those exact
  defaults; both callers (`mill-plan/SKILL.md` instructions, `millpy-review-plan.py`) already pass all
  three. Purely a doc-accuracy fix — no behavior change.
- Rejected: none — mechanical sync, no alternative design.

## Technical context

- All five fixes live in `plugins/mill/scripts/_plan_validate.py`. Key functions:
  - `_check_context_completeness` (~line 1453) — the check itself; touched by #807, #805, #793.
  - `_PROHIBITION_MARKERS` (~line 1365) — touched by #789 (extend tuple) and #807 (add sibling
    `_CITATION_MARKERS` tuple nearby, same comment style).
  - `run()` (~line 2615) — module docstring (top of file, ~line 9) touched by #796; the call site at
    ~line 2710-2714 (`errors.extend(_check_context_completeness(...))`) touched by #805 to add the new
    `moves_sources` argument; the already-computed local at ~line 2677
    (`moves_sources, moves_targets = compute_moves_union(plan_dir)`) currently only feeds
    `moves_targets` downstream — `moves_sources` is presently dead for this check.
  - `_check_context_completeness`'s docstring (~line 1464-1501) enumerates "Two exemptions" — becomes
    three after #807/#805; update the enumeration text along with the code.
- `compute_moves_union(plan_dir) -> tuple[set[str], set[str]]` in `_review_common.py:848` — returns
  `(moves_sources, moves_targets)`, already imported into `_plan_validate.py` (line 75).
- Error dict shape for `context-completeness` is `{check, batch, card, path, message, line}` — the
  `message` field is what #793 changes; `path`/`line`/`card`/`batch` are unaffected by any of these
  fixes.
- Companion doc file: `plugins/mill/skills/mill-plan/SKILL.md` line ~320, the `context-completeness`
  fix-table row — touched by #793's SKILL.md half.
- No other call sites of `_check_context_completeness` exist outside `run()` (verified via grep) — the
  new `moves_sources` parameter is not a breaking change to any other caller.

## Constraints

No `CONSTRAINTS.md` present at hub root — none apply beyond CLAUDE.md's repo-wide conventions (ASCII
`print()`/`_log()` output, no `sed`, `PYTHONPATH=` verify-command prefix for Python projects — none of
which this task's changes interact with directly).

## Testing

- `plugins/mill/unit_tests/test-plan-validate.py` already has a dense set of `context-completeness`
  tests (`test_check_context_completeness_clean_*` / `_dirty_*`, ~line 1551 onward) — follow this exact
  naming and structure (tempdir fixture, `_make_overview`/`_make_batch_file`/`_write_plan` helpers,
  `_plan_validate.run(plan_dir, project_root)`, filter `result` by `check == "context-completeness"`).
- New tests needed, one scenario each:
  - #807: a `Requirements:` line citing a real file via one of the new `_CITATION_MARKERS` phrases
    (e.g. `"...naming \`mill-config.yaml\` as an example of..."`) → 0 errors. Also add a negative case
    (a `Requirements:` line WITHOUT a citation marker, referencing a real file absent from own refs)
    stays flagged — regression guard that the new tuple doesn't over-exempt.
  - #805: a plan with an earlier batch's card declaring `Moves: \`old.py\` -> \`new.py\`` and a later
    batch's `Requirements:` mentioning `old.py` (not in its own refs) → 0 errors (was 1 before the fix).
    Companion case: the later card mentions `new.py` (the *target*, not source) with no own-ref
    coverage → still flagged, since `moves_targets`-only exemption behavior is unchanged (this
    preserves the existing `test_check_context_completeness_dirty_moves_target_only` test's intent).
  - #793: assert the exact error `message` string contains `"Moves:-source"` (not bare `"Moves:"` with
    no suffix) for the existing dirty-missing scenario.
  - #789: a `Requirements:` line reading `"...do not change \`x.py\`..."` and a second reading
    `"...must not modify \`y.py\`..."`, each referencing a real file absent from own refs → 0 errors
    for both.
  - #796: no automated test practical for a docstring string (no test currently exists for #742's or
    prior rounds' docstring text) — verify manually by reading the updated docstring against
    `def run(`'s real signature.
- All new/changed tests run via the project's Python test runner (see `python-build` skill) — TDD not
  mandated here (mirrors the existing file's convention of test-alongside-fix, not test-first).

## Q&A log

- **Q:** #807 fix approach — marker-substring exemption vs allowlist-of-consuming-verbs vs new
  plan-format annotation field? **A:** [auto-pick] Extend the existing marker-substring exemption
  pattern with a new `_CITATION_MARKERS` tuple. **Why:** matches both concrete #807 repro sentences,
  consistent with the established `_PROHIBITION_MARKERS` architecture and its already-accepted
  false-negative risk tolerance; the allowlist rewrite risks regressing existing passing tests, and a
  new annotation field is disproportionate scope for a heuristic-tuning task.
- **Q:** #807 — which marker phrases populate `_CITATION_MARKERS`? **A:** [auto-pick] `"as an
  example"`, `"as examples"`, `"for example"`, `"e.g."`, `"such as"`, `"cited as"`, `"citing"`.
  **Why:** covers both concrete repro sentences from #807 without reaching for broader phrases
  (`"listing"`, `"named as"`, `"references"`) that would raise false-negative risk beyond what the
  report demonstrated.
- **Q:** #789 — exact substrings to add to `_PROHIBITION_MARKERS`? **A:** [auto-pick] `"never
  change"`, `"not change"`, `"never modify"`, `"not modify"`. **Why:** mirrors the existing two-tier
  "touch" coverage pattern, scoped strictly to the brief's literal wording ("do not change X"/"must
  not modify X") rather than also adding unrequested "edit" variants.
- **Q:** #793 — does the mill-plan/SKILL.md fix-table row wording update belong in this task's scope?
  **A:** [auto-pick] Yes. **Why:** the issue explicitly names both the error message and the fix-table
  row as needing the `Moves:-source` qualifier; fixing only the message would leave the exact
  confusion #793 reports still live in the fixer's mechanical-fix instructions.
- **Q:** Testing approach — per-issue unit tests following the existing per-scenario convention, or a
  single combined smoke test? **A:** [auto-pick] Per-issue unit tests. **Why:** matches
  `test-plan-validate.py`'s established one-test-per-scenario structure; a combined smoke test would
  be harder to pinpoint on regression and inconsistent with the file's existing convention.
