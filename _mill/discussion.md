# Discussion: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches

```yaml
task: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches
slug: mill-nested-hub-and-skill-sync
status: discussing
parent: main
```

## Problem

Six GitHub bug reports (#495, #496, #497, #504, #505, #506) describe mill code and
SKILL.md prose that assumes a **flat layout** (`worktree_root == git_root`) or that
references a Python helper that was renamed/removed in the shipped plugin. They were
all filed by operators running mill against repos whose mill hub is a **subfolder** of
the git root (e.g. `…/wts/<slug>/src/csharp/NORCE.Models`), where `_mill/`,
`mill-config.yaml`, and `.millhouse/` live under the subfolder — not at the git root.

**Why now:** these are live operator-reported defects. The dangerous one (#497 bug 2)
silently corrupts *another task's* tracked state during a merge; the others produce
hard failures (`ParentBranchError`, `AttributeError`) or misleading validator errors
that invite wrong "mechanical fixes".

**Key finding from exploration — the brief is partly stale.** Commit `7fb8f586`
("Fix nested mill layout paths…", 2026-06-16 15:22, the commit immediately before this
task spawned) **already fixed four of the six** in source. The reports for #504/#505/#506
were filed *after* that commit, against the still-stale plugin **cache 2.0.0**, whose
copy lagged source because the plugin version was never bumped. So the genuinely-open
work is concentrated in `mill-merge` and `mill-merge-in` (neither was touched by
`7fb8f586`), plus a systemic guard against the SKILL-vs-shipped-API drift class.

## Scope

**In:**

- **mill-merge** (`plugins/mill/skills/mill-merge/SKILL.md`):
  - `1.5 Path Setup` (line ~35): replace `worktree_root = git_root` with hub resolution
    via `resolve_active_hub(...)` — fixes #506 + #497 bug 1.
  - `Step 1` config load (line ~21): replace the obsolete `<wiki_path>/config.yaml`
    overlay with the canonical `<hub_root>/mill-config.yaml` + `.millhouse/config.local.yaml`
    deep-merge (adjacent latent bug; prerequisite for correct hub resolution).
  - `Step 4`/`Step 5` squash safety: after `git merge --squash`, before commit, restore
    the parent branch's own `<task_dir>` from parent `HEAD` so the squash can never delete
    or modify the parent's unrelated `_mill/status.md` — fixes #497 bug 2.
- **mill-merge-in** (`plugins/mill/skills/mill-merge-in/SKILL.md`):
  - Entry step 2 (line ~13): replace cwd-relative `Path("_mill/status.md").resolve()` with
    hub-resolved `status_path`.
  - Verify-replay (line ~54): replace cwd-relative `Path("_mill/plan/").resolve()` with a
    hub-resolved `plan_dir` (line 56 already uses `resolve_hub_path()` — make lines 13/54
    consistent).
- **Regression / drift guard:**
  - Add a unit test that scans all SKILL.md files for `_<module>.<fn>(`-style mill-helper
    references and asserts each resolves to a real function defined under
    `plugins/mill/scripts/` **including its subpackages** (e.g. `wiki/`) — so heavily-used
    subpackage helpers like `_client.*` (`scripts/wiki/_client.py`, referenced by ~10
    SKILLs) resolve rather than false-positive. A small allowlist covers genuinely
    illustrative references only. Directly serves the task title's "SKILL.md vs shipped-API
    mismatches" and would have caught #504/#505.
  - Add a nested-hub scenario to integration `test-merge.py`: parent branch carries its own
    `_mill/status.md`; after the merge sequence, assert the parent's file survives and only
    production files land. Covers #497 bug 2 at the git level.
- **Verify (light) the four already-fixed issues** (#495, #496, #504, #505): confirm the
  source state described under *Technical context* still holds; no re-fix of correct code.

**Out:**

- Re-implementing #495/#496/#504/#505 — they are already correct in source (see Technical
  context). The drift-guard test is the regression coverage for #504/#505; #495's
  hub-resolved `project_root` is exercised by existing review-plan tests.
- Bumping the plugin version / forcing a cache refresh as the *primary* fix — the systemic
  answer is the drift-guard test, not version discipline. (A version bump may still be
  warranted at release time but is not this task's deliverable.)
- mill-go and millpy-review-plan code changes — already nested-hub-correct.
- Any production-code behavior in target repos; this task only touches the mill plugin.
- mill-cleanup teardown (worktree/branch/portal/wiki-active removal) — unchanged.

## Decisions

### hub-resolution-helper
- Decision: In mill-merge and mill-merge-in, resolve the hub via
  `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)`, matching
  mill-go's `Path Setup` (mill-go SKILL.md:42). Derive `status_path` /`task_dir` /`plan_dir`
  from the resolved hub via `_paths.resolve_task_path(hub, ...)`.
- Rationale: cwd-independent and slug-driven — robust whether the operator runs from the
  git root or the hub subfolder. mill-merge already resolves `container_path` and `slug` in
  Step 1, so the inputs are in hand. Keeps the two merge skills consistent with mill-go.
- Rejected: `resolve_hub_path()` (what the #506 workaround used) — simpler call but
  cwd-dependent (walks up from cwd, or relies on a git-root stub declaring
  `hub_relative_path`); more fragile when cwd is the git root of a nested layout.
- In-place-mode caveat (plan must confirm): mill-merge Step 1 sets `mode = 'inplace'` when
  `_inplace.is_inplace(slug, git_root, cfg)` is true, and `1.5 Path Setup` runs for **both**
  modes. In in-place mode cwd *is* the hub and there is no separate `wts/<slug>` worktree, so
  `resolve_active_hub` (which routes through `resolve_active_worktree` -> `container/"wts"/slug`)
  may not match the in-place layout. The discussion only cites mill-go's *worktree-mode* usage
  as precedent. The plan MUST verify the chosen resolver returns the correct hub in in-place
  mode, or branch to a mode-appropriate resolver (e.g. `resolve_hub_path()` / direct
  `git_root`) for the in-place case. Do not assume worktree-mode behavior transfers unchecked.

### squash-safety (#497 bug 2)
- Decision: Keep Step 4's child-side cleanup commit (`git rm -r <task_dir>`). In Step 5,
  after `git -C <parent-path> merge --squash "$CHILD_BRANCH"` and **before** the commit,
  restore the parent's own task_dir: unstage it and `git -C <parent-path> checkout HEAD --
  <task_dir>`. This restores whatever the parent tracked at that path (its own unrelated
  task state) and is a clean no-op when the parent tracks nothing there. Re-inspect the
  staged `--stat` and proceed only with the intended production files.
- Rationale: Always-safe regardless of whether the parent carries task state; no slug
  comparison or conditional logic to get wrong. Mirrors the manual recovery the #497
  reporter performed by hand (`git checkout HEAD -- <path>`).
- Rejected: (a) "exclude task_dir from the squash diff" — functionally the same mechanism
  but framed differently; the restore-from-HEAD framing is clearer and matches the reporter's
  fix. (b) "detect-and-compare slugs" — extra logic and failure modes for no added safety.

### drift-guard scope
- Decision: New unit test scans SKILL.md files for the mill-helper call convention
  `_<module>.<fn>(` (both inline-Python calls and `signature: _module.fn(...)` annotation
  lines), resolves each `(_module, fn)` against the functions defined under
  `plugins/mill/scripts/` **recursing into subpackages** (e.g. `wiki/`), and fails on any
  unresolved reference. The subpackage recursion is essential: `_client` lives only at
  `scripts/wiki/_client.py` and is referenced (`_client.get_task`, `set_phase`,
  `upsert_task`, `health_check`, `list_tasks_brief`, …) by ~10 SKILLs — a non-recursive
  `scripts/*.py` scan would false-positive on every one, and the allowlist must not be the
  workaround for a heavily-used shipped module. Maintain a small explicit allowlist only for
  deliberately-illustrative or not-yet-shipped references.
- Matching precision: the resolver matches each `(_module, fn)` against **module-level `def`s
  only** in `scripts/**/*.py`. The `_<module>.<fn>(` regex can also catch underscore-prefixed
  *locals* (e.g. a SKILL binding `_status = ...` then calling `_status.read(`) and
  dunder/private method calls — these are not module functions and will not resolve. The
  implementer should expect a handful of such legitimate non-module matches and curate them
  into the allowlist rather than treat them as drift failures; the allowlist is for exactly
  this (plus illustrative refs), not for masking real missing helpers.
- Rationale: Targets the exact convention mill uses (underscore-prefixed helper modules),
  keeping the false-positive rate low while catching the real drift class. Broad
  `name.fn()` matching would flood on stdlib (`json.dumps`, `Path.resolve`); `signature:`-only
  matching would miss bare inline calls like the one that caused #504/#505.
- Rejected: all-`module.fn()` matching (too noisy); `signature:`-lines-only (too narrow —
  misses inline calls).

### config-load fix (mill-merge Step 1)
- Decision: Fix the obsolete `<wiki_path>/config.yaml` config load in mill-merge Step 1 as
  part of this task; load the canonical deep-merge of `<hub_root>/mill-config.yaml` +
  `.millhouse/config.local.yaml` (the pattern used by mill-go / `_config.load_config`).
- Rationale: It sits in the same Path Setup region, it is wrong (wiki no longer carries
  config — see commit `ede22180`), and correct config is a prerequisite for correct hub
  resolution. Small, coherent change rather than a separate issue.
- Rejected: deferring to a new issue — would leave mill-merge loading config from a path
  that no longer exists, undermining the hub-resolution fix in the same file.

### treat-already-fixed-issues
- Decision: Verify (don't re-fix) #495, #496, #504, #505. Confirm the source facts in
  Technical context still hold and rely on the drift-guard + existing tests for regression
  coverage. Implementation effort goes to mill-merge / mill-merge-in (#497, #506).
- Rationale: Re-fixing correct code risks regressions and wastes the budget. The four were
  landed by `7fb8f586`; the reports post-date it and reflect cache staleness, not source
  defects.
- Rejected: deep re-audit of all six (no evidence the source fixes are wrong); ignoring the
  four entirely without verification (cheap but leaves the "already fixed?" claim unchecked).

## Technical context

**Layout invariant.** In a nested hub, `git_root` (e.g. `…/wts/<slug>`) ≠ the hub
(`…/wts/<slug>/src/csharp/NORCE.Models`). `_mill/`, `mill-config.yaml`, `.millhouse/` live
under the hub. Git operations (squash, push, archive tag) correctly use `git_root` /
`<parent-path>`; only **task-state paths** (`status_path`, `task_dir`, `plan_dir`) must be
hub-resolved. See CLAUDE.md `## Path invariants`.

**Helpers to reuse (do not reinvent):**
- `_paths.resolve_active_hub(container_path, slug, *, cfg, git_root) -> Path` — the
  cwd-independent hub resolver mill-go uses (`_paths.py:414`).
- `_paths.resolve_hub_path(cwd=None) -> Path` — cwd-walk hub resolver (`_paths.py:153`);
  already used at mill-merge-in line 56.
- `_paths.resolve_task_path(worktree_root, cfg_relative_path) -> Path` — resolve a
  config-relative path against the hub (`_paths.py:525`).
- `_paths.resolve_container_path(git_root)` and `_marker.task_data(...)` /
  `_marker.slug_from_branch(...)` — mill-merge Step 1 already resolves `container_path` and
  `slug`, so `resolve_active_hub` inputs are in hand.
- `_config.load_config(hub_root, worktree_root) -> dict` — canonical deep-merge config load.
- `_parent_branch.resolve(status_path, *, interactive=True) -> str` — reads `parent:` from
  status.md (raises `ParentBranchError` when absent / non-interactive).

**Files to change:**
- `plugins/mill/skills/mill-merge/SKILL.md` — Step 1 config load (~line 21), `1.5 Path
  Setup` (~line 35), Step 4/5 squash safety (~lines 84–107). Note other `git_root` uses in
  this file (Step 6 archive tag line ~203, wiki calls) are git-level and correct — leave them.
- `plugins/mill/skills/mill-merge-in/SKILL.md` — entry step 2 (~line 13), verify-replay
  `plan_dir` (~line 54). Line 56's `resolve_hub_path()` is already correct.
- `plugins/mill/unit_tests/test-<drift-guard-name>.py` — new; `run-all.py:58` auto-discovers
  any `test-*.py` via glob, so just name it `test-*.py` and keep it out of the `SKIP`
  frozenset — there is no registration step.
- `plugins/mill/integration_tests/test-merge.py` — add nested-hub + parent-tracked-task_dir
  scenario.

**Already-correct source state (verify only):**
- #495 — `millpy-review-plan.py:102` sets `project_root = _paths.resolve_hub_path()` (not
  `cwd`) and threads `git_root` into `_plan_validate.run(...)` for fallback path resolution.
- #496 — mill-go SKILL.md:529 `reviews_dir = hub / '_mill/reviews'`; `scratch_dir =
  git_root/.scratch` (line 530) is correct because `millpy-bg.py:179` writes bg logs to
  `git_root/.scratch`. Both holistic and per-batch crash-recovery read the right dirs.
- #504/#505 — `_cleanliness.revert_out_of_scope_drift(...)` exists (`_cleanliness.py:151`),
  is referenced correctly by mill-go step 2b (SKILL.md:247) with a matching `signature:`
  line, and has four unit tests in `test-cleanliness.py`.

**Squash mechanics (for #497 bug 2 fix and its test).** `git merge --squash <child>`
applies the merge-base→child diff to the parent's working tree. Because the child's cleanup
commit deletes `<task_dir>` and the parent independently tracks `<task_dir>/_mill/status.md`
at the *same relative path*, the squash stages a deletion of the parent's file. Restoring
`<task_dir>` from parent `HEAD` after the squash (and re-checking `--stat`) is the fix.

**Test harness note.** `test-merge.py` is an integration test that runs **real git** (no
LLM) and exercises the exact git sequence the prose prescribes. Its existing flat-hub flow
(seed trio → lock → merge-in no-op → squash → archive tag → Home flip → release) is the
template; the new scenario adds a nested hub and a parent-side `_mill/status.md`.

## Constraints

- No `CONSTRAINTS.md` at the hub.
- CLAUDE.md hard constraints apply: never pass junctions to helpers; all path resolution
  through `_paths.py` (no inline `container / "wts" / slug`); `${CLAUDE_PLUGIN_ROOT}` for
  intra-plugin paths in SKILL.md prose; ASCII-only stdout in scripts (`—`→` -- `, `->`→` -> `).
- Verify-command shape: this is a Python project, so plan `verify:` commands MUST start with
  `PYTHONPATH=` (literal empty value). Unit tests run via `uv run --project plugins/mill`;
  integration tests run their own way (see existing invocation in `integration_tests/`).
- SKILL.md edits are prose — they are validated indirectly via the helpers they call and the
  new drift-guard test; there is no "run the skill" unit test.
- Recursive-deletion / wiki-access invariants are not touched by this task (no rmtree, no
  direct wiki mutation introduced).

## Testing

- **Drift-guard unit test (TDD candidate).** New `test-*.py` under `plugins/mill/unit_tests/`.
  Walk every `SKILL.md` under `plugins/mill/skills/` (and consider plugin SKILLs if cheap),
  regex-extract `_<module>.<fn>(` references (covering inline calls and `signature:` lines),
  build the set of functions defined under `plugins/mill/scripts/` **recursing into
  subpackages** (`scripts/**/*.py`, so `wiki/_client.py` is included), and assert every
  referenced `(_module, fn)` exists. Allowlist a small set of intentional exceptions. Must
  FAIL today if pointed at the pre-#504-fix text and PASS against current source. No
  registration step — `run-all.py:58` auto-discovers `test-*.py` via glob; just keep the
  file out of the `SKIP` frozenset.
- **mill-merge nested-hub squash safety (integration, #497 bug 2).** Extend `test-merge.py`:
  build a nested hub (hub is a subdir of the worktree git root; `.millhouse/config.local.yaml`
  with `hub_relative_path`), put a `_mill/status.md` for a *different* task on the parent
  branch at the same relative path, run the cleanup-commit + squash sequence with the new
  restore-from-HEAD step, and assert: (a) the parent's `_mill/status.md` is unchanged after
  the merge commit, (b) only the intended production files are in the squash commit, (c) the
  archive tag still captures the child's cleanup state.
  - **Fixture caveat:** the existing `test-merge.py` fixture builds `<container>/worktrees/<slug>`
    (`test-merge.py:90`), whereas `resolve_active_hub` expects `container/"wts"/slug`
    (`_paths.py`). This scenario exercises the **git-level squash + restore-from-HEAD sequence
    directly** and does not need to route through `resolve_active_hub` — drive the raw git
    commands against the fixture's own paths. Only if the implementer wants to also exercise
    `resolve_active_hub` end-to-end must the fixture be rebuilt in `wts/`-form; that is
    optional and not required to validate bug 2.
- **Hub resolution (regression).** Lean on existing `test-paths.py` /
  `test-hub-relative-path.py` for `resolve_active_hub` / `resolve_task_path` nested behavior;
  add a case only if a gap is found while implementing.
- **Verification of already-fixed issues.** No new tests required beyond the drift guard;
  confirm the Technical-context source facts during implementation (a grep-level check is
  sufficient — do not re-fix).
- Run the full unit suite (`run-all.py`) and the affected integration test green before
  handoff. Do not merge with any red verify (see project rule: never merge defective code).

## Q&A log

- **Q:** How to treat the four issues already fixed by commit 7fb8f586 (#495, #496, #504, #505)?
  **A:** Verify (don't re-fix) and add regression coverage; focus implementation on mill-merge/mill-merge-in (#497, #506).
- **Q:** How should mill-merge prevent the squash from deleting the parent branch's own `_mill/status.md` (#497 bug 2)?
  **A:** After `git merge --squash`, before commit, restore the parent's `task_dir` from parent `HEAD` (no-op when parent tracks nothing there).
- **Q:** Address the "SKILL.md vs shipped-API mismatch" class systemically?
  **A:** Add a unit test that scans SKILL.md for `_module.fn(` references and asserts each resolves to a real shipped function.
- **Q:** Include the adjacent mill-merge config-loading bug (obsolete `<wiki_path>/config.yaml`)?
  **A:** Yes — fix it here; correct config is a prerequisite for correct hub resolution.
- **Q:** Which hub resolver should mill-merge / mill-merge-in use?
  **A:** `resolve_active_hub(container, slug, cfg, git_root)` — match mill-go; cwd-independent.
- **Q:** How to verify #497 bug 2 given mill-merge is prose driving real git?
  **A:** Add a nested-hub + parent-tracked-`_mill/` scenario to integration `test-merge.py`.
- **Q:** How strict should the drift-guard matching be?
  **A:** Underscore-helper calls only (`_module.fn(`), resolve against `scripts/`, with a small allowlist for illustrative references.
