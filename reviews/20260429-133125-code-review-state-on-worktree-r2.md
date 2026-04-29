# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — state-on-worktree

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: state-on-worktree
date: 2026-04-29
```

## Findings

### [NIT] Template HTML comments carry stale wiki paths
**Location:** `plugins/mill/templates/discussion.md:2`, `plan-overview.md:2`, `plan-batch.md:2`
**Issue:** All three templates still have `Template: <WIKI_PATH>/active/<slug>/...` in their HTML comment headers, contradicting the worktree-relative layout. These files are not in any Card 11–15 Modifies list, so the stale comments are pre-existing, but they will mislead anyone using the templates as documentation.
**Fix:** Update the comment paths to `<worktree_root>/discussion.md` etc. in a subsequent tidy pass (batch 04 or migration-and-docs).

### [NIT] mill-start SKILL.md Phase: Discussion Review shows nonexistent CLI flags
**Location:** `plugins/mill/skills/mill-start/SKILL.md` (Phase: Discussion Review, step 2)
**Issue:** The prose invokes `millpy-review-discussion.py --slug <slug> --round <N>`, but `millpy-review-discussion.py` accepts no positional or named arguments beyond `--help`; argparse would exit 2 on those flags. Pre-existing; Card 15's requirement is "preserve existing operator-facing flow".
**Fix:** Remove `--slug` and `--round` from the example invocation in a follow-up prose pass.

### [NIT] Forced-failure test assertion is trivially satisfied
**Location:** `plugins/mill/unit_tests/test-spawn-core.py:test_write_initial_status_forced_failure_raises_runtime_error`
**Issue:** The block `if not msg.strip().endswith("'"): pass` asserts nothing — `pass` is reached on both branches, so the check exists only as a comment in code form.
**Fix:** Replace with `assert msg.strip().endswith("'"), f"stderr not repr-quoted in message: {msg!r}"` to actually enforce the error format.

## Verdict

APPROVE
All five cards correctly implemented; three pre-existing prose/test NITs do not block.