Batch 01-deactivate-call-sites complete: 4 of 4 cards committed and verify passed.

Cards done:
1. plugins/mill/skills/git-commit/SKILL.md — deleted the Codeguide sync step (commit ed537abe)
2. plugins/mill/skills/mill-merge-in/SKILL.md — deleted the Codeguide update step and its dependent prose, renumbered old Step 5.5 to Step 5 (commit c0844a65)
3. plugins/mill/scripts/_parent_branch.py — deleted resolve_for_codeguide and its docstring entry (commit 7ded7cc6)
4. plugins/mill/unit_tests/test-parent-branch.py — removed the five resolve_for_codeguide assert/print pairs and its import (commit 35fc327a)

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py` passed: all remaining resolve/check_liveness/ParentBranchError assertions pass.

Pre-report self-check: `git status --porcelain --untracked-files=no` is clean (only the untracked brief file at _mill/briefs/implement-deactivate-call-sites-r1.md remains, which is out of scope for this batch and intentionally left alone).

Note: confirmed via repo-wide grep that no other call sites reference resolve_for_codeguide after this batch — only _mill/discussion.md, plan files, and review files mention it in prose/history, which is expected and out of this batch's scope (batch 2 handles remaining prose cleanup elsewhere).

{"status":"success","commit_sha":"35fc327aedad035ef59ae86909a9e21b839831ad","session_id":"e7f98397-a992-497a-8f03-5f45831d69b5","cards_done":[1,2,3,4]}
