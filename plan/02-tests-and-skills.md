# Batch: tests-and-skills

```yaml
task: '5 (A) — mill-bg.py: project-lokal backgrounding'
batch: tests-and-skills
cards: 5
verify: python plugins/mill/unit_tests/test-millpy-bg.py
depends-on: [core-script]
```

## Batch Scope

This batch adds the unit test suite for `millpy-bg.py` and updates the two SKILL.md files that instruct agents how to invoke long-running review scripts. After this batch, agents that follow `mill-start` or `mill-go` will use `millpy-bg` for review invocations instead of `run_in_background: true`, and all unit tests pass. The SKILL.md cards (4 and 5) are pure documentation changes with no runnable surface; the verify covers only the unit tests.

## Cards

### Card 3: Write `test-millpy-bg.py`

- **Reads:**
  - `plugins/mill/scripts/millpy-bg.py`
  - `plugins/mill/unit_tests/test-subprocess-util.py`
  - `plugins/mill/unit_tests/test-shortcut-wrapper.py`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Deletes:** none
- **Requirements:**

  Follow the test file pattern: a `main() -> int` function, `if __name__ == "__main__": sys.exit(main())`, `HUB` path resolution at the top, `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`. Collect failures in a list and print/return 1 at the end. Each passing case prints `PASS (<label>): <description>`.

  The test file imports `millpy-bg` via `importlib` or by `sys.path` insertion followed by `runpy.run_path`, since the filename is hyphenated and cannot be a direct Python import. Use `importlib.util.spec_from_file_location` / `spec.loader.exec_module` pattern to load the script as a module named `millpy_bg`. After loading, access `_launcher_main` and `_worker_main` directly.

  **Launcher mode tests** — use `unittest.mock.patch` to mock `subprocess.Popen` and `subprocess.run` (the git rev-parse call):

  - **(a) log path format:** Mock `subprocess.run` to return a fake git root (`/tmp/testrepo` or equivalent tempdir). Mock `Popen`. Call `_launcher_main(["--slug", "myslug", "--", "echo", "hi"])`. Capture stdout. Assert the output line matches `pid=<N> log=<path>` where path ends with `bg-<14-digit-timestamp>-myslug.log` under `.scratch/`.
  - **(b) .scratch/ created:** Same setup; assert `.scratch/` dir is created (pass a real tempdir as the fake git root; don't mock `Path.mkdir`).
  - **(c) stdout is exactly one line:** Assert the captured stdout has exactly one non-empty line and nothing extra.
  - **(d) Windows flags:** When `os.name` is patched to `"nt"`, assert Popen is called with `creationflags` containing `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` (`0x01200208`).
  - **(e) non-Windows flags:** When `os.name` is patched to `"posix"`, assert Popen is called with `start_new_session=True` and no `creationflags`.
  - **(f) missing --slug exits 1:** Call `_launcher_main(["--", "echo", "hi"])` and assert return value is 1.
  - **(g) missing -- exits 1:** Call `_launcher_main(["--slug", "x"])` and assert return value is 1.

  **Worker mode tests** — run directly in a `tempfile.TemporaryDirectory`, no mocking:

  - **(h) output captured to log:** Call `_worker_main(["--log", str(log_path), "--", sys.executable, "-c", "print('hello')"])`. Assert log_path exists and its text contains `hello`.
  - **(i) sentinel written on success:** Assert log text ends with `[mill-bg] EXIT 0` (after stripping trailing whitespace).
  - **(j) non-zero exit code in sentinel:** Call with `sys.executable, "-c", "import sys; sys.exit(3)"`. Assert log text contains `[mill-bg] EXIT 3`.
  - **(k) missing --log exits 1:** Call `_worker_main(["--", "echo", "hi"])` and assert return value is 1.
  - **(l) missing command exits 1:** Call `_worker_main(["--log", str(log_path), "--"])` and assert return value is 1.

- **Commit:** `test(mill-bg): add unit tests for millpy-bg launcher and worker modes`

### Card 4: Update `mill-start/SKILL.md` — background discussion reviews

- **Reads:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  In the `### Phase: Discussion Review` section, replace the current step 2 invocation block. The current text reads:

  ```
  2. Invoke the CLI as a subprocess:

     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
     ```

     The script writes the review file under `<worktree_root>/reviews/` and prints a one-line JSON summary: ...
  ```

  Replace it with:

  ```
  2. Background the CLI via `millpy-bg`:

     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug review-discussion-r<N> -- \
         uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
     ```

     This returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll the log file with `cat <log-path>` until the line `[mill-bg] EXIT` appears. Once it does, read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log). The script writes the review file under `<worktree_root>/reviews/` and emits a one-line JSON summary: `{"type": "discussion", "round": <int>, "verdict": "APPROVE" | "GAPS_FOUND", "blocking_count": <int>, "reviews": [{"scope": "holistic", "verdict": ..., "file": "<abs-path>", "session_id": "<id>"}]}`.
  ```

  No other changes to the file.

- **Commit:** `docs(mill-start): use millpy-bg for discussion review invocation`

### Card 5: Update `mill-go/SKILL.md` — background code reviews

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  In the `## Per-batch review loop` section (the section containing `For each round N from 1 to review.code.rounds`), replace step 2's invocation block. The current text reads:

  ```
  2. Invoke:

     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" --batch <batch_name> \
         [--extra-file <p> ...]
     ```

     The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.
  ```

  Replace it with:

  ```
  2. Background via `millpy-bg`:

     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug review-code-<batch_name>-r<N> -- \
         uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
             --batch <batch_name> [--extra-file <p> ...]
     ```

     Returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line (last non-empty, non-sentinel line). The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.
  ```

  Also find the holistic review invocation (the line `- Invoke \`uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py"\` (no \`--batch\`).`) and update it similarly:

  Replace:
  ```
  - Invoke `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py"` (no `--batch`).
  ```

  With:
  ```
  - Background via `millpy-bg`: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" --slug review-code-holistic-r<N> -- uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py"` (no `--batch`). Poll and extract JSON as per the per-batch pattern above.
  ```

  No other changes to the file.

- **Commit:** `docs(mill-go): use millpy-bg for code review invocations`

## Batch Tests

The verify command `python plugins/mill/unit_tests/test-millpy-bg.py` runs the unit test suite created in Card 3. It tests both launcher mode (with mocked Popen and git calls) and worker mode (real subprocess in tempdir). The SKILL.md cards (4 and 5) are pure documentation and have no automated verify surface; correctness is confirmed by human review.
