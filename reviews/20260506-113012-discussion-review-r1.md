I have enough information. Let me write the review now.

# Review: 19 (A) — mill-go + scripts infra fixes

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-06
```

## Findings

### [NOTE] Template "last line" language vs new parser
**Section:** Technical context — `implementer-brief.md` / Decision B
**Issue:** `implementer-brief.md` line 63 says "Your last line of output… MUST be a single JSON object" and line 84 says "anything other than this JSON on the last line is a protocol violation." The new regex parser finds JSON anywhere in the output, not strictly the last line. The template would remain stricter than the parser (defensively fine), but the inconsistency isn't noted — a future template reader may be confused about what "last line" means after this change.
**Fix:** Note in the discussion that the "last line" template language is intentionally stricter than the parser and is preserved as-is; or explicitly say the template's "last line" wording will also be updated to "bare JSON" without the positional constraint.

### [NOTE] Builder-lock CLI — mill_dir resolution unstated
**Section:** Technical context — `millpy-builder-lock.py`; Decision A
**Issue:** `_builder_lock.acquire(mill_dir, slug)` takes an explicit `mill_dir`. The CLI synopsis is `acquire <slug>` with no path argument, but the discussion doesn't state how the CLI resolves `mill_dir`. The convention `Path.cwd() / ".millhouse"` is established by `millpy-implement.py` line 93, so a plan writer familiar with the codebase will infer it, but it isn't stated.
**Fix:** Add one line: "Resolves `mill_dir` as `Path.cwd() / '.millhouse'`, consistent with other millpy-* scripts."

## Verdict

APPROVE — all five decisions are made, rationale and rejected alternatives are present, technical context is accurate against source files, and testing scenarios are adequate.