MILL_REVIEW_BEGIN
# Review: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative

```yaml
duration_s: 223.9
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:design] workflow-md-go-row rationale rests on a false premise
**Section:** Decisions > `workflow-md-go-row` **Issue:** Rationale claims that without the new Go row, "the new Step-0 load line... has no table-driven trigger to ever fire for a Go project" — but `plugins/mill/scripts/_agent_dispatch.py`'s `language_skills_directive` (LANG_MAP includes `.go` -> `golang`, confirmed by `test-language-skills-directive.py`) already names `golang-comments` for every implementer/fixer batch touching a `.go` file, entirely independent of `workflow.md`'s marker table. The table itself, per its only other consumers (`git-commit/SKILL.md`, `git-pr/SKILL.md`), drives `{lang}-build` lint/test routing, not `{lang}-comments` loading. **Fix:** Restate the rationale around the real gap (Go has no build/lint/test routing row for `git-commit`/`git-pr`, a pre-existing gap this task incidentally surfaces) rather than the nonexistent comments-skill trigger gap; the row addition itself is still correct.

### [NIT:consistency] python-comments intro prose echoes the mechanism-narration framing being removed
**Section:** Technical context (python-comments edit list) **Issue:** Lines 6-9 of `python-comments/SKILL.md` ("a developer should be able to understand the module's logic by reading the docstrings and comments without tracing through the implementation") use "logic"-oriented phrasing similar to the "How it works" framing being struck elsewhere in the same file, but this intro paragraph is not in the Technical Context's edit ranges (~18, ~20-51, ~102-113, ~138-149, ~169-175) nor addressed by any Decision. **Fix:** Either confirm this line is intentionally left as-is (purpose-level "logic" reading, not mechanism narration) or add it to the edit list.

### [NIT:scope] Merged mechanical-restatement rule is new content for csharp-comments, not just a move
**Section:** Scope > In (mechanical-restatements merge bullet) **Issue:** The bullet frames merging golang's "No mechanical restatements" and python's "No mechanical comments that restate what the code does" as consolidating existing duplicated wording ("same rule, previously worded differently") — but `csharp-comments/SKILL.md`'s Prohibited patterns (lines 65-72, verified) has no equivalent entry today, so shipping this into shared `code-comments` silently adds a new prohibition for C# that the "genuinely new" bullet list doesn't disclose. **Fix:** Note explicitly that this entry is net-new for C#, or move it under the "genuinely new" bullet list instead of the consolidation bullet.

## Verdict

REQUEST_CHANGES
One BLOCKING: the workflow-md-go-row decision's stated rationale is factually wrong per source verification.
MILL_REVIEW_END
