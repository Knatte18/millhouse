# Discussion: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs

```yaml
task: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs
slug: mill-merge-finalize-codeguide-bugs
status: discussing
parent: main
```

## Problem

Five independent bugs, all reported against the mill-merge / mill-merge-in / mill-finalize / codeguide-update finalize chain, surfaced across separate real task runs (loomyard, quarry, NORCE Models). None share a root cause — they cluster only by "lives in the finalize/codeguide chain" — so this task fixes each as its own self-contained change:

1. **#977** — `mill-merge` crashes on closed-PR re-entry because it invokes `mill-merge-in` bare instead of passing the parent branch it already resolved.
2. **#946** — `mill-merge-in`'s inline-mode codeguide docs get staged but never committed, leaving a dirty index after a "successful" merge-in.
3. **#945** — `mill-merge-in`'s `--recompute-baseline` step is a synchronous foreground call with no timeout ceiling protection, unlike its sibling verify-replay calls.
4. **#930** — `mill-finalize`'s pre-merge `_mill/` deletion silently breaks any permanent-doc citation of `_mill/discussion.md` (e.g. a roadmap entry), with nothing in the verify chain catching it.
5. **#943** — `codeguide-update`'s `resolve_scope.py` mis-resolves explicit file-path arguments in a nested-hub-root layout (hub root ≠ git root).

**Why now:** all five were filed and closed as individual GitHub issues (#977, #946, #945, #930, #943) after being hit in live task runs; this task batches them into one implementation pass since they're small, independent, and touch the same file family.

## Scope

**In:**
- `plugins/mill/skills/mill-merge/SKILL.md` — Step 2 passes `parent_branch` explicitly to `mill-merge-in` (uniformly, all routes reaching Step 2).
- `plugins/mill/skills/mill-merge-in/SKILL.md` — Step 5.5 commits codeguide docs alongside briefs; Step 3.5 switches to the `millpy-bg` background-dispatch-and-poll pattern.
- `plugins/mill/skills/mill-finalize/SKILL.md` — Step 3 gains a non-blocking scan-and-warn for surviving `_mill/discussion.md` citations before deletion.
- `plugins/codeguide/scripts/resolve_scope.py` — `_explicit_scope` anchors relative tokens to invocation cwd instead of git toplevel.
- A doc note (SKILL.md or CLAUDE.md-adjacent, wherever the existing `_mill/` lifecycle convention is documented) stating that citing `_mill/discussion.md` from a permanent/roadmap doc is unsafe (the file never survives merge).
- Unit test coverage for the `_explicit_scope` fix (#943) in `plugins/codeguide/unit_tests/test-resolve-scope.py`.

**Out:**
- `mill-finalize`'s PR Steps Step 1 `mill-merge-in` invocation — not affected by #977 (status.md still exists at that point in the sequence), left unchanged.
- Any change to `codeguide_commit.py` itself (#946's fix lives entirely in `mill-merge-in`'s commit step, not in the codeguide helper).
- New integration-test fixtures for the git-flow-level fixes (#977, #946, #945, #930) — these are SKILL.md procedure/doc changes, verified by re-reading rendered docs for consistency, not new pytest coverage.
- Any redesign of `resolve.py`'s inline/sibling walk, or of `_sibling.py` — #943 is isolated to `resolve_scope.py`'s `_explicit_scope` function.
- Blocking the merge on #930's scan finding a citation — it's an informational warning only, never a halt.

## Decisions

### 977-explicit-parent-branch

- Decision: `mill-merge`'s Step 2 ("Invoke mill-merge-in") passes the `parent_branch` value already resolved at Entry Step 4 (`plugins/mill/skills/mill-merge/SKILL.md:76-137`, including its `status_path`-absent fallback and the liveness-check rebind) as `mill-merge-in`'s optional positional `<branch>` argument (`plugins/mill/skills/mill-merge-in/SKILL.md:28-29`), on every route that reaches Step 2 — not just the `closed` PR-state route.
- Rationale: Entry Step 4 already computes the correct parent branch for every code path before Step 1/2 ever run. Passing it explicitly removes the whole bug class (mill-merge-in's own independent `_parent_branch.resolve(...)` call failing whenever `status.md` is absent) rather than special-casing the one route that happens to trigger it today. The mechanism already exists — mill-merge-in's Entry step 3 explicitly documents the override as being "for ad-hoc syncing from some other branch than the task's declared parent," which this use qualifies as.
- Rejected: Special-casing only the `closed` route — leaves the `done` route's bare call as a latent instance of the same bug if `status.md` is ever absent there too (e.g. a future re-entry path), for no real benefit (the explicit-arg call is not more expensive or more risky than the bare call).

### 946-commit-codeguide-docs

- Decision: Broaden `mill-merge-in` Step 5.5's guard (`plugins/mill/skills/mill-merge-in/SKILL.md:172-184`) from `git status --porcelain -- _mill/briefs` to an unrestricted `git status --porcelain`, so the single commit picks up both dispatch briefs and any inline-mode codeguide docs that Step 5's `codeguide_commit.py --mode inline` call (`plugins/codeguide/scripts/codeguide_commit.py:73-79`) already staged via `git add`.
- Rationale: `codeguide_commit.py --mode inline` deliberately only stages (its own docstring: "the outer `@git-commit` skill... will commit them"), matching the contract `codeguide-update/SKILL.md` documents ("Inline mode: do NOT commit... `codeguide_commit.py --mode inline` only stages"). `mill-merge-in` is that "outer" commit-owner in this call chain (it invokes codeguide-update directly in its own Step 5), so it must honor the same contract git-commit already does for its own inline-mode call. Widening the existing guard is the smallest change that satisfies it — mill-merge-in has no mechanism to reliably capture codeguide-update's per-group JSON summary (it's a Skill-tool dispatch, not a captured subprocess call), so parsing exact file lists back out is not viable.
- Rejected: Parsing codeguide-update's returned file list — not mechanically available to the caller through the Skill-tool dispatch path.

### 945-baseline-recompute-background-dispatch

- Decision: Convert `mill-merge-in` Step 3.5 (`plugins/mill/skills/mill-merge-in/SKILL.md:99-114`) from a synchronous foreground call to the same `millpy-bg.py --slug <name> -- ...` background-dispatch-and-poll pattern documented in `mill-go-base/SKILL.md`'s "0.5. Baseline pre-flight" (lines 544-575) and "0.6. Per-batch baseline recapture" (lines 576+), including the same `_bg.check_bg_status` liveness-check loop and `"dead"` handling.
- Rationale: `--recompute-baseline` replays the full regression suite plus per-batch verifies — identical underlying work to `millpy-implement.py --stage baseline`, which is exactly why 0.5/0.6 already moved to background dispatch ("removes the Bash-tool timeout ceiling entirely... a capped foreground Bash-tool call... has twice been observed to time out on tasks with several slow batch verify commands (#897, #875)"). Step 3.5 already documents itself as fail-safe and never blocking the merge on error — that same fail-safe contract maps directly onto 0.5/0.6's `"dead"` → "log the reason and continue" handling, so no new failure-handling design is needed, just the existing pattern reused.
- Rejected: Timeout-guidance-only (bump to 600000ms without background dispatch) — doesn't actually remove the ceiling for a task with a slow enough regression suite; the sibling call sites already rejected this approach for the identical underlying computation.

### 930-scan-and-document-discussion-citations

- Decision: Two changes. (1) `mill-finalize` Step 3 (`plugins/mill/skills/mill-finalize/SKILL.md:74-105`) gains a non-blocking scan immediately before the `git rm -r <task_dir>` / restore-from-base branches: grep the git-tracked tree (excluding `task_dir` itself) for the literal citation pattern (the task's own `_mill/discussion.md` relative path) and, if any hits are found, print a warning listing the citing files — this never halts the step. (2) Add a doc note stating that citing `_mill/discussion.md` from any permanent/roadmap doc is unsafe, since the file is guaranteed not to survive merge.
- Rationale: The reported failure mode is a *silent* dead link discovered only much later, in an unrelated task's own test run, with no attribution back to the task that broke it. A scan at the exact moment of deletion is the only point where mill has enough context (this task's own `task_dir`, this operator's own repo) to catch it cheaply. The doc note is nearly free and prevents new citations from being written in the first place — the two are complementary, not alternatives (the scan catches historical creep the doc note can't retroactively fix; the doc note stops new instances the scan can only report after the fact).
- Rejected: Scan-only (no doc note) — cheap to add both, and the doc note is the only thing that reaches a human who hasn't yet made the mistake. Doc-only (no scan) — relies on every future contributor having read and remembered the doc; the original #930 repro shows this convention was never documented anywhere before being violated.

### 943-explicit-scope-cwd-anchor

- Decision: Fix `_explicit_scope` in `plugins/codeguide/scripts/resolve_scope.py:199-208` to resolve relative path tokens against the actual invocation `cwd_path` (already computed at `enumerate_scope`'s top, `resolve_scope.py:235`) instead of `toplevel`. Concretely: thread `cwd_path` into `_explicit_scope` and build each path as `(cwd_path / token)` for relative tokens (a token that is already absolute is unaffected — `pathlib.Path.__truediv__` ignores the left operand when the right one is absolute).
- Rationale: Every other scope-resolution path in this file (`_no_arg_scope`, `_time_scope`, `_head_rev_scope`) derives paths from `git diff`/`git log` output, which git itself always reports relative to the true toplevel — so anchoring those to `toplevel` is correct by construction. `_explicit_scope` is different: its tokens are raw, uninterpreted argv strings the caller wrote from their own vantage point, exactly like a shell command's file arguments — normal CLI semantics resolve relative paths against the invoker's cwd, not some other root. In a nested-hub-root layout (hub root nested below git toplevel, e.g. NORCE Models' `src/csharp/NORCE.Models`), a human running `/codeguide-update file1.cs file2.cs` from within the hub gets `toplevel`-relative (wrong) paths today instead of hub-relative (correct, matching their own cwd) ones. This is consistent with `_get_toplevel`/`_git` already correctly using `-C str(toplevel)` for every *git-derived* path in the file — the fix narrows to just the one function that doesn't derive its paths from git.
- Rejected: Working around it only at specific call sites (e.g., relying on mill-merge-in's existing `cd <hub_root>` before invoking codeguide-update) — mill-merge-in's own call site uses the head-rev route (`"$CHK..HEAD"`), not explicit paths, so it was never actually exposed to this bug; the reported repro is a human invoking `/codeguide-update` directly with explicit file paths from a nested-hub-root cwd. Fixing only known call sites leaves the general case (any future explicit-path invocation from a nested hub) broken.

## Technical context

- `plugins/mill/skills/mill-merge/SKILL.md`:
  - Entry Step 4 (lines 76-137) resolves `parent_branch`, including the `status_path.exists()`-absent fallback (line 78) and the liveness-check rebind (lines 81-135).
  - `### PR-state gate` `closed` route (lines 210-227) is the actual crash site for #977 — reached when `status_path` is typically already absent (line 216).
  - `### 2. Invoke mill-merge-in` (lines 247-252) currently reads "no arguments — it picks up the parent from status.md the same way" — this is the line to change.
- `plugins/mill/skills/mill-merge-in/SKILL.md`:
  - Entry step 3 (lines 28-29) documents the optional positional `<branch>` override — the mechanism #977's fix uses.
  - `### 3.5. Baseline recompute` (lines 99-114) is the synchronous call #945 targets; its own text already documents the fail-safe/never-blocks contract (lines 109-110) that the background-dispatch conversion must preserve.
  - `### 5. Codeguide update` (lines 157-170) invokes `codeguide-update` inline-mode; `### 5.5. Commit dispatch briefs` (lines 172-184) is the guard #946 broadens.
- `plugins/mill/skills/mill-go-base/SKILL.md`:
  - `### 0.5. Baseline pre-flight` (lines 544-575) and `### 0.6. Per-batch baseline recapture` (lines 576-615+) are the reference pattern for #945's fix — same `millpy-bg.py --slug ... -- ...` wrap, same `_bg.check_bg_status` poll loop, same JSON-line extraction via `grep '^{' <log-path>`.
- `plugins/mill/skills/mill-finalize/SKILL.md`:
  - `### Step 3: Cleanup commit (issue #268)` (lines 74-105) is where #930's scan must run, immediately before either the rm-path or restore-path branches execute their deletion.
- `plugins/codeguide/scripts/codeguide_commit.py`:
  - `--mode inline` (lines 73-79) stages only (`git add`), never commits, and returns `{"mode": "inline", "committed": false, "files": [...]}` on stdout — confirms #946's premise; this file needs no changes itself.
- `plugins/codeguide/skills/codeguide-update/SKILL.md`:
  - Step 4g (lines 84-96) is the call site that invokes `codeguide_commit.py` per cg-root group.
  - `## Rules` (line 106) states the inline-mode non-commit contract explicitly.
- `plugins/codeguide/scripts/resolve_scope.py`:
  - `enumerate_scope` (lines 231-254) is the dispatcher; `cwd_path` is computed at line 235 but currently only passed to `_get_toplevel`.
  - `_explicit_scope` (lines 199-208) is the function #943 fixes — currently anchors every token to `toplevel` (line 200) regardless of invocation cwd.
  - `_no_arg_scope`/`_time_scope`/`_head_rev_scope` (lines 128-196) are the git-diff-derived routes that are already correct and must not be touched.
  - `plugins/codeguide/unit_tests/test-resolve-scope.py` already exists — extend it with a nested-cwd tmp-repo case rather than creating a new test file.

## Constraints

- No `CONSTRAINTS.md` present at the hub root.
- Every SKILL.md edit must preserve this repo's existing conventions: `${CLAUDE_PLUGIN_ROOT}` for intra-plugin script paths, no `sed`, ASCII-only in any `print()`/log text these skills emit, fenced ` ```yaml ` metadata blocks (not `---` frontmatter) if any new metadata block is added.
- The `resolve_scope.py` fix must not change behavior for any of the three git-diff-derived routes (`_no_arg_scope`, `_time_scope`, `_head_rev_scope`) — only `_explicit_scope`'s anchor changes.
- #930's scan must remain non-blocking under all circumstances — mill-finalize Step 3 is on the critical path of every PR-mode finalize, and this task must not introduce a new halt condition there.

## Testing

- **#943 (resolve_scope.py)** — TDD candidate. Extend `plugins/codeguide/unit_tests/test-resolve-scope.py` with a case that constructs a tmp git repo, creates a nested subdirectory (simulating a hub root below git toplevel), writes a file there, and asserts `enumerate_scope(["<relative-filename>"], cwd=<nested-subdir>)` returns the correct absolute path anchored to the nested cwd, not to the repo toplevel. Also assert the three git-diff-derived routes are unaffected by re-running (or confirming coverage of) their existing test cases.
- **#977, #946, #945, #930** — no new automated tests; these are SKILL.md procedure/doc changes with no directly executable unit under test. Verification is: re-read the rendered SKILL.md sections for internal consistency (cross-references, variable names, step numbering) after editing, matching how this repo's own `mill-plan`/mill-review-plan self-review process verifies plan/doc changes. If existing integration tests under `plugins/mill/integration_tests/` already exercise any of these flows (e.g. a merge-in or PR-state-gate fixture), confirm they still pass — but no new integration fixtures are being added for this task (see Scope/Out).

## Q&A log

- **Q:** #977 fix shape — pass parent_branch explicitly, and on every route or just `closed`? **A:** [auto-pick] Pass explicitly on every route reaching mill-merge Step 2 (uniform fix, not special-cased). **Why:** Entry Step 4 already resolves parent_branch before Step 1/2 run on any path; passing it explicitly everywhere removes the whole bug class instead of leaving a latent instance on the `done` route.
- **Q:** Should mill-finalize's own "no arguments" mill-merge-in call also change for #977? **A:** [auto-pick] No — out of scope. **Why:** that call site (PR Steps Step 1) runs before Step 3's cleanup commit removes status.md, so it isn't exposed to the bug; changing it would be unrelated churn.
- **Q:** #946 fix shape — broaden the Step 5.5 commit guard, or parse codeguide-update's file list back? **A:** [auto-pick] Broaden the guard to an unrestricted `git status --porcelain` check. **Why:** codeguide-update is invoked via the Skill tool, not a captured subprocess — its per-group JSON summary isn't mechanically available to the caller, so widening the existing guard is the only viable mechanism.
- **Q:** #945 fix shape — background-dispatch conversion, or just extend the timeout? **A:** [auto-pick] Convert to the same `millpy-bg` pattern as mill-go-base's 0.5/0.6. **Why:** the sibling call sites already rejected timeout-only for the identical underlying computation, since it doesn't remove the ceiling for a slow enough regression suite.
- **Q:** #930 fix shape — scan-and-warn, document-only, or both? **A:** [auto-pick] Both. **Why:** the scan catches citations that already exist (which a doc note can't retroactively fix); the doc note stops new ones from being written (which the scan can only report after the fact, at merge time).
- **Q:** #943 fix shape — fix `_explicit_scope`'s anchor in resolve_scope.py, or work around it at known call sites? **A:** [auto-pick] Fix `_explicit_scope` directly. **Why:** the only currently-known mill call site (mill-merge-in) never actually hits this path (it uses head-rev, not explicit paths) — the real repro is a human invoking `/codeguide-update` with explicit paths from a nested-hub-root cwd, which a call-site workaround can't cover in general.
- **Q:** Testing approach given 4/5 fixes are SKILL.md procedure changes? **A:** [auto-pick] Unit-test only #943 (extend existing `test-resolve-scope.py`); verify the SKILL.md changes by re-reading rendered docs for consistency, no new integration fixtures. **Why:** matches this task's doc/procedure-level scope; writing new integration fixtures for four independent one-off doc fixes would be disproportionate churn.
