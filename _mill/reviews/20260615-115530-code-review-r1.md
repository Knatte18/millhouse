MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-15
```

## Findings

### [BLOCKING] `_review_common.load_config` passes `.millhouse` dir as `worktree_root`

**Location:** `plugins/mill/scripts/_review_common.py:1420`
**Issue:** `resolve_repo_config_path(hub_root, mill_dir)` is called where `mill_dir` is the `.millhouse` directory (e.g. `<worktree>/.millhouse`), not the worktree root. Candidate 3 in `resolve_repo_config_path` therefore checks `<worktree>/.millhouse/mill-config.yaml` instead of `<worktree>/mill-config.yaml`, silently missing the worktree-root config. Candidate 2 (`resolve_main_worktree_root(mill_dir)`) still resolves correctly because git walks up from any subdir, so only candidate 3 is broken — but the plan spec says all three candidates must be checked against worktree-relative paths, not `.millhouse`-relative paths.
**Fix:** Pass the parent of `mill_dir` (i.e. `mill_dir.parent`) as the second argument: `resolve_repo_config_path(hub_root, mill_dir.parent)`.

### [BLOCKING] `git-pr` Step 1.5 bash guard never halts — no `exit 1` emitted

**Location:** `plugins/mill/skills/git-pr/SKILL.md:51-73`
**Issue:** Both the mill-python-resolution branch and the standalone-literal-check branch contain `# halt with the redirect message below` followed by a `: ` no-op. There is no `echo` or `exit 1` in either arm, so detection that `STATUS_PATH` exists never actually stops PR creation — it falls through to step 2. The guard is entirely inert.
**Fix:** Replace the `: ` no-op in each `if` arm with the redirect message echoed to stderr followed by `exit 1`. The outer `elif`/`else` structure in the standalone branch also needs a working termination path.

### [BLOCKING] Path C `cfg_remote` failure is silently swallowed in `_setup.clone_or_init`

**Location:** `plugins/mill/scripts/_setup.py:140-155`
**Issue:** After a successful Path C clone, `cfg_remote` is run but if its `returncode != 0` the code silently continues (no raise, no log) and `cfg_merge` is never run. The upstream-tracking config is then absent even though the plan requires it to be configured deterministically on all plain-clone paths.
**Fix:** Add `if cfg_remote.returncode != 0: raise WikiSetupError(...)` mirroring the Path D branch's error handling at lines 175-180.

### [NIT] `commit_push` re-imports `subprocess` as `sp` inside the function body

**Location:** `plugins/mill/scripts/wiki/_sync.py:209`
**Issue:** `import subprocess as sp` is issued inside `commit_push` but `subprocess` is already imported at module level (line 4). The local alias `sp` diverges from the rest of the module's `subprocess` usage without benefit.
**Fix:** Remove the inner `import subprocess as sp` and use the module-level `subprocess` name, changing `sp.run(...)` and `sp.TimeoutExpired` to `subprocess.run(...)` / `subprocess.TimeoutExpired`.

### [NIT] `test-wiki-sync.py` covers Path C upstream tracking but not Path D

**Location:** `plugins/mill/unit_tests/test-wiki-sync.py` (test `(o)`)
**Issue:** Card 6 requires upstream tracking on both Path C (clone without branch) and Path D (clone with specified branch). The test file exercises only Path C. A regression in the Path D tracking block (`lines 173-188` of `_setup.py`) would go undetected.
**Fix:** Add a second sub-test that calls `_setup.clone_or_init(str(bare), "main", clone5)` (branch-specified / Path D) and asserts `branch.main.remote` and `branch.main.merge` are set, matching the Path C verification pattern.

## Verdict

REQUEST_CHANGES
One argument-mismatch bug in `_review_common.load_config` and an inert git-pr guard need correction before merge.
MILL_REVIEW_END
