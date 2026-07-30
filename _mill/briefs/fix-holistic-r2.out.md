Perfect! All tests pass and the fix has been successfully committed. Let me provide the final status report:

## Summary

I successfully fixed the BLOCKING finding from the code review. The issue was in the test fixture `test_check_requirements_quote_indent_drift_dirty_fence_contains_nested_heading` in `/home/knatte/Code/millhouse/wts/mill-plan-requirements-byte-exactness-gap/plugins/mill/unit_tests/test-plan-validate.py`.

### The Fix

The original fixture had look-alike lines (like `- **SomeField:** value` and `### Nested Heading`) indented with list-continuation spaces, which prevented them from matching the field-header regex. This meant the test didn't actually prove the `in_fence` boundary guard was load-bearing.

The fix implements selective indentation:
- The `### Nested Heading` line is indented (2 spaces) to prevent `_parse_cards` from mis-splitting the card on this heading
- The fence delimiters and `- **SomeField:** value` line are flush-left (column 0) to properly match the field-header regex
- The other lines (`alpha`, `beta`) have drift indentation (2 spaces)

This allows the `in_fence` guard to be properly tested: when the flush-left look-alike line matches the regex, the `in_fence` flag prevents truncation of the field body, allowing the full fence body with drift to be compared against the target file.

### Verification

All unit tests pass, including the corrected test which now properly validates that the `in_fence` boundary detection is load-bearing.

{"status":"success","commit_sha":"d2b427c2261154036aaf1a3c5f65bef28c283021","session_id":"3a58df88-2756-4bec-9ae8-d2e2c39dc103"}
