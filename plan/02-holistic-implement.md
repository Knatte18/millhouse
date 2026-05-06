# Batch: holistic-implement

```yaml
task: '14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15)'
batch: holistic-implement
number: 2
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Delivers the complete holistic-fix dispatch path: the `implementer-holistic-brief.md` template, the `millpy-implement-holistic.py` CLI (plus `review.code.holistic_rounds` config key), the rewritten `## Holistic code review` section in `mill-go/SKILL.md`, and unit tests. Card 5 is the bootstrap card for the `wiki-config-mutation` validator check. Depends on batch 1 for `_implementer_common._forward_output`.

## Cards

### Card 4: Create template `implementer-holistic-brief.md`

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/scripts/_render.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/implementer-holistic-brief.md`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/templates/implementer-holistic-brief.md`. Add a leading HTML comment (`<!-- ... -->`) listing all 11 tokens (`<TASK_TITLE>`, `<SLUG>`, `<OVERVIEW_FILE>`, `<REVIEW_FILE>`, `<PROJECT_ROOT>`, `<WIKI_PATH>`, `<SESSION_ID>`, `<ROUND>`, `<SELF_FIX_ROUNDS>`, `<BATCH_FILES>`, `<BATCH_SESSION_IDS>`) and noting that `_render.render` strips this comment. Template body structure:
  - Title: `# Holistic Implementer Brief — <TASK_TITLE>`
  - Role statement: one paragraph explaining this is a fresh (cold-start) holistic implementer session tasked with fixing cross-batch findings, running all batch verify commands, and emitting a JSON report.
  - **Inputs** section listing: `<REVIEW_FILE>` (holistic review file), `<OVERVIEW_FILE>` (plan overview), `<PROJECT_ROOT>` (worktree cwd for git and verify), `<WIKI_PATH>`, Round `<ROUND>`. Then a fenced block under heading "Batch plan files (for `verify:` commands):" containing `<BATCH_FILES>` (renders as newline-separated absolute paths). Then a fenced block under heading "Batch session IDs — for CONTEXT ONLY. Do NOT pass these to `--resume`; holistic dispatch is always cold-start:" containing `<BATCH_SESSION_IDS>` (renders as `name: session_id` pairs).
  - **Before reading any finding** section: "Load the `mill-receiving-review` skill before reading any finding in `<REVIEW_FILE>`. This is non-negotiable."
  - **Fix discipline** section: apply findings in the order the review lists them; commit after each fix using the `git-commit` skill (so lint and `codeguide-update` run per commit); if a fix requires touching a file not mentioned in any batch plan, add it to the relevant batch file first and commit the plan edit before the code change.
  - **Verify** section: "After all fixes are committed, run every non-null `verify:` command from every batch plan file listed in `<BATCH_FILES>`, in the order listed. Run each from `<PROJECT_ROOT>` via Bash. If a verify command fails: self-fix and retry. After `<SELF_FIX_ROUNDS>` failing self-fix attempts for the same batch, stop and report stuck."
  - **Report** section: last output line must be bare JSON (no code fence). Success shape: `{"status":"success","commit_sha":"<last-HEAD-sha>","session_id":"<SESSION_ID>"}`. Stuck shape: `{"status":"stuck","stuck_type":"transient|verify|logic","reason":"<one-line>","commit_sha":"<last-HEAD-sha>","session_id":"<SESSION_ID>"}`. Instruct: "`session_id` MUST be exactly `<SESSION_ID>` — copy it verbatim."
  - **Tools** section: same as `implementer-brief.md` — Available: Read, Edit, Write, Bash, Grep, Glob. Banned: TodoWrite, WebFetch, WebSearch. Use `git -C <PROJECT_ROOT>` for commits; do not `cd`.
- **Commit:** `feat(mill): add implementer-holistic-brief template`

### Card 5: Create CLI `millpy-implement-holistic.py` and add `holistic_rounds` config key

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_timestamp.py`
  - `plugins/mill/templates/implementer-holistic-brief.md`
- **Edits:**
  - `wiki/config.yaml`
- **Creates:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Deletes:** none
- **Requirements:**

  **Bootstrap justification for `wiki/config.yaml` mutation (this card is the bootstrap card):** `review.code.holistic_rounds` is a new key with no existing readers in `scripts/` or `skills/` — grep for `holistic_rounds` confirms zero hits. The consuming code (`millpy-implement-holistic.py`) is created in this same card. Adding the key and its consumer together is safe because the key is purely additive, has a benign default (1), and no existing code path is affected by its presence.

  **`wiki/config.yaml` edit:** Under `review.code`, add `holistic_rounds: 1` on a new line after the existing `self_fix_rounds:` key.

  **`millpy-implement-holistic.py` implementation:** Module docstring mirrors `millpy-implement.py` style — describe flags, exit codes. Flags: `--review-file PATH` (optional, default None; checked manually), `--round N` (int, default 1). No positional arg, no `--resume`. Import block (in order): `from __future__ import annotations`, standard library (`argparse`, `json`, `subprocess`, `sys`, `uuid`, `pathlib.Path`), then `_active`, `_implementer_sonnet`, `_llm_claude`, `_paths`, `_plan_dag`, `_render`, `_review_common`, `_status`, `_timestamp`, `from _implementer_common import _forward_output`.

  `main(argv=None) -> int` procedure:
  1. `parser = argparse.ArgumentParser(...)`. Add `--review-file` (type str, default None) and `--round` (type int, default 1). Parse `args = parser.parse_args(argv)`. If `args.review_file is None`, print error to stderr, return 1.
  2. `project_root = Path.cwd()`, `mill_dir = project_root / ".millhouse"`.
  3. `git_root = _paths.resolve_git_root()`, `wiki_path = _paths.resolve_wiki_path(git_root)`.
  4. `cfg = _review_common.load_config(wiki_path, mill_dir)` — on `ReviewError` print to stderr, return 1.
  5. `slug = _active.read_slug(mill_dir)` — on `ActiveError` print to stderr, return 1.
  6. `status_path = project_root / "status.md"`. `full = _status.read_full(status_path)`. `task_title = full["yaml"].get("task", slug)`. `branch = _status.read_branch(status_path, cfg=cfg, slug=slug)`. `self_fix_rounds = cfg.get("review", {}).get("code", {}).get("self_fix_rounds", 2)`. `timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)`.
  7. Validate review file: `review_file = Path(args.review_file)`. If not absolute, resolve: `review_file = (project_root / review_file).resolve()`. If `not review_file.exists()`, print to stderr, return 1.
  8. `overview_path = project_root / "plan" / "00-overview.md"`. If `not overview_path.exists()`, print to stderr, return 1.
  9. `batches = _plan_dag.extract_batch_index(overview_path.read_text(encoding="utf-8"))` — on `PlanDAGError` print to stderr, return 1.
  10. Build `batch_files_text = "\n".join(str(project_root / "plan" / b["file"]) for b in batches)`.
  11. Build session IDs text: `batch_states = _status.read_batches(status_path)`. `sid_map = {b["name"]: b.get("implementer_session", "(none)") for b in batch_states}`. `batch_session_ids_text = "\n".join(f"{b['name']}: {sid_map.get(b['name'], '(none)')}" for b in batches)`.
  12. `session_id = str(uuid.uuid4())`.
  13. `_status.append_phase(status_path, "holistic-fixing", _timestamp.now_utc_iso())`.
  14. `review_file_arg = str(review_file.relative_to(project_root)) if review_file.is_relative_to(project_root) else str(review_file)`.
  15. `git add status.md <review_file_arg>` → check returncode, print stderr, return 1 on failure.
  16. `git commit -m f"mill-go: holistic fix round {args.round}"` → check returncode, return 1 on failure.
  17. `git push origin <branch>` → check returncode, return 1 on failure.
  18. `plugin_root = Path(__file__).resolve().parent.parent`. `template_path = plugin_root / "templates" / "implementer-holistic-brief.md"`. `prompt_text = _render.render(template_path, {"TASK_TITLE": task_title, "SLUG": slug, "OVERVIEW_FILE": str(overview_path), "REVIEW_FILE": str(review_file), "PROJECT_ROOT": str(project_root), "WIKI_PATH": str(wiki_path), "SESSION_ID": session_id, "ROUND": str(args.round), "SELF_FIX_ROUNDS": str(self_fix_rounds), "BATCH_FILES": batch_files_text, "BATCH_SESSION_IDS": batch_session_ids_text})`.
  19. `output, _ = _implementer_sonnet.run(prompt_text, session_id=session_id, resume=False, cwd=project_root, timeout=timeout)` — on `_llm_claude.LLMError`: print `json.dumps({"status": "stuck", "stuck_type": "transient", "reason": str(e)})` to stdout, print str(e) to stderr, return 1.
  20. `return _forward_output(output)`.

  Add `if __name__ == "__main__": sys.exit(main())` at the end.
- **Commit:** `feat(mill): add millpy-implement-holistic CLI and holistic_rounds config key`

### Card 6: Rewrite `## Holistic code review` in `mill-go/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace lines 155–163 of `plugins/mill/skills/mill-go/SKILL.md` — from the `## Holistic code review` heading through the `- On \`NEED_CONTEXT\` apply...` line (inclusive). Leave `## Handoff` and everything after it untouched. Additionally, in the **Entry** section of the same skill (earlier in the file), add `` `review.code.holistic_rounds` — max holistic fix rounds (default 1). `` to the list of config keys read in Entry step 3. The replacement section must:

  0. **Guard:** Only execute this section if `cfg.get("review", {}).get("code", {}).get("holistic", True)` is truthy. This preserves the existing behaviour when `review.code.holistic: false` is set in config.

  1. Read `review.code.holistic_rounds` (not `review.code.rounds`): `` `max_holistic_rounds = cfg.get("review", {}).get("code", {}).get("holistic_rounds", 1)` ``. Loop variable `H` starts at 1.

  2. **Crash-recovery:** Before firing the review CLI each round, scan `reviews/` for a file matching `*-code-review-r{H}.md` (holistic code review files have format `{ts}-code-review-r{N}.md` — no batch-name segment, no `-holistic-` substring). If found, skip the CLI and use that file's verdict directly (same pattern as per-batch; per-batch files embed `{batch_name}` so the glob never collides).

  3. Before each review: `_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())`. Commit: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: holistic reviewing round {H}"`.

  4. Fire holistic review via `millpy-bg` (same background pattern as per-batch, no `--batch`):
     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-holistic-r{H} -- \
       uv run --project "${CLAUDE_PLUGIN_ROOT}" \
         "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
         [--extra-file <p> ...]
     ```
     Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path), mirroring the per-batch review invocation. Poll and extract JSON as per the per-batch pattern.

  5. On `APPROVE`: `_status.append_phase(status_path, "holistic-approved", _timestamp.now_utc_iso())`. Commit status. Proceed to Handoff.

  6. On `REQUEST_CHANGES`: **Load `mill-receiving-review` before reading any finding.** Dispatch:
     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" \
       "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement-holistic.py" \
       --review-file <abs-path-to-holistic-review-file> --round {H}
     ```
     Parse stdout JSON (same last-`{"status":...}`-line pattern as per-batch). The CLI handles `holistic-fixing` phase + commit + push itself.
     - `stuck_type: transient`: one-retry policy (re-invoke once). If still transient: surface to user — retry fresh / skip holistic / block task.
     - `stuck_type: verify` or `logic`: surface to user — edit plan and retry / skip holistic and proceed to Handoff / block task.
     - On success: increment H and loop.

  7. On rounds-exhausted (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): surface to user with a **blocked-task halt** (not blocked-batch):
     > Holistic review exhausted {max_holistic_rounds} round(s). Task is blocked.
     > 1) Rethink — revise discussion and re-run mill-plan.
     > 2) Skip holistic — accept remaining findings and proceed to Handoff.
     > 3) Block — halt and leave for manual resolution.
     Wait for user choice before proceeding.

  8. On `NEED_CONTEXT`: apply the same extra-files / notify path as per-batch.

  Note: the `signature: _implementer_sonnet.run(...)` line present in the old stub is removed — the CLI handles dispatch entirely.
- **Commit:** `docs(mill): rewrite holistic code review section in mill-go SKILL.md`

### Card 7: Create `test-millpy-implement-holistic.py`

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- **Deletes:** none
- **Requirements:** Mirror `test-millpy-implement.py` structure. Load `millpy-implement-holistic` via `importlib.util.spec_from_file_location`. In `setUp`: create a `tempfile.mkdtemp()` fixture with `plan/` (containing `00-overview.md` with a `batches:` yaml block listing one batch entry: `name: test-batch`, `file: 01-test-batch.md`, `depends-on: []`, `verify: null`; and `01-test-batch.md`), `status.md` (full structure mirroring `test-millpy-implement.py`'s fixture: a leading `\`\`\`yaml` block with fields `phase: implementing`, `slug: test-slug`, `task: Test Task`, `branch: test-branch`, `parent: main`; then `## Timeline` + `\`\`\`text` fence with one entry; then `## Batches` + `\`\`\`yaml` fence listing `test-batch` with `state: pending`), `.millhouse/config.local.yaml` (`{}`), `wiki/config.yaml` (include `review:\n  code:\n    self_fix_rounds: 2\n    holistic_rounds: 1\n`), `reviews/`, and a `reviews/holistic-review.md` file. `os.chdir(tmp_path)` in setUp. Patch: `_paths.resolve_git_root` → tmp_path, `_paths.resolve_wiki_path` → tmp_path / "wiki", `_review_common.load_config` → `{"review": {"code": {"self_fix_rounds": 2, "holistic_rounds": 1}}, "llm": {"implementer_timeout": 1800}}`, `_active.read_slug` → `"test-slug"`, `_status.read_branch` → `"test-branch"`, `subprocess.run` → `CompletedProcess(args=[], returncode=0, stdout="abc1234\n", stderr="")`, `uuid.uuid4` → fixed UUID `00000000-0000-0000-0000-000000000001`.

  Required test cases:
  1. `test_1_fresh_dispatch_success`: call `main(["--review-file", str(review_file)])` with `_implementer_sonnet.run` returning success JSON → rc == 0, stdout last line parses to `{"status": "success", ...}`, timeline in `status.md` contains `holistic-fixing` entry.
  2. `test_2_llm_error`: `_implementer_sonnet.run` raises `_llm_claude.LLMError("timeout")` → rc == 1, stdout last line parses to `{"status": "stuck", "stuck_type": "transient", ...}`.
  3. `test_3_no_json_from_implementer`: `_implementer_sonnet.run` returns `("no json here\n", "sess")` → rc == 0, stdout last line parses to `{"status": "stuck", "stuck_type": "logic", ...}`.
  4. `test_4_missing_review_file_flag`: call `main([])` (no `--review-file`) → rc == 1, stdout is empty.
  5. `test_5_review_file_not_found`: call `main(["--review-file", "nonexistent.md"])` → rc == 1, stdout is empty.
  6. `test_6_batch_files_and_session_ids_injected`: call `main(["--review-file", str(review_file)])` with `_implementer_sonnet.run` mocked; inspect `prompt_text` (first positional arg to `run`) — assert it contains the absolute path to `01-test-batch.md` somewhere, and assert it contains `test-batch: (none)` (since the fixture status has no `implementer_session` field for `test-batch`).
- **Commit:** `test(mill): add test-millpy-implement-holistic unit tests`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` — runs the full test suite including `test-millpy-implement-holistic.py` (6 new test cases for the holistic CLI) and all existing tests as regression coverage.
