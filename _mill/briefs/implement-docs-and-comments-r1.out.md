All three cards are done. Cards 14 and 15 are committed (2 of 2 card commits). Card 16 is Commit: none and passed its checks. Verify (test-worktree, test-plan-dag, test-guards, test-done-gate) passed.

- Card 14: removed the speculative baseline launch bullet and the whole `### 0.5. Baseline pre-flight` section from plugins/mill/skills/mill-go-base/SKILL.md. Section 0.55 now points to "1. Implement". A grep of mill-go-base for the removed-step terms finds nothing.
- Card 15: reworded comments and docstrings in _long_path.py, _worktree.py, _plan_dag.py, test-worktree.py and test-done-gate.py. No code changes.
- Card 16: the final grep over plugins and mill-config.yaml found only allowed hits. These are the historical comments in test-cleanup.py and BENCHMARK.md, plus the rejection assertions in the earlier batches' tests. Compiled and virtualenv files (.pyc, .ruff_cache, .venv) also matched; they are not source, so I ignored them. _done_gate.py still imports _extract_failure_signatures and calls it without returncode.
- No tracked changes remain uncommitted.

{"status":"success","commit_sha":"0dfc0b5a15d550128f32d23bacfe5bffaee5247a","session_id":"8a2ff87e-14be-469f-9570-aca409022833","cards_done":[14,15,16]}
