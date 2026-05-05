# Batch: implement-cli

```yaml
task: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)
batch: implement-cli
cards: 3
verify: "uv run --project plugins/mill python -m py_compile plugins/mill/scripts/millpy-implement.py"
depends-on: []
```

## Batch Scope

This batch delivers the two new production artifacts: the `implementer-fix.md` template and the `millpy-implement.py` CLI script, plus the minor extension to `_implementer_sonnet.run` that exposes a `timeout` parameter. Together these encapsulate the full per-batch implementer dispatch sequence (10 steps → 1 subprocess call) for both initial dispatch and fix-cycle resume. The next batch (`tests-and-skill`) consumes `millpy-implement.py` as the subject under test.

Batch-local decisions beyond Shared Decisions:
- The `review_file` path is normalised to absolute before being written to status.md and passed to the template: `review_file = Path(args.review_file); if not review_file.is_absolute(): review_file = (project_root / review_file).resolve()`.
- The batch state is always overwritten on both initial dispatch (crash-recovery: `pending` or `running` → `running`) and fix-cycle resume (crash-recovery: `reviewing` or `fixing` → `fixing`). No guard check on the current state is needed.
- `--resume` without `--review-file` is validated after `parse_args`: `if args.resume and not args.review_file: print(..., file=sys.stderr); return 1`. Standard argparse `required=True` cannot express conditional requirements.

## Cards

### Card 1: implementer-fix.md template

- **Reads:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/scripts/_render.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/templates/implementer-fix.md`
- **Deletes:** none
- **Requirements:** Create the fix-cycle resume prompt template. The file must:
  - Begin with an HTML comment listing all tokens (stripped by `_render.render` at render time). List: `REVIEW_FILE`, `BATCH_FILE`, `SELF_FIX_ROUNDS`, `ROUND`.
  - After the comment, open with a heading that names this as a fix-cycle resume prompt and identifies the round using `<ROUND>`.
  - Instruct the implementer to: (1) load the `mill-receiving-review` skill before reading any finding; (2) read the review file at `<REVIEW_FILE>`; (3) apply VERIFY → HARM CHECK → FIX or PUSH BACK per finding; (4) re-run the `verify:` command from the batch frontmatter at `<BATCH_FILE>`, with up to `<SELF_FIX_ROUNDS>` self-fix attempts on failure; (5) report the same JSON shape as before (`{"status":"success|stuck","commit_sha":"...","session_id":"..."}`), reflecting post-fix state.
  - The tone and structure should mirror `implementer-brief.md` (heading, short prose sections, no markdown tables).
  - Keep it concise — the implementer's warm session already knows the code; this prompt adds only the review pointer and decision-tree reminder.
- **Commit:** `feat(templates): add implementer-fix.md for fix-cycle resume`

### Card 2: extend _implementer_sonnet.run with timeout

- **Reads:**
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Modifies:**
  - `plugins/mill/scripts/_implementer_sonnet.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add an optional keyword argument `timeout: int = 1800` to `_implementer_sonnet.run`. Pass it through to `run_implementer` as the `timeout` keyword argument. The default value `1800` must match `_llm_claude.run_implementer`'s existing default so existing callers are unaffected. Update the module docstring's `Public API` line for `run()` to mention the new parameter. No other changes.
- **Commit:** `feat(implementer): expose timeout kwarg on _implementer_sonnet.run`

### Card 3: millpy-implement.py CLI script

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/templates/implementer-fix.md`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Deletes:** none
- **Requirements:** Create the CLI script. The module-level docstring must reproduce the CLI surface and exit-code table from the discussion. Structure `main(argv=None) -> int` following `millpy-review-code.py`'s pattern (imports inside main, argparse, early validation, then work).

  **Argument parsing:**
  - Positional `batch_name` (required).
  - `--resume` flag (store_true).
  - `--round N` (int, default 1).
  - `--review-file PATH` (str, default None).
  - After `parse_args`: if `args.resume and not args.review_file`, print `"--resume requires --review-file"` to stderr and return 1.

  **Common setup (both paths):**
  1. `project_root = Path.cwd()` and `mill_dir = project_root / ".millhouse"`.
  2. `git_root = _paths.resolve_git_root()` then `wiki_path = _paths.resolve_wiki_path(git_root)`.
  3. `cfg = _review_common.load_config(wiki_path, mill_dir)`. Wrap in `try/except _review_common.ReviewError as e: print(str(e), file=sys.stderr); return 1`.
  4. `slug = _active.read_slug(mill_dir)`. Wrap in `try/except _active.ActiveError as e: print(str(e), file=sys.stderr); return 1`.
  5. `status_path = project_root / "status.md"`.
  6. `full = _status.read_full(status_path)` → `task_title = full["yaml"].get("task", slug)`.
  7. `branch = _status.read_branch(status_path, cfg=cfg, slug=slug)`.
  8. `self_fix_rounds = cfg.get("review", {}).get("code", {}).get("self_fix_rounds", 2)`.
  9. `timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)`.
  10. `overview_path = project_root / "plan" / "00-overview.md"`. If not exists → stderr + return 1.
  11. Parse batch index via `_plan_dag.extract_batch_index(overview_path.read_text(encoding="utf-8"))`. On `PlanDAGError` → stderr + return 1.
  12. Find `batch_entry = next((b for b in batches if b["name"] == batch_name), None)`. If None → stderr + return 1.
  13. `batch_file = project_root / "plan" / batch_entry["file"]`.
  14. `plugin_root = Path(__file__).resolve().parent.parent` (resolves to `plugins/mill/`).

  **Initial dispatch path (`not args.resume`):**
  1. `start_sha`: `result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=project_root)`. On non-zero returncode → stderr + return 1. `start_sha = result.stdout.strip()`.
  2. `session_id = str(uuid.uuid4())`.
  3. Three `_status.set_batch_field` calls: `state="running"`, `start_sha=start_sha`, `implementer_session=session_id`. Always overwrite (crash-recovery).
  4. Git commit: `result = subprocess.run(["git", "add", "status.md"], capture_output=True, text=True, cwd=project_root)`. On non-zero returncode → print `result.stderr` to stderr, return 1. Then `result = subprocess.run(["git", "commit", "-m", f"mill-go: start batch {batch_name}"], capture_output=True, text=True, cwd=project_root)`. On non-zero → stderr + return 1.
  5. Git push: `result = subprocess.run(["git", "push", "origin", branch], capture_output=True, text=True, cwd=project_root)`. On non-zero → print `result.stderr` to stderr, return 1.
  6. Render: `template_path = plugin_root / "templates" / "implementer-brief.md"`. `prompt_text = _render.render(template_path, {"TASK_TITLE": task_title, "SLUG": slug, "BATCH_NAME": batch_name, "BATCH_FILE": str(batch_file), "OVERVIEW_FILE": str(project_root / "plan" / "00-overview.md"), "PROJECT_ROOT": str(project_root), "WIKI_PATH": str(wiki_path), "SELF_FIX_ROUNDS": str(self_fix_rounds), "ROUND": "1"})`.
  7. Run: `output, _ = _implementer_sonnet.run(prompt_text, session_id=session_id, resume=False, cwd=project_root, timeout=timeout)`. Wrap in try/except `_llm_claude.LLMError` → print `json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)})`, print str(e) to stderr, return 1.
  8. Return `_forward_output(output)`.

  **Fix-cycle resume path (`args.resume`):**
  1. Normalise review_file: `review_file = Path(args.review_file); if not review_file.is_absolute(): review_file = (project_root / review_file).resolve()`. If not exists → stderr + return 1.
  2. Read `implementer_session`: `existing = _status.read_batches(status_path)`. `batch_state = next((b for b in existing if b["name"] == batch_name), None)`. `session_id = batch_state.get("implementer_session") if batch_state else None`. If not `session_id` → stderr + return 1.
  3. Three `_status.set_batch_field` calls: `state="fixing"`, `review_round=args.round`, `review_file=str(review_file)`. Always overwrite.
  3b. Append phase via `_status.append_phase(status_path, f"fixing-{batch_name}-r{args.round}", _timestamp.now_utc_iso())`.
  4. Compute `review_file_arg = str(review_file.relative_to(project_root)) if review_file.is_relative_to(project_root) else str(review_file)`. Git commit: `result = subprocess.run(["git", "add", "status.md", review_file_arg], capture_output=True, text=True, cwd=project_root)`. On non-zero → stderr + return 1. Then `result = subprocess.run(["git", "commit", "-m", f"mill-go: fixing batch {batch_name} round {args.round}"], capture_output=True, text=True, cwd=project_root)`. On non-zero → stderr + return 1.
  5. Git push: `result = subprocess.run(["git", "push", "origin", branch], capture_output=True, text=True, cwd=project_root)`. On non-zero → stderr + return 1.
  6. Render: `template_path = plugin_root / "templates" / "implementer-fix.md"`. `prompt_text = _render.render(template_path, {"REVIEW_FILE": str(review_file), "BATCH_FILE": str(batch_file), "SELF_FIX_ROUNDS": str(self_fix_rounds), "ROUND": str(args.round)})`.
  7. Run: `output, _ = _implementer_sonnet.run(prompt_text, session_id=session_id, resume=True, cwd=project_root, timeout=timeout)`. Wrap in try/except `_llm_claude.LLMError` (catches both `LLMError` and `LLMSessionError` since the latter is a subclass) → print `json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)})`, print str(e) to stderr, return 1.
  8. Return `_forward_output(output)`.

  **`_forward_output(output: str) -> int` (module-level helper):**
  Iterate `reversed(output.strip().splitlines())`. For each non-empty line, try `json.loads(line)`. On success, `print(line)` and `return 0`. If no valid JSON found, `print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))` and `return 0`.

  **`if __name__ == "__main__":`** block at the end: `sys.exit(main())`.

- **Commit:** `feat(scripts): add millpy-implement.py — per-batch implementer dispatch CLI`

## Batch Tests

The `verify:` command runs `py_compile` on the new script. This checks syntax without executing `main()`. Full behavioral testing lives in batch 02 (`test-millpy-implement.py`). The py_compile verify catches the most common implementer mistakes (syntax error, missing import, typo in module name).
