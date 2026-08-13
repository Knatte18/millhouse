Task: implement batch 4 (`integration-tests`) per the brief — Cards 9–14 of `_mill/plan/04-integration-tests.md`.

{"status":"success","commit_sha":"3c058bbe84b0d849f8a6369ed4d0641831edc729","session_id":"f0b623b5-70d9-446a-87f8-aa6fa64c63ed","cards_done":[9,10,11,12,13,14]}

6 of 6 cards committed (one combined commit, since all six necessarily touch the same file `plugins/mill/integration_tests/test-merge.py`, per the brief's combined-commit allowance), `verify:` passed (39 PASS lines, exit 0), tree clean:
- `3c058bbe` — test(mill): integration coverage for #817 legacy task/status.md layout fallback
  - Card 9 (#824 parent fast-forward success + divergence halt)
  - Card 10 (#824 rollback resets to origin, not checkpoint)
  - Card 11 (#817 torn-down/never-pushed/no-status-file dead-parent detection)
  - Card 12 (#817 two chained dead-parent hops)
  - Card 13 (#817 10-hop cycle cap)
  - Card 14 (#817 legacy `task/status.md` layout fallback)

{"status":"success","commit_sha":"3c058bbe84b0d849f8a6369ed4d0641831edc729","session_id":"f0b623b5-70d9-446a-87f8-aa6fa64c63ed","cards_done":[9,10,11,12,13,14]}