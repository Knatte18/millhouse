# Discussion: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
task: _plan_validate: context-completeness fires on forbidding/explanatory file mentions
slug: plan-validate-context-completeness-gaps
status: discussing
parent: main
```

## Problem

`_plan_validate.py`'s `context-completeness` check scans every backticked path in a plan card's `Requirements:` section and demands it also appear in that card's `Context`/`Edits`/`Creates`/`Deletes`/`Moves` sections, on the theory that any path mentioned in Requirements is a read dependency. That assumption is wrong for paths named only to **forbid** touching them (e.g. "Do not edit `manifest/roadmap.md`") or to **cite** as an example — for those, "add it to Context" inverts the card's actual intent, since Context implies the path will be read/touched.

An exemption mechanism already exists (`_PROHIBITION_MARKERS` / `_CITATION_MARKERS`, lowercased substring match over the Requirements line), but it's an enumerated phrase list that has already been patched twice ("round 2", "round 3" per commit history) and keeps missing real phrasings — most recently "do not add a link to `path`" (issue #814), and more generally any prohibition phrase whose verb isn't one of the ~9 hardcoded tuples (issue #828). Issue #841 is the concrete manifestation: real plan cards get false-positive `context-completeness` errors for paths they explicitly must not touch.

Why now: this blocks `mill-plan` from writing valid plan cards whenever a card legitimately needs to say "don't touch X" — a common and necessary thing for a plan card to say, especially in a self-hosted repo like this one where a task's own `_mill/discussion.md` or `CONSTRAINTS.md` gets mentioned by name for scoping reasons unrelated to being a dependency.

## Scope

**In:**
- Generalize `_PROHIBITION_MARKERS` detection in `_check_context_completeness` (`plugins/mill/scripts/_plan_validate.py:1365-1553`) from an enumerated (negation, verb) phrase-tuple list to a negation-word regex combined with a broader verb list, matched anywhere on the same physical Requirements line as the backtick path token.
- Add regression test coverage for all 9 existing prohibition markers (3 of 9 — `"forbid"`, `"not change"`, `"not modify"` — currently have a test) plus the new verb/negation combinations this fix adds.
- Document the still-unhandled nested-bullet/multi-line prohibition case (see Decisions) as a known limitation, both in a code comment and as a short plan-authoring guidance note in `mill-plan/SKILL.md`.

**Out:**
- `_check_verify_full_suite` / issue #823 (the `verify-full-suite` check contradicting `mill-plan/SKILL.md`'s documented unbounded-`run-all.py` escape hatch, and its missing Step 1.5 fix-table row). Confirmed via direct code read: `_check_verify_full_suite` (`_plan_validate.py:2173-2235`) shares zero helpers, zero data structures, and is wired independently from `_check_context_completeness` in `run()` (lines 2726 vs. 2739) — it operates on batch/overview `verify:` frontmatter, not Requirements prose. This is a separate, doc/logic-only fix and should be its own follow-up task.
- `_CITATION_MARKERS` generalization — no issue reports fragility against citation-marker detection; left as the existing enumerated substring list.
- Fixing the nested-bullet/multi-line prohibition gap (negation word on a parent bullet line, backtick path on a child bullet line) — real and currently untested, but out of scope; see Decisions.
- Any structural/opt-in-marker authoring syntax (e.g. requiring plan authors to write an explicit `<!-- prohibited -->` annotation) — rejected in favor of the regex-generalization approach; see Decisions.

## Decisions

### Prohibition-detection redesign: negation-regex + verb-list, not phrase-tuple enumeration or structural markup

- Decision: Replace the fixed `_PROHIBITION_MARKERS` phrase-tuple list with two word sets — a negation-word set and a verb-word set — and treat a Requirements line as prohibition-exempt if it contains at least one negation word AND at least one verb from the respective sets, anywhere on the line (same line-wide granularity as today's substring match, not positionally adjacent).
  - Negation words (include contractions): `do not`/`don't`, `does not`/`doesn't`, `never`, `must not`, `cannot`/`can't`, `shall not`, `won't`, `forbid`/`forbids`/`forbidden`, plus the existing bare `not`.
  - Verb words: `touch, change, modify, edit, add, link, read, use, reference, include, update, remove, delete, alter, rename, move, create, write, mention, cite`.
- Rationale: matches the issue reporters' own suggested fix direction (#814 explicitly asks for "negation adjacent to any imperative verb rather than an enumerated verb list"), stays within the existing single-function/line-scan architecture (minimal blast radius), and requires no new plan-authoring syntax — important since `mill-plan` writes Requirements prose autonomously and has no mechanism today to emit structural markup. Covers every verb literally cited across the 4 source issues (`edit`, `add`, `link`, `touch`, `change`, `modify`) plus common synonyms, so the fix doesn't require an immediate "round 5" patch for the next synonym.
- Tradeoff (line-wide vs. adjacency-scoped matching): matching negation-word-anywhere-on-line AND verb-word-anywhere-on-line (rather than requiring the two to be adjacent, as the old phrase-tuples implicitly did) trades false positives for a small false-negative risk — a multi-clause Requirements line naming a genuine dependency alongside an unrelated prohibition clause could now be silently exempted from the context-completeness check, which is a worse failure mode (a silently missing Context entry) than the false positives this task fixes. Adjacency-scoped matching (e.g. windowed proximity between negation and verb) was considered and rejected: it reintroduces a tunable with no empirical basis (window size), and Requirements lines are short prose sentences in practice, so unrelated-negation collision risk is low. The regression test suite (see Testing) includes a negative case proving a genuine dependency is not accidentally exempted, as a partial mitigation; this remains a known, accepted tradeoff rather than a fully closed gap.
- Rejected:
  - Enumerating more exact phrase tuples ("round 4" patch, per #814's literal ask): cheapest, but the commit history (`143df532` original, `fc1d20e9` "round 3") shows this pattern has already failed to converge twice; not durable.
  - Structural opt-in marker syntax (per #828's stronger ask): most robust long-term, but requires updating plan-authoring guidance/templates repo-wide and gives `mill-plan`'s prose-generation nothing to hook into without a larger, separate design effort.

### Nested-bullet / multi-line prohibitions: documented limitation, not fixed here

- Decision: Do not attempt to detect prohibitions where the negation word is on a parent bullet line and the backtick path is on a nested child bullet line (e.g. `- Do not touch:\n  - \`foo.py\`\n  - \`bar.py\``). Document this as a known limitation via a code comment near the new regex, and add a short guidance note in `mill-plan/SKILL.md`'s plan-authoring conventions steering the autonomous plan-writer to phrase prohibitions on the same line as the path.
- Rationale: confirmed via direct code read that `_extract_requirements_text` (`_plan_validate.py:1393-1414`) preserves raw physical lines (`"\n".join(collected)`, no collapsing), and `_check_context_completeness`'s marker check is scoped strictly per physical line (`_plan_validate.py:1540-1553`) — so this is a real, currently-untested false-positive gap. None of the 4 source issues report this shape, and fixing it requires indentation/block-aware parsing of the Requirements body — a materially different (larger) change than a same-line regex generalization. Steering `mill-plan`'s own phrasing habits via SKILL.md guidance is a cheap way to avoid triggering the gap in practice, versus a costly parser rewrite for a heuristic already understood to be "iteratively patched, not one-shot" (per its own commit history).
- Rejected: folding a block-aware rewrite into this task — scope creep risk, no reported real-world case.

### #823 (verify-full-suite / SKILL.md contradiction) spun out as a separate task

- Decision: Exclude #823 from this task's implementation. It should become its own single-card follow-up task.
- Rationale: confirmed via direct code read that `_check_verify_full_suite` (`_plan_validate.py:2173-2235`) is wired independently of `_check_context_completeness` in `run()`, operates on a different data source (batch/overview `verify:` frontmatter via `_plan_dag.parse_verify_field`, not Requirements prose), and shares no helpers. Bundling an unrelated doc/logic fix into a behavior-change task would force one plan to carry two logically disjoint batches, weakening scope cohesion for both; spinning it out is cheap in this system (mill-spawn exists for exactly this).
- Rejected: folding it in as a "small extra batch" — rejected because zero code sharing means it buys nothing except a bigger discussion/plan to review.

## Technical context

- Primary file: `plugins/mill/scripts/_plan_validate.py`.
  - `_PROHIBITION_MARKERS` / `_CITATION_MARKERS`: lines 1365-1387 (tuple definitions to be reworked into word-set form for prohibition; citation markers stay untouched).
  - `_PATH_CANDIDATE_EXTENSIONS`: line 1390 — gates which backtick tokens are path-shaped (`.py .go .cs .ts .md .yaml .yml .json`, or anything containing `/`). Not part of this fix's scope but relevant context for how tokens reach the marker check.
  - `_extract_requirements_text`: lines 1393-1414 — extracts the raw `Requirements:` body text between its header and the next `- **Field:**` header, preserving physical line breaks verbatim (no collapsing).
  - `_card_own_reference_set`: lines 1417-1466 — builds the card's own Context/Edits/Creates/Deletes/Moves-source reference set, used to check whether a resolvable path token is already accounted for.
  - `_check_context_completeness`: lines 1528-1596 — main check function. Control flow: extract Requirements body → per line, per backtick token → skip if not path-shaped → skip if line matches a prohibition marker → skip if line matches a citation marker → skip if token doesn't resolve to a real file/plan-DAG target → skip if resolvable token is already in the card's own reference set or plan-wide `moves_sources` → else emit a `context-completeness` error. The marker checks are lines 1547-1553 specifically; only this predicate logic changes for the fix, not the surrounding control flow.
  - `_check_verify_full_suite`: lines 2173-2235 — confirmed independent, out of scope (see Decisions).
  - Wiring in `run()`: `_check_verify_full_suite` at line 2726, `_check_context_completeness` at line 2739 — separate call sites, no shared state.
- History: prohibition/citation marker lists were introduced in `143df532` (5 original markers) and expanded in `fc1d20e9` ("round 3" — added `never change`/`not change`/`never modify`/`not modify` plus the full `_CITATION_MARKERS` block). No commit yet addresses the "do not `<verb>`" generalization or a structural-marker alternative — this task is effectively "round 4", but structurally different (word-set/regex instead of phrase-tuple enumeration) rather than another tuple-list expansion.
- `mill-plan/SKILL.md` around line 189-193 documents the unbounded-`run-all.py` verify escape hatch relevant to the out-of-scope #823; around line 322 is the Step 1.5 fix table that has a `context-completeness` row but no `verify-full-suite` row (also #823, out of scope).
- No `CONSTRAINTS.md` exists at the hub root — nothing to incorporate from it.

## Testing

- Primary test file: `plugins/mill/unit_tests/test-plan-validate.py`.
- TDD candidate: the new negation-word/verb-word predicate function (however `mill-plan` chooses to factor it out of the inline marker check) — write its unit tests first against the word-set membership logic before wiring it into `_check_context_completeness`.
- Existing coverage baseline (do not regress): `test_check_context_completeness_clean_prohibition_marker` (line 1951, `"forbid"`), `test_check_context_completeness_clean_prohibition_marker_change_modify` (line 2411, covers `"do not change"` / `"must not modify"` phrasing — i.e. markers `not change`/`not modify`), `test_check_context_completeness_clean_citation_marker` (line 2209), `test_check_context_completeness_dirty_citation_marker_absent` (line 2241), plus the general structural tests (`_clean_in_context/_edits/_creates/_deletes/_moves_source`, `_dirty_missing`, `_dirty_missing_scoped_to_own_card`, `_clean_non_path_token`, `_clean_unresolvable_token`, `_dirty_moves_target_only`, `_run_wiring_no_false_positives`, `_clean_line_range_suffix_in_context`, `_dirty_line_range_suffix_missing`).
- New scenarios to cover (currently zero coverage on all of these):
  - Each of the 6 currently-untested existing markers individually: `never touch`, `must not touch`, `do not touch`, `not touch`, `never change`, `never modify` (plus keep the existing `forbid`, `not change`, and `not modify` tests passing).
  - New verb/negation combinations added by this fix: `do not edit`, `do not add`, `do not link`, `do not read`, and at least one contraction form (`don't touch`).
  - A negative/regression case proving a genuine dependency mention is *not* accidentally exempted by the broadened word sets (e.g. a line containing an unrelated negation word plus a path that is genuinely a read dependency, still fires context-completeness).
  - Explicitly do **not** add a test asserting correct handling of the nested-bullet/multi-line case — it's a documented known limitation (see Decisions), not a target behavior for this task.

## Q&A log

- **Q:** How should prohibition detection be generalized — enumerate more phrase tuples, negation-regex + broader verb list, or structural opt-in markup? **A:** [auto-pick] Negation-regex + broader verb list (line-wide match, no positional adjacency requirement). **Why:** matches the issue reporters' own suggested direction, stays within the existing single-function architecture, avoids the syntax-migration cost of structural markup, and is materially more general than the enumerate-more-phrases approach that already failed to converge twice.
- **Q:** Should the negation-word set include contractions (`don't`, `doesn't`, `can't`, `won't`)? **A:** [auto-pick] Yes. **Why:** zero-cost to include; excluding it just reproduces a #814-shaped gap under a different name.
- **Q:** Should #823 (verify-full-suite / SKILL.md contradiction) be folded into this task? **A:** [auto-pick] No — spin out as a separate task. **Why:** confirmed zero shared code/data with context-completeness; bundling would force one plan to carry two logically disjoint batches.
- **Q:** Should `_CITATION_MARKERS` get the same regex generalization proactively? **A:** [auto-pick] No — leave untouched. **Why:** no issue reports fragility against citation markers; expanding scope to unreported code violates YAGNI.
- **Q:** Should known heuristic limitations (e.g. double negatives, nested bullets) be explicitly documented? **A:** [auto-pick] Yes — as a "Known limitations" note plus code comment, without attempting to solve them in this task. **Why:** the repeated "round 2/round 3" patch history shows this heuristic keeps getting re-litigated; an explicit note gives the next round a starting point.
- **Q:** Should this task also fix the newly-discovered nested-bullet/multi-line prohibition gap? **A:** [auto-pick] No — document as a known limitation only. **Why:** none of the 4 source issues report this shape; fixing it requires indentation/block-aware parsing, a materially bigger change than the same-line regex generalization already scoped.
- **Q:** Finalize the verb list for the new negation regex? **A:** [auto-pick] `touch, change, modify, edit, add, link, read, use, reference, include, update, remove, delete, alter, rename, move, create, write, mention, cite`. **Why:** covers every verb in the 4 issues' repro text plus common synonyms; marginal cost of a broader list is near zero versus needing another patch round for the next synonym.
- **Q:** Confirm the regression-test set: untested existing markers, new verb/negation combos, and known-limitation documentation? **A:** [auto-pick] Yes, this set. **Why:** 6 of 9 existing markers have zero test coverage regardless of this fix; closing that alongside the new gap is the same order of effort and prevents further "marker exists but untested" drift.
- **Q:** Where should the nested-bullet limitation be documented? **A:** [auto-pick] Both a code comment near the regex and a short guidance note in `mill-plan/SKILL.md`'s plan-authoring conventions. **Why:** `mill-plan` generates the Requirements prose in the first place — steering its phrasing habits sidesteps the gap rather than just documenting it after the fact.
- **Q:** [Discussion review r1 gap] The new negation/verb word sets omit `forbid`, breaking the existing `test_check_context_completeness_clean_prohibition_marker` test — how to fix? **A:** [auto-pick] Add `forbid`/`forbids`/`forbidden` to the negation-word set (no separate special-case predicate needed, since the existing test sentence already contains a verb). **Why:** keeps a single unified word-set design rather than reintroducing a second, special-cased code path for one word.
