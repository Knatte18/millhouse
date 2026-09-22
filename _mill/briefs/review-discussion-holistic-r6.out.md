MILL_REVIEW_BEGIN
# Review: compute_baseline: use the task worktree's own pre-edit state, not a parent-branch checkout

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-22
```

## Findings

### [BLOCKING:consistency] Default verify cwd stated as project_root
**Section:** Technical context > Gotchas, "`git_root` vs `project_root`"
**Issue:** The discussion says the in-worktree cwd is "`project_root` by default", but the gate it must mirror resolves `cwd_override is None` to **git_root** first (`_implementer_common.py:865-869`: `cwd_override if not None else (git_root if git_root is not None else project_root)`), and `_run_verify_gates` always passes a real `git_root` (`:1158-1160`); today's module-wide path agrees, since `_relative_cwd_fragment` collapses both `None` and `git_root` to "run at the checkout root", which mirrors `git_root`. In a nested-hub layout a plain-string `verify:` would therefore be captured in a different directory than it is gated in — breaking Decision `capture-set-equals-gate-set`'s own premise, and making the `module-wide-verdict-source` `(command, cwd)` seed key never match, so the dedup silently never fires.
**Fix:** State the default as `git_root` (falling back to `project_root` only when `git_root` is absent), matching `_run_verify_gate`, and say that both halves normalise the key the same way.

### [BLOCKING:design] compute_baseline's signature-return contract unstated
**Section:** Decision `module-wide-verdict-source`
**Issue:** The module-wide half must "extract failure signatures from its own runs and persist them" to `module_verify_baseline_signatures:`, but today `compute_baseline`/`_run_module_wide_verify_algorithm` discard each run's output (`_verify_baseline.py:292-313`) and return a bare `str`, and the caller that does the `_status` write has no access to those runs. The discussion never says whether `compute_baseline`'s return shape changes (e.g. `(verdict, signatures)`) or where extraction lives — and the Testing section reinforces the bare-string reading ("`(0)` → `"clean"`", "`compute_baseline`'s return value ... `"clean"` → ..."). The second call site, `millpy-merge-in-subagent.py:264`, consumes the same return value and would have to change with it.
**Fix:** State the post-change signature of `compute_baseline` explicitly, and state that the merge-in call site consumes the verdict only and persists no signatures.

### [NIT:scope] compute_batch_baselines' checkout-shaped surface undisposed
**Section:** Scope > In, `_verify_baseline.py`; Technical context bullet 1
**Issue:** Only the *module* docstring is marked for rewrite, but the surviving `compute_batch_baselines` keeps a parameter literally named `checkout_path` (an "ALREADY-CHECKED-OUT" worktree per its docstring), an unused `project_root`, and a docstring clause warning never to share a `pair_cache` across checkouts — none of which have a stated disposition once nothing is ever checked out.
**Fix:** Say what `checkout_path` becomes (renamed / what the caller passes) and that its docstring is rewritten, not just the module's.

### [NIT:design] "every command is runnable against the pre-edit tree" overstates
**Section:** Decision `capture-set-equals-gate-set`, rationale
**Issue:** A batch whose `verify:` targets a test file that same batch creates — the dominant TDD shape in this repo's plans — is not runnable pre-edit; its capture records a collection/not-found signature set. The resulting waive-the-batch's-own-missing-file hole is pre-existing (the deleted on-demand path computed at the parent SHA with the same shape), so it is not a regression, but the sentence is used as load-bearing rationale.
**Fix:** Narrow the claim to "nothing has been deleted yet" and note that not-yet-created verify targets produce a harmless-but-noisy baseline.

### [NIT:consistency] Edited SKILL prose keeps `_mill/discussion.md` citations
**Section:** Scope > In, the two SKILL.md entries
**Issue:** The exact passages being rewritten carry `_mill/discussion.md` citations (`mill-go-base/SKILL.md:610`, `mill-merge-in/SKILL.md:137`), which CLAUDE.md forbids in a permanent doc because `_mill/` is removed at merge time; the discussion neither preserves nor removes them.
**Fix:** State that the rewritten prose drops the `_mill/`-rooted citations.

### [NIT:scope] New _status accessors carry no stated test coverage
**Section:** Testing > `test-status.py`
**Issue:** The entry only deletes `baseline_parent_sha` tests, yet this task adds `get/set_module_verify_baseline_signatures` and widens `clear_module_verify_baseline` to clear the new field — both untested by the stated plan.
**Fix:** Add a line requiring accessor round-trip and clear-alongside coverage in `test-status.py`.

## Verdict

REQUEST_CHANGES
Capture cwd default contradicts the gate; compute_baseline's signature-return contract is unspecified.
MILL_REVIEW_END
