# Discussion: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize

```yaml
task: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize
slug: mill-infra-and-path-fixes
status: discussing
parent: main
```

## Problem

Six independent infrastructure/path bugs in the mill plugin, all surfaced while
running mill against real M2+ repos (where the hub is a git **subfolder** such
as `src/csharp/NORCE.Models/`) and against stacked task-branches. Each was filed
as a separate GitHub issue and folded into this single task because they share a
theme — mill made layout assumptions (hub == git root, parent == base, wiki
clone has tracking, ASCII-only console, single flat `_mill/`) that break outside
the self-hosting `millhouse` repo. **Why now:** these bugs actively wedge the
pipeline — `mill-add`/`mill-spawn` fail on fresh clones (#469, #462), `mill-go`
Handoff wedges (#467), per-repo reviewer overrides are silently ignored (#470),
a review warning prints garbage on Windows (#475), and PR finalize silently
deletes a parent task's state on stacked branches (#482).

The six issues:

- **#462** — wiki daemon `set_phase` masked a push failure as a misleading
  `WikiNotFoundError` when the wiki directory was not a git repo.
- **#467** — mill-go's terminal cleanliness gate (blanket `git status
  --porcelain`) wedges Handoff on unrelated tracked `_mill/` dirt from another
  task.
- **#469** — wiki push uses a bare `git push`, which fails with "no upstream
  branch" when the wiki clone's default branch lacks tracking config.
- **#470** — `_config.load_config` resolves the repo-layer `mill-config.yaml`
  via `<hub_root>/mill-config.yaml`; in container/`wts` layout that path does
  not exist, so per-repo `roles.*` overrides are silently dropped and template
  defaults win.
- **#475** — `_review_common`'s parse-divergence warning contains a U+2014 em
  dash that mojibakes on Windows cp1252 stderr.
- **#482** — mill-finalize PR cleanup runs `git rm -r <task_dir>`
  unconditionally; on a stacked task-branch whose base tracks `_mill/`, this
  deletes the base's own state. git-pr's task-branch guard also uses a literal
  `$GIT_ROOT/_mill/status.md` path that misses nested-hub layouts.

## Scope

**In:**

- **#462** — `wiki/_server.py`, `wiki/_sync.py`: surface a clear, specific error
  when the wiki directory is not a git repository (detected before/inside the
  add/commit/push path) instead of a raw git stderr; add a regression test
  locking the existing correct mapping (a push failure surfaces as
  `WikiPushError`/`ERR_PUSH_FAILED`, never `WikiNotFoundError`/`ERR_NOT_FOUND`).
- **#469** — `wiki/_sync.py` `commit_push`: replace the bare `git push` with an
  explicit-refspec push (`git push origin HEAD:<current-branch>`) so clones
  lacking upstream tracking succeed. Also set upstream tracking in the
  non-orphan clone paths of `_setup.py` (belt-and-suspenders for new clones).
- **#470** — `_config.load_config` (`_config.py`) + `_paths.py`: resolve the
  repo-layer `mill-config.yaml` from the actual clone in container/`wts`
  layout, with a search/fallback when `<hub_root>/mill-config.yaml` is absent;
  emit a warning (never silently drop) if a repo-layer config cannot be located.
- **#475** — `_review_common.py:1241`: make the parse-divergence warning text
  ASCII-only (`—` → ` -- `).
- **#467** — `mill-go/SKILL.md` terminal cleanliness gate (lines ~648-652) +
  a new helper in `_cleanliness.py`: scope the Handoff gate to task-owned paths
  rather than blanket-failing on any dirty tracked file.
- **#482** — `mill-finalize/SKILL.md` Step 3 + `git-pr/SKILL.md` Step 1.5:
  make PR cleanup conditional (restore vs. remove `<task_dir>` based on whether
  the PR base tracks it), and make the git-pr guard use the resolved `task_dir`
  rather than a literal git-root-relative `_mill/`.
- Unit and/or integration tests for every fix (see Testing).

**Out:**

- The spawn-time root cause behind #467/#482 (spawn rewriting a nested
  `_mill/status.md`, hub-vs-worktree `_mill/` placement) — **already fixed and
  merged to `main`** by prior commits (`c2780ec3` spawn `_mill/` at hub subdir,
  `d16807e6` resolve_hub_path cwd-walk for M2+sub repos). This task only fixes
  the downstream gates/cleanup that still mis-handle the resulting state.
- mill-merge (direct-mode) cleanup — #482 is scoped to PR mode + the git-pr
  guard per the issue. If mill-merge is found to have an analogous unconditional
  `git rm -r <task_dir>` during implementation, note it for a follow-up issue
  rather than expanding scope here.
- Gitignoring nested `_mill/` trees in source repos (#467 option a) — a
  cross-repo policy change out of scope; the gate-scoping fix (option b) is the
  in-repo fix.
- Any change to the per-batch cleanliness gate (`compute_new_dirt`) — it already
  diffs against a pre-batch snapshot and correctly ignores pre-existing dirt.
- Broadening the daemon error taxonomy beyond the not-a-git-repo case.

## Decisions

### 462-clear-non-git-repo-error

- Decision: The error-swallowing described in #462 (`set_phase` returning
  `ERR_NOT_FOUND` for a push failure) is **already corrected** in current
  `wiki/_server.py`: `_handle_set_phase` returns `ERR_NOT_FOUND` only when
  `get_task` is genuinely `None`, maps `WikiPushError → ERR_PUSH_FAILED`, and
  maps any other `Exception → ERR_PROTOCOL`. The remaining deliverable is two
  parts: (1) detect "wiki directory is not a git repository" early in the
  mutate path (`commit_push` in `wiki/_sync.py`, or a guard the handlers call)
  and raise a `WikiPushError` (or a new dedicated error) whose message names the
  wiki path and states it is not a git repo — instead of leaking a raw `fatal:
  not a git repository` stderr; (2) add a regression test that drives a
  set_phase / upsert against a non-git wiki dir and asserts the client raises
  `WikiPushError`, never `WikiNotFoundError`.
- Rationale: The misleading-error symptom is fixed; locking it with a test
  prevents regression, and the explicit not-a-git-repo message turns an opaque
  failure into an actionable one (operator knows the wiki clone is broken).
- Rejected: Re-implementing the exception mapping (already correct — would be
  churn). Adding a brand-new `ERR_*`/exception subclass for not-a-git-repo
  (reuse `WikiPushError` with a clear message; the existing taxonomy is
  sufficient and avoids touching the client mapping). Detecting at daemon
  startup only (the wiki can be deleted/de-git'd while the daemon runs; detect
  at the mutate path so the check is always current).

### 469-explicit-refspec-push

- Decision: In `wiki/_sync.py` `commit_push`, replace `git -C <wiki> push` with
  an explicit-refspec push: resolve the current branch
  (`git -C <wiki> rev-parse --abbrev-ref HEAD`) and push `origin
  HEAD:<branch>`. Keep the existing 2-attempt non-fast-forward retry loop
  wrapping it. Additionally, in `_setup.py`'s non-orphan clone paths
  (`clone` / `clone -b --single-branch`), set upstream tracking
  (`git config branch.<b>.remote origin` + `branch.<b>.merge refs/heads/<b>`,
  or push `--set-upstream` on first push) so freshly created clones are
  self-consistent.
- Rationale: The refspec push is the load-bearing fix because it repairs
  **already-existing** clones that lack tracking (a setup-only fix would not
  help clones created before the fix). The setup change is defensive for new
  clones. `HEAD:<branch>` is independent of `push.default` and
  `branch.*.remote`.
- Rejected: `git push --set-upstream origin <branch>` in the push path (mutates
  the user's wiki repo config as a side effect of a render; the refspec push is
  stateless). Hardcoding `master`/`main` (the wiki default branch name varies;
  derive it from HEAD). Setup-only fix (does not repair existing clones).

### 470-resolve-repo-config-from-clone

- Decision: Make `_config.load_config` locate the repo-layer `mill-config.yaml`
  robustly. The current single resolution `<hub_root>/mill-config.yaml`
  (`_paths.resolve_mill_config_path`) is correct when hub == git root (the
  self-hosting case) but yields a non-existent path in container/`wts` layout
  where `hub_root` is the container dir. Resolution order: (1) `<hub_root>/
  mill-config.yaml`; (2) if absent, the primary clone under the container —
  `<container>/wts/<repo>/mill-config.yaml` (derive container via
  `_paths.resolve_container_path`; repo via the main worktree name); (3) if
  still absent, the worktree's own `<worktree_root>/mill-config.yaml`. Merge the
  first that exists. If a repo-layer config is genuinely absent everywhere,
  proceed with template+local layers (current behaviour) but emit a one-line
  stderr note that no repo-layer config was found — never a silent drop.
- Rationale: Per-repo `roles.*` reviewer/model overrides must take effect in
  every supported layout. A search with an explicit "not found" note converts a
  silent correctness bug into either correct behaviour or a visible diagnostic.
- Rejected: Changing `resolve_mill_config_path` signature/contract for all
  callers (other callers expect the hub-root path; keep that helper, add the
  search in `load_config` or a new dedicated resolver). Requiring a stub at the
  worktree root (the M2+sub fix deliberately removed the stub requirement; do
  not reintroduce it). Silently skipping when missing (the bug we are fixing).

### 475-ascii-warning

- Decision: In `_review_common.py`, change the `_warn_if_prose_diverges`
  warning string (line ~1241) from `… (severity=…) — check review file …` to
  use ` -- ` instead of the U+2014 em dash. Scan the rest of the file's
  `print(...)`/`_log(...)` runtime-output paths and convert any other non-ASCII
  glyphs the same way. Leave em dashes in docstrings/comments untouched (they
  never hit cp1252 stdout).
- Rationale: Matches the project-wide invariant (CLAUDE.md: `print()`/`_log()`
  output must be ASCII; Windows cp1252 stdout crashes/mojibakes on non-ASCII).
- Rejected: Forcing UTF-8 on the stderr stream (a global stream-reconfigure is
  heavier and risks other interactions; the ASCII-text rule is the established
  convention). Suppressing the warning (it is a useful diagnostic).

### 467-scope-terminal-gate

- Decision: Replace the blanket terminal cleanliness gate in `mill-go/SKILL.md`
  Handoff (`git status --porcelain --untracked-files=no` → fail if any output)
  with a **task-scoped** check via a new pure-ish helper in `_cleanliness.py`,
  e.g. `compute_terminal_dirt(worktree, task_dir, parent_branch) -> list[str]`.
  Task scope = the union of (a) the `task_dir` subtree and (b) paths changed by
  the task's own commits (`git diff --name-only <parent>...HEAD`). The gate
  fails only when dirt falls inside that scope; dirt outside it (e.g. another
  task's nested `_mill/` tree rewritten on spawn) is ignored. The halt message
  keeps its current shape but lists only in-scope dirty files.
- Rationale: #467's expected behaviour (b) — scope to paths the task actually
  touched. Reuses the existing `_cleanliness` module and `parent_branch` is
  already resolvable from status.md, so no new plumbing into mill-go's state.
- Rejected: Keeping the blanket check (the bug). Capturing a spawn-time
  baseline snapshot for the whole worktree (more plumbing than the
  diff-against-parent approach, which is computable at Handoff from data already
  present). Scoping to `task_dir` only (would miss legitimately-dirty
  source files the task edited but failed to commit — the parent-diff term
  catches those).

### 482-conditional-cleanup-and-guard

- Decision: Two-part fix.
  (1) **mill-finalize Step 3:** before removing `<task_dir>`, detect whether the
  PR base tracks it — `git -C <worktree> cat-file -e <base_branch>:<task_dir
  -relative>/status.md` (or `git ls-tree <base_branch> -- <task_dir>`). If the
  base **tracks** `task_dir`: `git checkout <base_branch> -- <task_dir>` then
  commit (net `_mill/` diff against base becomes empty). If the base does **not**
  track it: keep the current `git rm -r <task_dir>`. Preserve idempotency for
  re-runs. The `base_branch` is the value already resolved in Dispatch.
  (2) **git-pr Step 1.5 guard:** resolve `task_dir` via `_paths`/`_config` when
  the worktree is inside a mill container (so the guard finds `_mill/` at the
  hub-relative location in M2+ repos) and fall back to the literal
  `$GIT_ROOT/_mill/status.md` only when config resolution is unavailable
  (git-pr can run standalone outside mill).
- Rationale: On a stacked task-branch the base tracks `_mill/`; deleting it
  corrupts the base task's state and pollutes the PR diff with unrelated
  deletions. Restoring to base's version yields a source-only PR diff — exactly
  the manual fix the reporter used. The guard must understand nested hubs or it
  silently fails to catch the very case it exists for.
- Rejected: Always `git checkout <base> -- <task_dir>` (wrong when base has no
  tracked `_mill/` — would error/no-op confusingly; the current `git rm` is
  right there). Always `git rm -r` (the bug). Extracting the whole cleanup into
  a Python helper is optional — if the conditional shell becomes unwieldy,
  mill-plan may factor the detection into a small helper for testability, but a
  conditional in the skill is acceptable.

### one-task-six-fixes

- Decision: Implement all six fixes under this one task, as independent
  parallel-friendly work items (each touches a disjoint file set), each with its
  own test(s). Group into plan batches by dependency: the six fixes are mutually
  independent and can each be their own batch.
- Rationale: They are bundled by the wiki task and share a release; they have no
  code overlap, so they parallelize cleanly and there is no reason to split into
  separate tasks.
- Rejected: Splitting into six tasks (overhead with no benefit; they ship
  together). One mega-batch (loses per-fix test isolation and review focus).

## Technical context

Layout reality: this repo (`millhouse`) self-hosts and is the **exception** —
its hub resolves to the worktree itself and `mill-config.yaml` sits at the
worktree root, so several of these bugs do not reproduce here. They reproduce in
**M2+ container repos** (hub is a git subfolder, e.g.
`src/csharp/NORCE.Models/`; primary clone under `<container>/wts/<repo>/`). Keep
that distinction in mind when writing tests — fixtures must simulate the
container/`wts` layout, not the self-hosting layout.

Files and exact current state (verified during discussion):

- **#462** — `plugins/mill/scripts/wiki/_server.py`:
  `_handle_set_phase` (lines 197-225) already returns `ERR_NOT_FOUND` only on a
  genuine `get_task is None`, `WikiPushError → ERR_PUSH_FAILED` (lines 214-218),
  `Exception → ERR_PROTOCOL` (220-224). `_handle_upsert_task` (144-167) mirrors
  this. Client mapping in `wiki/_client.py` `set_phase` (279-310):
  `ERR_NOT_FOUND → WikiNotFoundError`, `ERR_PUSH_FAILED → WikiPushError`, else
  `WikiProtocolError`. The `git add` that fails on a non-git dir is in
  `wiki/_sync.py` `commit_push` (lines 180-259; the add at ~205-206 raises
  `WikiPushError` via `_run` on non-zero exit). Error constants live in
  `wiki/__init__.py` (38-45): `ERR_NOT_FOUND`, `ERR_CONFLICT`,
  `ERR_PUSH_FAILED`, `ERR_PROTOCOL`, `ERR_AUTH`, `ERR_PATH`, `ERR_VALIDATION`;
  exception classes at 48-100.
- **#469** — `plugins/mill/scripts/wiki/_sync.py` `commit_push`, the push loop
  (lines ~230-235) is `git -C <wiki_path> push` (bare). Wiki clone creation is
  in `plugins/mill/scripts/_setup.py` `clone_or_init` (43-191): the orphan-init
  path (154-191) already sets `branch.<b>.remote`/`branch.<b>.merge`; the plain
  clone paths (Path C ~128-135, Path D `--single-branch` ~145-152) do not.
- **#470** — `plugins/mill/scripts/_config.py` `load_config` (151-229);
  repo-layer resolution at line 192 via
  `_paths.resolve_mill_config_path(hub_root)` (`_paths.py` 505-514, returns
  `hub_root / "mill-config.yaml"`); silent skip at 196-199 when the path is
  absent. Helpers: `_paths.resolve_container_path` (275-295, knows
  container-form via `main_root.parent.name == "wts"`),
  `_paths.resolve_hub_path` (145-211, cwd-walk for M2+sub). Merge order is
  template → repo-layer → local stub → local real → env overrides.
- **#475** — `plugins/mill/scripts/_review_common.py`,
  `_warn_if_prose_diverges` (1223-1243); the offending `print(..., file=
  sys.stderr)` is at line ~1238-1243 with U+2014 (`—`) at ~1241. Other em
  dashes in the file are in docstrings/comments only.
- **#467** — terminal gate in `plugins/mill/skills/mill-go/SKILL.md` Handoff
  (lines ~648-652): `git -C <worktree> status --porcelain
  --untracked-files=no`, halt on any output. Path Setup (lines ~38-49) already
  derives `worktree_root`, `status_path`, `task_dir = status_path.parent`,
  `parent_branch` available via status.md. Existing helper module
  `plugins/mill/scripts/_cleanliness.py` (`compute_new_dirt`, 26-50) uses
  `_pygit2_util.status_porcelain(worktree, include_untracked=False)` — reuse
  this for the new terminal helper.
- **#482** — `plugins/mill/skills/mill-finalize/SKILL.md`: Dispatch resolves
  `base_branch` (line 28) and `parent_branch` (29); PR Step 3 cleanup (53-62)
  does `git -C <worktree> rm -r <task_dir>`. `task_dir = status_path.parent`
  (Path Setup, 17). `plugins/mill/skills/git-pr/SKILL.md` Step 1.5 (34-50)
  checks literal `$GIT_ROOT/_mill/status.md`. Path resolution helper:
  `_paths.resolve_task_path` (`_paths.py` 517-530, with `_mill/`→`task/`
  fallback).

Helpers to reuse, not reinvent: `_cleanliness` (gate), `_paths`
(`resolve_container_path`, `resolve_hub_path`, `resolve_task_path`,
`resolve_main_worktree_root`), `_subprocess_util.run`, `_pygit2_util`,
`deep_merge` (in `_config`). Script invocation and test conventions per
CLAUDE.md (`PYTHONPATH=` verify prefix for Python; unit tests via
`uv run --project plugins/mill` + `run-all.py`).

## Constraints

- Console output (`print()`/`_log()`) must be ASCII only — Windows cp1252
  stdout crashes/mojibakes on non-ASCII (the entire point of #475).
- All path resolution goes through `_paths.py`; no inline `container/"wts"/slug`
  or `<wt>/hub_relative` outside the designated helpers. The #470 fix must use
  `_paths` helpers (`resolve_container_path` etc.), not hand-rolled joins.
- Wiki access only via `wiki/_client` / `git -C <wiki_path>` / `_sync`
  helpers — never `cd` into the wiki. The #462/#469 fixes stay inside
  `wiki/_sync.py` and `_setup.py`.
- Do not change `resolve_mill_config_path`'s contract for existing callers
  (#470 adds resolution in `load_config`, not in the shared helper's meaning).
- Verify commands for Python changes must start with the `PYTHONPATH=` (empty)
  prefix per CLAUDE.md so tests load worktree code, not the cache.
- Never silently drop a config layer (#470) — absent repo config must produce a
  visible note.

## Testing

Unit tests (in-memory/tempfile, no real LLM; `plugins/mill/unit_tests/
test-<name>.py`, run via `run-all.py`):

- **#470** — `test-config-repo-layer.py`: build a tempdir simulating
  container/`wts` layout (container dir as `hub_root`, primary clone under
  `wts/<repo>/mill-config.yaml` with a `roles.discussion-review.holistic
  .reviewer: opushigh` override); assert `load_config` returns `opushigh`, not
  the template default. Add a case where no repo config exists anywhere → assert
  template default + that a "no repo-layer config" note is emitted. TDD
  candidate.
- **#475** — `test-review-warning-ascii.py`: invoke `_warn_if_prose_diverges`
  (or its enclosing path) with diverging counts; capture stderr; assert every
  character is ASCII (`all(ord(c) < 128 for c in captured)`). TDD candidate —
  write the assertion first, then fix the string.
- **#467** — `test-cleanliness-terminal.py`: unit-test the new
  `compute_terminal_dirt` scoping logic. If the scope filter is factored as a
  pure function (porcelain lines + scope set → in-scope dirt), test it with
  synthetic input (in-scope dirt flagged; out-of-scope nested `_mill/` ignored).
  TDD candidate.

Integration tests (real git, no LLM; `plugins/mill/integration_tests/`, fixtures
in `.scratch/`):

- **#462** — drive `commit_push` (or a set_phase via the daemon with
  `WIKI_DAEMON_SKIP_PUSH` unset/handled) against a tempdir that is **not** a git
  repo; assert `WikiPushError` is raised (never `WikiNotFoundError`) and the
  message names the path / states "not a git repository". Where feasible, also
  assert the server returns `ERR_PUSH_FAILED`, not `ERR_NOT_FOUND`.
- **#469** — create a bare remote + a clone whose default branch has **no**
  upstream tracking; run `commit_push`; assert the push succeeds (refspec
  path). Also assert `_setup.py`'s plain-clone path leaves tracking configured.
- **#467** — (optional, if not fully covered by the unit test) a real git
  worktree with an out-of-scope dirty tracked file + an in-scope clean state;
  assert `compute_terminal_dirt` returns empty.
- **#482** — two cases: (a) base branch tracks `<task_dir>` → after cleanup the
  `git diff <base>...HEAD` for `_mill/` is empty (restore path); (b) base has no
  tracked `_mill/` → `<task_dir>` is removed (rm path). If the conditional stays
  as skill shell, cover via an integration script that exercises the same git
  commands; if factored into a helper, unit/integration-test the helper.

Scenarios that must be covered regardless of test tier: the M2+ container
layout (not the self-hosting layout) for #470/#467/#482; a non-git wiki dir for
#462; an untracked-default-branch clone for #469; cp1252-unsafe input for #475.

## Q&A log

- **Q:** Fix all six bundled issues in one task, or split them? **A:** [auto-pick] All six in one task as independent, parallel-friendly work items (one plan batch each). **Why:** they share the wiki task and a release, touch disjoint files, and have no code overlap — splitting adds overhead with no benefit.
- **Q:** #462 — the error-swallowing-to-NOT_FOUND already appears fixed in current `_server.py`. What is the deliverable? **A:** [auto-pick] Add early, clear "wiki dir is not a git repository" detection in the mutate path plus a regression test locking the correct mapping (push failure → WikiPushError, never WikiNotFoundError). **Why:** the symptom is fixed; the value left is an actionable message + regression protection, not re-doing the mapping.
- **Q:** #469 — fix the push path, the setup path, or both? **A:** [auto-pick] Both, with the explicit-refspec push (`git push origin HEAD:<branch>`) in `commit_push` as the load-bearing fix and upstream-tracking in `_setup.py`'s plain-clone paths as defence. **Why:** the refspec push repairs already-broken clones (a setup-only fix cannot); setup tracking keeps new clones self-consistent.
- **Q:** #470 — how should the repo-layer config be resolved in container layout? **A:** [auto-pick] Search hub-root → `<container>/wts/<repo>/mill-config.yaml` → worktree root, merging the first found; emit a visible note if none found. **Why:** per-repo reviewer overrides must apply in every layout; a search + explicit "not found" note eliminates the silent drop.
- **Q:** #475 — ASCII-rewrite the warning, or reconfigure the stream to UTF-8? **A:** [auto-pick] ASCII-rewrite (`—` → ` -- `) and scan other runtime-output lines. **Why:** matches the established project-wide ASCII-output invariant; a stream reconfigure is heavier and out of convention.
- **Q:** #467 — how to scope the terminal cleanliness gate? **A:** [auto-pick] Scope to task-owned paths = `task_dir` subtree ∪ `git diff --name-only <parent>...HEAD`, via a new `_cleanliness.compute_terminal_dirt` helper. **Why:** matches the issue's expected behaviour (b), reuses existing machinery, needs no new state plumbing into mill-go.
- **Q:** #482 — restore vs. remove `<task_dir>` in PR cleanup? **A:** [auto-pick] Conditional: if the PR base tracks `<task_dir>` → `git checkout <base> -- <task_dir>` (net _mill/ diff empty); else keep `git rm -r`. Plus fix the git-pr guard to use the resolved `task_dir`. **Why:** restoring to base yields a source-only PR diff on stacked branches without corrupting the base task's state; always-remove is the bug, always-restore breaks the clean-base case.
- **Q:** What is explicitly out of scope? **A:** [auto-pick] The already-merged spawn/path root-cause fixes, mill-merge direct-mode cleanup, gitignoring nested `_mill/`, and any change to the per-batch `compute_new_dirt` gate. **Why:** the spawn fixes already landed on `main`; the per-batch gate already handles pre-existing dirt; mill-merge and gitignore policy are separate concerns (note, don't expand).
