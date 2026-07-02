Clean working tree, both cards committed, verify passes.

{"status":"success","commit_sha":"48f150c2","session_id":"ef10ee26-7791-4bf3-9df0-6c67f9a7d2b7"}

Summary of work:
- `C:\Code\millhouse\wts\agent-mode-gaps\plugins\mill\scripts\_status.py` — added `get_module_verify_baseline`, `set_module_verify_baseline`, `clear_module_verify_baseline` (inserted after `set_blocked`, before `append_phase`), plus updated the module's Public API docstring list. Committed as `c853d502`.
- `C:\Code\millhouse\wts\agent-mode-gaps\plugins\mill\unit_tests\test-status.py` — added 6 new test cases covering fresh-file `None`, insert, rewrite-in-place (exactly one row), `ValueError` on bad value, clear-after-set, and no-op clear. Committed as `48f150c2`.

Note: ruff flagged a pre-existing `F811` duplicate `read` import in `test-status.py` (confirmed present on `main` before this batch's changes, unrelated to my edits) — left untouched since fixing it is out of this batch's scope.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py` passes (all 57 assertions green). Working tree is clean; both commits pushed to `hanf/agent-mode-gaps`.

{"status":"success","commit_sha":"48f150c2","session_id":"ef10ee26-7791-4bf3-9df0-6c67f9a7d2b7"}