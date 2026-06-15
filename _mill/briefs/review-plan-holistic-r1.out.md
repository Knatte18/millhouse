No existing usage — clean addition. Now I have enough to write the review. Let me also confirm the global step numbering: Batch 1 cards 1-3, Batch 2 cards 4-7. Sequential, no gaps. Good.

Let me double-check the Batch Index DAG integrity: batch 1 (filename-sanitization, file 01-filename-sanitization.md, depends-on []), batch 2 (skill-injection, file 02-skill-injection.md, depends-on [1]). Both files exist. No cycle. Good.

MILL_REVIEW_BEGIN
# Review: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [BLOCKING] test-agents-defs.py never runs under run-all.py
**Location:** Batch 2 / Card 7 (and batch-2 `verify:`)
**Issue:** `test-agents-defs.py` has no `if __name__ == "__main__"` block and no `main()` — `run-all.py` invokes each test via `subprocess.run([sys.executable, test])`, so this file imports its two `test_*` functions and exits 0 without ever calling them. Card 7's only guard against breaking `mill-implementer.md` frontmatter is therefore a silent no-op; the verify cannot catch a regression.
**Fix:** Card 7 must add a `__main__` runner block to `test-agents-defs.py` that invokes both test functions (mirroring the runner in `test-agent-dispatch.py`), and list that file under the card's `Edits:` and `Context:`.

### [BLOCKING] parse_batch_refs includes Context: (read-only) files in language detection
**Location:** Batch 2 / Card 4; Shared Decision `targeted-skill-injection`
**Issue:** The decision says the directive is "built from the batch's actually-touched files," but `parse_batch_refs` (in `_review_common`) returns the union of `Context:` + `Edits:` + `Creates:` + `Deletes:` tokens. `Context:` files are read-only references, not touched. A batch editing only `.py` but listing a `.go` file in `Context:` would be told to load `golang-comments`/`golang-testing` — a false directive contradicting the decision.
**Fix:** Card 4 must derive languages only from `Edits:`/`Creates:` tokens (the touched set), not the full `parse_batch_refs` union — either by filtering or by a dedicated extraction; update Requirements to name the specific lists used.

### [NIT] Card 5/6 token-comment edit not in a stable identifier
**Location:** Batch 2 / Cards 5, 6
**Issue:** Requirements say "add `<LANGUAGE_SKILLS>` to the token list inside the leading HTML comment" — fine — but the placement instruction "just before `## Implementation discipline`" / "`## Fix discipline`" is the only anchor; both templates have that heading, so this is adequately stable.
**Fix:** Optional: name the exact inserted heading (e.g. `## Required skills`) so the section is identifiable across rounds.

### [NIT] Card 3 inline-snippet match string must be exact
**Location:** Batch 1 / Card 3
**Issue:** Requirements quote the inline expression to replace as `.replace(":", "-").replace("/", "-").replace("\\", "-")`. The source (millpy-implement.py lines 189, 210) matches verbatim, so the card is correct; just confirm both occurrences are replaced (finalize branch + prepare/full branch).
**Fix:** None needed; the two sites are accurately described.

## Verdict

REQUEST_CHANGES
Card 7's verify is a no-op (no test runner); Card 4 detects Context-only languages, violating the touched-files decision.
MILL_REVIEW_END
