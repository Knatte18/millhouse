MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet) — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently knowable)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:scope] Card 10 Requirements cites `_implementer_common.py` without a Context entry
**Location:** `03-repoint-refs.md`, Card 10. **Issue:** Requirements says not to touch "the literal prefix `mill-go: start batch` that `_implementer_common.py` parses," naming a specific constant from a file that appears in neither `Context:` nor `Edits:` for this card — only `mill-go-base/SKILL.md` is listed. **Fix:** Add `plugins/mill/scripts/_implementer_common.py` to Card 10's `Context:`, or rephrase the caution to cite only the `script-side-prefixes-unchanged` Shared Decision (already plan-wide) without naming the specific file.

### [NIT:consistency] Card 6 Context lists two files that don't exist at that card's execution time
**Location:** `02-thin-variants.md`, Card 6. **Issue:** `Context:` lists `mill-go/SKILL.md` and `mill-go2/SKILL.md`, but the batch's own Batch Scope note states card 6 (writing the variant-contract test) deliberately runs before either file exists — cards 7/8 create them afterward. **Fix:** Drop the two not-yet-created paths from Card 6's `Context:`, since the Requirements text never actually needs their content, or add a note that they are forward references for orientation only.

## Verdict

REQUEST_CHANGES
One Context-completeness gap in Card 10 (BLOCKING); one minor Context-accuracy NIT in Card 6; otherwise thoroughly grounded against source.
MILL_REVIEW_END
