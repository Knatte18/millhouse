Batch fix-monitor-persistent-refs complete. All 3 of 3 cards committed and pushed to hanf/monitor-persistent-true-still-referenced.

- Card 1: plugins/mill/skills/mill-go-base/SKILL.md — replaced `persistent: true` Monitor call and reframed the re-arm bullet. Commit c6fead6d.
- Card 2: plugins/mill/skills/mill-plan/SKILL.md — same fix. Commit e0e3dda7.
- Card 3: plugins/mill/docs/harness-tool-contracts.md — corrected the canonical schema claim (no persistent param, 1800000ms cap). Commit 4cfd3726.

verify: null per batch frontmatter — ran the Batch Tests inspection checks instead: `grep -rn "persistent: true" plugins/mill/` returns no results; `grep -n "persistent" plugins/mill/docs/harness-tool-contracts.md` now only asserts the parameter does NOT exist. Both pass.

Pre-report self-check: `git status --porcelain --untracked-files=no` is clean (no in-scope dirty files). Card-count self-check: range-start 92b687d5 ("mill-go: start batch"), `git log 92b687d5..HEAD --oneline` shows exactly 3 commits matching all 3 cards' Commit: messages.

{"status":"success","commit_sha":"4cfd3726b80a83e78c303af4895a8085589ddc23","session_id":"33a0298e-546c-44b9-be8e-f9fc1ded5f56","cards_done":[1,2,3]}
