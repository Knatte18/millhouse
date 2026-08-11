MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] ERROR-parse-failure branch's "no review file" premise is false
**Section:** "Duration on the exception/error path" Decision (parse-failure / `except ReviewError` case).
**Issue:** The Decision states duration is "envelope/print-only — no yaml-header injection happens for a round that produced no review file at all," but this premise is contradicted by source: `_review_code.py::run()`'s `except ReviewError` branch (lines ~697-718, ~761-782) and `_review_discussion.py`'s equivalent (line ~193) both call `write_review_file()` and persist the raw (unparsed) reviewer text to disk with `"file": str(path)` — a real file exists. `_review_plan.py` is internally inconsistent on this same point: its per-batch `ReviewError` branch at line ~331 sets `"file": None` (no file), while its other `ReviewError` branches at lines ~664 and ~1145 also call `write_review_file()` and set `"file": str(path)`. So "no review file at all" holds for only one of at least five `ReviewError` call sites across the three backends; the other four leave a raw-text file on disk with no `duration_s` ever considered for it.
**Fix:** Correct the Decision to acknowledge that the parse-failure branch frequently does write a raw review file (distinct from the call-failure/`LLMError` branch, which genuinely never writes one), and explicitly decide whether that raw file should also receive `duration_s` (e.g. via the same find-or-inject helper, tolerant of a malformed/absent yaml fence) or is deliberately left bare — plus flag the pre-existing `_review_plan.py` file/no-file inconsistency across its own `ReviewError` branches as something the implementer should not silently paper over.

## Verdict
REQUEST_CHANGES
The exception-path Decision's "no review file" premise is contradicted by source in most of the actual call sites it describes.
MILL_REVIEW_END
