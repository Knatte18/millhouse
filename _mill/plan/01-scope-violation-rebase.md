# Batch: scope-violation-rebase

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: scope-violation-rebase
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py
depends-on: []
```

## Batch Scope

Fixes #603 and #608 (one underlying bug): `_cleanliness.compute_scope_violations` and `_cleanliness.clean_ephemeral_scope_violations` false-positive in nested hub layouts because `_pygit2_util.status_porcelain` always returns git-root-relative paths, but the existing junction-skip and `_mill/`-prefix checks assume those paths are already hub-relative. This batch rebases the paths correctly, drops any path outside the hub subtree (rather than misreporting it as a violation), and updates every caller — including the one external caller in `mill-go/SKILL.md` and the 9 existing flat-layout test cases. This batch's external interface (the two-argument `compute_scope_violations(hub_root, git_root)` / `clean_ephemeral_scope_violations(hub_root, git_root)` signatures) is not consumed by any other batch in this plan — it is independent of batches 2-8, which all deal with the separate `verify:` cwd bug class (#604).

## Cards

### Card 1: Rebase compute_scope_violations for nested hub layouts

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `compute_scope_violations(worktree: Path) -> list[str]` to `compute_scope_violations(hub_root: Path, git_root: Path) -> list[str]`. Compute `hub_prefix = hub_root.relative_to(git_root).as_posix()` (empty string `""` when `hub_root == git_root`, i.e. flat layout). Call `_pygit2_util.status_porcelain(hub_root, include_untracked=True)` unchanged (it always returns git-root-relative paths regardless of which path is passed). For each line starting with `"?? "`, extract `path = line[3:]`. If `hub_prefix` is non-empty: when `path` does not equal `hub_prefix` and does not start with `hub_prefix + "/"`, **drop the path entirely** (continue to the next line — it belongs to a different subtree, not a violation); otherwise strip the `hub_prefix + "/"` prefix to get the hub-relative remainder. If `hub_prefix` is empty, the remainder is `path` unchanged. Apply the existing checks (`not remainder.startswith("_mill/")`, then `remainder.split("/")[0] not in _JUNCTION_SKIP_SET`) to the remainder; on both passing, append the **hub-relative remainder** (not the original git-root-relative `path`) to `violations`. Return `sorted(violations)` as before. Update the docstring to describe the two-argument signature, the hub-relative return contract, and the drop-outside-hub-subtree behavior.
- **Commit:** `fix(cleanliness): rebase compute_scope_violations paths to hub_root in nested layouts (#603)`

### Card 2: Update clean_ephemeral_scope_violations for the new signature

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `clean_ephemeral_scope_violations(worktree: Path) -> tuple[list[str], list[str]]` to `clean_ephemeral_scope_violations(hub_root: Path, git_root: Path) -> tuple[list[str], list[str]]`, forwarding both straight into `compute_scope_violations(hub_root, git_root)`. Rename every remaining reference to the old `worktree` parameter inside the function body to `hub_root`, including the `_is_go_main_artifact(worktree, violation)` call and the file-removal join `file_path = worktree / violation` (becomes `file_path = hub_root / violation`) — both are now correct without further change since `compute_scope_violations` returns hub-relative paths and `hub_root` already held that value at every real call site. Update the docstring's `Args:` section (`worktree` -> `hub_root`, plus the new `git_root` param) accordingly.
- **Commit:** `fix(cleanliness): thread hub_root/git_root through clean_ephemeral_scope_violations (#608)`

### Card 3: Update _implementer_common.py call sites

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update all four call sites of `_cleanliness.compute_scope_violations(project_root)` to `_cleanliness.compute_scope_violations(project_root, git_root)`. `git_root` is already an in-scope local/parameter at each of these call sites (each enclosing function already threads `git_root` for its nearby `_run_verify_gate(..., git_root=git_root)` call) — do not add any new path resolution.
- **Commit:** `fix(implementer-common): pass git_root to compute_scope_violations call sites (#603)`

### Card 4: Update mill-go SKILL.md call site

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update the `_cleanliness.clean_ephemeral_scope_violations(worktree_root)` call to `_cleanliness.clean_ephemeral_scope_violations(worktree_root, git_root)`. Both `worktree_root` (already the resolved hub root via `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)`) and `git_root` are already local variables in scope at that point in the SKILL — no new resolution call needed.
- **Commit:** `docs(mill-go): thread git_root into clean_ephemeral_scope_violations call (#608)`

### Card 5: Update and extend test-cleanliness.py

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Update all 9 existing CESV cases (currently `clean_ephemeral_scope_violations(tmp_path)`) to `clean_ephemeral_scope_violations(tmp_path, tmp_path)` — same value for both roots, since those fixtures are flat-layout; every existing assertion in those 9 cases must remain unchanged (per the Shared Decision on flat-layout byte-identical behavior). Add a new nested-layout case for `compute_scope_violations`: build a fixture where `hub_root = tmp_path / "hub"` is nested one level under `git_root = tmp_path`, create an untracked file at `hub_root / "_mill" / "foo"` and a junction-named entry at `hub_root / ".active"`, and assert both are excluded from the returned violations (calling `compute_scope_violations(hub_root, git_root)`). Add a second nested-layout case with an untracked file *outside* the hub subtree (e.g. `git_root / "othermodule" / "foo.txt"`) and assert it is dropped entirely (absent from the returned list, not present as a violation). Add a new nested-layout case for `clean_ephemeral_scope_violations` asserting both correct violation detection and correct on-disk removal (the file is actually deleted at `hub_root / <violation>`, not at some `git_root`-relative miscomputed path) when `hub_root` is nested.
- **Commit:** `test(cleanliness): cover nested-layout scope-violation rebasing (#603, #608)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanliness.py` runs the full `test-cleanliness.py` file, covering all 9 existing flat-layout CESV cases (updated call signature, unchanged assertions) plus the 3 new nested-layout cases added by Card 5.
