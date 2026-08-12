All 4 declared cards (30, 31, 32, 33) are committed and match the expected `Commit:` messages exactly. 4 of 4 cards committed — all complete.

{"status":"success","commit_sha":"80b840ecb28484fb26f38d3ede6528f1b9da5244","session_id":"9d0d52c8-30c9-4ef5-8a13-9b7150fbac91","cards_done":[30,31,32,33]}

Summary of work (file paths absolute):
- Created `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/scripts/millpy-review-summary.py` — the new CLI (`parse_review_filename`, `build_rows`, `render_table`, `format_duration`, `main`).
- Created `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/unit_tests/test-review-summary.py` — 13 test cases covering filename parsing, row building (mixed formats, malformed yaml, no-fence, revise-N/ rglob, fixer-report exclusion), sort order, duration formatting, table rendering, and raw-number JSON shape.
- Created `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/skills/mill-review-summary/SKILL.md` — thin wrapper skill (had to quote its `description:` frontmatter value, fixed in the card-33 commit, since the unquoted colon broke YAML parsing for `millpy-skills-index.py`).
- Edited `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/plugins/mill/templates/review-output.schema.md` — added `duration_s`/`tool_calls`/`cost_usd` rows to the metadata table and sample yaml block, plus explanatory prose.
- Regenerated `/home/hanf/Code/millhouse/wts/reviewer-cost-summary/SKILLS.md` via `millpy-skills-index.py`; the diff includes the new `mill-review-summary` row plus one line of pre-existing unregenerated drift in the `mill-go2` row (confirmed via `git log main..HEAD` that no commit in this task touched that skill file — genuine prior drift, not something I introduced).

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-summary.py` passes. Working tree is clean (no uncommitted tracked changes).
