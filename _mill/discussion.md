# Discussion: 64 (A) -- Small infra fixes batch 9

```yaml
task: 64 (A) -- Small infra fixes batch 9
slug: mill-misc-fixes-9
status: discussing
parent: main
```

## Problem

Sixteen small independent bugs have accumulated across the mill plugin and its
unit tests. None is individually large enough to warrant its own task, but
collectively they cause noisy orchestrator logs, reviewer hallucination loops
that block merges, silent config misreads, test failures on main that red-CI
without new code, and opaque error messages when infra degrades mid-session.
A batch task groups them for one coordinated fix pass.

## Scope

**In:**
- `plugins/mill/scripts/_subprocess_util.py` -- suppress verbose spawn/exit logging on success (#339)
- `plugins/mill/scripts/millpy-bg.py` -- guarantee `[mill-bg] EXIT` is always written even when subprocess.run raises (#341)
- `plugins/mill/scripts/_review_common.py` -- fix `_deep_merge` None-clobber (#342); fix rounds:0 "Round 1 exceeds max 0" error in `_review_discussion.py` (#327 parallel)
- `plugins/mill/scripts/_review_code.py` -- fix rounds:0 error (#327); add repeated-finding detection (#326/#334)
- `plugins/mill/scripts/_review_plan.py` -- add repeated-finding detection (#323)
- `plugins/mill/scripts/_review_discussion.py` -- fix rounds:0 error (#327 parallel)
- `plugins/mill/scripts/_config.py` -- fix `deep_merge` None-clobber (#342); fix `resolve_plugin_template_path` invalid/stale CLAUDE_PLUGIN_ROOT (#340/#343)
- `plugins/mill/scripts/millpy-merge-in-subagent.py` -- read `merge.model` config key (#345)
- `plugins/mill/unit_tests/_test_helpers.py` -- fix `_make_task_worktree` layout incompatible with `resolve_wiki_path` (#325)
- `plugins/mill/unit_tests/test-review-common.py` -- fix "missing config -> ReviewError" test failure (#332)
- `plugins/mill/templates/plan-overview.md` -- add `<TASK_TITLE_RAW>` token for H1 heading (#321)
- `plugins/mill/templates/mill-config.yaml` -- add `merge.model` key (#345)
- `mill-config.yaml` (hub root) -- add `merge.model` key (#345)
- `plugins/mill/skills/mill-go/SKILL.md` -- fix load_config arg order in step 3 (#322); add exit-0/no-JSON handling for holistic reviewer (#333); add pre-invocation venv check (#344)
- `plugins/mill/skills/mill-plan/SKILL.md` -- add `TASK_TITLE_RAW` token supply; update hallucination detection in plan-review loop (#323)

**Out:**
- Reviewer registry changes or new reviewer strategies
- Psmux activation (separate task `claude-psmux-activate`)
- mill-go pipeline redesign (separate task `mill-orchestrator`)
- Any change to the `_marker.py`, `_paths.py`, `_wiki.py` core path-resolution stack
- Changes to `millpy-review-discussion.py`, `millpy-review-plan.py` CLI scripts (only backend helpers change)
- Reviewers.yaml or registry schema changes

## Decisions

### subprocess verbosity (#339)

- Decision: Suppress both `[subprocess] spawn argv=...` and `[subprocess] exit code=... duration=...s` lines when the process exits with code 0. Emit both on non-zero exit (the full pair is preserved so operators have context when debugging).
- Rationale: Orchestrators read bg logs after agent completion; ~2 lines per git/python call multiplies to hundreds of noise lines. On success the breadcrumbs have no value.
- Rejected: Adding a `verbose: bool` param (adds call-site complexity); always logging spawn but not exit (partial information is worse than none).

### millpy-bg EXIT guarantee (#341)

- Decision: Wrap `subprocess.run()` in the worker's `try/except Exception` with a `finally` block that writes `[mill-bg] EXIT -1` if the exception path was taken (i.e., the normal `log_f.write(f"[mill-bg] EXIT {result.returncode}")` was never reached). Separate `[mill-bg] WORKER ERROR` line for the exception text is written before EXIT.
- Rationale: Polling loops in mill-go / mill-start wait for `[mill-bg] EXIT`; if it is never written they hang forever. Any exception in subprocess.run (e.g. FileNotFoundError for a missing python.exe) must produce the sentinel.
- Rejected: Writing `[mill-bg] EXIT <exception>` on the same line (conflates sentinel and error text, making it harder to grep).

### _deep_merge None-clobber (#342)

- Decision: Both `_review_common._deep_merge` and `_config.deep_merge` skip overlay keys whose value is `None` (do not overwrite a base dict with None). Change: add `if val is None: continue` before the existing isinstance check.
- Rationale: Bare `roles:` in YAML parses to `roles: null`; merging that into a fully-populated base config should be a no-op, not a wipe. The value `None` cannot be a meaningful "clear this key" instruction because YAML has no dedicated null-removal sentinel.
- Rejected: Logging a warning on None skip (adds noise without actionable info for normal YAML typos).

### resolve_plugin_template_path fallback (#340/#343)

- Decision: After computing the CLAUDE_PLUGIN_ROOT template path, check if the file exists. If it does not, fall back to the source-tree path `Path(__file__).resolve().parent.parent / "templates" / filename` and emit a one-line stderr warning `[config] CLAUDE_PLUGIN_ROOT template not found at <path>; falling back to source tree`. Both `_config.resolve_plugin_template_path` and the identical copy in `_review_common` need the fix.
- Rationale: A stale or invalid CLAUDE_PLUGIN_ROOT currently makes `template_path.exists()` return False far from the source, causing downstream KeyError. A warning at the resolution point gives the operator an actionable message.
- Rejected: Hard-erroring immediately on missing template (breaks non-millhouse installs that rely on source-tree form without setting the env var).

### rounds:0 skip semantics (#327)

- Decision: In `_review_code.py`, `_review_discussion.py`, and `_review_plan.py`: when `effective_max == 0`, return a stub `ReviewResult` with `verdict="APPROVE"`, `round=0`, and `blocking_count=0`, plus a log line `[_review_code] rounds=0 -- review disabled, returning APPROVE`. Do NOT raise ReviewError.
- Rationale: The current "Round 1 exceeds max 0" message is nonsensical. The SKILL.md docs already describe "rounds: 0 OR reviewer: null means skip". The backend should mirror that contract.
- Rejected: Checking in the CLI scripts before calling the backend (dispersed logic); raising a differently-named error (callers would need updating).

### Repeated-finding (hallucination) detection (#323/#326/#334)

- Decision: Add a helper `detect_repeated_findings(reviews_dir, review_type, scope, current_round, current_review_text) -> bool` in `_review_common.py`. It extracts all `### [BLOCKING]` / `### [NIT]` headings from both the previous round's file and the current text; returns `True` if every heading in the current round's file matches exactly (same set, same titles) with the previous round. Call this after parsing the verdict in `_review_code.py` and `_review_plan.py`. If `repeated_findings=True`, add a `hallucination: true` field in the `reviews[*]` dict of the ReviewResult and set `repeated_findings=True` on the outer ReviewResult (new bool field). The CLI scripts serialise this field in JSON. The orchestrators (mill-go, mill-plan SKILL.md) check `repeated_findings` in the JSON envelope: if True, treat as APPROVE and fire a `_notify.notify("mill.reviewer-quality-issue", ...)` event.
- Rationale: Reviewers hallucinating the same findings across multiple rounds are not providing useful signal; blocking on them wastes implementer cycles. The detection is deterministic (string heading comparison) and low-cost. The notification creates a record for mill-self-report without silently swallowing the issue.
- Rejected: Detecting in orchestrators only (the orchestrator doesn't parse finding headings; adding that logic there is heavier than a shared helper). Adding a new `"HALLUCINAT"` verdict type (breaks the existing verdict enum surface area).

### mill-go exit-0/no-JSON (#333)

- Decision: In the holistic code-review section of mill-go SKILL.md, extend the exit handling rule: "If `[mill-bg] EXIT` reports any exit code (0 or non-zero) AND no JSON summary line is present in the log, halt with `BLOCKED: holistic review pre-launch failure` and surface the last 10 lines of the log to the user." Mirrors the per-batch section's existing rule.
- Rationale: Exit 0 with no JSON is just as unrecoverable as exit 1 with no JSON -- the reviewer crashed before emitting its result.
- Rejected: Retrying once (adds complexity; if the CLI can't produce JSON it will fail again).

### mill-go venv check (#344)

- Decision: In mill-go SKILL.md, before EACH `millpy-bg.py` invocation, add a bash check: if `[ ! -f "$MILL_PYTHON" ]`, attempt `uv sync --project plugins/mill` once; if the sync fails or `$MILL_PYTHON` is still absent, halt with "HALT: MILL_PYTHON not found at $MILL_PYTHON -- venv lost mid-session. Run 'uv sync --project plugins/mill' manually."
- Rationale: A mid-session venv loss currently produces an opaque shell "python.exe not found" error buried in the bg log. The orchestrator needs to know this is a recoverable infra issue, not a code bug.
- Rejected: Checking only once at startup (already done; the new check catches losses that occur after startup).

### plan-overview H1 token (#321)

- Decision: Add token `<TASK_TITLE_RAW>` to `plan-overview.md` template for the H1 heading (`# Plan: <TASK_TITLE_RAW>`). Keep `<TASK_TITLE>` (YAML-quoted) for the fenced yaml block. mill-plan SKILL.md adds `"TASK_TITLE_RAW": task_title` (unquoted) alongside the existing `"TASK_TITLE": quote_scalar(task_title)` in the tokens dict. Same fix for `plan-batch.md` if it has a heading that embeds the title.
- Rationale: `quote_scalar("64 (A) -- Small infra fixes batch 9")` wraps the string in single quotes (YAML safety); the H1 heading `# Plan: '64 (A) -- Small infra fixes batch 9'` is ugly and wrong.
- Rejected: Post-processing the rendered file to strip quotes from the H1 (fragile regex); not quoting TASK_TITLE at all (breaks YAML safety for titles containing colons or other special chars).

### load_config arg order (#322)

- Decision: Change mill-go SKILL.md step 3 from `_review_common.load_config(wiki_path, Path(".millhouse"))` to `_review_common.load_config(worktree_root, worktree_root / ".millhouse")`. Derive `worktree_root = _paths.resolve_git_root()` inline in step 3 (it is also derived in step 4.5; the two are consistent).
- Rationale: `load_config(repo_root, mill_dir)` -- first arg is the hub repo root, not wiki_path. Passing wiki_path causes `resolve_mill_config_path` to look for `mill-config.yaml` in the wiki directory (always absent), silently falling back to wiki/config.yaml.
- Rejected: No real alternatives; this is a documentation/instruction bug.

### merge.model config (#345)

- Decision: Add `model: haiku` under the `merge:` block in `plugins/mill/templates/mill-config.yaml` and `mill-config.yaml` (hub root). Update `millpy-merge-in-subagent.py` to read `cfg.get("merge", {}).get("model") or cfg.get("roles", {}).get("implementer", {}).get("model", "haiku")` -- explicit `merge.model` wins; if absent fall back to `roles.implementer.model` for backward compatibility.
- Rationale: The merge subagent does conflict resolution, which is different work from implementation; it may warrant a different model. Keeping it under `merge:` is semantically clear and avoids polluting `roles.implementer`.
- Rejected: Adding `roles.merge.model` (extends the roles namespace unexpectedly; roles are reviewer strategies, not merge config).

### _make_task_worktree container-form (#325)

- Decision: Change `_test_helpers._make_task_worktree` to create the git worktree at `tmp / "wts" / slug` (instead of `tmp / "worktree"`) and keep the wiki at `tmp / "wiki"`. This matches the container-form layout that `_sibling.resolve_path` and thus `resolve_wiki_path` expect (`parent.name == "wts"` triggers container-form). Update all callers in unit tests that reference `(wt, wiki)` -- since the function signature and return types are unchanged, only the internal layout changes; callers work without modification.
- Rationale: The current `tmp/worktree/` layout triggers prefix-form resolution: `resolve_path("wiki", tmp/worktree)` returns `tmp/worktree.wiki`, not `tmp/wiki/`. Any unit test that calls `resolve_wiki_path` from a fixture worktree fails.
- Rejected: Patching `resolve_wiki_path` in each test (dispersed; tests stop covering real resolution).

### test-review-common.py "missing config" test (#332)

- Decision: In `test-review-common.py`, wrap the "load_config missing config -> ReviewError" test with `unittest.mock.patch("_review_common.resolve_plugin_template_path", return_value=Path("/nonexistent/template.yaml"))` so the plugin template is treated as absent for that specific case.
- Rationale: Since `CLAUDE_PLUGIN_ROOT` is now set in the mill dev environment, `resolve_plugin_template_path` returns a real path. The strict "no sources -> ReviewError" branch can no longer be reached without mocking. The ReviewError path is still a valid contract to test.
- Rejected: Removing the test (the error path is still valid); updating it to expect no error (confuses "seeded from template" with "config explicitly present").

## Technical context

**`_subprocess_util.run()`** (`plugins/mill/scripts/_subprocess_util.py`): The two `print(..., file=sys.stderr)` calls (lines ~86 and ~153) unconditionally emit output. The fix is a conditional: `if proc.returncode != 0: print(...)`. The `popen_detached` function also logs one line but that is one line per call, not two; leave it unless the same issue is confirmed there (out of scope).

**`millpy-bg.py` worker mode** (`plugins/mill/scripts/millpy-bg.py`): The `subprocess.run(cmd, ...)` call at ~line 50 is wrapped in a broad try/except but the except only writes `[mill-bg] WORKER ERROR`. The fix: use a flag variable `exit_written = False`; in the normal path after the run, write EXIT and set the flag; in the except block, write EXIT -1 if flag is False.

**`_review_common._deep_merge`** (line ~1168) and **`_config.deep_merge`** (line ~283): Identical fix in both. Add `if val is None: continue` at the start of the loop body (before `isinstance` check).

**`_config.resolve_plugin_template_path`** (line ~126) and its copy in `_review_common` (line ~128): After `Path(plugin_root_env).resolve() / "templates" / filename`, add: `if not path.exists(): warnings.warn/stderr-print + fall back to source-tree path`.

**`_review_code.py` rounds:0** (line ~198-204): Add `if effective_max == 0:` before the `if round_n > effective_max:` check; in that branch, `print("[_review_code] rounds=0 -- review disabled, returning APPROVE", file=sys.stderr)` and return a stub ReviewResult.

**`_test_helpers._make_task_worktree`**: Change `worktree_path = tmp / "worktree"` to `worktree_path = tmp / "wts" / slug`. No other callers need changes.

**`plan-overview.md` template**: Line 23: `# Plan: <TASK_TITLE>` -> `# Plan: <TASK_TITLE_RAW>`. The `task:` field in the YAML block continues to use `<TASK_TITLE>` (quoted). Check `plan-batch.md` for the same pattern.

**`millpy-merge-in-subagent.py`**: Line ~155: `model_name = implementer_cfg.get("model", "sonnethigh")` -> read `cfg.get("merge", {}).get("model") or implementer_cfg.get("model", "haiku")`.

**`detect_repeated_findings` helper**: New function in `_review_common.py`. Signature: `detect_repeated_findings(reviews_dir: Path, review_type: str, scope: str, current_round: int, current_text: str) -> bool`. Find file for `round - 1` in reviews_dir matching the scope/type pattern; extract `### [<SEVERITY>]` headings from both; return True if non-empty and exactly equal as sets.

**mill-go SKILL.md changes**: (a) step 3 load_config fix; (b) holistic exit-0/no-JSON handling at step 3's "Exit handling" paragraph; (c) venv pre-check block before each `millpy-bg` invocation.

**mill-plan SKILL.md changes**: Add `"TASK_TITLE_RAW": task_title` to tokens dict; add hallucination check after receiving REQUEST_CHANGES from plan review.

## Testing

**`_subprocess_util`**: Unit test: mock a zero-exit subprocess; assert no lines written to stderr. Mock a non-zero exit; assert both spawn and exit lines appear.

**`millpy-bg` EXIT guarantee**: Unit test: mock subprocess.run to raise FileNotFoundError; call `_worker_main`; assert log file contains `[mill-bg] EXIT -1`.

**`_deep_merge` None-clobber**: Unit test: `_deep_merge({"a": {"b": 1}}, {"a": None})` should return `{"a": {"b": 1}}`. Same for `_config.deep_merge`.

**`resolve_plugin_template_path` fallback**: Unit test: set `CLAUDE_PLUGIN_ROOT` to a nonexistent dir; call `resolve_plugin_template_path("mill-config.yaml")`; assert result is the source-tree path and stderr contains the warning.

**`rounds:0` skip**: Unit test: call `_review_code.run(...)` with a config whose rounds=0; assert ReviewResult with verdict="APPROVE" and round=0.

**`detect_repeated_findings`**: Unit test: call with a reviews_dir containing a prior round with headings A, B; provide current_text with headings A, B; assert True. Provide current_text with headings A, C; assert False. Empty prior round file -> assert False.

**`_make_task_worktree` fix**: Existing tests in `test-review-common.py` that call `_make_task_worktree` and then use `resolve_wiki_path` will pass once the layout is fixed. Verify no other unit test references `"worktree"` as a literal path segment.

**`test-review-common.py` "missing config"**: The patched test must still raise ReviewError. Run the full test suite on both main and the fix branch to confirm all tests pass.

**`merge.model`**: Integration test: create a config with `merge: {model: "sonnethigh"}` and assert `millpy-merge-in-subagent.py` resolves to `sonnethigh`; create a config without `merge.model` and assert fallback to `roles.implementer.model`.

## Q&A log

- **Q:** Should subprocess verbose logging suppress only on exit-0, or never? **A:** [auto-pick] suppress both lines on success; emit both on non-zero exit. **Why:** cleans orchestrator logs without hiding failure context.
- **Q:** For millpy-bg EXIT guarantee, write EXIT -1 or EXIT with exception text? **A:** [auto-pick] EXIT -1 plus a separate WORKER ERROR line. **Why:** EXIT sentinel must be grep-able without parsing variable exception text.
- **Q:** Should _deep_merge None skip log a warning? **A:** [auto-pick] silent skip. **Why:** bare `roles:` is a YAML typo, not intentional; a warning is noise.
- **Q:** resolve_plugin_template_path: fallback silently, with warning, or error? **A:** [auto-pick] fallback with stderr warning. **Why:** silent breaks debugging; hard error blocks source-tree fallback in edge cases.
- **Q:** rounds:0 fix: in backend or CLI? **A:** [auto-pick] in backend; return stub APPROVE ReviewResult. **Why:** keeps CLI and orchestrators oblivious.
- **Q:** Hallucination detection: in backends or orchestrators? **A:** [auto-pick] backends (shared helper in _review_common); orchestrators read the flag. **Why:** heading extraction logic belongs with the reviewer layer.
- **Q:** Hallucination detected -> approve or new verdict? **A:** [auto-pick] treat as APPROVE + fire quality-issue notify event. **Why:** do not block merge on reviewer quality failures.
- **Q:** mill-go exit-0/no-JSON: retry or halt? **A:** [auto-pick] halt BLOCKED immediately. **Why:** exit-0 with no JSON is as unrecoverable as exit-1 with no JSON.
- **Q:** mill-go venv check: re-run uv sync or just error? **A:** [auto-pick] attempt uv sync once then halt with clear message. **Why:** recovers transient venv loss without manual intervention.
- **Q:** plan-overview H1: RAW token or post-processing? **A:** [auto-pick] TASK_TITLE_RAW token in template. **Why:** clean; post-processing is fragile.
- **Q:** merge.model: under merge: or roles:? **A:** [auto-pick] under merge:. **Why:** merge config belongs with merge, not the roles/reviewer namespace.
- **Q:** _make_task_worktree: container-form or mock resolve_wiki_path? **A:** [auto-pick] container-form layout. **Why:** tests cover real resolution.
- **Q:** test-review-common "missing config" fix: mock or remove? **A:** [auto-pick] mock resolve_plugin_template_path. **Why:** the error path is still a valid contract.
- **Q:** load_config arg order fix: just SKILL.md text change? **A:** [auto-pick] yes, text-only change to mill-go SKILL.md step 3.
