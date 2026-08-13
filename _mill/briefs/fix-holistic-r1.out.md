HEAD advanced (`2b2a8121` ≠ baseline), no tracked modifications remain. Reporting success.

Task: fix the holistic review round 1 BLOCKING finding per `/home/hanf/Code/millhouse/wts/mill-merge-and-merge-in-bugs/_mill/briefs/fix-holistic-r1.md` — mill-merge-in's dead-parent rebind claimed "identical" behavior to mill-merge's corrected `status_path` derivation while reusing the divergent `resolve_hub_path()`+literal-path pattern.

Verified the finding accurate, then applied the reviewer's second offered fix option (document safety) rather than the first (retrofit worktree_root-based derivation): confirmed via `_paths.py` that `resolve_hub_path()` is a cwd-based walk while mill-merge's corrected pattern (`resolve_active_hub`) is a slug-driven lookup needed only because mill-merge must reconcile cwd against a separately-tracked worktree (in-place-vs-worktree-mode ambiguity) — an ambiguity mill-merge-in doesn't have, and its own Step 4 already uses the identical `resolve_hub_path()` pattern. Documented this in the Card 7 paragraph.

All batch verify commands re-ran clean (10/10 + 39/39 PASS, exit 0).

{"status":"success","commit_sha":"2b2a81211176cc114c718d0ab033dea9a768a6f0","session_id":"083880cb-7391-43f1-936b-f3b64ff0c5dd"}