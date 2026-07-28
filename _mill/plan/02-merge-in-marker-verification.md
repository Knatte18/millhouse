# Batch: merge-in-marker-verification

```yaml
task: "Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure"
batch: "merge-in-marker-verification"
number: 2
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Fixes #713: `millpy-merge-in-subagent.py --mode conflicts` can self-report `{"status":"success"}` while residual `<<<<<<<`/`=======`/`>>>>>>>` conflict markers remain in a file it claimed to resolve, or while a file was never staged at all. This batch adds a marker-verification gate helper and wires it into both call sites that can emit a conflicts-mode success envelope (the `--stage full` direct path and the `--stage finalize` Agent-mode path), per `_mill/discussion.md`'s `merge-in-marker-verification (#713)` Decision. The gate is this batch's external interface: it returns either `None` (clean) or a `{"status":"stuck","stuck_type":"logic",...}` dict that both call sites use identically to override an otherwise-successful envelope. No other batch touches `millpy-merge-in-subagent.py` or `test-millpy-merge-in-subagent.py`.

## Cards

### Card 6: Implement the conflict-marker verification gate helper

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a module-level function `_verify_conflict_markers(files: list[str], project_root: Path) -> dict | None` to `plugins/mill/scripts/millpy-merge-in-subagent.py` (place it near `_collect_task_intent`, before `main`). It runs two checks via `_subprocess_util.run` (already imported in this module), both scoped to `files`, both always executed unconditionally (never short-circuit):
  1. `_subprocess_util.run(["git", "diff", "--name-only", "--diff-filter=U", "--", *files], cwd=project_root)` — same idiom as `mill-merge-in/SKILL.md` step 3 and `millpy-wikipush.py:44`. Any of `files` appearing in `result.stdout` (split on newlines) means that file was never staged.
  2. `_subprocess_util.run(["git", "diff", "--cached", "--check", "--", *files], cwd=project_root)` — grep the combined `stdout` for the substring `"conflict marker"`; any matching line names a file that WAS staged but still carries markers.
  For each check, before evaluating its positive signal, check whether its combined `stdout + stderr` contains the substring `"fatal:"` — if so, that check's own execution is untrustworthy (a git-level failure unrelated to markers, e.g. lock contention), and the function returns immediately: `{"status": "stuck", "stuck_type": "logic", "reason": f"conflict-marker verification itself failed to run: {combined_output}"}` (this case takes priority over any ordinary finding and short-circuits, unlike the two ordinary checks). If neither check's output contains `"fatal:"`: build a list of failure clauses — `"file(s) never staged / still unmerged: <comma-joined files from check 1>"` if check 1 found any, `"residual conflict markers found in staged files: <matched lines/files from check 2>"` if check 2 found any — and if the list is non-empty, return `{"status": "stuck", "stuck_type": "logic", "reason": "; ".join(clauses)}`. If both checks are clean and neither is `"fatal:"`, return `None`. A file in `files` that no longer exists on disk (a `git rm`'d modify/delete resolution) needs no special-casing: it will not appear in check 1's unmerged-path list (already resolved) and `git diff --cached --check` has nothing to diff for a removed path, so both checks naturally report nothing for it.
- **Commit:** `feat(merge-in): add conflict-marker verification gate helper (#713)`

### Card 7: Gate the `--stage full` conflicts-mode success path

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_run_conflicts` (`plugins/mill/scripts/millpy-merge-in-subagent.py:336`), the `stage == "full"` (default) branch currently ends with `return _forward_output(output, project_root)` (line 374), where `output` is the sub-agent's raw text captured from `_implementer_claude.run(...)`. Before that call, extract the self-reported status from `output` via `_implementer_common._extract_status_json` (module-private; import it alongside the existing `from _implementer_common import ...` line at the top of the file — add `_extract_status_json` to that import list). If the extracted dict is not `None` and its `"status"` is `"success"`, call `_verify_conflict_markers(args.files, project_root)` (from Card 6). If it returns a non-`None` stuck dict, `print(json.dumps(stuck_dict))` and `return 0` instead of calling `_forward_output`. If it returns `None` (clean), or the extracted dict is `None` (no valid JSON found), or the self-reported status was not `"success"` (e.g. `"stuck"`), fall through to the existing `return _forward_output(output, project_root)` unchanged — a `"stuck"` self-report, or no extractable JSON at all, never reaches the gate.
- **Commit:** `fix(merge-in): gate --stage full conflicts success on marker verification (#713)`

### Card 8: Gate the `--stage finalize` conflicts-mode success path

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()` (`plugins/mill/scripts/millpy-merge-in-subagent.py:188`), the `args.stage == "finalize"` branch (line 279) currently falls through, for `args.mode != "verify-fix"` (i.e. `"conflicts"`), to a bare `return finalize_from_output(Path(args.agent_output), project_root, start_sha=None, snapshot_path=None, session_id=None)` (lines 310-316) with no marker check. Insert a new `elif args.mode == "conflicts":` branch immediately before that final `return finalize_from_output(...)` (which becomes the fallback for when the gate passes or the sub-agent did not report success):
  1. Replicate `finalize_from_output`'s existing `is_file()` guard (`_implementer_common.py` lines ~1296-1307) inline: if `not Path(args.agent_output).is_file()`, print the same actionable message shape (`f"ERROR: --agent-output file not found: {args.agent_output} -- ..."`) to stderr and `return 1` — this new pre-read must not crash with a raw `FileNotFoundError` before `finalize_from_output`'s own guard ever runs (that guard is unreachable on the gate-fail branch).
  2. If `not args.files`: print `"--files is required for conflicts mode"` to stderr (matching the existing message at `_run_conflicts` line 337-339) and `return 1` — the finalize early-exit branch never reaches `_run_conflicts`'s own `--files` check.
  3. Read and `html.unescape` the agent-output file (mirroring `finalize_from_output`'s own internal read at `_implementer_common.py:1313`; import `html` at the top of `millpy-merge-in-subagent.py` if not already imported).
  4. Extract the self-reported status via `_extract_status_json` (imported in Card 7). If the extracted dict is not `None` and its `"status"` is `"success"`, call `_verify_conflict_markers(args.files, project_root)`. If it returns a non-`None` stuck dict, `print(json.dumps(stuck_dict))` and `return 0`.
  5. Otherwise (gate passed, or the extracted dict is `None`, or status was not `"success"`), call the existing `finalize_from_output(Path(args.agent_output), project_root, start_sha=None, snapshot_path=None, session_id=None)` unchanged and `return` its result.
- **Commit:** `fix(merge-in): gate --stage finalize conflicts success on marker verification (#713)`

### Card 9: Unit-test the marker-verification gate helper directly

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test class or a set of `test_2x_marker_gate_*` methods to `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` that call `millpy_merge_in_subagent._verify_conflict_markers(files, project_root)` directly against a REAL git repository (not mocked `_subprocess_util.run` — this helper's own two checks are exactly what needs proving), using `tempfile.mkdtemp()` + `subprocess.run(["git", "init", ...])` plus real commit/merge/conflict fixtures (mirroring the real-git-repo setup style already used in `plugins/mill/integration_tests/test-merge.py`, or a lighter-weight equivalent local to this file). Cover: (a) a file with residual markers, staged via `git add` (check-1 clean, check-2 fails) — assert the returned dict's `reason` mentions residual markers and the file; (b) a file left unmerged and never staged at all (check-1 fails, check-2 has nothing to diff) — assert the returned dict's `reason` mentions never-staged/still-unmerged and the file; (c) a clean, properly resolved-and-staged file — assert `None`; (d) one of `files` deleted via `git rm` (valid modify/delete resolution) — assert `None`, not an error; (e) a multi-file `files` list where one file trips check 1 and a different file trips check 2 simultaneously — assert the combined `reason` names both files and both failure shapes in one call; (f) a forced `"fatal:"`-prefixed output from one of the two checks (e.g. via `unittest.mock.patch.object(millpy_merge_in_subagent._subprocess_util, "run", ...)` with a `side_effect` returning a `fatal:`-prefixed `CompletedProcess` for exactly one of the two argv shapes) — assert the returned dict's `reason` mentions verification itself failing to run, distinct from an ordinary marker/unmerged finding.
- **Commit:** `test(merge-in): cover conflict-marker verification gate helper directly (#713)`

### Card 10: Update pre-existing conflicts-mode success tests to a realistic `side_effect` and prove both call sites reach the gate

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `test_1_conflicts_success`, `test_16_conflicts_discarded_field_preserved`, and `test_17_conflicts_success_no_discarded_is_clean` each mock `_implementer_common._subprocess_util.run` with one constant `return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="abc1234\n", stderr="")`. Once Cards 7-8 wire the gate into both call sites, the gate's own two `_subprocess_util.run` calls receive that same constant `"abc1234\n"` response too — which happens not to contain `"conflict marker"` or list any of the test's input filenames, so today's success assertions would keep passing, but by coincidence rather than because the gate genuinely verified a clean state. Convert each of these three tests' `_subprocess_util.run` mock from `return_value=` to `side_effect=` — a callable or list keyed on the `argv` passed to `run` — so the pre-existing `git rev-parse HEAD` call keeps returning `"abc1234\n"` while the two new marker-gate check invocations (`git diff --name-only --diff-filter=U ...` and `git diff --cached --check ...`) each get their own realistic clean response (empty `stdout`, `returncode=0`).

  `test_15_stage_finalize_conflicts` currently has NO `_subprocess_util.run` mock at all (verified: it only patches `millpy_merge_in_subagent._implementer_claude.run`). Once Card 8 wires the gate into the finalize path, this test's real, unmocked `_verify_conflict_markers` call will run actual `git diff` commands against `self.tmp_path`, which `setUp` never `git init`'s — producing `"fatal: not a git repository"`, which Card 6's own design converts to a stuck result, breaking this test's `status == "success"` assertion. Add the same `_implementer_common._subprocess_util.run` `side_effect` mocking used for the three tests above to `test_15_stage_finalize_conflicts`, giving the gate's two checks a clean response.

  `test_19_finalize_conflicts_accepts_parity_flags` mocks `finalize_from_output` itself (not `_subprocess_util.run`), specifically to avoid real git operations against the non-repo `self.tmp_path` (see its existing inline comment). Once Card 8's gate runs BEFORE `finalize_from_output` is ever called, this test's agent-output fixture (`{"status":"success","commit_sha":"xyz"}`) will trigger a real, unmocked `_verify_conflict_markers` call against the non-repo tempdir — same `"fatal:"` failure as `test_15` above, and since the gate would intercept and return before reaching `finalize_from_output`, `mock_finalize.assert_called_once()` would also break. Add `_implementer_common._subprocess_util.run` `side_effect` mocking (same clean-response pattern) to this test alongside its existing `finalize_from_output` mock, so the gate passes cleanly and control still reaches the mocked `finalize_from_output` call.

  Additionally add two new tests: `test_2x_stage_full_conflicts_reaches_gate` and `test_2x_stage_finalize_conflicts_reaches_gate`, each asserting (via the same `side_effect` pattern, but with one of the two marker-gate argv shapes returning a positive finding) that the success envelope IS overridden to a stuck dict at both the `--stage full` and `--stage finalize` call sites — proving Cards 7 and 8 actually gate, not just that the helper itself (Card 9) works in isolation. Add `test_2x_stuck_status_skips_gate`: a sub-agent report of `{"status":"stuck",...}` must never trigger a `_verify_conflict_markers` call at all (assert via a mock/spy that the gate function is not called, e.g. `unittest.mock.patch.object(millpy_merge_in_subagent, "_verify_conflict_markers")` with `.assert_not_called()`).
- **Commit:** `test(merge-in): prove existing success tests exercise the new gate, not a lucky constant mock (#713)`

### Card 11: Regression-test the finalize-stage `--agent-output` and `--files` guards

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `test_2x_finalize_conflicts_missing_agent_output_file` to `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`: call `main(["--mode", "conflicts", "--files", "a.py", "--stage", "finalize", "--agent-output", str(self.tmp_path / "does-not-exist.txt")])` and assert `rc == 1` with an actionable stderr-shaped message (not a raw traceback) — regression coverage for Card 8's own `is_file()` guard, proving it fires before `_extract_status_json`/`_verify_conflict_markers` ever run on a missing file. Add `test_2x_finalize_conflicts_missing_files_flag`: call `main(["--mode", "conflicts", "--stage", "finalize", "--agent-output", str(<a real, existing agent-output fixture file>)])` with `--files` omitted, and assert `rc == 1` with the `"--files is required for conflicts mode"` message, proving Card 8's own falsy-`--files` guard fires (the finalize early-exit branch never reaches `_run_conflicts`'s existing check at line 337).
- **Commit:** `test(merge-in): cover missing --agent-output and --files guards at finalize stage (#713)`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` directly (self-contained script with its own `main()` runner, same invocation convention as `test-config.py`). Covers all six cards: Card 9 proves the helper (Card 6) in isolation against real git fixtures; Card 10 proves the two wiring sites (Cards 7-8) actually invoke it and that pre-existing tests were not passing by mock coincidence; Card 11 covers the two new pre-read guards added in Card 8.
