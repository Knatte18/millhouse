Both cards for batch 01-long-path-helper are committed (2 of 2): Card 1 (`feat(worktree): add _long_path.to_extended for Windows extended-length path prefixing`, commit `5d60ceed`) and Card 2 (`test(worktree): add test-long-path.py for _long_path.to_extended`, commit `a6d6d718`). The batch's `verify:` frontmatter is `null`, so no verify command was required; I additionally ran `python3 plugins/mill/unit_tests/test-long-path.py` directly and all 4 cases passed. Working tree is clean (`git status --porcelain --untracked-files=no` empty) and both commits are pushed.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-go-windows-baseline-teardown-winerror145/plugins/mill/scripts/_long_path.py` (new)
- `/home/knatte/Code/millhouse/wts/mill-go-windows-baseline-teardown-winerror145/plugins/mill/unit_tests/test-long-path.py` (new)

{"status":"success","commit_sha":"a6d6d7187335b793d023485b3b68d9fcd5025fe","session_id":"7162cddf-10b2-4913-bc7f-c36e5d1bf669","cards_done":[1,2]}
