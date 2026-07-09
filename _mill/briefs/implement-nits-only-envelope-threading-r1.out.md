All work is complete. Summary of the batch:

**Batch:** `01-nits-only-envelope-threading` (4 cards) — all committed and pushed to `hanf/mill-go-nit-gate-and-dispatch-gaps`.

Files modified:
- `C:\Code\millhouse\wts\mill-go-nit-gate-and-dispatch-gaps\plugins\mill\scripts\_implementer_common.py` — added `nits_only: bool = False` param to `emit_prepare`, mirroring the `start_sha` omit-when-absent envelope pattern; documented in the docstring.
- `C:\Code\millhouse\wts\mill-go-nit-gate-and-dispatch-gaps\plugins\mill\unit_tests\test-implementer-common.py` — added Case 64 covering both the `nits_only=True` and default-omitted paths.
- `C:\Code\millhouse\wts\mill-go-nit-gate-and-dispatch-gaps\plugins\mill\scripts\millpy-fix.py` — wired `nits_only=args.nits_only` into the `--stage prepare` call to `emit_prepare` (the `--stage finalize` branch already had this correctly).
- `C:\Code\millhouse\wts\mill-go-nit-gate-and-dispatch-gaps\plugins\mill\unit_tests\test-millpy-fix.py` — added `test_stage_prepare_batch_scope_with_nits_only` and `test_stage_prepare_batch_scope_without_nits_only_omits_field`.

Commits (in order): `515ac506`, `67167f17`, `76b969ff`, `444aca5b`.

Verify command (`run-all.py --only test-implementer-common.py test-millpy-fix.py`) passed: 1 unittest suite (32 tests) + 64 manual cases in the implementer-common suite, all green. Ruff check clean on all touched files. `git status --porcelain --untracked-files=no` confirmed no dirty tracked files before reporting.

{"status":"success","commit_sha":"444aca5b24542a5123eb522b7af58dd1e723db5","session_id":"d03eb0c2-7b9a-4bc1-91a7-b6c15887d505"}
