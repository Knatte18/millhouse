No tracked in-scope modifications remain. Both cards committed and pushed cleanly.

{"status":"success","commit_sha":"8ba8ba5b","session_id":"671b9c19-9d39-45ec-a417-3413c804f4df"}

Summary of work done:

- plugins/mill/skills/mill-start/SKILL.md — Card 1: reordered Entry steps so path variables are bound first, then config is loaded, then the slug is read via _marker.slug_from_branch(git_root, wiki_path, cfg). Card 2: added [NOTE]-handling clause to step 5's On GAPS_FOUND branch in Phase: Discussion Review.
- plugins/mill/skills/mill-plan/SKILL.md — Card 1: same Entry reordering (bind path vars, load config, then read slug).

Commits:
- 63272359 fix(mill-start,mill-plan): load config and bind path vars before slug read in Entry
- 8ba8ba5b fix(mill-start): handle [NOTE] findings in GAPS_FOUND discussion-review branch

verify: null per the batch frontmatter (doc-only batch) — no test command was run.

{"status":"success","commit_sha":"8ba8ba5b","session_id":"671b9c19-9d39-45ec-a417-3413c804f4df"}
