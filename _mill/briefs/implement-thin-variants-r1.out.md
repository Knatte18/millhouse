All 3 cards match the log exactly. Full HEAD SHA: `181a41b0633632a66f51d347aeade89e605b5fa`. Verify passed with no self-fix needed. Working tree is clean of any in-scope modification.

Card-count self-check: 3 of 3 cards committed (cards 6, 7, 8) — all complete, verified honestly against the git log range.

{"status":"success","commit_sha":"181a41b0633632a66f51d347aeade89e605b5fa","session_id":"b2f72414-540a-4031-8b2a-f3e84a44cb95","cards_done":[6,7,8]}

Summary of work:
- `/home/knatte/Code/millhouse/wts/mill-go2-scaffold/plugins/mill/unit_tests/test-mill-go-variants.py` — new variant-contract test (7 checks: label binding, override-section presence, base-loaded, base's unbound-halt message, no re-inlined machinery, no-hook-as-name scoping, three-literal-family parameterization lock).
- `/home/knatte/Code/millhouse/wts/mill-go2-scaffold/plugins/mill/skills/mill-go/SKILL.md` — recreated as a thin 28-line/819-byte variant with the original frontmatter description (recovered from commit `6442a688`), binding `VARIANT_LABEL: mill-go`, empty `## Driver preamble` / `## Dispatch overrides`, and a closing instruction to load `mill:mill-go-base`.
- `/home/knatte/Code/millhouse/wts/mill-go2-scaffold/plugins/mill/skills/mill-go2/SKILL.md` — new thin 28-line/804-byte variant, same shape, binding `VARIANT_LABEL: mill-go2`, new description conveying the experimental opt-in purpose; not wired into any automatic path.

{"status":"success","commit_sha":"181a41b0633632a66f51d347aeade89e605b5fa","session_id":"b2f72414-540a-4031-8b2a-f3e84a44cb95","cards_done":[6,7,8]}