# Batch: discussion-review-tooling-claim-consistency-check

```yaml
task: 'mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies'
batch: discussion-review-tooling-claim-consistency-check
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-discussion-flow.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #812: a discussion.md's Testing section once asserted `PYTHONPATH=` was NOT needed for a grep-only `verify:` command — the opposite of `_plan_validate.py`'s actual, correct enforcement (which requires the prefix on every `verify:` command whenever any Python marker file exists in the project, per CLAUDE.md's documented rule verbatim) — and this false claim passed three discussion-review rounds unchallenged. The existing `consistency` finding class already covers "violates an established repo convention" in principle, but the reviewer was never specifically prompted to fact-check tooling/validator claims against source. The fix adds one explicit Criteria bullet to `review-discussion.md` instructing exactly that cross-check, generalizing beyond this one historical phrase to any future similarly-shaped false claim about tooling behavior.

External interface: none — this is a reviewer-prompt template addition, consumed only by the discussion-review LLM prompt at review time. Self-contained batch.

## Cards

### Card 11: add tooling/validator claim cross-check to the Criteria section

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/templates/review-discussion.md`'s `## Criteria (apply briefly to each)` section (lines 23-36), insert a new bullet immediately after the existing `- **Constraint coverage** — CONSTRAINTS.md items acknowledged; implicit perf/compat constraints stated.` bullet (lines 28-29) and before the existing `- **Failure modes** — empty states, concurrency, invalid input, partial failures addressed.` bullet (line 30):
  ```
  - **Tooling/validator claims** — any testing-plan claim about tooling, validator, or command-prefix requirements (e.g. `PYTHONPATH=`) must be cross-checked against CLAUDE.md and the actual enforcement (e.g. `_plan_validate.py`); a contradiction is `[BLOCKING:consistency]`.
  ```
  Do not modify any other bullet in the Criteria section, and do not modify the four-class rubric (`design`/`scope`/`decision`/`consistency`) at lines 93-105 — the new bullet uses the existing `consistency` class (already defined broadly enough to cover this case, per the discussion's Rationale), so no rubric change is needed.
- **Commit:** `feat(review-discussion): add tooling/validator claim cross-check criterion (#812)`

### Card 12: regression test asserting the new Criteria bullet is present

- **Context:**
  - `plugins/mill/templates/review-discussion.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new standalone function `test_criteria_section_has_tooling_claim_consistency_bullet() -> int` to `test-review-discussion-flow.py`, following the file's existing standalone-`test_xxx() -> int`-function convention (see `test_brief_path_nested_layout` at line 1475 and `test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path` at line 1620 for the exact style — direct file read, `print("FAIL: ...", file=sys.stderr); return 1` on failure, `print("PASS: ...")`; `return 0` on success). This is a direct template-file read-and-string-assertion, independent of this file's existing `_review_discussion.prepare`/`_review_discussion.run` fixture-based tests (which mock `prompt_text` as a literal `"prompt"` stub and never assert on rendered template content) — no wiki/worktree fixture, no `_make_fixture` call, no LLM invocation needed.

  Function body: read `HUB / "plugins" / "mill" / "templates" / "review-discussion.md"` (the module-level `HUB` constant already defined at line 20) as text. Assert the text contains the literal substring `**Tooling/validator claims**`. Assert the text also contains `PYTHONPATH=` within that same bullet's line (grep the line starting with `- **Tooling/validator claims**` and check `PYTHONPATH=` appears on it) — this pins the concrete example named in the discussion's Decision, not just the bullet's presence. On either assertion failing, `print(f"FAIL: test_criteria_section_has_tooling_claim_consistency_bullet: ...", file=sys.stderr)` and `return 1`; otherwise `print("PASS: review-discussion.md Criteria section has tooling/validator claim consistency bullet")` and `return 0`.

  Register the new function in `main()` by adding `errors += test_criteria_section_has_tooling_claim_consistency_bullet()` immediately after the existing `errors += test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path()` call (`test-review-discussion-flow.py:1435`).
- **Commit:** `test(review-discussion): assert Criteria section carries tooling/validator claim bullet (#812)`

## Batch Tests

`verify:` runs `test-review-discussion-flow.py` directly (single file). Card 12's new standalone test is a direct, LLM-free assertion against the rendered template text added by Card 11.
