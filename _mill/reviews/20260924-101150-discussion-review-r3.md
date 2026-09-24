MILL_REVIEW_BEGIN
# Review: status.md: rename parent to parent_branch, add parent_thread

```yaml
duration_s: 201.5
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

Cross-checked every line-numbered claim against source: `_status.py` (`read_parent_branch`'s `.get("parent")`, `set_module_verify_baseline`'s `parent:`-anchor insert, module docstring API list), `_parent_branch.py` (`_parse_parent_from_yaml_text`'s `startswith("parent:")`, `ParentBranchError` message text, `resolve_dead_parent`'s `git show` call), `_yaml_writer.quote_scalar` (raises only on `\n`, control chars fall through to `yaml.safe_dump` escaping), `_spawn_core.write_initial_status` (line 635, keyword-only `cfg`), `millpy-spawn.py` (line 298 call site, `--slug`/`--dry-run` args, validation point after `parse_args` before any claim work), `millpy-claim.py` (line 275), `millpy-cleanup.py` (line 484), the three templates (`status-discussing.md`, `discussion.md`, `plan-overview.md`, `implementer-brief.md`), and all five `update_field(status_path, "parent", ...)` sites (`mill-merge` L127, `mill-merge-in` L17/L31, `mill-go-base/SKILL.md` L692, `handoff.md` L58). Every line number, quoted string, and regex-collision claim matches the file read. `mill-resume`'s "parent" hits are all about copying `.millhouse/` from the parent worktree, not the status.md field — the discussion's out-of-scope call is correct. Grepping `plugins/mill/scripts/*.py` for the yaml key confirms only `_status.py` and `_parent_branch.py` touch it; no missed script call site.

## Findings

### [NIT:decision] "Skill prose" decision has no rejected alternative
**Section:** Decisions → Skill prose
**Issue:** Every other `### Decision:` block states a rejected alternative; this one has rationale only.
**Fix:** Non-blocking — the "alternative" (leave prose saying `parent:`) is already foreclosed by the rename decisions above it, so there's no independent fork to record; add a one-line "Rejected: leaving old prose — contradicts the renamed key" if strict uniformity is wanted.

## Verdict

APPROVE
Claims verified against source are accurate; scope, decisions, and testing plan are complete.
MILL_REVIEW_END
