MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Residual `<OUTPUT_FILE>` token contradicts the no-token constraint
**Section:** Technical context → Authoritative edit set (Groups 1 and 5); `reviewer-write-grant-scoped-to-briefs`; Q&A ("Who substitutes the `<OUTPUT_FILE>` token")
**Issue:** `output-path-in-prepare-envelope` bans `<OUTPUT_FILE>` outright ("never by a `<TOKEN>`"; the footer carries the literal path), yet Group 1 still says to reword `mill-implementer.md:20` "to name `<OUTPUT_FILE>` explicitly", Group 5 still says "`write_brief` owns `<OUTPUT_FILE>` substitution", the reviewer-grant Decision cites "the explicit `<OUTPUT_FILE>` path in the brief", and the Q&A still asks who substitutes the token — agent definitions are static text never passed through `_render`, so a literal `<OUTPUT_FILE>` shipped in `plugins/mill/agents/mill-implementer.md` would reach the model unsubstituted.
**Fix:** Purge the token from all four residual sites: the agent defs and `write_brief` name the report file *by description*, and the literal absolute path arrives only in the footer.

### [GAP] `build_tool_rule`'s new flag has no stated default; a red test is unlisted
**Section:** `output-contract-is-agent-mode-only`; Technical context → Group 6
**Issue:** The Decision says `build_tool_rule` "takes the existing `mode` plus a flag" but never says whether that flag is defaulted. `plugins/mill/unit_tests/test-review-common.py` calls it positionally with one arg at `:615`, `:652`, `:690`, `:691`, `:695`, `:2828`, `:2880` — a required second parameter makes all seven raise `TypeError`, and that file is absent from Group 6's "5 files that go red", so the file count and the "verify goes red otherwise" claim are both wrong under that reading.
**Fix:** State that the flag defaults to `False` (non-agent), mirroring `prepare()`; confirm `test-review-common.py` therefore stays green, or add it to Group 6 and bump the count.

### [GAP] Prepare-envelope carve-out list omits the plan-validator and error envelopes
**Section:** `output-path-in-prepare-envelope` (carve-out); Testing → "Prepare-envelope shape"
**Issue:** The Decision names `dispatch_needed: false` as the *only* envelope without `output_path`, and the shape test is specified as "`output_path` present … for every prepare-emitting CLI" with one converse case. But `millpy-review-plan.py:142-147` emits `{"errors": [...], "summary": ...}` from its `--stage prepare` branch (exit 1, no brief — consumed by `mill-plan/SKILL.md:158-159`), and all three review CLIs emit `print_error_envelope` from the same branch — none can carry `output_path`.
**Fix:** Name these as additional carve-outs and scope the shape assertion to brief-emitting success envelopes only.

### [NOTE] Template "Source-grounding rule" is a tool statement outside `build_tool_rule`
**Section:** Technical context → Group 2
**Issue:** Group 2's principle is that "all tool permissions must live in `build_tool_rule` and nowhere else", but `plugins/mill/templates/review-discussion.md:21` statically asserts "You are in tool-use mode — … open it with Read/Grep/Glob" (already false for a `bulk` reviewer today), and the sweep entry only mentions the `:1-4` header.
**Fix:** Include the source-grounding paragraph in the Group 2 sweep, or note explicitly that it is left as-is.

### [NOTE] Host files for the new tests are outside the enumerated 29
**Section:** Testing
**Issue:** Testing mandates six new suites (four-cell `build_tool_rule`, no-token regression, stale-`.out.md`, shape test, conformance sweep, unescape round-trip), but the edit set enumerates only contract-carrying files plus tests that go red, and is declared "the only file count in this document" against which the conformance test asserts.
**Fix:** State that new/extended test files are additive and not bounded by the 29, and name where the four-cell and conformance tests live.

## Verdict

GAPS_FOUND
Three concrete inconsistencies remain: stale `<OUTPUT_FILE>` references, an undefaulted flag, an incomplete carve-out list.
MILL_REVIEW_END
