MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] Card 1 names `resolve_existing_paths` from a file absent from its own Context:/Edits:
**Location:** batch `symbol-reference-check`, card 1, step 3.
**Issue:** Requirements prose says candidate-root precedence must mirror `` `resolve_existing_paths` ``'s own precedence, citing `` `_review_common.py:1023` `` by line — but card 1's `Context:` is `none` and `Edits:` lists only `_plan_validate.py`, so `_review_common.py` is nowhere in this card's own-refs. Per this check's own contract, the implementer must cold-start-explore to verify the mirrored precedence.
**Fix:** Add `_review_common.py` to card 1's `Context:`, or explicitly state (as card 4 does for its own citation) that the precedence is fully restated inline and no read is required.

### [BLOCKING:design] No encoding/error-handling policy for the new arbitrary-source-tree read
**Location:** batch `symbol-reference-check`, card 1, step 3 (`_resolve_symbol_files`).
**Issue:** The walk reads every matching-extension file's "text content" with no stated encoding or exception policy. Unlike every existing `read_text(encoding="utf-8")` call in this file (which only reads controlled plan/batch markdown), this walk reads arbitrary real-world project source trees; a single non-UTF-8 or unreadable file anywhere under the search root raises `UnicodeDecodeError`/`OSError` and crashes the entire `_plan_validate.py` run for every plan in that project.
**Fix:** Specify a decode-error policy (e.g. `errors="replace"`) and/or a try/except-skip-file fallback in card 1's Requirements.

### [NIT:design] Trailing-segment rule can return a non-qualifying search key
**Location:** batch `symbol-reference-check`, card 1, step 2(e).
**Issue:** When a 2-segment token has only its FIRST segment qualify (e.g. `Foo.bar`, where `bar` is plain lowercase), the algorithm still unconditionally returns the trailing segment (`"bar"`) as the search key — a word that would not itself pass the qualify gate. No card 2/3 test covers this shape; the algorithm's own filtering intent is inconsistently applied.
**Fix:** Either require the returned trailing segment to itself qualify (fall back to `None` otherwise), or add a test/note documenting this as an accepted trade-off.

### [NIT:scope] C# angle-bracket generics unhandled by the call/generic-suffix stripper
**Location:** batch `symbol-reference-check`, card 1, step 2(b).
**Issue:** Suffix stripping only handles trailing `()`/`[...]` groups. `.cs` is included in `_SYMBOL_SEARCH_EXTENSIONS`, but a C#-style token like `` `GetItems<T>()` `` retains the `<T>` after stripping, fails the shape regex, and is silently never treated as a symbol candidate.
**Fix:** Note this as an accepted limitation (mirroring the "Known limitations" doc pattern already used for `_is_prohibition_exempt`), or extend suffix-stripping to angle-bracket groups.

## Verdict

REQUEST_CHANGES
Card 1 cites an external function without listing its file, and omits a read-failure policy for tree-wide file reads.
MILL_REVIEW_END
