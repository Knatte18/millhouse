# Batch: plan-validate-dotnet-scoping

```yaml
task: 'mill-plan/verify/implement pipeline: misc small bugs, round 3'
batch: plan-validate-dotnet-scoping
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-subprocess-util.py
depends-on: []
```

## Batch Scope

Fixes GitHub #1118: the `verify-full-suite` check in `_plan_validate.py` flags a project-scoped `dotnet test <project>` as a full-suite run.
After this batch, a `dotnet test` segment is flagged only when it has no `--filter` AND names no target, or names a solution/solution-filter target.
Also corrects the `_subprocess_util.py` module docstring, stale since #1082's fix made successful spawns silent.
No external interface changes; the finding dict shape `{check, batch, card, path, message}` is unchanged.

## Cards

### Card 1: verify-full-suite accepts project-scoped dotnet test

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_plan_validate.py`:
  - Add `import shlex` to the module imports (alphabetical with `os`/`re`).
  - Add a module-level helper `_dotnet_test_segment_is_unscoped(segment: str) -> bool` next to `_RE_GO_TEST_INVOCATION` in the `# verify-full-suite check` section, plus the constants it needs: a regex `_RE_DOTNET_TEST_INVOCATION` matching `\bdotnet\s+test\b`, a frozenset `_DOTNET_TEST_VALUE_OPTIONS` of value-taking options, and a tuple `_DOTNET_SOLUTION_SUFFIXES`.
    The value-taking option set is exactly: -c, --configuration, -f, --framework, -r, --runtime, -o, --output, -s, --settings, -l, --logger, -v, --verbosity, -a, --test-adapter-path, -d, --diag, -e, --environment, --results-directory, --arch, --os.
    The solution suffixes are .sln, .slnx, .slnf, matched case-insensitively.
    The helper returns False when the segment has no `dotnet test` invocation or contains `--filter`.
    Otherwise it tokenises the text after the `dotnet test` match with `shlex.split` (falling back to `str.split` on `ValueError`), walks the tokens, skips any token starting with `-` and, for a token in the value-option set without an inline `=`/`:` value, also skips the following token; the first remaining token is the positional target.
    Return True when there is no positional target, or when the target's lowercased form ends with one of the solution suffixes; return False otherwise (a `.csproj`, a project directory name, a `.dll`).
  - In `_check_verify_full_suite`'s inner `_check_frontmatter`, replace the whole-command `"dotnet test" in command and "--filter" not in command` branch with a per-segment loop over `_RE_SHELL_OPERATOR.split(command)`, mirroring the existing `go test` loop, returning the finding for the first segment where `_dotnet_test_segment_is_unscoped(segment)` is True.
    New finding message: "verify command invokes 'dotnet test' with no project target (or on a whole solution) and no --filter; name a test project, add --filter, or document the cross-cutting-helper justification in ## Batch Tests".
    The `done_gate` exemption keeps precedence (unchanged placement).
  - Update `_check_verify_full_suite`'s docstring summary so the C# clause reads as the new rule (no project target or a solution target, and no --filter) instead of "dotnet test without --filter".
  - Update the module docstring's `verify-full-suite` entry in the check list near the top of the file, which today says only "invokes run-all.py without a -k/--only filter", to name all four runners in one entry: run-all.py without -k/--only, go test ./... without -run, dotnet test with no project target or a solution target and no --filter, bare pytest.
  In `plugins/mill/unit_tests/test-plan-validate.py` (follow the existing `test_check_verify_full_suite_dotnet_test_with_filter_is_ok` fixture shape: `_make_overview`, `_write_plan`, `_plan_validate.run`, filter on `check == "verify-full-suite"`, return 0/1 and print PASS/FAIL):
  - Rename `test_check_verify_full_suite_dotnet_test_without_filter_is_error` to `test_check_verify_full_suite_dotnet_test_project_target_is_ok` and flip it: `verify: dotnet test MyProject.csproj` now yields zero `verify-full-suite` findings. Update its docstring and its entry in `main()`'s `tests` list.
  - Add dirty tests (exactly one `verify-full-suite` finding whose message mentions "dotnet test"), one function each: bare `dotnet test`; `dotnet test MySolution.sln`; `dotnet test Backend.slnf`; `dotnet test --nologo -c Release` (the Release value is not a target); `dotnet build X.sln && dotnet test` (flagged via the test segment).
  - Add clean tests (zero `verify-full-suite` findings), one function each: `dotnet test NORCE.Models.Tests --nologo -clp:ErrorsOnly`; `dotnet test -c Release My.Tests.csproj`; `dotnet test MySolution.sln --filter Category=Unit`.
  - Register every new function in `main()`'s `tests` list next to the existing dotnet full-suite entries.
  - Leave `test_check_verify_not_isolated_no_python_marker_dotnet_test_clean` and `test_check_verify_full_suite_dotnet_test_with_filter_is_ok` passing unchanged.
- **Commit:** `fix(plan-validate): verify-full-suite no longer flags project-scoped dotnet test (#1118)`

### Card 2: correct stale _subprocess_util breadcrumb docstring

- **Context:**
  - `plugins/mill/unit_tests/test-subprocess-util.py`
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Docstring-only change; no behaviour change.
  - In the module docstring, rewrite point 2 (today: "Every spawn and exit is echoed to stderr as a one-line breadcrumb ...") to say the spawn/exit breadcrumb pair is emitted only on failure paths: a non-zero exit (unless the caller passes `quiet_nonzero=True`), a timeout, or a Popen raise; a successful run prints nothing. Keep the note that smoke tests grep this stream.
  - In the module docstring's "Public API" list, add `quiet_nonzero=False` to the `run(...)` signature line.
  - In `run`'s own docstring, change the summary line "Run a subprocess with UTF-8 text I/O and spawn/exit breadcrumbs on stderr." so it says the breadcrumbs are emitted on failure paths only.
- **Commit:** `docs(subprocess-util): breadcrumbs are emitted on failure paths only`

## Batch Tests

`verify:` runs `test-plan-validate.py` (card 1's new and flipped dotnet cases plus every existing validator test) and `test-subprocess-util.py` (guards that card 2 stayed docstring-only, including case (n)'s silent-success assertion).
