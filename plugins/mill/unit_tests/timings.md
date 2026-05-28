# Unit-test timings — tracking #388

Each column = one snapshot. Each row = one test file. Times are wall-clock seconds (Windows, single-threaded `uv run` invocation).

Columns left-to-right: oldest -> newest.

| File | Baseline (from #388) | After SKIP_PUSH (2026-05-27 v1) | After in-process + SKIP_GIT (2026-05-27 v2) | Speedup vs baseline |
|---|---:|---:|---:|---:|
| test-fold.py | 104 | 23.6 | **1.0** | **104x** |
| test-marker.py | 92 | 39.4 | **8.6** | **10.7x** |
| test-millpy-terminal.py | 34 | 2.8 | 3.4 | 10x |
| test-millpy-vscode.py | 34 | 11.5 | 11.3 | 3x |
| test-bg-launcher.py | 33 | 7.8 | 3.8 | **8.7x** |
| test-claude-sub.py | 15 | 14.6 | 14.7 | 1x (LLM-stub waits) |
| test-spawn-core.py | n/a | n/a | 12.3 | (uses SKIP_PUSH; needs commits) |
| test-implementer-common.py | 11 | 5.0 | - |  |
| test-pygit2-util.py | 10 | 6.1 | - |  |
| test-paths.py | 8 | 4.1 | - |  |

Baseline source: issue #388 (created 2026-05-27 12:36).

## What's in each column

- **Baseline** — from the issue body. Pre-fix, V3-daemon-per-test.
- **After SKIP_PUSH (v1)** — server respects `WIKI_DAEMON_SKIP_PUSH=1` (commits run, push is skipped). Modest win; still pays daemon-subprocess spawn cost (~1.5 s) per test.
- **After in-process + SKIP_GIT (v2)** — three new test-mode env vars working together:
  - `WIKI_DAEMON_INPROCESS=1` — `wiki._client._dispatch` routes ops directly to an in-process `WikiServer.handle_request` call. No subprocess, no socket, no token. Saves ~1.5 s of Python interpreter startup per test that hits the daemon.
  - `WIKI_DAEMON_SKIP_GIT=1` — server skips pull/commit/push entirely. Renders files and updates TinyDB; no git invocations. Saves ~3 × 150 ms per op on Windows. Most tests don't assert on git state.
  - `WIKI_DAEMON_SKIP_PUSH=1` — fallback when a test does assert on commit log (e.g. test-spawn-core). Commits still happen; only the network push is skipped.
  - Test fixture helpers (`_test_helpers.init_wiki_repo`, `test-fold._setup_tempfile_wiki`) also detect `SKIP_GIT` and skip their own dead-weight `git init --bare` + push setup.

  All three default to off in production. `_test_helpers.py` enables `INPROCESS + SKIP_GIT` by default; individual tests that need real commits opt out by clearing `SKIP_GIT` and setting `SKIP_PUSH` before importing helpers.

## Where the time goes (after-fix, test-fold.py)

- 1 test ~= 1 daemon spawn (~3 s) + N daemon ops (~0.2-0.5 s each, no push).
- Floor is the daemon spawn — each test creates a fresh tempdir = fresh wiki_path = fresh daemon process.
- To break that floor: share wiki_path across tests in a file (module-scoped daemon). Bigger change; not done here.

## Tests not yet remeasured

The 9 above are the ones #388 listed. The full suite has ~70 more `test-*.py` files but they were sub-baseline in the issue. If we want a complete picture, run them in batches and append rows.

## Observations after batch 1

- **Biggest absolute wins:** test-fold (-80 s), test-marker (-53 s), test-millpy-terminal (-31 s).
- **test-millpy-terminal at 2.8 s** — the SKIP_PUSH path is essentially free here; the previous 34 s was almost all push/pull overhead inside daemons that the test mocked away anyway.
- **test-claude-sub barely moved (15 -> 14.6 s)** — daemon is not the bottleneck. LLM-stub idle-wait loops are; would need their own optimisation.
- **test-fold at 23.6 s is now spawn-bound** — 16 fresh tempdirs = 16 daemon spawns × ~1.5 s each. To break that floor, share wiki_path across tests in a file (module-scoped daemon fixture).
- **test-marker still at 39 s** — each test creates a worktree + wiki + seeds via daemon. Same spawn-per-test floor.

## Next levers (not yet pulled)

1. **Module-scoped daemon fixture** — one wiki_path per test file, reset state between tests. Expected: test-fold ~5 s, test-marker ~8 s.
2. **Drop bare-origin setup in tests** — with SKIP_PUSH there's no push, so the `bare.git` repo + `git push --set-upstream` calls in `_setup_tempfile_wiki` are dead weight. Maybe 0.5-1 s/test back.
3. **Reduce daemon-spawn poll cadence** (0.1 s -> 0.02 s in `_ensure_daemon`) — saves 50-100 ms per spawn. Small absolute, but applies to every test.
4. **Parallelise `run-all.py`** — independent of per-file fixes; could halve wall time on multi-core boxes.

---

## Final state (v3, 2026-05-28 — full suite measurement)

```
Full suite (run-all.py --jobs 4):  1m 04 s   (was: 2m 30s baseline)
77 -> 70 test files (-7 via consolidation)
```

Top 10 slowest (still in suite):

| File | Wall time |
|---|---:|
| test-review-plan-flow.py | 32.0s |
| test-review-code-flow.py | 29.2s |
| test-spawn-core.py | 23.1s |
| test-review-common.py | 16.1s |
| test-claude-sub.py | 14.6s |
| test-pygit2-util.py | 12.9s |
| test-subprocess-util.py | 10.5s |
| test-implementer-common.py | 9.1s |
| test-wiki-noop-commit.py | 8.9s |
| test-review-discussion-flow.py | 8.6s |

### Consolidations performed

| Group | Before | After | Delta |
|---|---:|---:|---:|
| Guards (no-rmtree + no-arrow + no-cwd) | 3 files | 1 file (`test-guards.py`) | -2 |
| Paths (test-paths + status + resolve-task-path) | 3 files | 1 file (`test-paths.py`) | -2 |
| VSCode helpers (vscode + vscode-processes) | 2 files | 1 file (`test-vscode.py`) | -1 |
| Reviewers (reviewers + reviewer-single) | 2 files | 1 file (`test-reviewers.py`) | -1 |
| LLM Claude (llm-claude + llm-claude-argv) | 2 files | 1 file (`test-llm-claude.py`) | -1 |
| Inplace (inplace + mill-merge-inplace) | 2 files | 1 file (`test-inplace.py`) | -1 |
| **Total** | **14** | **6** | **-8** |

### Architectural changes shipped

1. `WIKI_DAEMON_INPROCESS=1` — auto-register in-process `WikiServer`; bypass subprocess spawn for tests.
2. `WIKI_DAEMON_SKIP_GIT=1` — server writes `tasks.json` + Home.md only; no git ops at all.
3. `WIKI_DAEMON_SKIP_PUSH=1` — server commits locally but skips push (for tests asserting on commit log).
4. `_test_helpers.init_minimal_git_repo` — pygit2 implementation, 60ms vs 600ms for subprocess `git init+commit`.
5. `run-all.py --only test-X.py test-Y.py` — scoped subsets so per-batch `verify:` can avoid the full suite.
6. mill-plan SKILL.md + plan-batch.md template now instruct planners to write per-batch scoped verify (`--only`) rather than default `run-all.py`.

### Skipped (would not help or wrong target)

- Merging `test-render.py` (generic template renderer) and `test-wiki-render.py` (wiki-specific): different modules.
- Merging `test-bg-launcher.py` / `test-bg-liveness.py` / `test-millpy-bg.py`: testing different modules (`_bg` helper vs `millpy-bg` script).
- Consolidating `test-spawn-core.py`: uses `WIKI_DAEMON_SKIP_PUSH` (commits required) — git is genuinely needed.

### Next levers if more speed is needed

- Move `test-review-*` infrastructure to in-process / mock reviewer dispatch (currently the slowest cluster).
- Module-scoped wiki fixture for tests that share wiki shape (test-marker, test-spawn-core).
- pygit2 rewrite of remaining subprocess-git callsites in tests that need real git (test-spawn-core, test-wiki-noop-commit).
