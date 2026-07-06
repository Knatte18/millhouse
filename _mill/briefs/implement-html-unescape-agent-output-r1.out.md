No tracked modifications remain dirty. All 4 cards are committed and verify passes.

{"status":"success","commit_sha":"f62a373ed5754ecd6f2dca8e0af33e9ce098a9bd","session_id":"15c287e6-809b-47f7-bf78-267f8a14eadb"}

Summary of work:

- `plugins/mill/scripts/_implementer_common.py` — `finalize_from_output` now wraps its `read_text` with `html.unescape(...)` (added `import html`).
- `plugins/mill/unit_tests/test-implementer-common.py` — added Case 63 verifying the unescape via a mocked `_forward_output`.
- `plugins/mill/scripts/millpy-review-code.py` — `--stage finalize`'s `raw_text` read now unescaped (added `import html`).
- `plugins/mill/scripts/millpy-review-discussion.py` — same fix.
- `plugins/mill/scripts/millpy-review-plan.py` — same fix.
- `plugins/mill/unit_tests/test-review-finalize.py` — added `test_review_code_finalize_unescapes_html_entities`, `test_review_discussion_finalize_unescapes_html_entities`, `test_review_plan_finalize_unescapes_html_entities`, each asserting via the mocked `finalize`'s `call_args.args[2]` outside any exception-swallowing block (per the brief's guardrail against the `except Exception: return True` pattern), and wired all three into `main()`.

Commits (all pushed to `hanf/mill-go-dispatch-and-skill-gaps`):
- `f0f5e278` fix(implementer-common): unescape HTML entities in finalize_from_output agent-output read
- `84ca3e1c` fix(review-code): unescape HTML entities in finalize agent-output read
- `4a49b12f` fix(review-discussion): unescape HTML entities in finalize agent-output read
- `f62a373e` fix(review-plan): unescape HTML entities in finalize agent-output read

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-review-finalize.py` passes (all cases green, including new Case 63 and the three new `_unescapes_html_entities` tests).

{"status":"success","commit_sha":"f62a373ed5754ecd6f2dca8e0af33e9ce098a9bd","session_id":"15c287e6-809b-47f7-bf78-267f8a14eadb"}
