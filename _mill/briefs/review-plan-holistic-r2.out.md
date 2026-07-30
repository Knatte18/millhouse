MILL_REVIEW_BEGIN
# Review: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: plan/
date: 2026-07-30
```

## Findings

### [BLOCKING] `_requirements_fence_aware_body` boundary loop likely self-terminates on the header line
**Location:** Batch 01 / Card 1, item 3 (`_requirements_fence_aware_body`)
**Issue:** The spec says: locate the `Requirements:` header's own line index, then "from the found index, walk forward... collect lines until (a) a line matches `^-\s*\*\*[A-Za-z]+:\*\*` while `in_fence` is False." The header line itself (`- **Requirements:**`) matches that same stop-condition regex. Read literally, the very first line visited (the header, at the found index) triggers stop-before-this-line, yielding an empty collected result for every card — the fence regex then finds zero fences and the check silently never fires for any card, defeating the entire task.
**Fix:** Explicitly mirror `_extract_requirements_text`'s pattern: unconditionally append the header line to the result first, then run the boundary/`in_fence` check starting at index+1, not at the header's own index.

### [NIT] Module-level fence regex constant left unnamed
**Location:** Batch 01 / Card 1, item 4
**Issue:** Every other module-level regex constant used by this check (`_RE_REFS_HEADER`, `_RE_REFS_SUB`, etc.) is given an explicit `_RE_*` name in the plan; the new fence-body regex (`` re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL) ``) is described only by its pattern, with no name specified.
**Fix:** Name it explicitly (e.g. `_RE_FENCE_BODY`) so Card 3's tests and Card 1's own body text reference a stable identifier.

## Verdict

REQUEST_CHANGES
Card 1 item 3's boundary-scan spec risks making the new check a permanent silent no-op; everything else verified byte-accurate against source.
MILL_REVIEW_END
