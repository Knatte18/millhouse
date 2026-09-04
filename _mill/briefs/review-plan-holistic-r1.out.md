MILL_REVIEW_BEGIN
# Review: mill-implementer: commit_sha transcription/truncation and final-status-line reliability — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:design] `commit_sha_field_name` override leaves stale `commit_sha` key in output
**Location:** Batch 03, Cards 3/4/5/6. **Issue:** Card 3's fix (`parsed[commit_sha_field_name] = result.stdout.strip()`) only *adds* a key under the new name; it never pops/deletes `parsed["commit_sha"]` when `commit_sha_field_name != "commit_sha"`. Since the conflicts-mode self-report already contains a literal `"commit_sha"` key (per Card 6's own fixture `'{"status":"success","commit_sha":"xyz"}\n'` and `_clean_gate_side_effect`, verified against `_implementer_common.py` lines 1873-1901), the emitted JSON after the override will contain BOTH the stale self-reported `commit_sha` ("xyz"/"abc") AND the new `pre_merge_head`. This defeats the batch's stated purpose (issue #953: stop emitting a misleading `commit_sha`) and makes Card 5's Case 78 (`assert "commit_sha" not in data`) and Card 6's `test_20`/`test_21` (`assertNotIn("commit_sha", data)`) fail against Card 3's own spec'd implementation, so `verify:` in this batch cannot pass as written. **Fix:** Card 3's Requirements must add `parsed.pop("commit_sha", None)` (or equivalent) immediately before/after the `parsed[commit_sha_field_name] = ...` line whenever `commit_sha_field_name != "commit_sha"`, so the override actually renames rather than appends.

### [NIT:consistency] Card 1 quotes an anchor sentence that isn't the paragraph's actual end
**Location:** Batch 01, Card 1 (first insertion, "Never restate commit_sha in prose"). **Issue:** The Requirements say to insert "immediately after the existing paragraph that ends `...never write an unqualified "all complete"/"all done" claim without having actually verified the count this way.`" — but per `implementer-brief.md` lines 142-147, that sentence is not the paragraph's end; the same paragraph continues with one more sentence ("This applies regardless of which model is running this session...") before the blank line at 148. The quoted anchor text doesn't exist as a paragraph boundary. **Fix:** Correct the anchor quote to end with "...independent of whatever the machine-readable JSON status line below says." (the real end of the Card-count self-check paragraph), or drop the mis-quoted anchor and rely solely on the (accurate) "before the paragraph beginning `Your last line of output...`" anchor.

## Verdict

REQUEST_CHANGES
Card 3's field-rename mechanism doesn't strip the old key, breaking Cards 5/6's own regression tests.
MILL_REVIEW_END
