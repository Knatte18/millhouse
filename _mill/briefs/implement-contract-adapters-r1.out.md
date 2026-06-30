That's the correct 40-char SHA (matches the `ffd43695` short form from the push output). All three cards are committed, verify passes, and the working tree is clean.

{"status":"success","commit_sha":"ffd4369542412c36f8692676f2745549903050e3","session_id":"6034d0ea-0d8d-462c-b503-c587e0e96896"}

Summary of work done in this batch (`01-contract-adapters.md`):

- `C:\Code\millhouse\wts\mill-ghissues-source-adapter\plugins\mill\scripts\_gh_issues.py` — added `to_contract(issues, repo) -> dict`, mapping `fetch()`-shaped issue dicts into the triage-report contract envelope; updated module docstring's `Public API:` list. Commit `d1f5f5f0`.
- `C:\Code\millhouse\wts\mill-ghissues-source-adapter\plugins\mill\unit_tests\test-gh-issues.py` — added `test_to_contract_maps_issues_to_triage_contract()`, wired into `main()`. Same commit.
- `C:\Code\millhouse\wts\mill-ghissues-source-adapter\plugins\mill\scripts\_sandbox_report.py` (new) — `read(path)` + `SandboxReportError`, strict validation per the brief (source check, items-array check, per-item ref/title/body, duplicate-ref rejection), returns the contract envelope with `ref_prefix=""`, `detail_hint=None`, `embed_body=True`. Commit `87d5f4fc`.
- `C:\Code\millhouse\wts\mill-ghissues-source-adapter\plugins\mill\unit_tests\test-sandbox-report.py` (new) — covers all 8 required cases plus per-field missing-field variants and both non-object top-level JSON shapes. Same commit.
- `C:\Code\millhouse\wts\mill-ghissues-source-adapter\plugins\mill\templates\triage-report.schema.md` (new) — full envelope field table, two JSON examples, per-Sources-bullet rendering prose (including fold-in), Produced-by/Consumed-by section. Commit `ffd43695`.

`verify:` (`run-all.py --only test-gh-issues.py test-sandbox-report.py`) passes (29 assertions across both files, all PASS). `ruff check` clean on all changed/created files. Working tree clean at HEAD.