# Discussion: 64 (A) -- Small infra fixes batch 9

```yaml
task: 64 (A) -- Small infra fixes batch 9
slug: mill-misc-fixes-9
status: discussing
parent: main
```

## Problem

Twelve small independent bugs have accumulated across the mill plugin and its
unit tests. None is individually large enough to warrant its own task. Together
they cause: opaque orchestrator logs, reviewer cross-file attribution failures
that produce phantom BLOCKING findings across multiple rounds, test failures on
main that red-CI without new code, and unclear error messages when infra degrades
mid-session. A batch task groups them for one coordinated fix pass.

Issues #340, #342, and #343 (config-load bugs) are handled in the concurrent
task mill-config-load-fixes. Issues #333 and #334 were already fixed in commit
f424c90 (task 66). The remaining twelve issues are the scope of this task.

## Scope

**In:**
- `plugins/mill/scripts/_subprocess_util.py` -- suppress verbose spawn/exit logging on success (#339)
- `plugins/mill/scripts/millpy-bg.py` -- guarantee `[mill-bg] EXIT` sentinel always written, even when subprocess.run raises (#341)
- `plugins/mill/scripts/_review_common.py` -- add `--- END FILE: <path> ---` close delimiters to `bulk_files()` and `bulk_files_with_diff()` to reduce cross-file attribution failures (#323/#326)
- `plugins/mill/scripts/_review_code.py` -- clean skip when rounds=0 (#327)
- `plugins/mill/scripts/_review_discussion.py` -- clean skip when rounds=0 (#327)
- `plugins/mill/scripts/_review_plan.py` -- clean skip when rounds=0 (#327)
- `plugins/mill/scripts/millpy-merge-in-subagent.py` -- read `merge.model` config key (#345)
- `plugins/mill/unit_tests/_test_helpers.py` -- add `layout` keyword to `_make_task_worktree` (#325)
- `plugins/mill/unit_tests/test-review-common.py` -- add FAIL labels to silent-failure paths; fix the "missing config -> ReviewError" test case (#332)
- `plugins/mill/templates/plan-overview.md` -- replace `<TASK_TITLE>` with `<TASK_TITLE_YAML>` in fenced yaml block; keep `<TASK_TITLE>` raw in H1 (#321)
- `plugins/mill/templates/plan-batch.md` -- replace `<TASK_TITLE>` with `<TASK_TITLE_YAML>` and `<BATCH_NAME>` with `<BATCH_NAME_YAML>` in fenced yaml block; keep heading tokens raw (#321)
- `plugins/mill/templates/mill-config.yaml` -- add `model: haiku` under `merge:` block (#345)
- `mill-config.yaml` (hub root) -- add `model: sonnethigh` under `merge:` block (#345)
- `plugins/mill/skills/mill-go/SKILL.md` -- fix load_config arg order in Entry step 3 (#322); add per-invocation venv check before each millpy-bg call (#344)
- `plugins/mill/skills/mill-plan/SKILL.md` -- update token dict to supply `TASK_TITLE_YAML: quote_scalar(task_title)` + `TASK_TITLE: task_title` (raw), and similarly for BATCH_NAME (#321)

**Out:**
- Config-load bugs #340, #342, #343 (handled in mill-config-load-fixes task)
- Issues #333 and #334 (already fixed in commit f424c90, task 66 A)
- Reviewer registry changes, new reviewer strategies, psmux activation, mill-go pipeline redesign
- Any change to `_marker.py`, `_paths.py`, `_wiki.py` core helpers
- `_review_common.load_config` or `_config.load_config` internals (those belong to mill-config-load-fixes)
- Holistic reviewer prompt template text changes (deferred; structural file-delimiter fix is the code change)

## Decisions

### subprocess verbosity (#339)

- Decision: Buffer the spawn message in a local variable before `Popen`; emit the buffered spawn line AND the exit line only when `proc.returncode != 0`. On success both lines are suppressed. If `Popen` itself raises (before `proc` exists), emit the buffered spawn message followed by the exception, since the operator needs to know what was attempted. The `popen_detached` one-line log is not touched (single line per call, not double).
- Rationale: Orchestrators read bg logs after agent completion; ~2 lines per git/python call multiplies to hundreds of noise lines. On success the breadcrumbs have no value. On failure the pair gives context. The spawn line must be buffered (not wrapped in `if proc.returncode != 0:`) because `proc` does not exist at the point the message is assembled.
- Rejected: `verbose: bool` param (adds call-site complexity); always logging spawn but not exit (partial info worse than none).

### millpy-bg EXIT guarantee (#341)

- Decision: In the worker's inner try/except, introduce a boolean flag `exit_written = False`. In the try block, after `subprocess.run()` succeeds, write `[mill-bg] EXIT {result.returncode}` and set the flag. In the except branch, write `[mill-bg] WORKER ERROR {exc!r}` then, if the flag is still False, write `[mill-bg] EXIT -1`. This guarantees the EXIT sentinel appears regardless of whether `subprocess.run()` raised or returned normally.
- Rationale: Polling loops in mill-go, mill-plan, and mill-start wait forever for `[mill-bg] EXIT`. Any exception in subprocess.run (e.g. FileNotFoundError for a missing python.exe) must produce the sentinel so the poll terminates.
- Rejected: Moving EXIT into a `finally:` block (the normal path writes the real returncode; the except path needs a known non-zero sentinel -- mixing them in one finally is more confusing).

### bulk_files END FILE delimiters (#323/#326)

- Decision: In `_review_common.bulk_files()` and `bulk_files_with_diff()`, add an explicit close delimiter after each file's content. For FILE branches: `--- END FILE: {p} ---\n`. For the DIFF branch in `bulk_files_with_diff`: `--- END DIFF: {p} ---\n`. The openers (`--- FILE: {p} ---`, `--- DIFF: {p} ---`) are kept as-is; the new closers give the LLM unambiguous boundaries so content from one entry cannot bleed into the next. Both FILE and DIFF entries get closers because the same attribution risk applies to diff content.
- Rationale: #323 and #326 are both traced to cross-file content attribution: the reviewer conflates adjacent similarly-structured files in the bulk (plan templates, SKILL.md files). Adding an unambiguous close delimiter is the cheapest structural fix. This does NOT prevent all hallucination but removes the main structural ambiguity that enables it.
- Rejected: Fanning out per-template reviews (high effort, touches scheduling); prompt-level warning injection (soft constraint; not reliable across rounds); full solution deferred to reviewer prompt audit.

### rounds:0 skip semantics (#327)

- Decision: In `_review_code.py`, `_review_discussion.py`, and `_review_plan.py`: when `effective_max == 0`, return a stub `ReviewResult` with `verdict="APPROVE"`, `round=0`, `blocking_count=0`, and a reviews list entry `{"scope": scope, "verdict": "APPROVE", "file": None, "skipped": True}`. Log one line: `[_review_code] rounds=0 -- review disabled, returning APPROVE`. Do NOT raise ReviewError.
- Rationale: "Round 1 exceeds max 0" is nonsensical to operators. The SKILL.md docs describe "rounds: 0 means skip". The backend should mirror that contract so even a bypass caller gets a sensible result.
- Rejected: Checking in CLI scripts before calling the backend (dispersed logic); raising a renamed error (callers need updating).

### _make_task_worktree layout keyword (#325)

- Decision: Add `layout: Literal["prefix", "container"] = "prefix"` keyword to `_make_task_worktree`. When `layout="prefix"` (default): current behaviour -- worktree at `tmp/worktree`, wiki at `tmp/wiki`. When `layout="container"`: worktree at `tmp/wts/{slug}`, wiki at `tmp/wiki`. Existing tests keep working without changes.
- Rationale: `resolve_wiki_path` uses prefix-form lookup (`tmp/worktree.wiki`) for the current default layout; tests that need real `resolve_wiki_path` calls must use container-form. Keeping prefix as default preserves the ~10 existing tests that inject `wiki_path` directly.
- Rejected: Changing the default to container-form (breaks no test in practice, but is a behavioural change to existing fixtures); patching `resolve_wiki_path` in each test (dispersed, defeats the purpose).

### plan-overview.md / plan-batch.md token split (#321)

- Decision: In the templates, rename the token in fenced yaml blocks from `<TASK_TITLE>` to `<TASK_TITLE_YAML>` (plan-overview.md) and from `<TASK_TITLE>` / `<BATCH_NAME>` to `<TASK_TITLE_YAML>` / `<BATCH_NAME_YAML>` (plan-batch.md). The H1 heading tokens (`<TASK_TITLE>` and `<BATCH_NAME>`) remain unchanged and are supplied as raw (unquoted) strings. In mill-plan SKILL.md, add `TASK_TITLE_YAML: quote_scalar(task_title)` and `BATCH_NAME_YAML: quote_scalar(batch_name)` to the tokens dict alongside the existing raw versions; remove the `quote_scalar` wrapping from `TASK_TITLE` and `BATCH_NAME` (those go raw now). The `<SLUG>`, `<STARTED>`, `<PARENT_BRANCH>` tokens still go through `quote_scalar` as before.
- Rationale: The same `<TASK_TITLE>` token appears in both the H1 heading (plain markdown) and a fenced yaml block (where special chars like `:` must be quoted). Pre-quoting produces `# Plan: '...'` with visible quotes in rendered docs. Issue #321 confirms this was observed in production.
- Rejected: Post-processing the rendered file to strip quotes from H1 (fragile regex); not quoting at all (breaks YAML safety); using `<TASK_TITLE_RAW>` for H1 instead (requires renaming the existing H1 token, which is an unnecessary breaking change).

### mill-go load_config arg order (#322)

- Decision: Change mill-go SKILL.md Entry step 3 from `_review_common.load_config(wiki_path, Path(".millhouse"))` to `_review_common.load_config(worktree_root, worktree_root / ".millhouse")` where `worktree_root = _paths.resolve_git_root()`. This is a documentation-only fix to the SKILL.md instruction.
- Rationale: `load_config(repo_root, mill_dir)` -- first arg is the hub repo root, not the wiki path. Passing wiki_path causes `resolve_mill_config_path` to look for `mill-config.yaml` inside the wiki dir (always absent), silently returning template-only config values (e.g. batch.rounds=3) instead of the configured ones (e.g. batch.rounds=0).
- Rejected: No real alternatives.

### mill-go venv check (#344)

- Decision: In mill-go SKILL.md, add a venv-check bash block before each `millpy-bg.py` invocation (both per-batch and holistic). The block checks `[ ! -f "$MILL_PYTHON" ]`; if absent, attempts `uv sync --project plugins/mill` once; if sync fails or `$MILL_PYTHON` is still absent afterward, halts with "HALT: MILL_PYTHON not found at $MILL_PYTHON -- venv lost mid-session. Run 'uv sync --project plugins/mill' manually."
- Rationale: Step 0 checks the venv at session start but not between batches or on resume. A mid-session venv loss currently produces an opaque bash "No such file or directory" error buried in a bg log.
- Rejected: Checking only once at startup (already done; misses mid-session losses); wrapping the invocation in a subshell that prints a custom message (harder than a simple pre-check).

### merge.model config (#345)

- Decision: Add `model: haiku` under the `merge:` block in `plugins/mill/templates/mill-config.yaml`. Add `model: sonnethigh` in `mill-config.yaml` (hub root, the operator's local override). Update `millpy-merge-in-subagent.py` to read `cfg.get("merge", {}).get("model") or cfg.get("roles", {}).get("implementer", {}).get("model", "haiku")` -- explicit `merge.model` wins; fall back to `roles.implementer.model` for backward compatibility.
- Rationale: Issue #345 says Haiku is too weak for conflict resolution; operator prefers sonnethigh. Making it configurable lets each hub set its own preference without code changes. Template default stays `haiku` (conservative); operator override in hub config sets it to `sonnethigh`.
- Rejected: Using `roles.implementer.model` only (couples merge quality to implementer quality; they're different tasks).

### test-review-common.py silent failures (#332)

- Decision: (a) Scan every `errors += 1` site in `test-review-common.py` that lacks a preceding `print(f"FAIL: ...", file=sys.stderr)` and add one. (b) Fix the "missing config -> ReviewError" test: wrap the load_config call with `unittest.mock.patch("_review_common.resolve_plugin_template_path", return_value=Path("/nonexistent/template.yaml"))` so the plugin template is treated as absent, restoring the ReviewError path.
- Rationale: The issue says the test exits with `1 test(s) FAILED` but no FAIL line is printed -- diagnosing which sub-test failed requires instrumentation. Part (b) fixes the actual root cause: since CLAUDE_PLUGIN_ROOT is set in the dev environment, `resolve_plugin_template_path` now returns a real path, which means "no sources" is never reached. The ReviewError contract is still valid and should be tested.
- Rejected: Removing the test (error path is still a valid contract); updating it to expect no error (misleading).

## Technical context

**`_subprocess_util.run()`** (`plugins/mill/scripts/_subprocess_util.py`): The spawn print at line ~86 fires BEFORE `proc = subprocess.Popen(...)` at line ~126, so `proc.returncode` is not yet available. Pattern: assign `_spawn_msg = f"[subprocess] spawn argv={argv!r} timeout={timeout}"` before `Popen`; after exit code is known emit `_spawn_msg` + exit line only when `proc.returncode != 0`. If `Popen` itself raises (before `proc` exists), emit `_spawn_msg` + the exception info. On success: suppress both lines. The timeout exit-code paths and the Windows watchdog branch each need the same conditional treatment.

**`millpy-bg.py` worker mode** (`plugins/mill/scripts/millpy-bg.py`): `subprocess.run(cmd, ...)` at line ~50. Introduce flag `exit_written = False`. In try: write EXIT and set flag. In except: write WORKER ERROR, then write EXIT -1 if not exit_written.

**`_review_common.bulk_files()`** (line ~728): Currently each file section ends immediately with its content. Add `\n--- END FILE: {p} ---\n` after each content block. **`bulk_files_with_diff()`** (line ~770): Has four `parts.append(...)` branches. The three FILE branches (lines ~778, 784, 791) each get `\n--- END FILE: {p} ---\n`. The DIFF branch (line ~788) gets `\n--- END DIFF: {p} ---\n`. Both closer styles match their opener naming convention.

**`_review_code.py` rounds:0** (line ~198-204): Current code: `if round_n > effective_max: raise ReviewError(...)`. Prepend: `if effective_max == 0: print(..., file=sys.stderr); return ReviewResult(type="code", round=0, verdict="APPROVE", blocking_count=0, reviews=[{"scope": scope_label, "verdict": "APPROVE", "file": None, "skipped": True}])`. Same pattern in `_review_discussion.py` (line ~63-66) and `_review_plan.py`.

**`_test_helpers._make_task_worktree`**: Add `layout: Literal["prefix", "container"] = "prefix"` keyword. When "container": `worktree_path = tmp / "wts" / slug`. When "prefix" (default): keep `worktree_path = tmp / "worktree"`. No callers need to change.

**`plan-overview.md` template** (line 23): `# Plan: <TASK_TITLE>` stays as-is. YAML block line changes: `task: <TASK_TITLE>` -> `task: <TASK_TITLE_YAML>`.

**`plan-batch.md` template** (line 18, 21-22): `# Batch: <BATCH_NAME>` stays as-is. YAML block changes: `task: <TASK_TITLE>` -> `task: <TASK_TITLE_YAML>`, `batch: <BATCH_NAME>` -> `batch: <BATCH_NAME_YAML>`.

**`millpy-merge-in-subagent.py`** (line ~155): Change `model_name = implementer_cfg.get("model", "sonnethigh")` to `model_name = cfg.get("merge", {}).get("model") or implementer_cfg.get("model", "haiku")`.

**mill-go SKILL.md**: (a) Step 3: fix load_config invocation; (b) Add venv-check block before each millpy-bg call. Two locations: per-batch loop step 2 and holistic loop step 3.

**mill-plan SKILL.md**: Add `TASK_TITLE_YAML: quote_scalar(task_title)` and `BATCH_NAME_YAML: quote_scalar(batch_name)` to the tokens dict. Change existing `TASK_TITLE: quote_scalar(task_title)` -> `TASK_TITLE: task_title` (remove the quote_scalar wrapping). Same for BATCH_NAME. Keep `SLUG`, `STARTED`, `PARENT_BRANCH` going through quote_scalar.

## Testing

**`_subprocess_util`** (new test in existing test file or a new `test-subprocess-util.py`): mock a zero-exit subprocess; assert nothing written to stderr. Mock a non-zero exit; assert both spawn and exit lines appear.

**`millpy-bg` EXIT guarantee** (existing `test-bg-liveness.py` or new): mock subprocess.run to raise FileNotFoundError; call `_worker_main`; assert log file contains `[mill-bg] EXIT -1`.

**`bulk_files` END FILE delimiters** (existing `test-review-common.py`): assert that `bulk_files([file1, file2])` output contains `--- END FILE: {file1} ---` and `--- END FILE: {file2} ---`. Same for `bulk_files_with_diff`.

**`rounds:0` skip** (new or existing): call `_review_code.run(...)` with a mocked config having rounds=0; assert ReviewResult with verdict="APPROVE" and round=0 is returned (no ReviewError raised). Same for `_review_discussion` and `_review_plan`.

**`_make_task_worktree` layout** (existing tests unaffected; new test in `test-review-common.py` or `test-bg-launcher.py`): call with `layout="container"`, then `resolve_wiki_path(wt)` and assert it returns the correct wiki path.

**`plan-overview.md` token rendering** (no dedicated test needed; manual: render the template with a title containing a colon and verify the H1 has no quotes and the yaml block has the quoted form).

**`merge.model` config** (manual/integration): create a config with `merge: {model: sonnethigh}`; assert `millpy-merge-in-subagent.py` resolves to `sonnethigh`. Create without `merge.model`; assert fallback to `roles.implementer.model`.

**`test-review-common.py`**: Run the full suite after fixes; assert all tests PASS and exit 0. The "missing config -> ReviewError" test must still raise ReviewError under the mock.

## Q&A log

- **Q:** Suppress subprocess logging on success -- suppress both lines, just exit line, or parametric? **A:** [auto-pick] suppress both lines on success; emit both on non-zero exit. **Why:** operators need the breadcrumbs only when something went wrong.
- **Q:** millpy-bg EXIT -- finally block or flag approach? **A:** [auto-pick] flag approach: normal path writes real returncode, except path writes -1 sentinel. **Why:** clearly separates "subprocess completed" from "subprocess failed to start".
- **Q:** bulk_files END FILE delimiter -- add closer or restructure prompt? **A:** [auto-pick] add `--- END FILE: <path> ---` after each file block. **Why:** cheapest structural fix; removes the attribution ambiguity.
- **Q:** rounds:0 -- return APPROVE stub or raise cleaner error? **A:** [auto-pick] return APPROVE stub ReviewResult. **Why:** mirrors the "skip" semantics documented in the SKILL.md; no caller needs updating.
- **Q:** _make_task_worktree -- add layout keyword or change default? **A:** [auto-pick] add layout keyword with "prefix" as default. **Why:** preserves existing tests.
- **Q:** plan token fix -- new YAML-suffixed tokens or new RAW-suffixed tokens? **A:** [auto-pick] new YAML-suffixed tokens; H1 tokens stay as-is. **Why:** H1 token renaming is an unnecessary breaking change.
- **Q:** load_config arg fix -- code change or SKILL.md text-only? **A:** [auto-pick] SKILL.md text-only. **Why:** the bug is in the skill instruction, not in the Python helper.
- **Q:** mill-go venv check -- re-run uv sync or just clear error? **A:** [auto-pick] attempt uv sync once then halt. **Why:** recovers transient venv loss without manual intervention.
- **Q:** merge.model -- under merge: or roles:? **A:** [auto-pick] under merge:. **Why:** merge config belongs with merge, not the roles/reviewer namespace.
- **Q:** test-review-common silent failures -- mock the template or remove the test? **A:** [auto-pick] mock resolve_plugin_template_path. **Why:** the error path is still a valid contract.
- **Q:** Are #333 and #334 already fixed? **A:** Yes -- crash-recovery three-way branch and parse_verdict error-envelope handling were both added in commit f424c90 (task 66 A). Not in scope.
- **Q:** Are #340, #342, #343 in this task? **A:** No -- GH issues say "Folded into wiki task: mill-config-load-fixes". Active worktree mill-config-load-fixes exists. Not in scope here.
