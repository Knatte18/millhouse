# Discussion: (A) -- Central safe-rmtree helper + ban direct rmtree

```yaml
task: (A) -- Central safe-rmtree helper + ban direct rmtree
slug: safe-rmtree
status: discussing
parent: main
```

## Problem

A third wiki-wipe incident occurred on 2026-05-13 during the
`mill-misc-fixes-7` batch 1 verify run. A test or script invoked
`shutil.rmtree` against a worktree that still had live NTFS directory
junctions; `shutil.rmtree` followed those junctions into shared state
(wiki / portals / hub root) and deleted them.

The existing rule in `CLAUDE.md` (`## Path invariants`) already mandates
calling `_junction.strip_all_in_worktree(worktree, junctions_cfg)`
before any recursive deletion. That rule has now been violated three
times -- twice from production scripts, once from a test fixture.
Operator discipline is not enough; the prevention must be enforced
mechanically.

The fix has two parts: (1) a centralised helper that detects junctions
on the filesystem (independent of `junctions_cfg`) and strips them
before deletion, and (2) a unit-test gate that fails the suite if any
direct `shutil.rmtree` / `rmdir /s` / `os.removedirs` call appears in
mill code outside an explicit whitelist.

## Scope

**In:**

- New helper module `plugins/mill/scripts/_safe_rmtree.py` exposing
  `safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None`.
- Recursive NTFS reparse-point detection inside `path` (Windows) via
  `os.path.isjunction` (Py 3.12+) with `st_file_attributes & 0x400`
  fallback for Py 3.10/3.11. Each detected junction is removed via
  `_junction.remove` before `shutil.rmtree`.
- Hard refusal (`SystemExit`) when `path` -- or any path it resolves
  to -- matches a blacklisted shared-state location: the container
  root, `<container>/wiki/`, `<container>/portals/`, or
  `<container>/wts/<main-repo-name>/`. Blacklist derived via
  `_paths.resolve_container_path(allowed_root)`.
- Hard refusal when `path` itself is a junction (caller should use
  `_junction.remove`).
- Silent no-op when `path` does not exist.
- `ignore_errors=True` passthrough to `shutil.rmtree`.
- Migration of `_worktree.remove_safe`'s `shutil.rmtree` fallback to
  call `_safe_rmtree` (single source of truth for safe rmtree).
- Migration of every `shutil.rmtree` / `rmdir /s` / `os.removedirs`
  callsite in `plugins/mill/` (scripts + unit_tests + integration_tests)
  to `_safe_rmtree`, except for an explicit whitelist.
- New gate file `plugins/mill/unit_tests/test-no-direct-rmtree.py` that
  greps `plugins/mill/` for direct removal calls and fails if any
  appear outside the whitelist. Discovered automatically by
  `unit_tests/run-all.py`.
- New unit test `plugins/mill/unit_tests/test-safe-rmtree.py` covering:
  blacklist refusal, junction stripping before rmtree,
  `ignore_errors` semantics, missing-path no-op, path-is-junction
  refusal, POSIX skip-detection branch.

**Out:**

- `plugins/codeguide/` callsites. One plugin at a time; codeguide
  remains free to call `shutil.rmtree` directly until a separate task
  migrates it.
- `_junction.strip_all_in_worktree` -- kept as-is. It serves a
  different purpose (config-driven CRUD for named junctions in
  `mill-cleanup`) and is not removed or deprecated. `_safe_rmtree`
  does FS-level walk-and-detect, which is independent of
  `junctions_cfg` and complementary.
- Changing `_worktree.remove_safe`'s git-first flow. Only the
  `shutil.rmtree` fallback line is migrated; the `git worktree remove`
  attempt and long-path / locked-error handling stay where they are.
- Pre-commit hooks. The gate runs inside `unit_tests/run-all.py` only.
- `os.unlink` / `pathlib.Path.unlink` / single-file `os.remove`.
  Scope is recursive deletion only -- single-file deletes cannot
  follow a junction recursively.
- Any change to `_junction.create` / `_junction.remove`. These are the
  underlying primitives `_safe_rmtree` calls; their contracts do not
  change.

## Decisions

### API shape

- Decision: One function -- `safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None`.
- Rationale: `allowed_root` forces the caller to declare the
  containment scope of the operation (typically the scratch tempdir
  or task worktree it owns). The helper uses `allowed_root` to
  resolve the container via `_paths.resolve_container_path` and
  computes the blacklist from there. Forcing the caller to name the
  scope is the safety contract -- a function that takes only `path`
  cannot distinguish "I am tearing down my scratch tempdir" from "I
  am being passed an attacker-controlled string".
- Rejected:
  - A path-only API (`safe_rmtree(path)`) -- weaker safety contract.
  - Two specialised functions (`safe_rmtree_worktree`,
    `safe_rmtree_scratch`) -- duplicates the strip+rmtree body; the
    single function is enough.

### Refusal blacklist

- Decision: Refuse with `SystemExit` if `path.resolve()` is, or is a
  parent of, any of: `<container>/`, `<container>/wiki/`,
  `<container>/portals/`, `<container>/wts/<main-repo-name>/`. Also
  refuse if `path` resolves outside `allowed_root`.
- Rationale: These are the four shared-state locations whose loss is
  unrecoverable in the millhouse container layout (see CLAUDE.md
  `## Project shape`). `<main-repo-name>` is the directory under
  `<container>/wts/` whose name matches the container's name -- i.e.
  the primary clone.
- Rejected:
  - Adding `<container>/codeguide/` to the blacklist -- codeguide is
    in the container but task is mill-scoped; codeguide migration is
    a separate task. The blacklist can be extended later.
  - Adding *all* sibling `<container>/wts/<slug>/` worktrees --
    sibling task worktrees ARE intended to be deletable by
    `mill-cleanup`; blacklisting them breaks the normal flow. The
    `allowed_root` containment check is the right protection for
    sibling-worktree confusion (operator passes the wrong worktree
    path -- `allowed_root` mismatch catches it).
  - Paranoid blacklist (home dir / drive root / cwd) -- not needed;
    container-scoped blacklist plus `allowed_root` containment
    covers the realistic failure modes.

### Reparse-point detection

- Decision: Walk `path` with `os.scandir(..., follow_symlinks=False)`
  before calling `shutil.rmtree`. For every entry: if it is a
  junction (per `os.path.isjunction` on Py 3.12+ or
  `st_file_attributes & 0x400` fallback) or symlink, call
  `_junction.remove` and skip recursion into it. Recurse only into
  real directories.
- Rationale: The task description explicitly requires detection
  "uavhengig av `junctions_cfg`" -- i.e. the helper cannot trust
  config; it must discover junctions on the filesystem. This catches
  ad-hoc junctions created by tests, half-cleaned-up junctions from
  earlier mill-spawn runs, and anything else the config does not
  know about.
- Rejected:
  - Trust `junctions_cfg` only -- reproduces the very bug the helper
    is meant to prevent.
  - Belt-and-suspenders (strip via config first, then walk) -- the
    walk is strictly more general; calling
    `strip_all_in_worktree` first is redundant inside
    `_safe_rmtree`. Callers that want the named CRUD still call
    `_junction.strip_all_in_worktree` directly for its own purpose.

### Relationship to `_junction.strip_all_in_worktree`

- Decision: Keep `_junction.strip_all_in_worktree` as-is. Document in
  its docstring that it is the config-driven named-junction CRUD API
  (used by `mill-cleanup` to remove the predictable
  `.wiki` / `.active` / `.portals` set), and that `_safe_rmtree` is
  the FS-level walk-and-detect API used as a safety prelude to
  recursive deletion. The two have distinct, complementary scopes.
- Rationale: The task description states explicitly that
  "`_junction.py` beholder sitt eksisterende scope (junction CRUD) --
  sletting av worktree-trær er separat ansvar". The two APIs are
  not duplicates; they answer different questions ("remove these
  named junctions" vs. "find and strip every junction inside this
  tree").
- Rejected:
  - Deprecate `strip_all_in_worktree` -- removes useful named-CRUD
    behaviour for callers that do not actually delete the tree
    afterwards (mill-cleanup partial paths).
  - Have `_safe_rmtree` subsume it -- mixes responsibilities.

### `_worktree.remove_safe` migration

- Decision: The `shutil.rmtree(str(path), ignore_errors=False)` call
  on line `_worktree.py:267` is replaced with
  `_safe_rmtree.safe_rmtree(path, allowed_root=path)`. The rest of
  `remove_safe` (junction-config strip, `git worktree remove
  --force`, error classification, `git worktree prune`) stays as-is.
- Rationale: `_worktree.remove_safe` already strips config-declared
  junctions before the rmtree fallback; calling `_safe_rmtree`
  there adds the walk-and-detect safety pass and routes through the
  single audited helper. `allowed_root=path` is correct: the
  worktree directory is exactly the scope being torn down.
- Rejected:
  - Leave `_worktree.remove_safe` alone and whitelist it in the gate
    -- bypasses the safety net the helper provides.
  - Replace `remove_safe` body entirely with a `_safe_rmtree` call
    -- loses the `git worktree remove --force` happy path that
    avoids the rmtree fallback in 99% of cases.

### Gate mechanism

- Decision: A new test file
  `plugins/mill/unit_tests/test-no-direct-rmtree.py` runs as part of
  `unit_tests/run-all.py`'s normal `test-*.py` discovery. It greps
  every `.py` file under `plugins/mill/` for the patterns
  `shutil\.rmtree`, `os\.removedirs`, and `rmdir\s+/s` (cmd.exe
  recursive-delete idiom used inside `subprocess.run` strings). Any
  match outside the whitelist fails the test.
- Rationale: Test-suite gating is enforced by CI (and by the
  `mill-go` per-batch test contract). Pre-commit hooks are
  out-of-band and easy to bypass; a unit test is not.
- Rejected:
  - Pre-commit hook -- bypassable, not enforced by CI.
  - Inline check in `run-all.py` -- separating the gate into its own
    file keeps `run-all.py` minimal.
  - Both -- one mechanism is enough; duplicate enforcement is just
    noise.

### Gate whitelist

- Decision: The gate file declares an explicit `ALLOWED_FILES: set[str]`
  list (paths relative to repo root). Initially:
  `_safe_rmtree.py` (the implementation itself) and
  `test-safe-rmtree.py` (which uses `shutil.rmtree` in its mocked
  branches). Any other file that triggers a match fails the test.
- Rationale: Auditable in one place; no in-line `# noqa:`
  decorations cluttering callsites. Adding a new entry requires an
  explicit edit reviewable in PR.
- Rejected:
  - `# noqa: safe-rmtree` per line -- scatters audit data across the
    codebase; reviewers cannot tell at a glance which files are
    exempt.
  - Both mechanisms -- duplicate exemption channels invite drift.

### `ignore_errors` semantics

- Decision: `safe_rmtree(path, *, allowed_root, ignore_errors=False)`.
  When `True`, the parameter is forwarded to `shutil.rmtree`. There
  is no `onerror` callback parameter.
- Rationale: Many existing test cleanups use `ignore_errors=True` to
  be robust against locked files in Windows CI; preserving that
  semantics is required for a drop-in migration. Custom `onerror`
  callbacks are not used in the existing callsites (only
  `test-review-code.py:_remove_tree` has one, and that file's
  function will be replaced wholesale by a `safe_rmtree` call).
- Rejected:
  - Refuse `ignore_errors` entirely (always raise) -- forces a
    rewrite of every test teardown; out-of-scope churn.
  - Add `onerror` passthrough -- no caller needs it; YAGNI.

### Platform behaviour

- Decision: The blacklist refusal and `allowed_root` containment
  check apply on all platforms. The reparse-walk step is a no-op on
  POSIX (no junctions; symlinks are skipped via
  `os.scandir(follow_symlinks=False)` which `shutil.rmtree` already
  handles correctly).
- Rationale: The refusal logic protects against logic bugs (caller
  passes the wrong path); those bugs exist on every platform.
  Reparse-points are Windows-specific.
- Rejected:
  - Windows-only refusal -- weakens cross-platform safety;
    integration tests run on POSIX CI.

### Path-is-junction handling

- Decision: If `path` itself is a junction (`os.path.isjunction(path)`
  or `path.is_symlink()`), refuse with `SystemExit`. Message points
  the caller at `_junction.remove`.
- Rationale: `shutil.rmtree` on a junction follows the junction;
  this is the original failure mode. Refusing forces the caller to
  use the correct primitive.
- Rejected:
  - Strip and return as no-op -- silent surprise; caller may have
    intended to delete the real target.
  - Strip and rmtree the resolved target -- amplifies the blast
    radius; defeats the safety goal.

### Missing-path handling

- Decision: If `path` does not exist (`not path.exists() and not
  path.is_symlink()` -- the symlink check handles broken junctions),
  return silently. No exception regardless of `ignore_errors`.
- Rationale: Matches `shutil.rmtree(..., ignore_errors=True)` for
  missing inputs and is what every existing test teardown assumes.
- Rejected:
  - Raise `FileNotFoundError` unless `ignore_errors=True` -- forces
    every teardown to pass `ignore_errors=True`, defeating the
    "default to strict" philosophy.

### Long-path / git fallback chain

- Decision: `_safe_rmtree` owns only strip + `shutil.rmtree`. It
  does not invoke `git worktree remove`. `_worktree.remove_safe`
  keeps its existing git-first happy path and calls `_safe_rmtree`
  only when it needs to fall back to a direct filesystem delete.
- Rationale: `git worktree remove` is the right primitive for
  worktree teardown; `_safe_rmtree` is the right primitive for
  scratch dirs and the worktree-fallback case. Mixing them in one
  function couples concerns.
- Rejected:
  - `_safe_rmtree` internally tries `git worktree remove` first --
    confuses the API; scratch-dir callers do not have a git
    worktree.
  - Drop the git-first fallback -- loses the only path that handles
    `is in use` errors cleanly.

### Container resolution

- Decision: The helper computes the blacklist by calling
  `_paths.resolve_container_path(allowed_root)`. From the returned
  container, derive: `container`, `container / "wiki"`,
  `container / "portals"`, `container / "wts" / container.name`.
- Rationale: `_paths.resolve_container_path` already exists and is
  the authoritative resolver; the helper reuses it. The main-repo
  name equals the container name by convention (see CLAUDE.md
  `## Project shape`: `c:/Code/millhouse/wts/millhouse/`).
- Rejected:
  - Caller passes `container_root` explicitly alongside
    `allowed_root` -- duplicate information; the container can be
    derived from any path inside it.
  - Walk up from `path` to find the container -- works but
    duplicates `_paths` logic.

## Technical context

**Helper location:** `plugins/mill/scripts/_safe_rmtree.py`. Underscore
prefix per the existing convention for non-CLI helper modules.

**Key existing modules:**

- `plugins/mill/scripts/_junction.py` -- junction CRUD primitives.
  `_safe_rmtree` calls `_junction.remove(link_path)` for each
  detected junction. Reuses the existing Py-version-aware
  `isjunction` detection logic (`os.path.isjunction` or
  `st_file_attributes & 0x400`).
- `plugins/mill/scripts/_paths.py` -- has
  `resolve_container_path(path) -> Path`. Returns the container root
  for any path inside `<container>/wts/<...>/`.
- `plugins/mill/scripts/_worktree.py` -- `remove_safe` is the sole
  production caller migrated in this task (line `_worktree.py:267`).
- `plugins/mill/unit_tests/run-all.py` -- discovers
  `test-*.py` automatically. No change needed there;
  `test-no-direct-rmtree.py` is picked up by the existing
  discovery.

**Callsites to migrate** (output of `grep -rn 'shutil\.rmtree\|rmdir\s\+/s\|os\.removedirs' plugins/mill/`):

`plugins/mill/scripts/`:
- `_worktree.py:267` -- the `shutil.rmtree` fallback inside
  `remove_safe` (replaced by `_safe_rmtree` call).
- `millpy-cleanup.py:405` -- comment reference only; no actual call
  here. No change.

`plugins/mill/unit_tests/`:
- `test-millpy-implement-holistic.py:106`,
  `test-millpy-implement.py:95`,
  `test-millpy-merge-in-subagent.py:36`,
  `test-millpy-spawn.py:825, 887, 1002` --
  `addCleanup(shutil.rmtree, self.tmp_path, ignore_errors=True)`.
  Migrated to `addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path,
  allowed_root=self.tmp_path, ignore_errors=True)`.
- `test-worktree.py:196, 255` -- `patch("_worktree.shutil.rmtree",
  ...)`. The patch target changes to
  `_worktree._safe_rmtree.safe_rmtree` (or whatever the import shape
  is); these tests stay in the whitelist temporarily as `noqa` is
  not used. The patch-mock invocations are not real
  `shutil.rmtree` calls but the regex would match them; whitelist
  this file. The line-241/242 string `expected path to be removed
  by rmtree` is a comment / string and also matches the regex; the
  whitelist takes care of it.
- `test-cleanup.py:481` -- comment string only. Whitelist or
  reword.

`plugins/mill/integration_tests/`:
- `smoke-llm-claude.py:154`, `smoke-llm-gemini.py:142`,
  `test-cleanup.py:235`, `test-go-assets.py:306`,
  `test-merge.py:361`, `test-inspect.py:164, 193`,
  `test-spawn.py:139, 264`, `test-plan-assets.py:261`,
  `test-status.py:215`, `test-wiki-concurrency.py:128`,
  `test-abandon.py:198`, `test-review-discussion.py:85`,
  `test-review-plan.py:86` --
  `shutil.rmtree(container_or_scratch, ignore_errors=True)`.
  Migrated to `_safe_rmtree.safe_rmtree(target, allowed_root=target,
  ignore_errors=True)`. Note that integration tests typically delete
  a fresh `.scratch/test-<name>/` container they just built; the
  blacklist will not match these because they are under
  `<repo>/.scratch/`, not under the real container's shared paths.
  The blacklist's container is resolved from `allowed_root`, which
  for `.scratch/test-X/` resolves to a synthetic container -- safe.
- `test-review-code.py:183` --
  `_remove_tree(root)` calls `shutil.rmtree(root, onerror=_on_error)`.
  Replaced with `_safe_rmtree.safe_rmtree(root,
  allowed_root=root, ignore_errors=True)`. The custom `_on_error`
  handler for read-only `.git` files is lost; `ignore_errors=True`
  is sufficient because the test is in teardown.

**`resolve_container_path` behaviour for non-container paths:**
`_safe_rmtree` operates on tempdir paths that are NOT inside any
container (e.g. `tempfile.mkdtemp()` returns a path under
`$TEMP\<tmp>`, well outside `<container>/wts/<slug>/`). The
implementation must handle this gracefully: if
`resolve_container_path(allowed_root)` raises or returns a path that
does not match the millhouse container layout, the blacklist
defaults to "no shared-state paths to protect" -- the
`allowed_root` containment check still applies. The
implementation can wrap `resolve_container_path` in a try/except
and skip blacklist construction when it fails.

**Symlink vs. junction detection:**
`os.path.isjunction` is Py 3.12+. For Py 3.10/3.11 (the project
supports both -- see CI matrix), fall back to
`os.lstat(path).st_file_attributes & 0x400`. The exact pattern is
already implemented in `_junction.remove` (`_junction.py:171-178`)
and should be lifted into a private helper
`_is_reparse_point(p: Path) -> bool` to avoid duplication.

**Long-path concern:** the existing `_worktree.remove_safe`
fallback explicitly mentions long-path failures on Windows (deep
claude session JSONs under `.scratch/`). When `_safe_rmtree` is
called from `remove_safe`, it inherits the same exposure. The
walk-and-detect pass uses `os.scandir`, which handles long paths
no worse than `shutil.rmtree`. If `shutil.rmtree` itself raises a
long-path `OSError`, `_safe_rmtree` lets it propagate (callers
handle it as `WorktreeLockedError` upstream).

**Path resolution for blacklist check:**
Resolve both `path` and the blacklist entries via
`Path(p).resolve()` before comparing. This handles relative paths
and the `\\?\` Windows long-path prefix consistently. Comparison
is `resolved_path == blacklist_entry or blacklist_entry in
resolved_path.parents` (equality OR ancestor -- protects against
"trying to delete the wiki" and "trying to delete the container").

## Constraints

- **Cross-platform.** All Windows-specific reparse-point checks
  must be guarded by `os.name == "nt"`; POSIX falls through.
- **Python 3.10+ support.** `os.path.isjunction` is 3.12+ only.
  Lift the existing 3.10/3.11 fallback from `_junction.remove`.
- **ASCII-only stdout/stderr** (CLAUDE.md). Helper `print()`s use
  ASCII only; em-dash -> ` -- `, arrow -> ` -> `.
- **No `if __name__ == "__main__":` smoke-test block** in the
  helper (CLAUDE.md: "Helpers hold only production code").
- **`PYTHONPATH` invocation form for tests** (CLAUDE.md): the gate
  is invoked via the existing `run-all.py` discovery; nothing
  special needed.
- **No mutations to `_junction.py`'s public API.** The existing
  `create` / `remove` / `strip_all_in_worktree` / `resolve_target`
  / `has_slug_token` signatures are stable.
- **No mutations to `_worktree.py`'s public API.** Only the
  internal `shutil.rmtree` call on line 267 changes.

## Testing

**TDD candidate:** `_safe_rmtree.safe_rmtree`. Pure-FS contract
that lends itself to a `tempfile.TemporaryDirectory()` setup +
explicit assertions. Write tests first.

**`plugins/mill/unit_tests/test-safe-rmtree.py` -- scenarios:**

- `test_refuses_when_path_equals_container_root`: build a fake
  container layout under tempdir, call `safe_rmtree(container,
  allowed_root=container)`, assert `SystemExit`.
- `test_refuses_when_path_is_wiki`: same fake layout, target
  `container/wiki`, assert `SystemExit`.
- `test_refuses_when_path_is_portals`: target `container/portals`,
  assert `SystemExit`.
- `test_refuses_when_path_is_main_repo_worktree`: target
  `container/wts/<container.name>`, assert `SystemExit`.
- `test_refuses_when_path_is_ancestor_of_blacklist`: target the
  container root via a parent dir -- e.g. `safe_rmtree(parent,
  allowed_root=parent)` where `parent` contains the wiki -- assert
  `SystemExit`. (Catches "delete this whole tree" mistakes.)
- `test_refuses_when_path_outside_allowed_root`: `allowed_root`
  points at `tempdir/a`, `path` is `tempdir/b`, assert
  `SystemExit`.
- `test_refuses_when_path_is_junction` (Windows-only, skipped on
  POSIX): create a junction via `_junction.create`, call
  `safe_rmtree` against the junction itself, assert `SystemExit`.
- `test_strips_junction_inside_tree_before_rmtree` (Windows-only):
  build `scratch/sub/.wiki -> shared_target/`, call
  `safe_rmtree(scratch, allowed_root=scratch)`, assert `scratch`
  is gone AND `shared_target/` still exists with its contents
  intact. This is the regression-guard for the wiki-wipe
  incident.
- `test_strips_multiple_junctions_at_different_depths` (Windows):
  junctions at root, at depth 2, at depth 3 -- all stripped.
- `test_strips_symlink_inside_tree` (POSIX): same as junction
  test but with `os.symlink`. Verifies cross-platform behaviour.
- `test_missing_path_is_noop`: path does not exist, returns
  silently regardless of `ignore_errors`.
- `test_ignore_errors_true_swallows_oserror`: mock
  `shutil.rmtree` to raise; verify `ignore_errors=True` makes the
  exception not propagate, `ignore_errors=False` re-raises.
- `test_passes_ignore_errors_to_shutil`: assert via mock that
  `shutil.rmtree` is called with `ignore_errors=` matching the
  caller's argument.
- `test_handles_non_container_allowed_root`: `allowed_root` is a
  `tempfile.mkdtemp()` path outside any millhouse container --
  `resolve_container_path` failure does not crash the helper;
  blacklist defaults to empty; rmtree proceeds.

**`plugins/mill/unit_tests/test-no-direct-rmtree.py` -- scenarios:**

- `test_no_direct_shutil_rmtree_in_plugins_mill`: grep
  `plugins/mill/` for `shutil\.rmtree`, fail if any non-whitelisted
  file contains a match.
- `test_no_direct_os_removedirs_in_plugins_mill`: same for
  `os\.removedirs`.
- `test_no_rmdir_recursive_in_plugins_mill`: same for `rmdir\s+/s`.
- `test_whitelist_files_exist`: every path in `ALLOWED_FILES`
  must exist on disk -- guards against drift where a file is
  renamed but the whitelist entry isn't updated.

**Migrating existing test files:** the unit-test files that
already use `shutil.rmtree` in `addCleanup` are migrated to call
`_safe_rmtree.safe_rmtree`. None of their behaviour changes; the
existing assertions stay.

**Integration tests:** all integration tests that build a
`.scratch/<name>/` container and tear it down via
`shutil.rmtree(container, ignore_errors=True)` are migrated. No
new integration tests are required; the existing tests exercise
the migrated path and would fail if the migration breaks
teardown.

## Q&A log

- **Q:** What is the primary entry-point API? **A:** [auto-pick] `safe_rmtree(path: Path, *, allowed_root: Path, ignore_errors: bool = False) -> None`. **Why:** `allowed_root` forces the caller to declare the operation's scope; the helper derives the blacklist from there.
- **Q:** Which paths are blacklisted (refused)? **A:** [auto-pick] `<container>/`, `<container>/wiki/`, `<container>/portals/`, `<container>/wts/<main-repo-name>/`. **Why:** Four shared-state paths whose loss is unrecoverable; codeguide and sibling worktrees deliberately excluded.
- **Q:** How are junctions detected before rmtree? **A:** [auto-pick] FS-walk with `os.scandir(follow_symlinks=False)` and `os.path.isjunction`/`st_file_attributes` detection, independent of `junctions_cfg`. **Why:** Task description requires "uavhengig av junctions_cfg"; catches ad-hoc test junctions.
- **Q:** What happens to `_junction.strip_all_in_worktree`? **A:** [auto-pick] Kept as-is. **Why:** Different scope -- named-CRUD for `mill-cleanup`; `_safe_rmtree` is FS-level walk-and-detect. Complementary, not duplicate.
- **Q:** Does `_worktree.remove_safe` migrate? **A:** [auto-pick] Yes -- only the `shutil.rmtree` fallback line (line 267); rest of `remove_safe` stays. **Why:** Single source of truth for safe rmtree without disrupting the git-first happy path.
- **Q:** Which directories' callsites get migrated? **A:** [auto-pick] `plugins/mill/` only (scripts + unit_tests + integration_tests). **Why:** One plugin at a time; codeguide migration is a separate task.
- **Q:** How is the gate enforced? **A:** [auto-pick] `plugins/mill/unit_tests/test-no-direct-rmtree.py` -- grep gate discovered automatically by `run-all.py`. **Why:** Tests are CI-enforced; pre-commit hooks are bypassable.
- **Q:** How is the whitelist expressed? **A:** [auto-pick] Explicit `ALLOWED_FILES` set in the gate file. **Why:** Auditable in one place; no scattered `# noqa:` decorations.
- **Q:** `ignore_errors` semantics? **A:** [auto-pick] `ignore_errors=False` default, `True` forwards to `shutil.rmtree`. No `onerror` callback. **Why:** Drop-in migration for existing test teardowns; no caller needs `onerror`.
- **Q:** Refusal behaviour on POSIX? **A:** [auto-pick] Applies on all platforms; reparse-walk is no-op on POSIX. **Why:** The refusal logic catches logic bugs on every platform.
- **Q:** Path is itself a junction? **A:** [auto-pick] Refuse with `SystemExit`, point caller at `_junction.remove`. **Why:** Prevents silent recursion into the junction's target.
- **Q:** Path does not exist? **A:** [auto-pick] Silent no-op. **Why:** Matches `shutil.rmtree(ignore_errors=True)` and what every existing test teardown assumes.
- **Q:** Does `_safe_rmtree` try `git worktree remove` first? **A:** [auto-pick] No -- it owns only strip + `shutil.rmtree`; `_worktree.remove_safe` keeps its git-first flow. **Why:** Separation of concerns; scratch-dir callers do not have a git worktree.
- **Q:** Unit-test coverage scope? **A:** [auto-pick] Refusal cases, junction-strip-before-rmtree (the regression guard for the wiki-wipe incident), `ignore_errors` semantics, missing-path no-op, path-is-junction refusal, POSIX symlink branch. **Why:** Covers every documented decision; the junction-strip scenario is the specific incident this task exists to prevent.
- **Q:** How does the helper know the container root? **A:** [auto-pick] `_paths.resolve_container_path(allowed_root)`. **Why:** Reuses the authoritative resolver; main-repo name equals container name by convention.
