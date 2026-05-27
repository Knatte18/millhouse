# Batch: fixer-isolation

```yaml
task: "mill-merge / fixer teardown recovery"
batch: fixer-isolation
number: 4
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Eliminates two fixer-subprocess corruption vectors (#367 + #368) that share the same dispatch surface. The first vector: inherited `GIT_*` env vars from a polluted parent shell (or a fixture-setup script) cause the fixer's `git commit` calls to author against the wrong repo. The second: a worktree-local `git config user.email` set by the fixer's session pollutes subsequent CLI state commits. Fixes: (a) strip seven named git-state env vars in `_llm_claude._invoke` so neither the implementer nor the fixer inherits them; (b) add `_subprocess_util.git_commit(cwd, message, *, name, email)` and route every CLI state commit in `millpy-fix.py` and `millpy-implement.py` through it, with `name` and `email` resolved once from `git config --global` at script start. Plus brief edits documenting cwd discipline for the LLM sessions.

External interface for batches 1/2/3: none — this batch is self-contained.

## Cards

### Card 8: Failing test for `_subprocess_util.git_commit`

- **Context:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-cli-commit-author.py`
- **Deletes:** none
- **Requirements:** Write `test-cli-commit-author.py` exercising `_subprocess_util.git_commit(cwd, message, *, name, email)` against a tmp git repo. Setup per test: create tmp dir, `git init`, `git config user.email test@test.com` and `git config user.name "Test Pollution"` (worktree-local pollution), write + add a file. Test methods: (1) `test_explicit_author_overrides_local_config` — call `_subprocess_util.git_commit(tmp, "feat: thing", name="Real Author", email="real@example.com")`; assert returncode 0; `git -C tmp log -1 --format=%an<%ae>` returns `Real Author<real@example.com>` (NOT `Test Pollution<test@test.com>`). (2) `test_returns_completed_process_shape` — call returns a `subprocess.CompletedProcess` with `.returncode`, `.stdout`, `.stderr` attributes. (3) `test_message_with_special_chars_preserved` — pass message containing parentheses and colons (e.g. `chore(merge): pre-merge cleanup`); commit message in `git log -1 --format=%s` matches exactly. (4) `test_local_config_unchanged` — after the call, `git -C tmp config --get user.email` still returns `test@test.com` (helper does not mutate worktree config). Use the existing `HUB` import idiom. Run before card 9 to confirm it fails with `AttributeError: module '_subprocess_util' has no attribute 'git_commit'`.
- **Commit:** `test(subprocess-util): add failing test for git_commit helper`

### Card 9: Implement `_subprocess_util.git_commit`

- **Context:**
  - `plugins/mill/unit_tests/test-cli-commit-author.py`
- **Edits:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `git_commit(cwd: Path | str, message: str, *, name: str, email: str) -> subprocess.CompletedProcess[str]` to `_subprocess_util.py`. Implementation: `return run(["git", "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", message], cwd=cwd)`. Reuse the existing `run()` for env/encoding/watchdog semantics — do not duplicate that logic. Place the new function at module level, after `run()` and before any class definitions. Add a one-paragraph docstring matching the surrounding style: state the purpose (CLI state commits robust to worktree-local config drift), the parameters, the return type, and a one-line note that the helper does NOT mutate the worktree's `.git/config`. Export the symbol (add `git_commit` to any `__all__` if one exists at the top of the module; if no `__all__`, the function being module-level is sufficient).
- **Commit:** `feat(subprocess-util): add git_commit helper with explicit -c author`

### Card 10: Failing test for `_llm_claude._invoke` env-strip

- **Context:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-fixer-env-isolation.py`
- **Deletes:** none
- **Requirements:** Write `test-fixer-env-isolation.py` verifying that `_llm_claude._invoke` strips the named env-var blocklist before spawning the subprocess. Use `unittest.mock.patch.object(_subprocess_util, "run")` to capture the `env=` kwarg passed by `_invoke`. Use `os.environ` monkey-patching via `unittest.mock.patch.dict(os.environ, ..., clear=False)` to set the seven blocklisted vars plus a few benign vars before each test. Set up a minimal `_invoke` call that returns immediately by having the mocked `run` return a `CompletedProcess(args=[], returncode=0, stdout='{"type":"result","session_id":"abc","result":"ok"}', stderr="")` — or whatever shape `_parse_stream_json` minimally accepts; consult `test-llm-claude.py` for the existing minimal stream-json fixture. Test methods: (1) `test_strips_seven_named_vars` — set `GIT_DIR=/x`, `GIT_WORK_TREE=/y`, `GIT_INDEX_FILE=/z`, `GIT_AUTHOR_NAME=A`, `GIT_AUTHOR_EMAIL=a@b`, `GIT_COMMITTER_NAME=C`, `GIT_COMMITTER_EMAIL=c@d`; call `_invoke(...)`; assert none of the seven keys appear in the captured `env` dict. (2) `test_preserves_benign_git_vars` — set `GIT_PAGER=less`, `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_GLOBAL=/tmp/cfg`, `GIT_PYTHON_REFRESH=quiet` in env; call `_invoke`; assert all four ARE present in the captured `env`. (3) `test_preserves_unrelated_vars` — set `PATH=/x:/y`, `HOME=/h`, `CLAUDE_PLUGIN_ROOT=/p`, `PYTHONPATH=/q`; assert all four present in captured `env`. (4) `test_strip_constant_is_exact_set` — `assert _llm_claude.STRIP_VARS == {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"}` — pins the blocklist contents against accidental drift. Test must cover both `_invoke` branches (`_get_via_psmux_flag()=True` and `False`); use `unittest.mock.patch.object(_llm_claude, "_get_via_psmux_flag", return_value=False)` and a separate test with `return_value=True`. Run before card 11 to confirm tests (1)–(4) fail with `AttributeError` on `STRIP_VARS` and the captured env still contains the blocklisted vars.
- **Commit:** `test(llm-claude): add failing test for _invoke env-strip`

### Card 11: Implement env-strip in `_llm_claude._invoke`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-fixer-env-isolation.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a module-level constant `STRIP_VARS = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"})` immediately after the existing top-of-module imports. In `_invoke`, immediately before each of the two `_subprocess_util.run(...)` call sites (the psmux branch at `result = _subprocess_util.run(argv, input=prompt_text, timeout=float(timeout), cwd=cwd)` inside the `if _get_via_psmux_flag():` branch, AND the direct-spawn branch at `result = _subprocess_util.run(argv, input=prompt_text, timeout=float(timeout), cwd=cwd)` after `argv = _build_argv(...)`), construct an explicit `env`: `child_env = {k: v for k, v in os.environ.items() if k not in STRIP_VARS}` and pass `env=child_env` as a new kwarg to the `run()` call. Apply the same change at the fast-fail retry call site in the direct-spawn branch (the second `_subprocess_util.run(argv, ...)` call after `print(f"[_llm_claude] fast-fail retry...")`). All three subprocess invocations must pass `env=child_env`. Do NOT introduce a helper function for env construction — inline at each call site is acceptable for three identical occurrences and matches `_invoke`'s existing flat style. Do NOT modify `run_bulk`, `run_tool_use`, `run_implementer`, or any other function — the strip is centralised in `_invoke` because that is the single subprocess-spawn surface all three route through. Add a one-line ASCII comment above the `STRIP_VARS` constant: `# Git env vars that must NOT be inherited by spawned Claude sessions (see #367).`.
- **Commit:** `feat(llm-claude): strip 7 git env vars from _invoke subprocess env`

### Card 12: Route `millpy-fix.py` CLI commits through `git_commit`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-fix.py`'s `main()`, after the existing `cfg = _review_common.load_config(...)` call (around line 90) and before the existing scope-branch dispatch, resolve the intended git identity:
  ```python
  name_result = _subprocess_util.run(["git", "config", "--global", "--get", "user.name"], cwd=project_root)
  email_result = _subprocess_util.run(["git", "config", "--global", "--get", "user.email"], cwd=project_root)
  git_name = name_result.stdout.strip()
  git_email = email_result.stdout.strip()
  if not git_name or not git_email:
      print("git config --global user.name and user.email must be set", file=sys.stderr)
      return 1
  ```
  Replace both existing `["git", "commit", "-m", f"mill-go: fixing batch {args.batch_name} round {args.round}"]` (batch scope, around line 170) and `["git", "commit", "-m", f"mill-go: holistic fix round {args.round}"]` (holistic scope, around line 218) invocations. Each is currently a `_subprocess_util.run([...], cwd=project_root)` call wrapped in a returncode check. Replace the `_subprocess_util.run([...])` argv with `_subprocess_util.git_commit(project_root, "<the message>", name=git_name, email=git_email)`. Preserve the existing returncode-check error-handling block around each call exactly as-is. Do NOT modify the `git add` calls (those don't author commits). Do NOT modify the `git push` calls. Do NOT modify the fixer dispatch itself.
- **Commit:** `fix(millpy-fix): pin CLI state commits to global git identity`

### Card 13: Route `millpy-implement.py` CLI commits through `git_commit`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Mirror card 12's pattern in `millpy-implement.py`. Resolve `git_name` and `git_email` once at the top of `main()` (after config load, before any commit), with the same fail-fast block (`exit 1` if either is empty). Then replace every `["git", "commit", "-m", ...]` invocation in the script with the equivalent `_subprocess_util.git_commit(project_root, "<message>", name=git_name, email=git_email)` call, preserving the existing error-handling shape around each. Read `millpy-implement.py` to confirm the commit site — the script has exactly one `git commit` call (`mill-go: start batch {batch_name}`, around line 141); that one becomes a `git_commit` call. Do not modify any `git add`, `git push`, or non-commit git invocations. Do not modify the implementer subprocess dispatch itself.
- **Commit:** `fix(millpy-implement): pin CLI state commits to global git identity`

### Card 14: Document cwd discipline in fixer + implementer briefs

- **Context:**
  - `plugins/mill/skills/conversation/SKILL.md`
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
  - `plugins/mill/templates/fixer-holistic-brief.md`
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the three brief templates, locate the existing `## Cross-worktree isolation` section. Append a new bullet immediately after the existing "**If you need a file from the parent:**" bullet (the last bullet in that section today), with this exact text:
  > - **Never `cd` into a test fixture or scratch directory.** Fixtures under `.scratch/`, `unit_tests/fixtures/`, or any sub-tree may contain their own `.git/` — `cd <fixture>` corrupts every subsequent `git commit` in this session because git resolves the repo from cwd. To inspect a fixture, use the `Read` tool (for files) or `git -C <fixture> log/status` (for git queries). To run a test that exercises a fixture, run the test from the worktree root.
  Do not modify any other section of the briefs. Do not modify the existing "Banned" or "Allowed" bullets. The new bullet is appended once per file; the three files get identical text. Preserve every other character in each file exactly as-is, including the trailing newline.
- **Commit:** `docs(briefs): document fixture cwd discipline in cross-worktree isolation`

## Batch Tests

`verify:` runs the full unit test suite via `run-all.py`. The two new tests in this batch — `test-cli-commit-author.py` and `test-fixer-env-isolation.py` — together cover the four new code surfaces (`_subprocess_util.git_commit`, `_llm_claude.STRIP_VARS`, `_llm_claude._invoke` env construction in both psmux + direct branches). The existing test suite (`test-llm-claude.py`, `test-llm-claude-argv.py`, etc.) acts as a regression net for the `_invoke` change — those tests must still pass after card 11 since they exercise the same function. Cards 12–13 are exercised end-to-end at the next real `mill-go` run; no unit test surface for the CLI-script integration. Card 14 is a doc edit; no test surface.
