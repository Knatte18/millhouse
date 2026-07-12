MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Stale `.out.md` is never truncated on re-dispatch
**Section:** `subagent-writes-its-own-out-md` / `missing-out-md-defers-to-git-state`
**Issue:** Today the orchestrator rewrites `&lt;brief&gt;.out.md` immediately before every `finalize` (`mill-go/SKILL.md:149`, `:163`), so the file is always fresh; deleting that Write removes the freshness invariant, and nothing in the codebase unlinks or truncates `.out.md` (grep for `unlink` across `scripts/` shows no `.out.md` deletion). A transient retry (step 4(a): "re-dispatch once immediately using a fresh brief and session") and the warm-`SendMessage` resume both reuse the same role/scope/round, hence the **same** `.out.md` path — so if attempt 1 wrote the file and attempt 2 dies before writing, `finalize` reads attempt 1's output as attempt 2's result. The missing-file guard only covers *absent* and *empty*, not *stale*.
**Fix:** State that the `.out.md` is removed at brief-write time (natural home: `write_brief`, already the sole owner of the path), so a dead agent yields a genuinely absent file and routes into `missing-out-md-defers-to-git-state`; add a test asserting a pre-existing `.out.md` does not survive a re-prepare.

### [GAP] Reviewer finalize has no backstop against a stale verdict
**Section:** `missing-out-md-defers-to-git-state`
**Issue:** The decision leans on the git-state recount to make a bogus report survivable, but that backstop exists **only** for implementer/fixer/merge-in. The review CLIs parse the verdict straight out of the file text, so a stale same-round `.out.md` (per the finding above) is consumed as the current round's verdict — a killed-then-retried reviewer that wrote `APPROVE` before dying would hand mill-start/mill-plan a green verdict no live reviewer produced. This is the false-success class the discussion elsewhere guards against (#574).
**Fix:** Name the reviewer case explicitly — either the truncation above, or a freshness check (e.g. `.out.md` mtime newer than the brief) at the three review read sites — and add it to the `finalize` missing/empty test matrix as a third "stale" case.

### [GAP] Edit set omits a fifth test pinned to `write_brief`'s return
**Section:** Technical context — "Authoritative edit set — 28 files", Group 6
**Issue:** Group 6 names only `test-agent-dispatch.py:86-164` as pinning the single-`Path` return, but `unit_tests/test-agent-mode-dispatch.py:370-377` also calls `write_brief(...)` and then `brief_path.exists()`; once `write_brief` returns the brief path **and** the output path, that call goes red too. The document declares this list the single authoritative enumeration and has a conformance test asserting against it, so the list and the file count (28 → 29) are both wrong as written.
**Fix:** Add `unit_tests/test-agent-mode-dispatch.py` to Group 6 and correct the count.

### [NOTE] `_review_plan.py:196`'s disposition is left ambiguous
**Section:** `output-contract-is-agent-mode-only`
**Issue:** The Decision lists `_review_one_batch` (`:196`) alongside `prepare()` and `run()` but then says only "the `run()`-side call must keep the non-agent rule", naming `:836`. `_review_one_batch` is reached solely from `run()` (submitted to a `ThreadPoolExecutor` at `_review_plan.py:752`), so `:196` is also full-path-only and must keep the non-agent rule.
**Fix:** Say so explicitly, so a plan writer does not thread the agent-mode flag into `_review_one_batch`.

### [NOTE] Plan-review batch scope is dispatchable but inventoried as holistic-only
**Section:** Technical context — dispatch inventory
**Issue:** The table lists plan review as `--holistic-only`, yet `_review_plan.prepare()` takes `scope: str | None` and has a batch-scope `build_tool_rule` call at `:401`, so a batch-scope prepare is reachable.
**Fix:** Confirm agent-mode plan review is holistic-only in practice, or note that both prepare callsites carry the flag regardless.

## Verdict

GAPS_FOUND
Deleting the orchestrator's Write drops the `.out.md` freshness guarantee; stale-file handling is unspecified.
MILL_REVIEW_END
