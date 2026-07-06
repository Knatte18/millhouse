MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [GAP] clean_ephemeral signature + mill-go SKILL callsite unspecified
**Section:** Scope; Decision "compute_scope_violations rebasing"; Technical context (`_cleanliness.py:243`)
**Issue:** Changing `compute_scope_violations` to `(hub_root, git_root)` forces `clean_ephemeral_scope_violations` (line 243 forwards its arg) to also take both roots, but the discussion says there is "no logic to update there"; its real caller `mill-go/SKILL.md:749` passes only `worktree_root`, and the 9 CESV cases in `test-cleanliness.py` call it with one arg — none of these are enumerated.
**Fix:** State that `clean_ephemeral_scope_violations` gains `(hub_root, git_root)`, that `mill-go/SKILL.md:749` must pass both (both resolvable there via `resolve_hub_path`/`resolve_git_root`), and that the CESV tests must be updated.

### [GAP] Removal base path for rebased violations undefined
**Section:** Decision "compute_scope_violations rebasing"
**Issue:** After rebasing, `compute_scope_violations` returns hub-relative paths, but `clean_ephemeral_scope_violations` deletes via `worktree / violation` (line 268); the discussion never states which base (hub_root vs git_root) the `os.remove` join must use post-fix, so nested-layout deletions could target the wrong file.
**Fix:** Specify that the removal join must use `hub_root` since violation strings are now hub-relative.

### [GAP] Verify `cwd`-field parse/thread site (millpy-implement.py) omitted
**Section:** Decision "Verify-cwd explicit field (#604)"; Technical context
**Issue:** The decision names `_run_verify_gate`, plan schema, `_plan_validate.py`, and mill-plan, but the plan `verify` value is actually read in `millpy-implement.py` (lines 371/591 batch, 311 overview) via `.get("verify")`; with the mapping form these return a dict and must extract command+cwd. `_run_verify_gate` only receives a string `verify_cmd` + `git_root`, so how the resolved cwd reaches it is unspecified.
**Fix:** Add `millpy-implement.py` to scope and state how `cwd` is resolved to a path and threaded into `_run_verify_gate`/`_run_verify_gates`.

### [GAP] Module-wide (overview) verify cwd unaddressed
**Section:** Decision "Verify-cwd explicit field (#604)"
**Issue:** The `cwd` field is scoped "per-batch," but the module-wide verify (`overview_frontmatter.get("verify")`, run through the same `_run_verify_gates` with `git_root=git_root`) has no cwd control; a nested-layout repo needing hub-relative execution would still run its module-wide gate at git_root, partially reproducing #604.
**Fix:** State whether the overview/module-wide verify also accepts `cwd`, or explicitly declare it out of scope with rationale.

### [NOTE] mill-plan PYTHONPATH auto-prepend vs mapping form
**Section:** Decision "Verify-cwd explicit field"
**Issue:** CLAUDE.md says mill-plan auto-prepends `PYTHONPATH=` on `verify-not-isolated` failure; with `verify` as a `{cwd, command}` mapping this must operate on `command`, not the dict.
**Fix:** Note that the auto-prepend/validation path handles the mapping form.

## Verdict

GAPS_FOUND
Rebased-path callsites (clean_ephemeral, SKILL, removal base) and the #604 parse/thread site need specifying.
MILL_REVIEW_END