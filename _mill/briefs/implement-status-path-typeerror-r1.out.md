No tracked modifications remain uncommitted. Both cards are committed, verify passed, and the working tree is clean.

Summary of changes:
- `C:\Code\millhouse\wts\mill-script-fixes\plugins\mill\scripts\_status.py` — added `_require_path` guard helper and invoked it as the first statement in all 17 public `status_path`-taking functions.
- `C:\Code\millhouse\wts\mill-script-fixes\plugins\mill\unit_tests\test-status.py` — added regression tests asserting `TypeError` (with function name + `"pathlib.Path"` in the message) for `append_phase`, `update_field`, and `set_blocked` when passed a plain `str`.

Note: `ruff check` on `test-status.py` reports a pre-existing `F811` (duplicate `read` in the import list) that predates this batch — confirmed present in `git show main:plugins/mill/unit_tests/test-status.py`. Left unchanged since it is out of scope for this batch and not something these edits introduced.

{"status":"success","commit_sha":"f2b09109","session_id":"1b335ea0-ae9a-44eb-910e-50efca3e292e"}
