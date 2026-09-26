Holistic fix round 1: no code changes. The review verdict was APPROVE with two NITs, both stating no fix required. Pushed back on both. (1) The `_MutationWindow` class matches the batch-local decision. (2) The lock acquired outside the `try` goes stale after 5 minutes and the SKILL documents recovery, and moving it would change the documented design. HEAD is unchanged from the baseline; no verify commands were run because nothing changed.

{"status":"success","commit_sha":"f314a2ff80cc428b005edd9c9b7a2f89abc44c02","session_id":"9b46c8d8-7065-4e60-ba57-c056b9efdafe"}
