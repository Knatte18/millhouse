All 5 cards committed, matching all 5 `Commit:` messages declared in the batch file. 5 of 5 cards committed — all complete, verified honestly via the range-start commit log match above.

{"status":"success","commit_sha":"f24506053ba6ef01bd9d14d654f80b812bea224d","session_id":"ced3206b-df9c-4411-aa4b-c3adf9f6824a","cards_done":[1,2,3,4,5]}

Summary of files touched (all absolute paths under `/home/knatte/Code/millhouse/wts/review-manifest-listings-full-path-clutter`):
- `plugins/mill/scripts/_review_common.py` — added `DisplayRoots` frozen dataclass and `build_path_roots_section()`; added `roots: DisplayRoots | None = None` keyword-only parameter to `build_manifest_section`, `bulk_files`, `bulk_files_with_diff`, and `build_reattached_section`, all defaulting to `None` for byte-identical back-compat.
- `plugins/mill/unit_tests/test-review-common.py` — added tests for `DisplayRoots.render`, `build_path_roots_section`, the `roots=` keyword on all four helpers (both with/without paths), and a regression pin for `build_deletes_section` proving it already emits relative tokens verbatim.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-common-guard.py` passes (2/2 unit test files). Working tree is clean of tracked in-scope modifications.

{"status":"success","commit_sha":"f24506053ba6ef01bd9d14d654f80b812bea224d","session_id":"ced3206b-df9c-4411-aa4b-c3adf9f6824a","cards_done":[1,2,3,4,5]}
