I have completed my review. The plan is thorough, well-grounded in the discussion, and verified against source. All claims about source APIs check out. Below are my findings.

MILL_REVIEW_BEGIN
# Review: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [NIT] Card 5 cites mill-fold/SKILL.md but omits it from Context
**Location:** Batch 3, Card 5
**Issue:** Requirements say "mirror how `mill-fold/SKILL.md` documents its invocation forms," but `mill-fold/SKILL.md` is not in Card 5's `Context:` list (Card 6 includes it; Card 5 does not).
**Fix:** Add `plugins/mill/skills/mill-fold/SKILL.md` to Card 5's Context, or drop the cross-reference and point at `mill-ghissues-to-tasks/SKILL.md` (already in Context) for the invocation-doc pattern.

### [NIT] "matching /mill-fold's output" for fold-ins is imprecise (brief vs body)
**Location:** Overview Shared Decision "per-Sources-bullet rendering"; Batch 2, Card 4 Step 5
**Issue:** `millpy-fold.py` appends `- Sources: #N — <title>` to the task **brief** (`upsert_task(..., brief=...)`), whereas today's `mill-ghissues-to-tasks` and this plan append to **body**. The bullet *string* matches /mill-fold; the rendered location does not.
**Fix:** Confirm body is the intended target (it is — preserves ghissues parity) and soften the "matching /mill-fold's output today" wording to "matching /mill-fold's bullet string format," to avoid implying brief-placement parity.

### [NIT] _sandbox_report tests omit the top-level-not-a-dict case
**Location:** Batch 1, Card 2 (test cases 1–7)
**Issue:** `read()` requires the parsed top-level value to be a dict (else `data.get("source")` raises `AttributeError` on a list/string), but no listed test covers a valid-JSON-but-non-object top level.
**Fix:** Add one test: a file whose JSON top level is a list (or string) → `read()` raises `SandboxReportError`, not an uncaught `AttributeError`.

### [NIT] _paths.* used in skill cards without a Context entry
**Location:** Batch 2 Card 4; Batch 3 Card 5; Batch 4 Card 6
**Issue:** Cards reference `_paths.resolve_wiki_path` / `_paths.resolve_git_root` but `_paths.py` is not in their Context. Mitigated because the exact `python -c` call pattern is visible in the in-Context `mill-ghissues-to-tasks/SKILL.md`, so no cold-start exploration is required.
**Fix:** Optional — note in each card that the `_paths` call is copied verbatim from the in-Context source skill, or add `_paths.py` to Context for precision.

## Verdict

APPROVE
Plan is complete, well-sequenced, and source-grounded; only minor NITs remain.
MILL_REVIEW_END