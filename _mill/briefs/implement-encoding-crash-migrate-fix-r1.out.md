No tracked modifications remain. Both cards are committed and pushed, and verify passes.

{"status":"success","commit_sha":"f09993c9","session_id":"d7a5fe03-4cda-4835-b391-3c9dac4ce4c6"}

Summary of work:
- `plugins/mill/scripts/millpy-wiki-migrate.py` — added `_ensure_utf8_stdout()` (called first in `main()`) to reconfigure `sys.stdout` to UTF-8/replace before `_print_task_brief()` prints externally-authored, potentially non-ASCII wiki content; also removed a pre-existing unused `import re` flagged by ruff on this same file.
- `plugins/mill/unit_tests/test-wiki-migrate-print.py` (new) — loads the hyphenated script via `importlib.util.spec_from_file_location`, simulates a cp1252 stdout, and asserts the guard prevents `UnicodeEncodeError` on printing `"test: ->"`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-migrate-print.py` passes (1 passed, 0 failed). Both cards committed and pushed as `ea0ed973` and `f09993c9`; working tree is clean of tracked modifications.