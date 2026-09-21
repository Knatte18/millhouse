# Batch: pr-state-and-cache-freshness

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: pr-state-and-cache-freshness
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-pr-state.py test-cleanup.py
depends-on: []
```

## Batch Scope

Fixes #1105 (`_pr_state.resolve_pr_state` omits `--repo` and silently coerces a genuine `gh` failure
into the same `state: "none"` used for "no PR exists") and #1077 (a self-hosting plugin-cache-freshness
gap at `mill-merge` — the underlying pathspec bug is already fixed in this dev tree via commit
`ace7dbbf`; what remains is documenting the cache-refresh recovery). Grouped in one batch because
cards 5 and 6 both edit `plugins/mill/skills/mill-merge/SKILL.md` (different sections), and keeping
both in one batch avoids a cross-batch `parallel-modifies-overlap` conflict on that file.

## Cards

### Card 3: `_pr_state.resolve_pr_state` — `--repo` flag and `error` field (#1105)

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_pr_state.py`
  - `plugins/mill/unit_tests/test-pr-state.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_pr_state.py`:
  1. Add `import _gh_issues` at module scope (alongside the existing `import _subprocess_util`).
  2. In `resolve_pr_state`, before building the `gh pr list` argv, resolve
     `repo = _gh_issues.detect_repo(Path(cwd))` (wrap `cwd` in `Path(...)` since `detect_repo` expects
     a `Path | None`, while `resolve_pr_state`'s own `cwd` parameter accepts `Path | str`). When
     `repo` is a non-empty string, insert `"--repo", repo` into the argv list passed to
     `_subprocess_util.run` (immediately after `"gh", "pr", "list"`, before `"--head"`, order does not
     matter functionally but keep it readable). When `repo` is `""`, omit `--repo` entirely — leave
     `gh`'s own cwd-based auto-detection as the fallback, unchanged from today.
  3. Add an `"error"` key to both the `_none_result` sentinel dict and every dict this function
     returns, defaulting to `None`. Populate it with a descriptive string ONLY on the genuine-failure
     branches: the `except Exception` branch around the `_subprocess_util.run` call (use
     `str(exc)`), and the `result.returncode != 0` branch (use `result.stderr.strip()` or, if empty,
     a fallback string noting the non-zero exit with no stderr). Every other `_none_result`-returning
     branch (empty stdout, JSON parse failure, empty parsed list, no PR object matching a known
     state) is a genuine "no PR" outcome, not a `gh` failure — `error` stays `None` for those. Update
     the function's docstring `Returns:` section to document the new `"error"` key.
- **Commit:** `fix(pr-state): resolve --repo explicitly and distinguish gh failure from no-PR (#1105)`

### Card 4: `millpy-cleanup.py` PR-reap logs the `error` field (#1105)

- **Context:**
  - `plugins/mill/scripts/_pr_state.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `millpy-cleanup.py`'s `_apply_pr_reap_record`, the `state == "none"` branch currently prints
  `f"[cleanup] PR-reap {record.slug}: no PR / gh unavailable"` to stderr and returns. Read the new
  `pr.get("error")` (from Card 3's `_pr_state.resolve_pr_state` return dict) and, when it is not
  `None`, append it to the same print call, e.g. `f"[cleanup] PR-reap {record.slug}: no PR / gh
  unavailable ({pr['error']})"`. When `error` is `None` (a genuine no-PR result), keep the message
  exactly as it is today — no behavior change beyond the added diagnostic text. Do not change this
  branch's control flow (it still returns `wiki_relative_paths` unchanged, still relies on the next
  cleanup sweep to retry) — this sweeper's own retry-on-next-pass behavior already tolerates a
  transient `gh` failure; only the log message gains detail.
- **Commit:** `fix(cleanup): surface gh error detail in PR-reap no-PR log line (#1105)`

### Card 5: mill-merge PR-state gate distinguishes a `gh` failure from a real "no PR" (#1105)

- **Context:**
  - `plugins/mill/scripts/_pr_state.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `mill-merge/SKILL.md`'s `### PR-state gate` section, the `none` route currently reads:
  ```
- **`none`** -- silent fallback to phase-based behavior (no new output):
  - If `phase: done`: continue to Step 1 (today's direct squash).
  - If `phase: pr-pending`: keep today's halt -- "status.md says pr-pending but no PR on this branch;
    inspect manually."
  ```
  Add a check before this phase-based fallback: parse the `error` field from `PR_STATE_JSON` (Card
  3 adds this key to `_pr_state.resolve_pr_state`'s return dict, which this section's existing
  `PR_STATE_JSON` bash block already captures via the Python one-liner calling `resolve_pr_state`).
  When `error` is non-null, halt immediately instead of falling into the phase-based `none` behavior,
  with a message naming the branch and the captured error text and instructing the operator to
  investigate the `gh` failure (auth, repo detection, network) before re-running `/mill-merge` — do
  not route this into "status.md says pr-pending but no PR on this branch; inspect manually", since
  that message is misleading when the real cause is a `gh` call failure, not an actually-missing PR.
  Only when `error` is null does the existing phase-based `none` fallback (the two bullets above)
  apply, unchanged.
- **Commit:** `docs(mill-merge): distinguish a gh failure from a genuine no-PR state in the PR-state gate (#1105)`

### Card 6: self-hosting plugin-cache-freshness note (#1077)

- **Context:**
  - `./update-plugins.sh`
- **Edits:**
  - `CLAUDE.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  The underlying bug this issue reported (`git grep` pathspec using `:!<task_dir>` instead of
  `:(exclude)<task_dir>`) is already fixed in this dev tree (commit `ace7dbbf`) — both
  `mill-merge/SKILL.md`'s and `mill-finalize/SKILL.md`'s citation-scan blocks already use
  `:(exclude)`. What remains is documenting the cache-refresh recovery for the self-hosting gap that
  let the bug recur live even after the fix landed on `main`:
  1. In `CLAUDE.md`'s `## Hard constraints` section, add a new bullet immediately after the existing
     `**Task-worktree path for source verification, not CLAUDE_PLUGIN_ROOT.**` bullet, stating: a fix
     merged to `main` under `plugins/mill/**` during the current session does not take effect in any
     *dispatched* mill-go/mill-merge/mill-plan invocation until the plugin cache is refreshed —
     those dispatches read `${CLAUDE_PLUGIN_ROOT}`, a frozen copy, not the dev tree — and that
     `./update-plugins.sh`, run from the hub root, is the existing mechanism to force that refresh.
  2. In `plugins/mill/skills/mill-merge/SKILL.md`'s `### 4. Cleanup commit` section, immediately
     after the `**Citation scan (non-blocking, #930).**` paragraph's introductory sentence (before
     the two `git ... grep` bash blocks), add a one-line pointer back to the new CLAUDE.md bullet, so
     a future stale-cache symptom at this exact call site is one hop from the fix instead of
     requiring independent rediscovery (this exact citation-scan pathspec was where #1077's
     incident occurred).
- **Commit:** `docs: document plugin-cache-freshness recovery for self-hosting sessions (#1077)`

## Batch Tests

- Card 3: extend `plugins/mill/unit_tests/test-pr-state.py` with: (a) a test mocking
  `_pr_state._gh_issues.detect_repo` to return `"owner/repo"` and asserting the `argv` passed to the
  mocked `_subprocess_util.run` call (via `mock.call_args`) contains `"--repo"` immediately followed
  by `"owner/repo"`; (b) a test with `detect_repo` returning `""` asserting `"--repo"` is absent from
  the argv; (c) a test asserting `test_nonzero_returncode`'s existing scenario now also has
  `result["error"] == "gh error"` (the stderr the mock already supplies); (d) a test asserting a
  successful empty-array result has `result["error"] is None`. Also **update** the existing
  `test_empty_array`'s full-dict-equality assertion (`assert result == {"state": "none", "number":
  None, "url": None, "merge_commit": None}, ...`) to include `"error": None` in the expected dict —
  this is a genuine, intentional return-contract change per Card 3's Requirements, not a regression.
- Card 4: extend `plugins/mill/unit_tests/test-cleanup.py`'s existing "apply_plan PR-reap: gh pr list
  failed" case (`stderr_text_18d` assertions, around the `_mock_run_18d` fixture) with an additional
  assertion that the mocked `gh` failure's stderr text (`"gh: command not found"`) now also appears
  in `stderr_text_18d`, proving `error` propagated from `_pr_state.resolve_pr_state` through
  `_apply_pr_reap_record`'s log line.
- Cards 5 and 6 are documentation-only (`SKILL.md`/`CLAUDE.md` prose) with no runnable surface —
  verified by re-reading the edited sections for accuracy against Card 3's actual return-dict shape
  and commit `ace7dbbf`'s actual diff, not by an automated test.
