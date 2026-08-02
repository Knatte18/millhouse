# Batch: bug2-nested-go-module-cwd

```yaml
task: Verify/build gates leak shell state and ignore nested Go modules
batch: bug2-nested-go-module-cwd
number: 2
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py"
depends-on: []
```

## Batch Scope

Fixes #751: the go-build-tag-retiering gate (`_go_build_tag_retiering_stuck`
in `_implementer_common.py`) always runs its `go build` compile check
with `cwd=project_root`, even when the transitioned `.go` file lives
inside a nested Go module (its own `go.mod` under `project_root`, e.g.
a plugin with an independent module). `go build` resolves module
boundaries relative to cwd, so pointing it at `project_root` for a
nested module fails with "directory prefix ... does not contain main
module" — a false stuck/verify verdict even though the nested module
compiles fine on its own. This batch adds a filesystem walk-up that
finds the nearest enclosing `go.mod` for an affected directory and
scopes the compile check's `cwd`/pattern to it, falling back to
today's exact behavior when no nested module is found. No external
interface changes; independent of batch 1 (different files, no shared
edits).

## Cards

### Card 3: Detect the nearest enclosing go.mod and scope the compile check to it

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_implementer_common.py`, add a new function
  `_nested_go_module_root_and_pattern(project_root: Path, dir_str: str) -> tuple[Path, str]`
  immediately after `_go_build_pattern` (which returns `"./..."` for
  `dir_str == "."`, else `f"./{dir_str}/..."`) and before
  `_is_qualifying_custom_tag`. The function:

  1. Sets `affected_dir = project_root / dir_str` and `candidate = affected_dir`.
  2. Checks `(candidate / "go.mod").exists()` at the CURRENT `candidate`
     value first — starting with `candidate == affected_dir` itself,
     before any `.parent` advance — and only if that check is `False`
     and `candidate != project_root` does it advance
     `candidate = candidate.parent` and check again. The walk stops as
     soon as either the check is `True` at the current candidate, or
     `candidate == project_root` (a plain filesystem check, no
     subprocess — matching the existing fail-open
     `(project_root / "go.mod").exists()` convention in
     `_plan_validate.py`'s `_check_verify_excludes_integration_test`,
     e.g. its `if not (project_root / "go.mod").exists(): return []`
     line). This ordering matters: `affected_dir` itself must be
     checked before ever advancing to its parent, so a nested module
     whose `go.mod` lives directly in the affected directory (case 66j)
     is detected at `candidate == affected_dir`, not skipped past.
  3. If the walk stopped because `candidate == project_root` (no closer
     `go.mod` was found): return `(project_root, _go_build_pattern(dir_str))`
     — byte-identical to today's behavior.
  4. Else (`candidate` is a nested module root strictly under
     `project_root`): if `candidate == affected_dir`, return
     `(candidate, "./...")`. Otherwise return
     `(candidate, _go_build_pattern(affected_dir.relative_to(candidate).as_posix()))`
     — the pattern re-derived relative to the nested module root.

  Then wire this into both `go build` invocation sites inside
  `_go_build_tag_retiering_stuck`:
  - The added-tag site (`["go", "build", _go_build_pattern(dir_str)]`,
    `cwd=project_root`): replace with a call to
    `_nested_go_module_root_and_pattern(project_root, dir_str)` unpacked
    as `build_cwd, build_pattern`, then invoke
    `_subprocess_util.run(["go", "build", build_pattern], cwd=build_cwd)`.
  - The removed-tag site (`["go", "build", "-tags", tag, _go_build_pattern(dir_str)]`,
    `cwd=project_root`): same resolution, invoke
    `_subprocess_util.run(["go", "build", "-tags", tag, build_pattern], cwd=build_cwd)`.

  Both sites already check `(project_root / dir_str).is_dir()` and
  `continue` before reaching the build call — call
  `_nested_go_module_root_and_pattern` only after that existing
  directory-existence check, unchanged. No other line in
  `_go_build_tag_retiering_stuck` changes (dedup, tag-qualification,
  and stuck-dict construction are untouched).
- **Commit:** `fix(implementer-common): scope go-build-tag-retiering compile checks to the nearest enclosing go.mod`

### Card 4: Widen the go-gate test mock to capture cwd

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-implementer-common.py`, widen
  `_go_gate_mock` (the helper that mocks only `go`-prefixed
  `_subprocess_util.run` invocations, delegating everything else to the
  real implementation) to also capture each mocked call's `cwd` kwarg:
  add a new local list `cwd_calls: list[Path | None] = []` alongside
  the existing `calls: list[list[str]] = []`, append
  `kwargs.get("cwd")` to `cwd_calls` in lockstep with `calls.append(list(argv))`
  inside `_side_effect`, and change the function's `return` statement
  from `return _side_effect, calls` to `return _side_effect, calls, cwd_calls`.
  `calls` itself (bare argv lists) is unchanged — every existing
  bare-argv assertion (`calls[0] == [...]`, `calls == []`, `len(calls) == 1`)
  needs no edit.

  Every call site in this file that unpacks `_go_gate_mock(...)` as
  `side_effect, calls = _go_gate_mock(...)` must be updated to
  `side_effect, calls, cwd_calls = _go_gate_mock(...)` to match the new
  3-tuple return (a mechanical, uniform rename — there are 10 such call
  sites in this file, all inside the `_go_build_tag_retiering_stuck`
  test cases numbered 66a through 66i). Do not touch the assertion
  bodies below each call site — only the unpacking line itself.
- **Commit:** `test(implementer-common): widen _go_gate_mock to capture the go-build cwd`

### Card 5: Cover nested-module cwd/pattern resolution and its fallback

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-implementer-common.py`, add three new
  cases immediately after case 66i (the filesystem-deletion case, ending
  with its `errors += 1` under `except Exception as exc:`) and before
  the `# Case 67` comment, following the existing case 66a/66f fixture
  style (`_setup_fixture`, `_go_gate_mock`, mock via
  `unittest.mock.patch.object(_subprocess_util, "run", side_effect=side_effect)`,
  print `PASS:`/`FAIL:` and increment `errors` on failure):

  1. **Case 66j** (nested module root): build a fixture with
     `project_root/plugins/foo/go.mod` (e.g. `"module foo\n\ngo 1.21\n"`)
     and `project_root/plugins/foo/bar.go`, commit both untagged, then
     transition `bar.go` to add a `//go:build integration` line (an
     added-tag transition, mirroring case 66a). Call
     `_go_build_tag_retiering_stuck(project_root, start_sha, "sess-j")`
     under the widened mock. Assert `result is None`, exactly one mocked
     call with `calls[0] == ["go", "build", "./..."]`, and
     `cwd_calls[0] == project_root / "plugins" / "foo"` (not
     `project_root`).
  2. **Case 66k** (nested module subpath): same `project_root/plugins/foo/go.mod`
     module root, but the transitioned file is one level below it at
     `project_root/plugins/foo/sub/baz.go` (added-tag transition). Assert
     `calls[0] == ["go", "build", "./sub/..."]` (relative to the module
     root, not `./plugins/foo/sub/...`) and
     `cwd_calls[0] == project_root / "plugins" / "foo"`.
  3. **Case 66l** (fallback, no nested module): a fixture with
     `project_root/plugins/bar/qux.go` and no `go.mod` anywhere under
     `project_root/plugins/bar` up to `project_root` (added-tag
     transition). Assert `calls[0] == ["go", "build", "./plugins/bar/..."]`
     and `cwd_calls[0] == project_root` — byte-identical to the pre-fix,
     single-module-repo behavior already covered by case 66a's assertion
     shape.
- **Commit:** `test(implementer-common): cover nested-go-module cwd/pattern resolution and its fallback`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-implementer-common.py` in
full — a single in-process script (`print`-based PASS/FAIL, no real
Go toolchain, no network) already covering `_go_build_tag_retiering_stuck`
via cases 66a-66i; the three new cases (66j/66k/66l) plus the 10
updated `_go_gate_mock` unpacking sites all run within the same file,
so the existing full-file `verify:` scope is unchanged and still
correct (no cross-cutting helper outside this file was touched).
