# Stage B builder findings — response1, 19 October 2026

Updated only the ignored source-design document and this response. No implementation, tests, project imports, probes, model work or Git operations occurred.

1. Corrected transport semantics: the guarded response has no query IDs. Future verification binds the hash-verified ordered request to immutable response bytes and checks positional shapes. `_result_from_record` is worker-internal; the later adapter must decode `numeric=result_json` with explicit null/nonfinite semantics and cannot invent identity echoes.
2. Made encode quarantine precede all reading: stop writes, retain trigger/state/bytes, skip read, and emit eight failure-complete rows matching `score_episode`. Reader/transport/schema/counter failures remain infrastructure stops.
3. Applied the root scope ruling: only a limited future pure component is specified for plan/null blocking, artifact IO, record inventory, score composition/selection/costs and controlled stub driving. Every nonnull approval/release is NOT_READY. Actual approval/release validators, production/runtime adapters and nested evidence/admission/launch schemas remain explicitly unspecified and unauthorized until full Stage A and independent review. No opaque reference substitutes for closed semantic evidence validation.

The revised design is not presented as builder-ready for whole production. Its remaining scientific/runtime gates and native qualification remain separate future decisions. Setup06 capacity HOLD and all historical STOPPED/FAILED labels remain unchanged.
