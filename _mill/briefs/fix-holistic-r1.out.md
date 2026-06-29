Applied Fix:
- Finding: [NIT] Dead branch in Rule 3 of clean_ephemeral_scope_violations
- Action: Removed the unreachable `basename.endswith(".test.exe")` check from line 262 of `plugins/mill/scripts/_cleanliness.py`
- Rationale: Rule 1's `basename.endswith(".exe")` already catches all `.exe`-suffixed filenames (including `.test.exe`), making this branch dead code.

Verification:
- Batch 01 (bare-tier-aliases): PASS — 45/45 tests passed
- Batch 02 (go-artifact-allowlist): PASS — all tests passed (including regression test for `.test.exe`)
- Batch 03 (idempotent-checkpoint): verify: null (prose-only, skipped)

Commit: 95d9585d — "Remove dead branch for .test.exe suffix in clean_ephemeral_scope_violations". Pushed to origin/hanf/mill-scope-and-infra-gaps.

{"status":"success","commit_sha":"95d9585d762f64abfcec6d4f961e106176e96c16","session_id":"e2f00674-14ba-4039-be82-034ad29e28d9"}
