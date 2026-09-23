# Discussion: mill-plan/verify/implement pipeline: misc small bugs, round 3

```yaml
task: 'mill-plan/verify/implement pipeline: misc small bugs, round 3'
slug: mill-plan-verify-implement-misc-r3
status: discussing
parent: main
```

## Problem

Seven GitHub issues (all closed and consolidated into this task) report small, mutually unrelated bugs hit mid-run inside the plan/verify/implement pipeline:

- #1118 — `_plan_validate`'s `verify-full-suite` check flags any `dotnet test` without `--filter`, including the project-scoped `dotnet test <project>` that .NET repos document as their safe per-batch default, forcing a `--skip-check verify-full-suite` waiver for a correctly scoped command.
- #1133 — `mill-plan/SKILL.md` tells the orchestrator to call `_plan_validate.run` in the foreground (Phase: Plan self-run, Phase: Plan Review steps 4b/4c/4d) with no extended Bash-tool timeout note; on a large C# repo each call takes ~2 minutes and exceeds the default 120 s Bash timeout.
- #1082 — per-path `git check-ignore` spawn breadcrumbs flooded the orchestrator context on the in-process `_plan_validate.run` self-run.
- #1120 / #1121 (same bug) — `millpy-merge-in-subagent.py --recompute-baseline` passed a mapping-form `verify:` dict to `compute_baseline`, crashing with `expected str, bytes or os.PathLike object, not dict`.
- #1124 — an implementer/fixer sub-agent backgrounded a long `dotnet test` piped through `tail`; `tail` buffers until EOF so the output file stayed empty, the agent read that as a hang, spawned redundant `until` polling loops, and had no way to kill them.
- #1114 — `_status.append_phase` (and every `_status` helper guarded by `_require_path`) raises `TypeError` on a `str` `status_path`, while every SKILL.md pseudocode call site shows a bare `status_path` with no `Path(...)` wrapping, so an orchestrator following the docs literally fails on the first call.

Why now: all were hit in real runs in the last week and each costs a waiver, a timeout, context, or a wasted call per task.

Exploration found three of the seven already fixed on `main`; the reporting sessions ran a stale plugin cache:

- #1082: commit `599a2c1b` made `_subprocess_util.run` silent on success and added `quiet_nonzero=True` to the `git check-ignore` probe in `_plan_validate.py` (`_is_confirmed_git_ignored`). A `git check-ignore` run now prints nothing on either exit 0 or exit 1. `test-subprocess-util.py` case (n) already asserts success is silent.
- #1120 / #1121: commit `5d111edf` routed `_run_recompute_baseline` in `millpy-merge-in-subagent.py` through `_plan_dag.parse_verify_field` and threads the resolved cwd override into `compute_baseline`. `test-millpy-merge-in-subagent.py` `test_21_recompute_baseline_mapping_verify_field` and `test_22_recompute_baseline_malformed_verify_field` already cover it.

## Scope

**In:**

- #1118 — narrow the `dotnet test` sub-check of `_check_verify_full_suite` in `plugins/mill/scripts/_plan_validate.py` so a project-scoped invocation passes.
- #1133 — add an extended Bash-tool timeout note (600000 ms) for every `_plan_validate.run` call site in `plugins/mill/skills/mill-plan/SKILL.md`.
- #1082 residual — correct the now-stale module docstring of `plugins/mill/scripts/_subprocess_util.py` (point 2 still says "Every spawn and exit is echoed to stderr"; since `599a2c1b` breadcrumbs are emitted only on failure paths: non-zero exit unless `quiet_nonzero`, timeout, Popen raise). Also update the "Public API" `run(...)` signature line in the same docstring to include `quiet_nonzero=False`.
- #1124 — add background-verify guidance to the `## Shell conventions` section of all six implementer agent definitions under `plugins/mill/agents/` (`mill-implementer.md` and the `-low`/`-medium`/`-high`/`-xhigh`/`-max` variants).
- #1114 — make `_status` helpers accept `str | os.PathLike` for `status_path` by coercing to `Path`, replacing the raise-on-`str` guard.

**Out:**

- #1120/#1121: no code change; the fix and its regression tests are already on `main`.
- #1082: no behaviour change; only the docstring correction above. No batched `git check-ignore --stdin` rewrite — the noise was the problem, and it is gone.
- #1133: no progress output or performance work inside `_plan_validate.run`; doc-only fix, mirroring the existing 600000 ms finalize-stage notes in `mill-go-base/SKILL.md`.
- #1124: no change to the implementer's tool grant (no `TaskStop`/kill tool added) and no change to `implementer-brief.md` / fixer brief templates. The agent definition is the single place shared by every dispatch that uses a `mill:mill-implementer*` agent type (implementer, fixers, merge-in).
- #1114: no rewrite of the ~60 SKILL.md pseudocode call sites; coercion makes them correct as written.
- Other runners' full-suite sub-checks (`run-all.py`, `go test`, bare `pytest`) are unchanged.

## Decisions

### dotnet-test-scoping-rule

- Decision: in `_check_verify_full_suite`, evaluate `dotnet test` per shell segment (reuse `_RE_SHELL_OPERATOR`, as the `go test` sub-check does). A segment is flagged only when it invokes `dotnet test`, contains no `--filter`, AND either has no positional target argument or its positional target ends in `.sln`, `.slnx` or `.slnf` (case-insensitive; `.slnf` is a solution filter, which can still span many projects). A positional target is the first token after `test` (tokenised with `shlex.split`, falling back to `str.split` on a `ValueError`) that does not start with `-` and is not the value of a value-taking option. The value-taking options to skip are `-c`/`--configuration`, `-f`/`--framework`, `-r`/`--runtime`, `-o`/`--output`, `-s`/`--settings`, `-l`/`--logger`, `-v`/`--verbosity`, `-a`/`--test-adapter-path`, `-d`/`--diag`, `-e`/`--environment`, `--results-directory`, `--arch`, `--os`. Any other target (a `.csproj`, a project directory name such as `NORCE.Models.Tests`, a `.dll`) counts as scoped and passes. The `done_gate` exemption keeps precedence, as today.
- Rationale: `dotnet test <project>` is already scoped to one project, the analogue of `run-all.py --only`. The unscoped cases the check targets are a bare `dotnet test` (runs every project in the solution found in cwd) and an explicit solution file, which does the same. Per-segment evaluation matches the `go test` fix for #961, so `dotnet build X && dotnet test` still flags only the test segment.
- Rejected: (a) pass any positional argument, including `.sln`: this lets the explicit whole-solution run through, which the check exists to catch. (b) Probe the filesystem to tell whether a directory argument holds a `.sln`: adds I/O and cwd-resolution coupling to a lexical check for a rare case. (c) Keep the current rule and document the waiver: the waiver is required on the repo-documented default command every time.
- Message: keep a finding message that names both remedies, e.g. "verify command invokes 'dotnet test' with no project argument (or on a whole solution) and no --filter; name a test project, add --filter, or document the cross-cutting-helper justification in ## Batch Tests".

### plan-validate-timeout-note

- Decision: add one note to `mill-plan/SKILL.md`, placed right after the Phase: Plan "Self-run the validator gate" instruction, saying that every `_plan_validate.run` Bash-tool call in this SKILL gets an explicit 600000 ms (10-minute) Bash-tool timeout, because the validator walks the whole source tree and spawns git subprocesses per path, emits no progress output, and has taken ~2 minutes on a large repo. The note should also cite the analogous finalize-stage note in `mill-go-base/SKILL.md`. Steps 4b, 4c and 4d each get a short back-reference to that note ("with the extended timeout from Phase: Plan's self-run note"), not a copy.
- Rationale: stating the rule once and back-referencing it follows the prose skill's "say it once" rule. 600000 ms is the Bash tool's maximum and matches the existing finalize and done_gate precedents.
- Rejected: backgrounding via `millpy-bg` (the self-run returns a Python list consumed in-process; a background job adds log plumbing for no gain under the 10-minute cap); adding progress output to `_plan_validate.run` (out of scope, and it would reintroduce context noise).

### implementer-background-verify-guidance

- Decision: append a short rule block to `## Shell conventions` in all six `plugins/mill/agents/mill-implementer*.md` files, with identical body text. Its content:
  1. Run the `verify:` command in the foreground with an explicit Bash-tool `timeout` (up to 600000 ms), not backgrounded.
  2. If a command must run in the background, redirect its output straight to a file (`cmd > log 2>&1`). Never pipe it through `tail`, `head` or any other filter that buffers until EOF. `tail` emits nothing until the whole command finishes, so a polled log stays empty and looks like a hang.
  3. Wait on any given background job with at most one polling loop. Never start a second loop for the same target to "check" a first one that looks stuck; an extra loop cannot be killed later.
- Rationale: the agent definition is loaded by every dispatch that uses a `mill:mill-implementer*` agent type (per-batch implementer, batch and holistic fixers, merge-in), and #1124 happened in a holistic fix round, so it is the single shared site. Foreground-first removes the need for a kill tool.
- Rejected: adding `TaskStop` to the agents' `tools:` grant (the issue's "ideally"): unnecessary once polling loops are not spawned, and it widens the sub-agent's tool surface. Putting the text in `implementer-brief.md`: that misses the fixer and merge-in briefs. Putting it in `mill:cli`: implementers do not load that skill by default.

### status-path-coercion

- Decision: replace `_status._require_path(status_path, fn_name) -> None` with a coercing helper `_as_path(status_path, fn_name) -> Path`. The helper returns `status_path` unchanged when it is already a `Path`, returns `Path(status_path)` for a `str` or any `os.PathLike`, and still raises the existing clear `TypeError` (`"<fn>: status_path must be a pathlib.Path, str, or os.PathLike, got <type>"`) for anything else (e.g. `None`, `dict`, `int`). Every public function that currently calls `_require_path` rebinds `status_path = _as_path(status_path, "<fn>")` as its first statement, so internal helpers it calls (e.g. `_write_batches`) receive a `Path`. Public signatures change their annotation to `status_path: Path | str` (or `str | os.PathLike`), and each docstring's `status_path` Args entry says a `str` is accepted and coerced. The module docstring's API list needs no per-line change beyond any note about accepted types.
- Rationale: the SKILL.md pseudocode across ~60 call sites in 8 SKILLs is then correct as written. Most other path-taking helpers in the codebase already accept `str | Path`. The #597 goal (a clear error, not a bare `AttributeError` deep in the module) is kept for types that cannot be coerced.
- Rejected: wrapping every SKILL.md pseudocode call in `Path(...)` (many edits across 8 files, easy to miss one, and a new call site would regress); leaving the guard as it is (the reported bug).

## Technical context

- `plugins/mill/scripts/_plan_validate.py`
  - `_check_verify_full_suite` (the `# verify-full-suite check` section) holds an inner `_check_frontmatter` closure with sequential sub-checks: `run-all.py`, then per-segment `go test` via `_RE_SHELL_OPERATOR.split(command)` and `_RE_GO_TEST_INVOCATION`, then `dotnet test` (currently a whole-command substring test: `"dotnet test" in command and "--filter" not in command`), then bare `pytest`. The `dotnet test` branch is the only one to change.
  - The stale dotnet wording ("dotnet test without --filter") lives in `_check_verify_full_suite`'s own docstring summary sentence and in the emitted finding message; update both to the new rule.
  - The module docstring's check list (near the top, the `verify-full-suite —` entry) mentions only run-all.py ("invokes run-all.py without a -k/--only filter") and has been stale since the go/dotnet/pytest sub-checks were added. Broaden it to name all four runners in one line, e.g. "invokes an unscoped full-suite runner (run-all.py without -k/--only, go test ./... without -run, dotnet test with no project target or a solution target and no --filter, bare pytest)".
  - `shlex` is not yet imported (current imports: `os`, `re`, `yaml`, `pathlib.Path`); add `import shlex`.
- `plugins/mill/scripts/_subprocess_util.py` — the module docstring's point 2 and "Public API" line are stale. `run()`'s own docstring summary ("with spawn/exit breadcrumbs on stderr") should also say breadcrumbs are emitted only on failure paths.
- `plugins/mill/skills/mill-plan/SKILL.md`
  - Phase: Plan, "**Self-run the validator gate** before committing: call `_plan_validate.run` directly." — insert the timeout note here.
  - Phase: Plan Review step 4b ("Then run a full validator re-run: call `_plan_validate.run` with the identical 8 keyword arguments…"), step 4c and step 4d ("Run the identical full-validate gate…") — add back-references there. Locate these by text, not line number.
  - Precedent wording: `plugins/mill/skills/mill-go-base/SKILL.md`, the "Give any `--stage finalize` call an extended Bash-tool timeout — recommend 600000ms (10 minutes)" paragraph.
- `plugins/mill/agents/mill-implementer{,-low,-medium,-high,-xhigh,-max}.md` — the six files are identical apart from `name:` and `effort:` frontmatter. Each ends with `## Shell conventions` (the no-`sed` rule). `plugins/mill/unit_tests/test-agents-defs.py` has one test per implementer file plus a plugin.json registration test; check whether it asserts body equality across variants and keep all six bodies identical either way.
- `plugins/mill/scripts/_status.py` — `_require_path` is defined near the top, after the imports. It is called by every public function taking `status_path` (`read`, `update_field`, `set_blocked`, the module-verify-baseline getters/setters, `append_phase`, `read_batches`, `read_status`, `read_full`, `read_parent_branch`, `phase_entry_timestamp`, `read_slug`, `read_branch`, `init_batches`, `set_batch_field`, `set_batch_fields`, `remove_batch`, `append_recovery_log`, and the other `append_*_log` / `read_*_log` helpers). `grep -n "_require_path" plugins/mill/scripts/_status.py` enumerates them all. `import os` is needed for `os.PathLike`.
- Nothing needs to change in `millpy-merge-in-subagent.py` or in the `check-ignore` probe.

## Testing

- `plugins/mill/unit_tests/test-plan-validate.py` (TDD candidate for #1118):
  - The existing dirty test asserting that `verify: dotnet test MyProject.csproj` is flagged encodes the old, wrong rule. Flip it to clean (no `verify-full-suite` finding), keeping the test's intent visible in its docstring.
  - New dirty cases: bare `dotnet test`; `dotnet test MySolution.sln`; `dotnet test Backend.slnf`; `dotnet test --nologo -c Release` (flags only, the `Release` value must not count as a target); `dotnet build X.sln && dotnet test` (flagged per segment).
  - New clean cases: `dotnet test NORCE.Models.Tests --nologo -clp:ErrorsOnly` (a directory-name target); `dotnet test -c Release My.Tests.csproj` (target after a value-taking option); `dotnet test MySolution.sln --filter Category=Unit` (the filter still exempts).
  - The existing clean `--filter` case and the "C# project + dotnet test -> no verify-not-isolated error" test stay green. That test uses bare `verify: dotnet test` for a different check; confirm it asserts only on `verify-not-isolated`, not on the full list of findings.
  - Run via `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py` (or the `-k` equivalent).
- `plugins/mill/unit_tests/test-status.py` (TDD candidate for #1114): the existing "str-input-raises-TypeError (GitHub #597)" regression block asserts the old behaviour. Replace it with: a `str` path works for `append_phase`, `update_field`, `set_blocked` and a read helper (e.g. `read_status`), producing the same file content as a `Path` call; an `os.PathLike` that is not a `Path` works; a non-path type (`None`, `int`) still raises a `TypeError` whose message names the function.
- `plugins/mill/unit_tests/test-subprocess-util.py`: no new test for the docstring-only change.
- `plugins/mill/unit_tests/test-agents-defs.py`: add an assertion that each implementer definition's body contains the new background-verify guidance (e.g. that it mentions `tail` and the single-polling-loop rule), and keep all six bodies identical.
- SKILL.md edit (#1133): no automated test; verified by review.
- Final gate: the full `run-all.py` suite stays green.

## Q&A log

- **Q:** #1082, #1120 and #1121 are already fixed on `main` (commits `599a2c1b`, `5d111edf`) with regression tests. What does this task do for them? **A:** [auto-pick] No code change; only correct the stale `_subprocess_util` module docstring that still claims every spawn is echoed. **Why:** the reports came from sessions on a stale plugin cache; re-fixing would duplicate work, but the docstring now misdescribes the behaviour.
- **Q:** Which `dotnet test` forms should `verify-full-suite` flag? **A:** [auto-pick] Only when there is no `--filter` AND either no positional target or a `.sln`/`.slnx`/`.slnf` target, evaluated per shell segment. **Why:** a project target is already scoped; a solution target or bare invocation is the true full-suite run.
- **Q:** How is #1133 fixed? **A:** [auto-pick] A doc note in `mill-plan/SKILL.md` giving `_plan_validate.run` calls a 600000 ms Bash-tool timeout, stated once and back-referenced from 4b/4c/4d. **Why:** it mirrors the existing finalize-stage precedent; backgrounding or progress output adds complexity for no gain.
- **Q:** Where does the #1124 guidance live, and should the implementer get a kill tool? **A:** [auto-pick] In the `## Shell conventions` section of all six implementer agent definitions; no tool-grant change. **Why:** the agent definition covers the implementer, fixer and merge-in dispatches alike, and foreground-first verify removes the orphaned-loop scenario.
- **Q:** #1114: coerce in `_status` or wrap every SKILL.md call in `Path(...)`? **A:** [auto-pick] Coerce `str`/`os.PathLike` to `Path` inside `_status` and keep a clear `TypeError` for other types. **Why:** one code change makes ~60 documented call sites correct and cannot regress on a new call site.
