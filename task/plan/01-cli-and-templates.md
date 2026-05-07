# Batch: cli-and-templates

```yaml
task: '29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent'
batch: cli-and-templates
number: 1
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Creates the three new files that form the core of this task: `millpy-merge-in-subagent.py` (the CLI dispatcher), `merge-in-conflict-brief.md` (conflict sub-agent prompt template), and `merge-in-verify-brief.md` (verify-fix sub-agent prompt template). Together these allow the SKILL to delegate both real-code conflict resolution and verify failures to a Sonnet sub-agent, with the Builder reading only a JSON verdict. Batch 2 (SKILL.md + config) and Batch 3 (unit tests) both depend on this batch. No verify command since these are new files with no existing test coverage yet; the unit tests in Batch 3 provide coverage.

Batch-local decision: the CLI uses `shell=True` when running the verify command in `_run_verify_fix` because the verify command comes from the plan's frontmatter and may include shell operators (pipes, redirects). This matches how mill-go's verify step would have run it.

## Cards

### Card 1: Create millpy-merge-in-subagent.py

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_implementer_sonnet.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Deletes:** none
- **Requirements:** Create `millpy-merge-in-subagent.py` following the same dispatch pattern as `millpy-implement.py`. The module docstring must document: purpose, `--mode conflicts|verify-fix` flag, per-mode flags, and exit codes (0 = sub-agent ran, JSON on stdout; 1 = pre-launch error, no JSON). Structure:
  1. `main(argv=None)` — argparse setup, common setup (project_root, mill_dir, plugin_root, git_root, wiki_path, cfg, slug, timeout), mode dispatch.
  2. `_run_conflicts(args, project_root, plugin_root, cfg, timeout) -> int` — validates `--files` is non-empty (exit 1 if missing), formats file list as markdown bullets (`- \`<path>\`` per file, joined by newlines, assigned to token `CONFLICTING_FILES`), renders `merge-in-conflict-brief.md` via `_render.render`, calls `_implementer_sonnet.run(prompt_text, session_id=None, resume=False, cwd=project_root, timeout=timeout)`, catches `_llm_claude.LLMError` (print stuck/transient JSON + stderr, return 1), returns `_forward_output(output, project_root)`.
  3. `_run_verify_fix(args, project_root, plugin_root, cfg, timeout) -> int` — validates `--cmd` and `--checkpoint` are non-None (exit 1 if missing). Runs the verify command via `subprocess.run(args.cmd, shell=True, capture_output=True, text=True, cwd=project_root)`. If returncode == 0: no fix needed — run `git rev-parse HEAD` via subprocess; if that succeeds use the sha, otherwise use `""` as fallback; print `{"status":"success","commit_sha":"<sha>"}`, return 0. If returncode != 0: capture `verify_output = (result.stdout + result.stderr).strip()`, run `git diff <checkpoint>..HEAD` via `subprocess.run(["git", "diff", f"{args.checkpoint}..HEAD"], capture_output=True, text=True, cwd=project_root)`, set `merge_diff = diff_result.stdout` (or `"(diff unavailable)"` on failure), read `verify_fix_rounds = cfg.get("merge", {}).get("verify_fix_rounds", 3)`, render `merge-in-verify-brief.md` with tokens `VERIFY_CMD`, `VERIFY_OUTPUT`, `MERGE_DIFF`, `VERIFY_FIX_ROUNDS`, `PROJECT_ROOT`, call `_implementer_sonnet.run`, catch `LLMError` (same pattern), return `_forward_output(output, project_root)`.
  Token names passed to `_render.render`: `CONFLICTING_FILES`, `PROJECT_ROOT` (conflicts); `VERIFY_CMD`, `VERIFY_OUTPUT`, `MERGE_DIFF`, `VERIFY_FIX_ROUNDS`, `PROJECT_ROOT` (verify-fix).
  Argparse: `--mode` is `required=True`, `choices=["conflicts", "verify-fix"]`. `--files` is `nargs="+"`, `default=None`. `--cmd` and `--checkpoint` are `default=None`.
- **Commit:** `feat(merge-in): add millpy-merge-in-subagent.py dispatcher CLI`

### Card 2: Create merge-in-conflict-brief.md

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Deletes:** none
- **Requirements:** Create the conflict resolution brief template. It must: (1) start with an HTML comment (stripped by `_render.render`) listing all tokens: `<CONFLICTING_FILES>`, `<PROJECT_ROOT>`. (2) After the comment, open with a heading `# Conflict Resolution Brief`. (3) Explain the sub-agent's sole job: resolve git conflict markers in the listed files, stage each resolved file via `git add <file>`, do NOT commit and do NOT run `git merge --continue` (the SKILL does that after receiving `{"status":"success"}`). (4) List the conflicting files using the `<CONFLICTING_FILES>` token. (5) Instruct: for each file, read the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`), understand both sides, write a resolution that preserves the intent of both, run `git add <file>` for each resolved file. Never use `git checkout --ours` or `git checkout --theirs` — they silently discard one side. (6) Include a Report section: the last output line MUST be a bare JSON object (no fence) — `{"status":"success"}` on success, `{"status":"stuck","stuck_type":"logic","reason":"<one-line>"}` if unable to resolve. (7) Tools section: Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C <PROJECT_ROOT>` for any git commands; do not `cd`. Worktree cwd is `<PROJECT_ROOT>`.
- **Commit:** `feat(merge-in): add merge-in-conflict-brief.md template`

### Card 3: Create merge-in-verify-brief.md

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/templates/merge-in-verify-brief.md`
- **Deletes:** none
- **Requirements:** Create the verify-fix brief template. It must: (1) start with an HTML comment listing all tokens: `<VERIFY_CMD>`, `<VERIFY_OUTPUT>`, `<MERGE_DIFF>`, `<VERIFY_FIX_ROUNDS>`, `<PROJECT_ROOT>`. (2) After the comment, open with heading `# Verify-Fix Brief`. (3) Explain: the verify command `<VERIFY_CMD>` failed after a merge. The sub-agent's job is to diagnose the failures and fix the code so the verify command passes. (4) Include a `## Verify Output` section showing `<VERIFY_OUTPUT>` verbatim in a code block. (5) Include a `## Merge Diff` section showing `<MERGE_DIFF>` verbatim in a diff code block. (6) Instructions: read the failing tests and the code they exercise, fix the root cause (not the tests themselves unless they're genuinely wrong due to the merge), re-run `<VERIFY_CMD>` after each fix attempt. Self-fix up to `<VERIFY_FIX_ROUNDS>` times before reporting stuck. Commit each fix attempt with a clear commit message. (7) Report section: last output line MUST be bare JSON: `{"status":"success","commit_sha":"<last-HEAD-sha>"}` on success; `{"status":"stuck","stuck_type":"verify","reason":"<one-line>","commit_sha":"<last-HEAD-sha>"}` after exhausting fix rounds. (8) Tools section: Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C <PROJECT_ROOT>` for git; do not `cd`. Worktree cwd is `<PROJECT_ROOT>`.
- **Commit:** `feat(merge-in): add merge-in-verify-brief.md template`

## Batch Tests

`verify: null` — this batch creates new files with no pre-existing test surface. Coverage is provided by Batch 3 (`unit-tests`), which verifies all three files created here via `python plugins/mill/unit_tests/run-all.py`. Batch 3 depends on this batch, so its verify gate covers these files.
