MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: C:\Code\millhouse\wts\explore-fork-agent-opportunities\_mill\discussion.md
date: 2026-07-12
```

## Findings

### [GAP] `&lt;OUTPUT_FILE&gt;` in templates breaks `_render.render`
**Section:** `output-path-in-prepare-envelope` ("Who substitutes what"), Authoritative edit set Groups 2 &amp; 3
**Issue:** The design puts a literal `&lt;OUTPUT_FILE&gt;` token *inside* the five brief templates and five review templates, but `_render.render` (`plugins/mill/scripts/_render.py:35,103-105`) matches `&lt;[A-Z][A-Z0-9_]*&gt;` and raises `KeyError: Unresolved template tokens` for any token absent from the caller's `values` dict — and every brief/review prompt is rendered through it (`millpy-implement.py:533`, `millpy-fix.py:402,468`, `millpy-merge-in-subagent.py:339,418`, `_review_common.py:1359`). Rendering therefore hard-fails *before* `write_brief` — which is stated to be the sole owner of the path — ever runs; `millpy-implement.py:555` documents exactly this strictness. The `--stage full` path renders the same review templates and has no brief path to supply at all.
**Fix:** Decide the substitution mechanism explicitly: either every render callsite passes a placeholder `OUTPUT_FILE` value that `write_brief` post-substitutes, or the templates carry no `&lt;TOKEN&gt;`-grammar marker at all and the output-contract text is appended only as a `write_brief` footer (which also keeps `--stage full` clean).

### [GAP] `test-agents-defs.py` pins the reviewer's read-only tool list
**Section:** Authoritative edit set, Group 6 ("existing tests that pin the old behaviour — 3 files")
**Issue:** `plugins/mill/unit_tests/test-agents-defs.py:60-69` asserts `mill-reviewer` tools are **exactly** `{Read, Grep, Glob}` and that `Write` is absent (`mutating = {"Edit","Write","Bash","NotebookEdit"}`). Granting `Write` turns this test red, and it is listed in neither the 27-file edit set nor Group 6, so the plan writer will create a batch whose verify fails.
**Fix:** Add it to Group 6 (count becomes 28 / Group 6 = 4 files) and state the intended new assertion — exactly `{Read, Grep, Glob, Write}` with `Edit`/`Bash`/`NotebookEdit` still forbidden — since this test *is* the reviewer safety invariant, not incidental scaffolding.

### [GAP] Q&amp;A log contradicts the agent-mode-only carve-out
**Section:** Q&amp;A log (the "Are the `subprocess`/`psmux` dispatch paths a constraint?" entry — "**A:** No — they are dead in practice")
**Issue:** That answer directly contradicts the `output-contract-is-agent-mode-only` Decision, the Scope "Out" bullet ("`--stage full` is **not** dead"), and the later Q&amp;A entry that reverses it. The discussion is the self-contained input to a zero-history plan session, and the stale entry endorses precisely the global prompt change that would break the reviewer's API-error fallback.
**Fix:** Delete or rewrite the stale entry so the Q&amp;A log agrees with the Decision.

### [NOTE] `mill-go/SKILL.md:123` omitted from the affected-edits list
**Section:** `ack-is-the-completion-discriminator` → "Affected edits in `mill-go/SKILL.md`"
**Issue:** `:123` says "Read the subagent's final message from the notification payload — that is the text used in steps 4 and 5 below"; step 5 is deleted, so the line is stale and still instructs reading the full message. The enumerated list covers 4(a), 4(b), 5, 6, 6.5 and `:135` but not `:123`.
**Fix:** Add `:123` to the mill-go edit list (reword to "used in step 4's classification only").

### [NOTE] Duplicate missing-`.out.md` Q&amp;A entries
**Section:** Q&amp;A log
**Issue:** Two near-identical entries answer "what happens when `.out.md` is missing/empty", one attributing the #574 catch to "review" and the other to "round-1 review".
**Fix:** Collapse into one entry.

## Verdict

GAPS_FOUND
Token-substitution design is unbuildable as written; one pinned test missing from the edit set.
MILL_REVIEW_END
