MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-12
```

## Findings

### [BLOCKING] finalize never raises ReviewError — ERROR-envelope rationale is wrong
**Location:** Batch 2, cards 9(c) / 10(c) / 11(c), and card 12(b)
**Issue:** All three backends already swallow parse failures: `_review_discussion.py:146-164`, `_review_code.py:547-559` and `_review_plan.py:568-575` catch `ReviewError` from `finalize_scope` and **return** an ERROR `ReviewResult`/entry, so the CLI prints it via `result.to_dict()` and exits **0** — `print_error_envelope` is never reached and `except ReviewError` never fires on an empty `raw_text`.
**Fix:** Correct the rationale (the ERROR envelope comes from the backend's own ERROR result, exit 0), and rewrite card 12(b)'s prescribed mock — a `finalize` `side_effect` that re-raises `ReviewError` pins behaviour the real system does not have, and its `return code == 1` assertion is fiction.

### [BLOCKING] Card 12/13 mocking discipline is unrunnable as written
**Location:** Batch 2, card 12 ("use the real `_review_common`"), card 13 (same)
**Issue:** With the real `_review_common`, the CLIs call `find_active_slug` (raises `ReviewError` → exit 1 before finalize/prepare in a tempdir with no marker/branch) and `resolve_path`, which internally calls `_paths.resolve_git_root()` / `resolve_active_hub` on the **real** `_paths` bound at `_review_common` import time (`_review_common.py:353-375`) — env-dependent, and against repo convention (no real git in unit tests).
**Fix:** Keep `ReviewError`, `parse_verdict` and `print_error_envelope` real, but pass `--slug <slug>` and patch `load_config` / `resolve_path` as **attributes on the real `_review_common`** rather than mocking only `_paths`/`_reviewers`/backend.

### [BLOCKING] Batch 3's verify does not cover the five template edits
**Location:** Batch 3, Batch Tests ("`test-render.py` is the regression net ... catches an accidentally-introduced `<UPPERCASE>` token")
**Issue:** `test-render.py` renders only `tempfile` fixtures (`test-render.py:16-96`); it never reads `plugins/mill/templates/`. Cards 15 and 16 therefore ship with **zero** automated coverage in their own batch — verify stays green on a template that no longer renders, and detection is deferred to batch 5.
**Fix:** Either land card 22(b)'s "every template still renders" assertion in batch 3 (a small new/extended test in its verify set), or drop the false claim and state plainly that template edits are gated only at batch 5.

### [NIT] `_review_plan.run()` does not call `prepare()`
**Location:** Batch 2, Batch Scope + card 8
**Issue:** The scope text says `run()` "calls that same `prepare()`" — true for discussion (`_review_discussion.py:215`) and code (`_review_code.py:629`), but `_review_plan.run()` (`:594`) re-renders inline and has its **own** `build_tool_rule` call at `:836`. Card 8 also labels `:836` as "`run()`", which is the call, not the def.
**Fix:** Reword the scope note and cite `_review_plan.py:594` (def) / `:836` (inline `build_tool_rule` inside `run`) so the implementer does not go looking for a `prepare()` call that is not there.

### [NIT] Context gaps in batch 5
**Location:** Batch 5, cards 21 and 22
**Issue:** Card 21's Requirements assert against `mill-implementer.md`'s `tools:` line, but that file is not in its `Context:`; card 22(b) must render each of the five review templates with its full token set, but `plugins/mill/templates/` is absent from card 22's `Context:`.
**Fix:** Add `plugins/mill/agents/mill-implementer.md` to card 21's `Context:` and the five template paths to card 22's.

### [NIT] Card 1 `Context:` lists `_paths.py` with no use
**Location:** Batch 1, card 1
**Issue:** `output_path_for` is pure `pathlib`; nothing in the card's Requirements touches `_paths`.
**Fix:** Drop `_paths.py` from card 1's `Context:` (or state the purpose, e.g. the `sanitize_filename_component` naming rule it must stay consistent with).

## Verdict

REQUEST_CHANGES
Contract design is sound; two test cards rest on false backend claims and batch 3 is unguarded.
MILL_REVIEW_END
