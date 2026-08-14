MILL_REVIEW_BEGIN
# Review: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (best-effort self-assessment)
reviewed_file: plan/
date: 2026-08-14
```

## Findings

### [BLOCKING:consistency] Card 7 script invocation contradicts CLAUDE.md's explicit script-invocation rule
**Location:** batch 2 / card 7 **Issue:** Card 7 mandates `PYTHONPATH=plugins/mill/scripts "$MILL_PYTHON" plugins/mill/scripts/millpy-skills-index.py` (worktree-relative), justified as "not the plugin cache copy, per this repo's self-hosted-repo source-verification rule." CLAUDE.md's own text says the opposite for this exact case: "`${CLAUDE_PLUGIN_ROOT}` remains correct for script invocation — this bullet narrows only the source-code-verification case, it does not revise the bullet above it," and `mill-skills-index/SKILL.md` itself documents the canonical cache-form invocation. `_repo_root()` in `millpy-skills-index.py` resolves via `git rev-parse --show-toplevel` (cwd-based), so the worktree-form deviation buys no correctness benefit while violating a documented hard constraint. **Fix:** Use the standard cache form `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"` and drop the misapplied source-verification-rule justification.

### [NIT:consistency] Batch 1 scope understates its own decision inventory
**Location:** batch 1 scope statement **Issue:** Batch 1's scope says "No batch-local decisions beyond the three listed in the overview's `## Shared Decisions`," but card 3 invokes `python-how-it-works-conflict` and card 4 invokes `csharp-file-header-syntax` — two additional discussion.md decisions neither listed there nor declared as batch-local. **Fix:** Either add these two decisions to the overview's Shared Decisions or explicitly enumerate them as batch-local in batch 1's scope prose.

### [NIT:consistency] Card 4's requirements mislabel a C#-only trim as "Go/C#-specific"
**Location:** batch 1 / card 4 **Issue:** Card 4's Requirements text says it "trims 'XML documentation' to keep only the Go/C#-specific `/// <summary>` requirement," but this card only touches `csharp-comments/SKILL.md`; Go has no `/// <summary>` construct. **Fix:** Reword to "C#-specific."

### [NIT:consistency] Card 5's verification grep pattern never matches the actual pre-edit text
**Location:** batch 1 / card 5, item 1 **Issue:** The prescribed check `grep -n "must begin with a comment describing" plugins/golang/skills/golang-comments/SKILL.md` is meant to confirm removed purpose-not-mechanism prose is gone, but the original file's wording is "must begin with a comment that describes" (not "comment describing") — the pattern never matched even before the edit, so the check is vacuously true regardless of whether card 2 landed correctly. **Fix:** Correct the grep string to match the actual source text (e.g. "must begin with a comment that describes"), or point it at a substring that genuinely appears in the pre-edit file.

## Verdict

REQUEST_CHANGES
Card 7's script-invocation form contradicts CLAUDE.md's explicit hard constraint for script invocation.
MILL_REVIEW_END
