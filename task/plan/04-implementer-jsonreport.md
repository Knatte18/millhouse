# Batch: implementer-jsonreport

```yaml
task: 50 (A) — Bug-fix batch 5 (post-44 triage)
batch: implementer-jsonreport
number: 4
cards: 3
verify: python plugins/mill/unit_tests/test-implementer-common.py
depends-on: []
```

## Batch Scope

Address #243: long Sonnet implementer sessions occasionally truncate their
final stdout, causing `_implementer_common._forward_output` to emit a false
`stuck_type: logic` sentinel for batches that actually succeeded. The fix is
dual:

1. **Tighten the brief** so future sessions emit JSON earlier and more
   defensively (Card 10).
2. **Recover the already-degraded case** with a fallback in `_forward_output`
   that infers success when (a) `_cleanliness.compute_new_dirt(project_root,
   snapshot_path)` returns an empty list, (b) `git rev-parse HEAD` differs from
   the batch's `start_sha`, and (c) the snapshot file exists on disk (refuses
   to infer without a real baseline). Threaded via two new keyword arguments
   on `_forward_output`; resolved at both `millpy-implement.py` call sites
   (initial-dispatch + fix-cycle resume) (Cards 11, 12).

External interface for follow-on review: `_forward_output(output, project_root,
*, start_sha=None, snapshot_path=None)` is the new signature. Both kwargs
default to `None`; when either is `None` or the snapshot file is missing,
behaviour is identical to today's (emit the stuck-logic sentinel when no JSON
is found).

Batch-local decisions:

- The inferred-success payload includes a `"inferred": true` flag so consumers
  (mill-go) can later distinguish "explicit success" from "inferred success"
  if they need to gate behaviour. Mill-go's current consumer
  (`millpy-implement.py` returns; mill-go reads stdout) ignores unknown JSON
  fields, so the flag is forward-only and adds no immediate consumer dep.
- `session_id` in the inferred payload is the literal string `"unknown"` —
  we cannot reconstruct the implementer's session_id without the JSON it
  was supposed to emit. The implementer-fix-cycle re-resume path uses
  `status.md`'s `implementer_session` field, not the report's `session_id`,
  so `unknown` is safe.
- The brief reinforcement is one new paragraph appended to the existing
  `## Report` section. It adds NO new template tokens — the wording is
  hard-coded and visible to the implementer in every batch.

## Cards

### Card 10: Harden `implementer-brief.md` long-session JSON-report guarantee

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/templates/implementer-brief.md`'s `## Report` section, insert a new paragraph immediately after the existing two `**Do not wrap the JSON in a code block...**` paragraphs and BEFORE the `## On review resume` heading. New paragraph text:

  > **Long-session reminder:** if you have produced a lot of tool output earlier in this session (e.g. many `Bash` calls, large `Read` results), your final assistant turn's text output may be truncated by the orchestrator before the JSON line is captured. To protect against this, emit the JSON line as the **first** non-tool content of your final assistant turn, before any optional commentary or further tool calls. Re-emit the JSON line at the end of the same turn as well — duplicate JSON is fine, `_implementer_common._forward_output` reads the last match.

  No other line in the file changes. The new paragraph adds zero template tokens (no `<TOKEN>` placeholders), so `_render.render`'s token-resolution behaviour is unaffected.
- **Commit:** `docs(implementer-brief): require early JSON emission in long sessions`

### Card 11: `_forward_output` infers success when JSON is missing but worktree is clean + advanced

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite `_forward_output` in `plugins/mill/scripts/_implementer_common.py` to:
  1. Change the signature to `def _forward_output(output: str, project_root: Path, *, start_sha: str | None = None, snapshot_path: Path | None = None) -> int:`. Both new kwargs default to `None` so callers that do not yet pass them retain today's behaviour.
  2. Add `import _cleanliness` at the top of the file alongside the existing `import _subprocess_util`.
  3. The first regex-find-and-emit block (current lines 14–28) stays unchanged: when a JSON object containing `"status"` is found, augment with `commit_sha` and print.
  4. When the regex finds nothing, BEFORE emitting the existing `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}` sentinel, attempt the inference path:
     - Guard: if `start_sha is None` or `snapshot_path is None` or `not snapshot_path.exists()` → skip inference; fall through to the stuck-logic sentinel.
     - Compute `new_dirt = _cleanliness.compute_new_dirt(project_root, snapshot_path)`. If `new_dirt != []` → skip inference (worktree has new dirt the implementer left behind); fall through.
     - Compute current HEAD via `_subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)`. If the call fails (returncode != 0) or the stdout-stripped value equals `start_sha` (no new commits) → skip inference; fall through.
     - All checks passed: build the inferred payload `{"status": "success", "commit_sha": "<head>", "session_id": "unknown", "inferred": True}` (Python dict; json.dumps emits `true`), print it, return 0.
  5. The final `print(json.dumps({"status": "stuck", ...}))` line stays as the catch-all fall-through, reached only when inference is skipped or fails any of its checks.
  Update the module docstring to reflect the new signature: the existing one-liner `"""Shared helpers for millpy-implement.py and millpy-implement-holistic.py."""` is fine; do NOT add a long docstring to `_forward_output` (the function is private and the call sites document context).
- **Commit:** `feat(_implementer_common): infer success when JSON missing but worktree clean`

### Card 12: Thread `start_sha` + `snapshot_path` through `millpy-implement.py`

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-implement.py`:
  1. **Initial-dispatch path (line 186):** the call `return _forward_output(output, project_root)` already has `start_sha` and `snapshot_path` in scope (lines 128 and 130). Change to `return _forward_output(output, project_root, start_sha=start_sha, snapshot_path=snapshot_path)`.
  2. **Fix-cycle resume path (line 259):** the call `return _forward_output(output, project_root)` does NOT yet have `start_sha` or `snapshot_path` in scope. Immediately before the `return` line, read both from existing batch state:
     ```python
     batch_state_for_forward = next((b for b in _status.read_batches(status_path) if b["name"] == args.batch_name), None)
     start_sha_for_forward = batch_state_for_forward.get("start_sha") if batch_state_for_forward else None
     snapshot_path_for_forward = project_root / "task" / f".cleanliness-snapshot-{args.batch_name}.txt"
     ```
     Then change the return to `return _forward_output(output, project_root, start_sha=start_sha_for_forward, snapshot_path=snapshot_path_for_forward)`.
     Variable names use the `_for_forward` suffix to avoid shadowing the existing `batch_state` (line 198) and `session_id` (line 199) locals.
  3. `millpy-implement-holistic.py` is OUT of scope for this card — it currently calls `_forward_output(output, project_root)` too (verify by grep before committing this card). The fix for the holistic implementer would require parallel plumbing of `start_sha`/`snapshot_path` from a different code path; #243's repro is the per-batch implementer and that is what ships here. Leave `millpy-implement-holistic.py` unchanged; add no fallback for it in this task.
- **Commit:** `feat(millpy-implement): pass start_sha + snapshot_path to _forward_output`

### Card 13: Tests for `_forward_output` fallback paths

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-implementer-common.py` with four test functions, each invoked from `main()` and printing one `PASS:` line on success. Use `tempfile.TemporaryDirectory` + `subprocess.run(["git", "init", "-q", tmp])` for each fixture, then `git config user.email/user.name` + `git commit --allow-empty -m initial` to produce a base commit (the same pattern used by `test-review-common.py`). For each case, call `_capture_stdout` on `_forward_output(...)` and assert the captured JSON shape:

  Case 1 — **inferred success**: seed worktree → `capture_snapshot` → make a new commit → call `_forward_output("garbage with no json", project_root, start_sha=<base_sha>, snapshot_path=<path>)`. Assert stdout contains `"status": "success"`, `"inferred": true`, and the new HEAD sha.

  Case 2 — **no new commits → no inference**: seed worktree → `capture_snapshot` → DO NOT make a new commit → call `_forward_output(...)` same way. Assert stdout contains `"status": "stuck"` and `"stuck_type": "logic"` — inference skipped because HEAD == start_sha.

  Case 3 — **dirty worktree → no inference**: seed worktree (the base commit MUST include a tracked file such as `README.md` — extend the fixture commit to `(project_root / "README.md").write_text("seed", encoding="utf-8")` then `git add README.md && git commit -m initial`) → `capture_snapshot` → make a new commit → MODIFY the already-tracked `README.md` without committing (`(project_root / "README.md").write_text("dirty", encoding="utf-8")`) → call `_forward_output(...)`. The modified-but-uncommitted tracked file appears as ` M README.md` in `git status --porcelain --untracked-files=no`, making `compute_new_dirt` return a non-empty list. Assert stuck-logic JSON — inference skipped. Note: untracked files (e.g. `dirty.txt` created from scratch) would be invisible to `--untracked-files=no` and would NOT trigger the dirty-worktree branch, defeating the test's intent.

  Case 4 — **missing snapshot → no inference**: seed worktree → SKIP `capture_snapshot` → make a new commit → call `_forward_output(..., snapshot_path=<nonexistent path>)`. Assert stuck-logic JSON — inference skipped because `snapshot_path.exists()` is False.

  Helper `_capture_stdout(fn)` uses `contextlib.redirect_stdout(io.StringIO())` and returns `(returncode, captured_text)`. Mirror the top-of-file import pattern from `test-status.py`:

  ```python
  HUB = Path(__file__).resolve().parent.parent.parent.parent
  sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))
  from _implementer_common import _forward_output  # noqa: E402
  import _cleanliness  # noqa: E402
  ```

  The `main()` function returns `0` on success, `1` on first failure (consistent with other unit tests). Add `if __name__ == "__main__": sys.exit(main())` at the bottom.
- **Commit:** `test(_implementer_common): cover _forward_output inference paths`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-implementer-common.py` runs the
four new test cases. Each case sets up an isolated git worktree, exercises
one branch of the `_forward_output` decision logic, and asserts the emitted
JSON shape. The full suite still runs via `python
plugins/mill/unit_tests/run-all.py` — no behavioural change there because the
existing tests do not touch `_implementer_common`.
