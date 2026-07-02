{"status":"success","commit_sha":"fe44a20a856895a4c9e94e37171675791f01c204","session_id":"5cfc92b9-98a8-40e7-a0f2-bfe7ce4eae83"}

Both cards for batch `03-skills-index-fail-loud` are implemented, committed, pushed, and verified:

- `plugins/mill/scripts/millpy-skills-index.py` — Card 5: added `FrontmatterParseError`, threaded `path` through `_extract_frontmatter`, and `_scan()` now reports YAML parse failures distinctly from missing-frontmatter (commit `6d004d16`).
- `plugins/mill/unit_tests/test-skills-index.py` — Card 6: new test covering valid frontmatter, no-frontmatter-block, and the #589 unquoted-colon repro (commit `fe44a20a`).

`verify:` (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skills-index.py`) passes all 3 tests. Working tree is clean (no uncommitted tracked changes).

{"status":"success","commit_sha":"fe44a20a856895a4c9e94e37171675791f01c204","session_id":"5cfc92b9-98a8-40e7-a0f2-bfe7ce4eae83"}