# Discussion: Verify/build gates leak shell state and ignore nested Go modules

```yaml
task: Verify/build gates leak shell state and ignore nested Go modules
slug: mill-verify-gate-scoping-bugs
status: discussing
parent: main
```

## Problem

Two independent scoping bugs in mill's verify/gate infrastructure, both surfaced on an external "prowler" task that legitimately introduced a nested Go module (`plugins/prowler/` with its own `go.mod`), were filed as GitHub issues #752 and #751 and bundled into this one task.

**Bug 1 (#752):** `_resolve_holistic_verify` in `plugins/mill/scripts/millpy-fix.py` joins every contributing batch's `verify:` command into a single shell invocation with plain `" && ".join(...)` (line 116). When a batch's plain-string `verify:` command contains an unscoped `cd` (a natural thing to write, e.g. `cd plugins/prowler && go test ./...`), that `cd` is not contained to its own segment — it changes the shell's cwd for every subsequent `&&`-joined batch command in the same joined invocation, since they all run in one shell process. This broke a later batch's relative-path command (`bash plugins/prowler/scripts/selftest.sh`), which resolved against the wrong (already-`cd`'d) directory and failed with "No such file or directory".

**Bug 2 (#751):** the go-build-tag-retiering gate (`_go_build_tag_retiering_stuck` in `plugins/mill/scripts/_implementer_common.py`, added for #642) always runs its `go build ./<dir>/...` compile check with `cwd=project_root` (the outer/main module), with no awareness of nested Go modules. When a `.go` file inside a nested module (its own `go.mod`, e.g. `plugins/prowler/`) gains or loses a `//go:build <tag>` constraint, the gate tries to build `./plugins/prowler/...` from the outer module root, which fails with "directory prefix plugins/prowler does not contain main module or its selected dependencies" — a false "stuck" verdict, since the nested module actually compiles fine on its own.

**Why now:** both bugs block legitimate task completion (a batch's finalize stage reports `status: stuck` for reasons that aren't real code problems) and were independently reproduced and root-caused against a real task run, with verified working fixes already sketched in the issues.

## Scope

**In:**
- Fix `_resolve_holistic_verify` (`millpy-fix.py`) to wrap each contributing batch's command in its own subshell before joining, so a `cd` (or any other cwd/env-mutating construct) in one batch's `verify:` can never leak into the next.
- Fix `_go_build_tag_retiering_stuck` (`_implementer_common.py`) to detect the nearest enclosing `go.mod` for each affected directory and, when it differs from `project_root`'s, run the compile check scoped to that nested module (its own root as cwd, pattern re-derived relative to that root) instead of always building from `project_root`.
- Unit test coverage for both fixes, added to existing test files (`test-millpy-fix.py`, `test-implementer-common.py`).

**Out:**
- No change to the `verify: {cwd: hub|git_root, ...}` mapping-form conflict-detection logic already in `_resolve_holistic_verify` (the `cwd_to_batch_name` conflict check) — only the plain-string join path is fixed.
- No change to the existing per-directory dedup semantics in the go-build-tag-retiering gate (multiple affected dirs are still checked independently; no new collapsing of multiple dirs under the same nested module into a single `go build ./...`).
- No new general-purpose "find nested go.mod" utility/module — the walk-up logic is added inline in `_go_build_tag_retiering_stuck`; nothing else in the codebase currently needs it.
- No change to how `_go_build_tag_retiering_stuck` is triggered (still gated purely on `//go:build` diff lines being present; no new top-level `go.mod`-presence gate added to this function).
- No real-shell-execution integration test for bug 1 — the join logic is pure string manipulation, covered by string-level unit assertions.

## Decisions

### bug1-subshell-wrap

- Decision: change `_resolve_holistic_verify`'s join from `" && ".join(command for _, command, _ in batch_verifies)` to `" && ".join(f"({command})" for _, command, _ in batch_verifies)`.
- Rationale: matches the issue's own verified repro/fix; isolates each batch's `cd`/env mutations to its own subshell while preserving `&&` short-circuit semantics between batches and the existing single-combined-stdout/stderr failure-reporting shape (still one subprocess call, one `cwd`).
- Rejected: prefixing every segment with an explicit `cd <project_root>` (doesn't guard non-`cd` state leaks like `export`, more fragile); splitting into separate per-batch subprocess calls (bigger change, alters output-capture semantics, out of scope for a targeted fix).

### bug1-cwd-override-unchanged

- Decision: `cwd_override` resolution (the `cwd_to_batch_name` conflict-detection logic) is untouched by this fix.
- Rationale: it already resolves to a single shared cwd (or `None`) correctly; the leak bug only exists in the joined command *string* for plain-string (`cwd=None`) batches. Cwd-mapping-form batches were never exposed to this bug.
- Rejected: threading per-batch cwd through env — unnecessary given the above.

### bug2-nested-module-detection

- Decision: detect the nearest enclosing `go.mod` for an affected directory by walking up from `project_root / dir_str` toward `project_root`, checking `(candidate / "go.mod").exists()` at each level (inclusive of `project_root` itself as the final fallback).
- Rationale: pure filesystem check, no subprocess dependency; matches the existing fail-open `(project_root / "go.mod").exists()` convention already used elsewhere in the codebase (`_plan_validate.py`'s `_check_verify_excludes_integration_test`); keeps the gate hermetically unit-testable with plain fixture files instead of needing to mock `go env`/`go list` calls.
- Rejected: `go env -C <dir> GOMOD` or `go list -m -f '{{.Dir}}'` — both authoritative but require shelling out to a real (or mocked) Go toolchain per affected directory, adding mock surface for no behavioral benefit over a filesystem walk.

### bug2-nested-module-cwd-and-pattern

- Decision: when the nearest enclosing `go.mod` differs from `project_root`'s, run the compile check with `cwd=<nested_module_root>` and a pattern re-derived relative to that root (`./...` when the affected directory *is* the nested module root; otherwise `./<remaining-subpath-under-nested-root>/...`).
- Rationale: `go build` always resolves module boundaries relative to its cwd — there's no way to keep `cwd=project_root` and still correctly build a differently-rooted module.
- Rejected: n/a — cwd must change; this is the only workable shape.

### bug2-fallback-no-nested-module

- Decision: if the walk-up finds no `go.mod` anywhere between the affected directory and `project_root` (inclusive), fall back to today's exact behavior: `cwd=project_root`, pattern `./<dir_str>/...`.
- Rationale: preserves current behavior byte-for-byte for the overwhelmingly common single-module-repo case; only repos with an actual nested module boundary get the new scoping behavior. Fails open rather than erroring or skipping the check.
- Rejected: treating "no go.mod found" as gate-disabled (skip the compile check entirely) — would silently drop a real transition check instead of running it with the existing (correct, in this case) settings.

### bug2-mock-widening-shape

- Decision: widen `_go_gate_mock` by adding a new parallel list `cwd_calls: list[Path | None]`, appended in lockstep with the existing `calls` list on every mocked `go`-prefixed invocation. `calls` itself (bare argv lists) is unchanged.
- Rationale: zero changes to any of the ~11 existing bare-argv assertions across cases 66a/66b/etc.; the new nested-module test reads `cwd_calls[i]` for its cwd assertion without touching existing coverage.
- Rejected: changing `calls` to `(argv, cwd)` tuples — would require updating every existing assertion site for no benefit over the parallel-list approach.

### bug2-dedup-unchanged

- Decision: keep the existing per-directory dedup (multiple transitioned files in the same directory still dedupe to one compile check per directory); do not collapse multiple affected directories under the same nested module into a single `go build ./...` run.
- Rationale: avoids scope creep beyond fixing #751's wrong-cwd bug; the multi-directory-same-nested-module case is rare and not what was reported.
- Rejected: module-level collapsing — more efficient in a rare case, not worth the added complexity/test surface for this fix (YAGNI).

## Technical context

- **Bug 1 site:** `plugins/mill/scripts/millpy-fix.py:116` — `joined_command = " && ".join(command for _, command, _ in batch_verifies)`, inside `_resolve_holistic_verify` (function starts at line 67). Called from two sites in the same file (~line 451, ~line 574) during holistic-scope finalize.
- **Bug 2 site:** `plugins/mill/scripts/_implementer_common.py`, `_go_build_tag_retiering_stuck` (starts ~line 1031). The two `go build` invocation sites are at ~line 1140 (added-tag transition: `["go", "build", _go_build_pattern(dir_str)]`) and ~line 1177 (removed-tag transition: `["go", "build", "-tags", tag, _go_build_pattern(dir_str)]`), both currently hardcoding `cwd=project_root`. `_go_build_pattern(dir_str)` (~line 980) returns `"./..."` for `dir_str == "."`, else `f"./{dir_str}/..."` — the pattern-construction helper that needs a nested-module-relative variant/adjustment.
- Directory-existence checks already present at ~line 1129 and ~line 1165 (`if not (project_root / dir_str).is_dir(): ... skip`) — the nested-module walk-up should happen after these, i.e. only walk up for directories confirmed to still exist on disk.
- **Existing convention to reuse:** `plugins/mill/scripts/_plan_validate.py:2107` — `if not (project_root / "go.mod").exists(): return []` — the fail-open, filesystem-only Go-detection pattern already established in this codebase; the new nested-module walk-up should follow the same style (plain `Path.exists()`, no subprocess).
- **Test infrastructure for bug 2:** `plugins/mill/unit_tests/test-implementer-common.py` already has full coverage for `_go_build_tag_retiering_stuck` (cases 66a/66b/etc., starting ~line 3988) using `_setup_fixture` (real tempfile git repo) + `_go_gate_mock` (~line 46) — a `_subprocess_util.run` mock that intercepts only `go`-prefixed argv (delegating everything else, e.g. `git`, to the real implementation) and records `calls: list[list[str]]` (argv only, no kwargs currently). This mock needs widening to also capture the `cwd` kwarg per call so a nested-module test can assert the compile check ran with the nested module's root as cwd, not `project_root`.
- **Test infrastructure for bug 1:** no existing unit test covers `_resolve_holistic_verify` — new coverage belongs in `plugins/mill/unit_tests/test-millpy-fix.py` (class `TestMillpyFix`, ~line 100), which already imports `_implementer_common` and has the general fixture style for this area of the codebase. `_resolve_holistic_verify` itself is pure (no I/O) so tests can call it directly with hand-built `batch_verifies` tuples — no tempdir/subprocess needed.
- `parse_verify_field` (`_plan_dag.py:366`) is the single normalizer for `verify:` producing `(command, cwd)` — plain-string batches always resolve `cwd=None`, which is exactly the case exposed to bug 1's leak.

## Constraints

No `CONSTRAINTS.md` present at hub root.

## Testing

- **Bug 1 (`_resolve_holistic_verify`):** unit test in `test-millpy-fix.py`. TDD candidate: construct `batch_verifies` as `[("batch-a", "cd plugins/prowler && go test ./...", None), ("batch-b", "bash plugins/prowler/scripts/selftest.sh", None)]`, call `_resolve_holistic_verify`, assert the returned `joined_command` equals `"(cd plugins/prowler && go test ./...) && (bash plugins/prowler/scripts/selftest.sh)"` (each command's original text preserved verbatim, individually parenthesized, joined by `" && "`). Also cover: a single-batch case (no `&&` needed between segments, still gets wrapped in parens); the existing multi-cwd-conflict-raises-`ValueError` path is unaffected by this change and doesn't need re-testing beyond confirming it still raises before any joining happens.
- **Bug 2 (`_go_build_tag_retiering_stuck`):** extend `test-implementer-common.py`. TDD candidate: a fixture with `project_root/plugins/foo/go.mod` (minimal valid content) and `project_root/plugins/foo/bar.go`, tag-transitioned (added or removed `//go:build`) the same way existing cases 66a/66b do, asserting via the widened (`cwd_calls`-capturing) `_go_gate_mock` that the mocked `go build` call used `cwd=project_root/plugins/foo` and pattern `./...` (not `cwd=project_root` + `./plugins/foo/...`). Second TDD candidate covering the subpath-derivation branch: same `plugins/foo/go.mod`, but the transitioned file is one level below the module root at `plugins/foo/sub/baz.go` — assert pattern `./sub/...` (not `./plugins/foo/sub/...`) and `cwd=project_root/plugins/foo`. Also cover the fallback case: same transition but with no nested `go.mod` present anywhere under `project_root/plugins/foo` up to `project_root` — assert behavior is byte-identical to the pre-fix case (cwd=project_root, pattern=`./plugins/foo/...`), to confirm the single-module common case is unaffected.
- Both fixes are pure/deterministic given their inputs — no flakiness risk, no real Go toolchain needed for either test (bug 1 needs no subprocess at all; bug 2 continues mocking `go` invocations while using real git/filesystem for setup, per existing convention).

## Q&A log

- **Q:** Fix approach for bug #752 (holistic-verify join)? **A:** [auto-pick] Wrap each batch's command in its own subshell when joining (`f"({command})"`). **Why:** matches the issue's own verified repro/fix, smallest diff, no change to output-capture semantics.
- **Q:** Does `cwd_override` handling need to change alongside the join fix? **A:** [auto-pick] No — cwd resolution is already correct and orthogonal to the string-join bug. **Why:** only plain-string (`cwd=None`) batches are exposed to the leak; `cwd:`-mapping-form batches already go through single-cwd-or-conflict-error logic untouched by this bug.
- **Q:** How should the nearest enclosing `go.mod` be detected for bug #751? **A:** [auto-pick] Walk up from the affected directory checking `Path.exists()` at each level — pure filesystem check. **Why:** matches the existing fail-open `go.mod`-presence convention already used in `_plan_validate.py`; keeps the gate hermetically unit-testable without mocking a real Go toolchain.
- **Q:** What cwd/pattern should the compile check use once a differing nested `go.mod` is found? **A:** [auto-pick] `cwd=<nested_module_root>`, pattern re-derived relative to that root. **Why:** `go build` always resolves modules relative to cwd — there's no alternative that keeps `cwd=project_root`.
- **Q:** Fallback behavior when no `go.mod` is found anywhere up to `project_root`? **A:** [auto-pick] Fall back to today's exact behavior (`cwd=project_root`, original pattern). **Why:** preserves byte-identical behavior for the common single-module case; fails open rather than skipping the check.
- **Q:** Should compile checks collapse per nested-module-root instead of per-directory? **A:** [auto-pick] No — keep existing per-directory dedup unchanged. **Why:** avoids scope creep beyond fixing #751's wrong-cwd bug; the multi-directory-same-module case is rare (YAGNI).
- **Q:** Testing approach for bug #752? **A:** [auto-pick] Pure string-level unit test on `_resolve_holistic_verify` directly, added to `test-millpy-fix.py`. **Why:** the join logic has no I/O; a real-shell-execution test would be unnecessary extra surface for the same guarantee.
- **Q:** Testing approach for bug #751? **A:** [auto-pick] Extend the existing `test-implementer-common.py` fixture/mock pattern, widening `_go_gate_mock` to also capture the `cwd` kwarg. **Why:** existing infra already covers this function closely; no need for a new test file.
- **Q:** Should nested-module detection in tests use real `go.mod` files or mock `Path.exists`? **A:** [auto-pick] Real files in the tempdir fixture. **Why:** matches `_setup_fixture`'s existing real-git/real-files style; unnecessary indirection otherwise.
- **Q:** (Discussion review r1 gap) How should `_go_gate_mock` be widened to capture cwd without breaking existing bare-argv assertions? **A:** [auto-pick] Add a new parallel `cwd_calls` list alongside the unchanged `calls` list. **Why:** zero changes to ~11 existing assertion sites; smallest diff that adds the needed capture.
- **Q:** (Discussion review r1 gap) Is the "remaining-subpath-under-nested-root" pattern branch covered by a named test case? **A:** [auto-pick] Added a second nested-module TDD candidate with the transitioned file at `plugins/foo/sub/baz.go`, asserting pattern `./sub/...`. **Why:** the decision defines two pattern outcomes (module-root case and subpath case); only the module-root case had a named test before this gap.
