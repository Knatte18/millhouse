MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness: path-token exemption list gaps

```yaml
duration_s: 241.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:consistency] Ownership-exemption regex lacks past/gerund forms it claims to have
**Demoted-from:** BLOCKING
**Section:** Decisions § Ownership-phrase exemption **Issue:** The rationale claims the verb set "follow[s] the same 'spell out the inflected forms by hand' convention `_PROHIBITION_VERB_FORMS` uses" (verified: that dict hand-spells base/3rd-person/past/gerund per verb, e.g. `write`→5 forms including irregular `wrote`/`written`), but the given regex (`owns?|fixes?|corrects?|rewrites?|addresses?|handles?|resolves?|covers?|edits?|updates?`) only covers base and `+s` via a bare `?` quantifier — no past tense (`fixed`, `corrected`, `rewrote`/`rewritten`, `addressed`...) or gerund (`fixing`, `correcting`, `rewriting`...) forms, and isn't hand-spelled at all. **Fix:** either state the verb set is deliberately narrower than `_PROHIBITION_VERB_FORMS`'s convention (and drop the "mirrors that convention" claim), or extend it to a hand-spelled 4-form-per-verb table matching precedent.

### [NIT:consistency] Testing section never exercises the six added synonym verbs
**Section:** Testing § Ownership exemption **Issue:** Q&A decides to extend the verb set to `addresses/handles/resolves/covers/edits/updates`, but the listed tests only cover `fixes` and `corrects`; contrast with the illustrative-output exemption's testing section, which explicitly requires an extra `_OUTPUT_VERB_FORMS` test "mirroring how `..._prohibition_marker_new_verbs` exercises more than one verb form." **Fix:** add a `clean_ownership_<synonym>` test for at least one extended synonym verb, matching that same internal precedent.

### [NIT:design] Output-verb set also omits past-tense forms
**Section:** Decisions § Illustrative-example/output-framing exemption **Issue:** `_OUTPUT_VERB_FORMS` is described as base/`-s`/`-ing` only (`emit(s)/emitting`, etc.) — a past-tense phrasing ("the answer emitted the bare `README.md`") would not be exempted, even though the mechanism otherwise generalizes the reported `#985` idiom. **Fix:** confirm this omission is intentional (e.g. rare in Requirements: prose) or add past-tense forms alongside the existing three.

### [NIT:consistency] "owns" cited as exact issue wording but is the discussion's own paraphrase
**Section:** Decisions § Ownership-phrase exemption **Issue:** The rationale says the verb set "mirrors both issues' exact wording ('fixes', 'owns', 'corrects', 'rewrites')," but `owns` only appears in the Problem section's own paraphrase of #1022 ("to say another card/batch owns it"), not in either issue's quoted sentence — only `fixes`, `corrects`, `rewrites` are verbatim. **Fix:** reword to distinguish the two verbatim-quoted verbs from the paraphrase-derived one.

## Verdict

APPROVE
Ownership-exemption regex's verb-form coverage contradicts its own stated precedent-adherence claim.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
