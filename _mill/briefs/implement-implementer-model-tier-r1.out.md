Perfect! The implementation is complete. Both cards have been successfully implemented and committed:

1. **Card 11** - Changed `roles.implementer.model` from `haiku` to `sonnethigh` in both:
   - `plugins/mill/templates/mill-config.yaml`
   - `mill-config.yaml` (hub config)

2. **Card 12** - Added a unit test `test_implementer_model_default_is_sonnethigh()` that:
   - Loads both config files using YAML
   - Asserts that `roles.implementer.model == "sonnethigh"` in both files
   - Added the test function to the `tests` list in `main()`

The `verify` command has been run and all tests pass successfully.

{"status":"success","commit_sha":"c58e02cf1e4e39170b72693c8b40fa89d991d516","session_id":"a2ea5001-ec35-482b-b468-851cddeb931b"}
