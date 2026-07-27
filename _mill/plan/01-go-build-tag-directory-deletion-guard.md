# Batch: go-build-tag-directory-deletion-guard

```yaml
task: "mill-go verify/cleanup gates misclassify build-tag deletions and round-suffixed phases"
batch: go-build-tag-directory-deletion-guard
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes #715: `_go_build_tag_retiering_stuck` (in `_implementer_common.py`)
schedules a `go build` compile check against a package directory without
first confirming the directory still exists on disk. A batch that deletes
a whole directory containing a `//go:build`-tagged file causes the gate to
misclassify the deletion as a same-directory detagging edit and run a
compile check against a path that no longer exists, producing a spurious
`stuck_type:verify`. This batch adds a directory-existence guard to both
compile-check loops (`added_dirs` and `removed_dirs`) and covers both with
new unit tests. This is a self-contained fix to one function; nothing in
this batch depends on or is consumed by batch 2.

## Cards

### Card 1: Skip go-build-tag compile check when the target directory no longer exists on disk

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `_go_build_tag_retiering_stuck` (`plugins/mill/scripts/_implementer_common.py`,
    ~line 1004-1137), inside the `for dir_str in sorted(added_dirs):` loop
    (~line 1097-1105), add a guard immediately before the `go build`
    compile-check call: if `not (project_root / dir_str).is_dir()`, print
    `f"[go-build-tag-retiering] skip: {dir_str} no longer exists on disk (directory deleted)"`
    to `sys.stderr` (already imported) and `continue` to the next
    `dir_str` — skip the compile check for that directory entirely.
  - Apply the identical guard inside the
    `for dir_str, entry in sorted(removed_dirs.items()):` loop
    (~line 1107-1131), placed as the last skip condition — after the
    existing `entry.get("tag_mismatch", False)` check and the existing
    `_is_qualifying_custom_tag(tag)` check (both of which must still run
    and log their own specific skip reasons first) — and immediately
    before the `go build -tags` compile-check call.
  - No change to `_parse_go_build_tag_diff`, `_go_build_tag_dir`,
    `_go_build_pattern`, `_is_qualifying_custom_tag`, or
    `_go_build_tag_stuck_dict` — this card only adds the existence guard
    at the two compile-check call sites.
  - Add two new test cases to `plugins/mill/unit_tests/test-implementer-common.py`,
    following the existing "Case 66a"–"Case 66g" convention (~lines
    3791-4163: real git repo fixture via `_setup_fixture`, `_go_gate_mock`
    for mocking `_subprocess_util.run`, per-case `try/except Exception`
    incrementing the file's existing `errors` counter, `PASS`/`FAIL`
    printed). Insert both new cases immediately before the
    `if errors:` block (~line 4165):
    - **Case 66h** (removed_dirs / real directory deletion via git):
      reuse case 66b's git setup (a single custom-tag file — e.g.
      `//go:build integration` — in a package directory, committed, with
      `start_sha` captured), then `git rm -r` the whole package directory
      and commit that removal. The tag transitions to "removed" per
      `_parse_go_build_tag_diff`, but the directory no longer exists on
      disk. Assert `_go_build_tag_retiering_stuck(project_root, start_sha, session_id)`
      returns `None`, that zero `go build` calls were recorded (mock
      `calls == []`), and that a stderr skip line mentions the directory
      no longer existing — mirror case 66c's
      `contextlib.redirect_stderr` + `"skip" in stderr_buf.getvalue().lower()`
      assertion style.
    - **Case 66i** (added_dirs / filesystem-only deletion, git history
      intact): reuse case 66a's git setup (a file gains a
      `//go:build <tag>` line, committed, directory present in git at
      HEAD), then physically remove the directory from disk with
      `shutil.rmtree(pkg_dir)` — WITHOUT committing that removal, so
      git's diff still classifies the file as an added-tag transition,
      but the filesystem no longer has the directory. Assert
      `_go_build_tag_retiering_stuck(...)` returns `None`, zero `go build`
      calls recorded, and a stderr skip line mentions the directory no
      longer existing. Add `import shutil` to the file's existing import
      block (~lines 3-11) — not currently imported.
  - Skip-log wording is fixed for both new guards:
    `f"[go-build-tag-retiering] skip: {dir_str} no longer exists on disk (directory deleted)"`,
    matching the existing `[go-build-tag-retiering] skip: ...` convention
    used by the `tag_mismatch` and non-qualifying-tag skip branches in the
    same function.
- **Commit:** `fix(implementer): skip go-build-tag compile check for deleted directories`

## Batch Tests

`verify:` runs the entire `test-implementer-common.py` file (single test
file this batch's only edited test file lives in), which includes cases
66a-66g (unchanged, must still pass) plus the two new cases 66h and 66i
added by Card 1.
