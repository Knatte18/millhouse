# Review: status.md: rename parent to parent_branch, add parent_thread

```yaml
verdict: APPROVE
reviewer_model: orchestrator
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:consistency] "Four skill sites" is five call lines
**Section:** Decisions / Writing the parent branch; Q&A log
**Issue:** The text says four skill sites switch from `_status.update_field(status_path, "parent", ...)`, but Technical context lists five lines in four files: `mill-merge` (~127), `mill-merge-in` (~17 prose and ~31 rebind), `mill-go-base/SKILL.md` (~692), `mill-go-base/handoff.md` (~58). All five exist in the tree.
**Suggested fix:** Say "five call lines in four files" so the plan writer edits both `mill-merge-in` lines.

### [NIT:design] Baseline rows land between `parent_branch:` and `parent_thread:`
**Section:** Decisions / Insertion anchor for baseline rows; `parent_thread` rendering
**Issue:** Both `render_initial` (`parent_thread`) and `set_module_verify_baseline(_signatures)` insert "immediately after `parent_branch:`". Once a baseline is written, its rows sit between the two parent rows. It is harmless to every reader, but the Testing item "row appears right after `parent_branch:`" only holds at render time.
**Suggested fix:** State that the ordering is intentional and cosmetic, or anchor the baseline insertion after `parent_thread:` when that row exists.

### [NIT:decision] Invalid `--parent` fails late with a bare ValueError
**Section:** Decisions / `millpy-spawn --parent`
**Issue:** "No format validation" means a value containing a newline reaches `quote_scalar`, which raises `ValueError`, from `write_initial_status` (`millpy-spawn.py:298`) after the wiki claim and worktree creation. The LIFO rollback cleans up, but the error is obscure and the work is wasted.
**Suggested fix:** Reject newline/control characters in `--parent` at argument-parse time, before the claim, and keep "no other format validation".

## Verdict

APPROVE
Sound, verified against the tree, legacy-fallback reasoning holds; three minor NITs only.
