Working tree is clean. All three cards implemented, committed, and verify is green.

Files changed:
- `C:\Code\millhouse\wts\mill-scope-and-infra-gaps\plugins\mill\templates\mill-agents.yaml` — added `opus`, `opus_bulk` before `opushigh`, and `sonnet`, `sonnet_bulk` before `sonnethigh`, each at `effort: medium` with a comment.
- `C:\Code\millhouse\wts\mill-scope-and-infra-gaps\plugins\mill\scripts\_reviewers.py` — enriched the `resolve()` unknown-name error to append `. Available: <sorted names>`.
- `C:\Code\millhouse\wts\mill-scope-and-infra-gaps\plugins\mill\unit_tests\test-reviewers.py` — added `_load_real_template_registry()` helper and three test functions (`test_bare_aliases_resolve_with_correct_spec`, `test_validate_role_refs_accepts_bare_aliases`, `test_resolve_unknown_name_lists_available`), registered in `main()`. Also fixed two pre-existing unused imports caught by ruff.

{"status":"success","commit_sha":"2d77a036896e581bce24888b8ab4fc5017195df6","session_id":"7b987173-d78b-46f3-9879-b699b3bd742d"}
