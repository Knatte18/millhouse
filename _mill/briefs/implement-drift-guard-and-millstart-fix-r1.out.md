{"status":"success","commit_sha":"61104b445e68fb2c319bc54e8a6dbe1cca4978bf","session_id":"83e09d37-37b8-4cf5-87ea-e58876e46a4b"}

All three cards are complete and verify passes. Here is a summary of the files changed:

`plugins/mill/skills/mill-start/SKILL.md` — Card 1: Phase: Select bash snippet now emits `STATUS:` on line 1 followed by `--- BRIEF ---` / `--- BODY ---` sentinel delimiters. Added prose stating the status gate reads only the `STATUS:` first line. Phase: Explore now opens with an instruction to re-call `_client.get_task(wiki_path, slug)` (fresh subprocess) and read `task['body']` and `task['brief']` before touching any source file, with the full key set documented and an empty-field fallback rule.

`plugins/mill/unit_tests/test-skill-helper-drift.py` — Card 2: regex in `_extract_helper_references` gains the negative lookbehind so `gate_cmd.lower()` is no longer mis-extracted; `ALLOWLIST` emptied with an explanatory comment. Card 3: new `_run_extract_unit_checks()` asserts the negative and positive regex cases; `_run_regression_locks()` gains the mill-start body/brief lock; `main()` wires in the third check group; module docstring updated.

{"status":"success","commit_sha":"61104b445e68fb2c319bc54e8a6dbe1cca4978bf","session_id":"83e09d37-37b8-4cf5-87ea-e58876e46a4b"}
