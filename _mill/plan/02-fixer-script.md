# Batch: fixer-script

```yaml
task: "Dedicated fixer agent for post-holistic-review fix cycles"
batch: "fixer-script"
number: 2
cards: 4
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py"
depends-on: [1]
```

## Batch Scope

Delivers the new fixer surface end-to-end: two prompt templates, the unified `millpy-fix.py` CLI that dispatches them via cold-start `_implementer_claude.run(..., resume=False)`, and a unit test suite covering both `--scope batch` and `--scope holistic`. No existing scripts are modified or deleted in this batch -- both `millpy-implement.py` (with its `--resume` branch) and `millpy-implement-holistic.py` continue to exist and be referenced from mill-go. The cut-over to the new script happens in batch 3. The external interface the next batch consumes is the `millpy-fix.py` CLI: `--scope batch --batch-name NAME --review-file PATH --round N` or `--scope holistic --review-file PATH --round N`, JSON report on stdout matching the existing implementer JSON shape.

Batch-local decisions (override Shared Decisions only if listed):
- Test fixtures use the same in-memory + tempfile pattern as `test-millpy-implement-holistic.py` (mocks for `_paths`, `_review_common.load_config`, `_reviewers.load`/`resolve`, `_marker.slug_from_branch`, `_subprocess_util.run`, `_implementer_claude.run`).

## Cards

### Card 3: Write the per-batch fixer prompt template

- **Context:**
  - `plugins/mill/templates/implementer-fix.md`
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/templates/fixer-batch-brief.md`. The file is rendered by `_render.render` and starts with an HTML comment header (stripped by `_render.render`) listing every token. Tokens: `<TASK_TITLE>`, `<SLUG>`, `<BATCH_NAME>`, `<BATCH_FILE>`, `<OVERVIEW_FILE>`, `<REVIEW_FILE>`, `<PROJECT_ROOT>`, `<WIKI_PATH>`, `<SESSION_ID>`, `<ROUND>`, `<SELF_FIX_ROUNDS>`. Body sections (modelled on `implementer-fix.md` plus `implementer-brief.md`'s Report block):
  1. Title: `# Fixer Brief -- <TASK_TITLE> / <BATCH_NAME>` (round number appears in the Round line below, not the title).
  2. Intro paragraph stating: this is a cold-start fix session, you have NO prior conversation context, you must read the review file plus the batch plan to do the work.
  3. Inputs block listing: Review file `<REVIEW_FILE>`, Batch file `<BATCH_FILE>`, Overview `<OVERVIEW_FILE>`, Worktree cwd `<PROJECT_ROOT>`, Wiki path `<WIKI_PATH>`, Round **<ROUND>**.
  4. "Before reading any finding" block: load `mill-receiving-review` skill before opening the review file. Non-negotiable.
  5. Fix discipline: apply findings via VERIFY -> HARM CHECK -> FIX or PUSH BACK from the skill; for each FIX commit via the `git-commit` skill, one commit per finding; for each PUSH BACK note the rebuttal without modifying code; PLAN-CONFLICT escalation -- if a finding cannot be fixed without revising the plan, report `{"status":"stuck","stuck_type":"logic","reason":"plan conflict: <finding title>"}` (use the EXACT prefix `plan conflict: ` so mill-go routes correctly).
  6. Verify: after all fixes committed, re-run the batch's `verify:` command from the frontmatter of `<BATCH_FILE>`; on failure self-fix and retry, after **<SELF_FIX_ROUNDS>** failing attempts report `stuck_type: verify`; if `verify: null` skip to Report.
  7. Report block: copy verbatim from `implementer-brief.md`'s Report section (the "single JSON object on the last line" rule, the bare-line-no-fence rule, the duplicate-emit hedge against output truncation), with `<SESSION_ID>` substitution and `stuck_type` values `transient|verify|logic`.
  8. Tools block: same allowed/banned tool list as `implementer-brief.md` (Read, Edit, Write, Bash, Grep, Glob allowed; TodoWrite, WebFetch, WebSearch banned).
  9. Cross-worktree isolation block: copy verbatim from `implementer-brief.md` (no `cd` to parent, `git -C` for parent reads, `git -C <PROJECT_ROOT> show <parent-branch>:<path>` for file content).
- **Commit:** `templates: add fixer-batch-brief.md`

### Card 4: Write the holistic fixer prompt template

- **Context:**
  - `plugins/mill/templates/implementer-holistic-brief.md`
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/templates/fixer-holistic-brief.md`. Tokens: `<TASK_TITLE>`, `<SLUG>`, `<OVERVIEW_FILE>`, `<REVIEW_FILE>`, `<PROJECT_ROOT>`, `<WIKI_PATH>`, `<SESSION_ID>`, `<ROUND>`, `<SELF_FIX_ROUNDS>`, `<BATCH_FILES>` (newline-separated absolute paths). NOTE: NO `<BATCH_SESSION_IDS>` token -- removed deliberately because cold-start dispatch never reuses warm sessions. Body sections (modelled on `implementer-holistic-brief.md` minus the BATCH_SESSION_IDS block, plus the same plan-conflict escalation as card 3):
  1. Title: `# Holistic Fixer Brief -- <TASK_TITLE>`.
  2. Intro stating: fresh cold-start session, full worktree access, may touch any file mentioned in any finding.
  3. Inputs: Holistic review file `<REVIEW_FILE>`, Plan overview `<OVERVIEW_FILE>`, Worktree cwd `<PROJECT_ROOT>`, Wiki path `<WIKI_PATH>`, Round **<ROUND>**. Batch plan files in a fenced text block holding the literal `<BATCH_FILES>` substitution.
  4. "Before reading any finding": load `mill-receiving-review` skill. Non-negotiable.
  5. Fix discipline: same VERIFY -> HARM CHECK -> FIX or PUSH BACK rules as card 3; one `git-commit` per finding; if a fix requires touching a file not mentioned in any batch plan file, add the file to the relevant batch file first and commit the plan edit before the code change; PLAN-CONFLICT escalation -- same `stuck_type: logic` reason prefix as card 3.
  6. Verify: after all fixes committed, run every non-null `verify:` command from every batch plan file in the order listed, each from `<PROJECT_ROOT>`. On failure self-fix and retry, after **<SELF_FIX_ROUNDS>** failing attempts for the same batch's verify stop and report `stuck_type: verify`.
  7. Report block: copy verbatim from `implementer-holistic-brief.md`'s Report section (same JSON shape, same bare-line rule, same duplicate-emit hedge), with `<SESSION_ID>` substitution.
  8. Tools and cross-worktree isolation blocks: copy verbatim from `implementer-holistic-brief.md`.
- **Commit:** `templates: add fixer-holistic-brief.md`

### Card 5: Write the millpy-fix.py CLI

- **Context:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/scripts/_implementer_claude.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/millpy-fix.py` as a flat-Python CLI with a module docstring describing the unified fixer. Implement `def main(argv=None) -> int:` only -- no module-level side effects. Argument parser:
  - `--scope` required, choices `["batch", "holistic"]`.
  - `--batch-name` optional string; required iff `--scope batch`, must be absent iff `--scope holistic` (argparse-level mutual constraint: validate after parse, exit 1 with stderr message on violation).
  - `--review-file` required, string path (absolute or relative; resolve relative to `Path.cwd()` and require `.exists()` before any state mutation; missing file -> exit 1, no JSON on stdout, message on stderr).
  - `--round` int, default 1.

  Setup sequence (mirror `millpy-implement-holistic.py` lines 60-93 for shared resolution; differ where noted):
  1. `project_root = Path.cwd()`, `mill_dir = project_root / ".millhouse"`.
  2. `git_root = _paths.resolve_git_root()`, `wiki_path = _paths.resolve_wiki_path(git_root)`.
  3. `cfg = _review_common.load_config(git_root, mill_dir)`; on `_review_common.ReviewError` exit 1 with stderr.
  4. `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`; on `_marker.MarkerError` exit 1 with stderr.
  5. `status_path = _paths.status_path(project_root, cfg)`. `full = _status.read_full(status_path)`. `task_title = full["yaml"].get("task", slug)`.
  6. `branch = _status.read_branch(status_path, cfg=cfg, slug=slug)`.
  7. `self_fix_rounds = cfg.get("roles", {}).get("implementer", {}).get("self_fix_rounds", 2)`. `timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)`.
  8. `model_name = cfg.get("roles", {}).get("fixer", {}).get("model", "haiku")`. `registry = _reviewers.load(git_root)`. `impl_spec = _reviewers.resolve(registry, model_name)`. `impl_model = impl_spec["model"]`. `impl_effort = impl_spec.get("effort")`. On `_reviewers.ReviewerError` exit 1 with stderr.
  9. Resolve `review_file = Path(args.review_file)`; if not absolute, `review_file = (project_root / review_file).resolve()`. If not `review_file.exists()`, exit 1 with stderr `f"review file not found: {review_file}"`.
  10. `plan_base = _paths.resolve_task_path(project_root, "_mill/plan/")`. `overview_path = plan_base / "00-overview.md"`. If missing, exit 1 with stderr. Parse `batches = _plan_dag.extract_batch_index(overview_path.read_text(encoding="utf-8"))`; on `_plan_dag.PlanDAGError` exit 1.
  11. `session_id = str(uuid.uuid4())`.

  Branch on `args.scope`:

  **scope == "batch":**
  - Look up `batch_entry = next((b for b in batches if b["name"] == args.batch_name), None)`. If None, exit 1 with stderr `f"batch {args.batch_name!r} not found in overview"`.
  - `batch_file = plan_base / batch_entry["file"]`.
  - `_status.set_batch_fields(status_path, args.batch_name, {"state": "fixing", "review_round": args.round, "review_file": str(review_file)})`.
  - `_status.append_phase(status_path, f"fixing-{args.batch_name}-r{args.round}", _timestamp.now_utc_iso())`.
  - Compute `review_file_arg = str(review_file.relative_to(project_root)) if review_file.is_relative_to(project_root) else str(review_file)`.
  - `git add status_path review_file_arg` via `_subprocess_util.run`; on returncode != 0, print stderr and exit 1.
  - `git commit -m "mill-go: fixing batch {batch_name} round {round}"`; on failure exit 1.
  - `git push origin <branch>`; on failure exit 1.
  - Render template at `<plugin_root>/templates/fixer-batch-brief.md` with tokens `TASK_TITLE`, `SLUG`, `BATCH_NAME`, `BATCH_FILE` (str of batch_file), `OVERVIEW_FILE` (str of overview_path), `REVIEW_FILE` (str of review_file), `PROJECT_ROOT` (str of project_root), `WIKI_PATH` (str of wiki_path), `SESSION_ID`, `ROUND` (str), `SELF_FIX_ROUNDS` (str).

  **scope == "holistic":**
  - `batch_files_text = "\n".join(str(plan_base / b["file"]) for b in batches)`.
  - `_status.append_phase(status_path, "holistic-fixing", _timestamp.now_utc_iso())`.
  - Same `review_file_arg`, `git add`, `git commit -m "mill-go: holistic fix round {round}"`, `git push` sequence as batch.
  - Render template at `<plugin_root>/templates/fixer-holistic-brief.md` with tokens `TASK_TITLE`, `SLUG`, `OVERVIEW_FILE`, `REVIEW_FILE`, `PROJECT_ROOT`, `WIKI_PATH`, `SESSION_ID`, `ROUND`, `SELF_FIX_ROUNDS`, `BATCH_FILES` (== batch_files_text). The token `BATCH_SESSION_IDS` MUST NOT be passed -- it is deliberately removed; template has no slot for it.

  Both scopes share the dispatch tail:
  ```python
  try:
      output, _ = _implementer_claude.run(
          prompt_text,
          model=impl_model,
          effort=impl_effort,
          session_id=session_id,
          resume=False,
          cwd=project_root,
          timeout=timeout,
      )
  except _llm_claude.LLMError as e:
      print(json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)}))
      print(str(e), file=sys.stderr)
      return 1
  return _forward_output(output, project_root, session_id=session_id)
  ```
  `resume=False` is the load-bearing assertion enforced by Shared Decision "Cold-start dispatch only".

  Module footer: `if __name__ == "__main__": sys.exit(main())`. Imports follow the order used by `millpy-implement-holistic.py` for diff legibility.
- **Commit:** `scripts: add millpy-fix.py unified fixer CLI`

### Card 6: Write unit tests for millpy-fix.py

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-millpy-fix.py` modelled on `test-millpy-implement-holistic.py`. Use `importlib.util.spec_from_file_location("millpy_fix", str(HUB / "plugins" / "mill" / "scripts" / "millpy-fix.py"))` to load the module under test. Add a status.md fixture that contains both a batch entry (`test-batch`) and the required yaml block. Patch the same external surfaces in setUp: `_paths.resolve_git_root`, `_paths.resolve_wiki_path`, `_review_common.load_config` (returning a cfg that includes `roles.fixer.model: haiku`), `_marker.slug_from_branch`, `_status.read_branch`, `_subprocess_util.run` (returning `CompletedProcess(returncode=0, stdout="abc1234\n", stderr="")`), `uuid.uuid4`, `_reviewers.load`, `_reviewers.resolve` (returning a haiku-shaped spec `{"type":"single","provider":"claude","model":"claude-haiku-4-5-20251001"}` -- no `effort` key, since haiku has none). Tests required:
  1. `test_batch_happy_path` -- `--scope batch --batch-name test-batch --review-file <path> --round 1`. Assert: rc == 0, last JSON line on stdout has `status == "success"`, timeline contains a row starting with `fixing-test-batch-r1`, the batch entry's `state == "fixing"`, the patched `_implementer_claude.run` was called with `resume=False`, and the prompt_text contains the absolute review file path.
  2. `test_batch_missing_batch_name` -- `--scope batch --review-file <path>` without `--batch-name`. Assert rc == 1 and stdout empty.
  3. `test_batch_unknown_batch_name` -- `--scope batch --batch-name nonexistent --review-file <path>`. Assert rc == 1 and stdout empty (the batch lookup branch).
  4. `test_holistic_happy_path` -- `--scope holistic --review-file <path>`. Assert: rc == 0, success JSON, timeline contains a row starting with `holistic-fixing`, prompt_text contains the absolute batch file path AND does NOT contain the substring `BATCH_SESSION_IDS` AND does NOT contain `test-batch: (none)` (regression-guards the removal of the BATCH_SESSION_IDS token).
  5. `test_holistic_missing_review_file_flag` -- `--scope holistic` with no `--review-file`. Assert rc == 1, stdout empty.
  6. `test_review_file_not_found` -- both scopes when `--review-file` points to a nonexistent path. Parameterise with two scope values; assert rc == 1, stdout empty.
  7. `test_llm_error_propagates_as_stuck_transient` -- patch `_implementer_claude.run` to raise `_llm_claude.LLMError("timeout")`. Assert rc == 1, stdout's last JSON line has `status == "stuck"` and `stuck_type == "transient"`.
  8. `test_implementer_no_json_emits_stuck_logic` -- patch `_implementer_claude.run` to return `("no json here\n", "sess")`. Assert rc == 0 (the fallback path inside `_forward_output`), stdout's last JSON line has `status == "stuck"` and `stuck_type == "logic"`.
  9. `test_resume_false_always_passed` -- regression guard. Capture the `resume` kwarg via `side_effect`, run both batch and holistic happy paths, assert both passed `resume=False`.
  Use `unittest.main()` at the module footer.
- **Commit:** `tests: add test-millpy-fix.py`

## Batch Tests

`uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py` -- every test function above must PASS. The verify command at the frontmatter runs only this file; `run-all.py` is used in batch 3's verify.
