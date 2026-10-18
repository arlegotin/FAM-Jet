# First SELF sample: narrow parent-proof correction

**NEEDS_REVISION on this newly identified interaction.** My v2 approval did not account for the first SELF sample's ordering. The parent-proof cutoff unnecessarily excludes a qualifying terminal helper in that sample, even when the parent's genuine live proof and baseline subsequently join. This qualifies the earlier approval; no broader finding is added.

In `process_tree`, `sample_start` precedes helper launch. The helper is communicated with/reaped and its completion recorded before `sample_end`; native image lookups follow `sample_end`. `record_baseline` then emits the tagged SELF observation and matching baseline. Thus the first reader proof necessarily has `lookup_end > helper.sample_start`. Waiting for its baseline cannot repair v2's temporal inequality. This is a conditional source-path incompatibility, not evidence that the sampling helper actually appeared as `<defunct>` in a native run. In particular, successful live-display/ESRCH helper rows remain outside the proposed literal-terminal branch.

**Minimal exception:** allow a terminal PS helper's parent qualification through either v2's earlier historical proof or an applicable **live parent row in the very same retained sample**, subject to all of these conditions:

- Bind the helper to the same unique accepted root/reader generation and preserve every existing vector, artifact, parent, lifetime, provenance and failure check. Require a shared immutable sample/event reference; coincident timestamps or another emitter's copy are insufficient.
- The parent row is unambiguous, has exact permitted live display and successful matching native image/hash. Its timing satisfies `parent.launch_start <= sample_start <= sample_end <= parent.lookup_start <= parent.lookup_end`, with proof ending strictly before any parent completion. Retain v2's parent/helper launch bounds and rejection of observed release, reuse or contradiction.
- Root proof must originate from its actual owning supervisor's sample under unreaped ownership. Reader proof must be that reader's genuine `emitter_pid=self_pid=reader_pid` SELF row and matching post-import/pre-allocation baseline join, including RSS equality and `proof.lookup_end <= baseline.monotonic <= parent.completion_end` when completion exists.
- The helper independently satisfies the full literal-terminal helper predicate and its own actual launch/reap witnesses. Parent proof may follow helper completion: these describe different processes. Never require an invented helper return code or historical helper image.

Keep the helper pending until the same-sample parent proof and required reader baseline are accepted; use the already specified parent dependencies and wakeups. Record the proof reference and distinguish same-sample live-parent qualification from historical absent-parent qualification.

**Python's own terminal predicate stays unchanged:** its historical proof must end no later than its terminal sample starts. A terminal or absent parent cannot use this exception.

Focused controls should accept the first genuine reader SELF/baseline join and supervisor-owned same-sample root proof, and reject cross-sample/copied proof, missing baseline, terminal parent, invalid timing and parent failure. No tests, native execution or source edits were performed.
