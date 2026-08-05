MILL_REVIEW_BEGIN
# Review: markdown skill: use semantic line breaks instead of one unbroken line per paragraph

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

## Findings

### [GAP] python-comments' own docstring example already hard-wraps mid-sentence
**Section:** Decisions / Existing-content reformatting; Technical context (python-comments)
**Issue:** `python-comments/SKILL.md` lines 63-64 and 66-67 (inside the `create_CBI_from_SSB_and_RSI` docstring example) split single sentences across two lines at a fixed column, mid-sentence — the exact defect the discussion explicitly checked for and fixed in `golang-comments` lines 29-31, but never checked here.
**Fix:** Verify whether this example needs the same bounded in-file fix (per the golang precedent's own rationale), or state explicitly why python-comments' example is exempt.

### [GAP] "Mechanical" comma+conjunction trigger doesn't reliably signal independent clauses
**Section:** Decisions / Break granularity: sentence-per-line, plus clause-boundary breaks
**Issue:** The decision calls comma+coordinating-conjunction "mechanical...unambiguous," but comma+"and"/"or" also occurs in Oxford-comma lists and compound predicates with no second independent clause — e.g. python-comments/SKILL.md lines 69-71's own "...index was created, and a "count" column representative..." is comma+"and" with no second subject+verb.
**Fix:** State the actual disambiguator (does the agent check for a second subject+verb, or is judgment still required despite the "mechanical" framing?) and consider adding a negative worked example (comma+conjunction that should NOT trigger a break) alongside the required positive one.

### [NOTE] Technical context line-count off-by-one (two files)
**Section:** Technical context
**Issue:** `markdown/SKILL.md` is stated as "27 lines total" (actual: 26); `python-comments/SKILL.md` is stated as "139 lines" (actual: 138) — confirmed by direct count.
**Fix:** Correct both counts; harmless for the cited section ranges (24-26, 29-31, 197-198 all verified accurate) but worth tightening given this discussion has twice already corrected line-number claims in earlier rounds.

### [NOTE] Blockquote rationale conflates CommonMark syntax requirement with a single-line constraint
**Section:** Scope / In, bullet 1
**Issue:** Blockquotes require a `>` prefix per physical line, but that doesn't itself force single-sentence-per-blockquote content — CommonMark permits multiple `>`-prefixed lines to soft-wrap into one rendered paragraph, so the "must stay on one line regardless of sentence count" conclusion doesn't follow from the cited reason (repo's actual blockquotes, checked via grep, are all short one-liners today, so this has no practical effect).
**Fix:** Either drop the CommonMark justification or restate it as a stylistic choice rather than a syntax-forced one.

## Verdict

GAPS_FOUND
Two GAPs: unchecked python-comments self-consistency, and an under-specified "mechanical" clause-boundary disambiguator.
MILL_REVIEW_END
