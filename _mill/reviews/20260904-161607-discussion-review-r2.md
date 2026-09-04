MILL_REVIEW_BEGIN
# Review: code-comments skill: prohibit enumerating current consumers/writers of a shared resource

```yaml
duration_s: 100.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

All source-grounded claims verified against the worktree:

- `plugins/mill/skills/code-comments/SKILL.md` — `## Prohibited patterns` at line 58, exactly four existing bullets as described; new bullet placement (appended as item 5) is correct.
- `plugins/golang/skills/golang-comments/SKILL.md:220` has a `## Prohibited patterns` section with the single syntax-only bullet quoted correctly.
- `plugins/csharp/skills/csharp-comments/SKILL.md` and `plugins/python/skills/python-comments/SKILL.md` confirmed to have **no** `## Prohibited patterns` section at all — the discussion's current wording ("have no such section to extend") correctly matches this, resolving the fabricated-evidence issue from round 1.
- `SKILLS.md:35` confirmed to reference only frontmatter `description:`, unaffected by the change.
- `grep -n "code-comments" plugins/mill/unit_tests/*.py` returns nothing, confirmed.
- `test-skills-index.py`, `test-skill-writer.py`, `test-skill-helper-drift.py` all exist; none assert on `code-comments/SKILL.md` prose body, consistent with the "no new test" rationale.
- CLAUDE.md's `PYTHONPATH=` verify-prefix requirement is correctly applied — `plugins/mill/pyproject.toml` exists (Python marker), so the mandatory prefix is correctly reflected in the plan's proposed verify command.
- `markdown/SKILL.md`'s semantic-line-break and em-dash conventions match the Technical Context's formatting guidance and the existing bullets' actual style.
- "Correction to the brief's premise" decision verified: no bullet referencing "current task/fix/callers" exists in the skill today.

No undecided items, scope ambiguity, missing rejected-alternatives, or unaddressed constraints found. All six `### Decision:` blocks carry rationale and rejected alternatives.

## Verdict

APPROVE
All claims verified against source; round-1 fabricated-evidence finding is correctly resolved.
MILL_REVIEW_END
