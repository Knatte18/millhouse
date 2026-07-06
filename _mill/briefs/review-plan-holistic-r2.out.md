MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-06
```

## Findings

### [BLOCKING] compute_scope_violations crashes on git_root=None
**Location:** Batch 1, Cards 1 & 3
**Issue:** Card 3 updates the four `_forward_output` call sites to `compute_scope_violations(project_root, git_root)`, passing `_forward_output`'s `git_root` param whose default is `None`; many existing flat-layout tests call `_forward_output(output, ...)` without `git_root` (e.g. test-millpy-implement.py:1143 `_forward_output(output, Path("/fake"))`, and non-mocking cases in test-implementer-common.py), so Card 1's `hub_root.relative_to(git_root)` runs `relative_to(None)` -> TypeError, breaking batch 4's verify and the flat-layout-byte-identical Shared Decision.
**Fix:** Card 1 must treat `git_root is None` (and `git_root == hub_root`) as flat layout with `hub_prefix = ""`, so the `None`-defaulted param path stays byte-identical.

### [BLOCKING] Unbound cwd_override at fixer finalize stage
**Location:** Batch 5, Cards 19 & 20
**Issue:** In millpy-fix.py finalize stage the batch read (line ~239) is nested in `if batch_entry is not None:` and the holistic read (line ~244) in `if batch_verifies:`, with only `verify_cmd = None` pre-initialized (line 231). Cards 19/20 replace those reads with `verify_cmd, cwd_override = parse_verify_field(...)` but never initialize `cwd_override`, so a batch-not-found or all-null-verify holistic finalize leaves `cwd_override` unbound -> NameError at the `finalize_from_output(..., cwd_override=cwd_override)` call. Card 20 additionally describes the finalize holistic read without its existing `if batch_verifies:` guard, which would set `verify_cmd=""` (not `None`) on an empty list.
**Fix:** Initialize `cwd_override = None` alongside `verify_cmd = None` before the scope branch, and preserve the `if batch_verifies:` guard in the finalize holistic path.

### [NIT] Baseline dependency junctions not re-anchored for cwd:hub
**Location:** Batch 4, Card 14
**Issue:** `compute_baseline` junctions `_DEPENDENCY_DIR_CANDIDATES` to `tmp_path / name` (git-root level), but Card 14 re-anchors the verify run to `tmp_path / cwd_override_relative`; for a nested-hub `cwd: hub` baseline the verify runs in the hub subdir while `.venv`/`node_modules` sit one level up, defeating dependency reuse (bounded — baseline is fail-safe).
**Fix:** Also create the junctions under `tmp_path / cwd_override_relative` when it is set.

### [NIT] Garbled Batch Scope prose in batch 5
**Location:** Batch 5, `## Batch Scope`
**Issue:** The narrative is unfinished/self-correcting ("prepare/full stage `~357` — wait, both branches share the same holistic block..."), leaving inaccurate line references; the cards themselves are correct.
**Fix:** Rewrite the paragraph to state the four read sites cleanly (finalize batch ~239, finalize holistic ~242-244, full batch ~284, full holistic ~357).

## Verdict

REQUEST_CHANGES
Two latent crashes (git_root=None deref; unbound cwd_override) must be fixed before approval.
MILL_REVIEW_END