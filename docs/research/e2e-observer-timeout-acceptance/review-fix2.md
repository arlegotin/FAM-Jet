# R6 observer follow-up / fix round 2 — independent scoped source review

Reviewed 2026-10-25. **SPEC: NO. QUALITY: NOT APPROVED.** Two narrowly scoped corrections remain before the next native qualification. The timeout/reuse separation, three-guard public scale path, and recorded source checks otherwise satisfy the inspected follow-up requirements. This is a source review, not native or scientific completion review.

## Scope and boundary

Requirements reviewed: `.superpowers/sdd/2026-10-16-famjet/e2e-observer-timeout-brief.md`, `docs/amendments/2026-10-25-observer-operation-timeout.md`, the appended fix-round-2 section of `docs/research/e2e-measured-execution-report.md`, and the supplied public/resource-only run05 failure index. Prior accepted R6 constraints remain in force.

Exact reviewed range: `02d6c5b8512a05f5f205aacb7cbb0e27d525f8b8..1e627d84`; production source implementation `9641ab47e47f384b40ef7fc977b779e72ca400e4`. Review package: 60,356 bytes, SHA-256 `eed95d0968a716df61930ca730c5b436495ee93e88aed6bffdd235c4a680bb49`.

No tests, native qualification, fitting, benchmark, protected/scientific work or experiment were run by this reviewer. No run04 private ledger, private rows, predictions, summaries or private data were read. Run05's committed failure index was read only as the explicitly supplied public/resource diagnosis; referenced run artifacts were not opened. No tracked source or Git state was modified. Only this ignored review file was created.

## Findings

### R6-F2-1 — P1: The unchanged two-second teardown rejects valid five-second operations

References: `famjet_poc/resources.py:59`, `:66`, `:90`, `:283`–`:291`; `tests/test_measured_execution.py:192`–`:228`.

The new default allows a host operation to complete within five seconds, but `__exit__` still joins the background sampler for only two seconds and then permanently latches `host resource observer did not stop`. If a background callback has just begun and validly finishes after, for example, three seconds, an otherwise successful stage leaving its context fails after two seconds despite the callback staying within the newly accepted operation bound. It also skips the forced exit observation because failure has already been latched. A background callback can still update samples/metrics after the failed receipt has been written.

This interaction is directly introduced by increasing the operation allowance beyond the existing shutdown wait. It can reproduce the class of unnecessary public-stage invalidation that this amendment is meant to avoid. The new 0.31-second foreground callback fixture cannot expose it; the blocked fixtures deliberately inject a 0.05-second timeout.

Required correction: make graceful teardown account for an already in-flight observer's bounded remaining operation/serialization allowance, while retaining a finite overall shutdown bound and the owner's 20-second shutdown reserve. Do not reset the operation clock, permit stale success, clear sticky failure, or increase scientific wall budgets. Ensure the final receipt is taken after the sampler has stopped, or from a stable failed snapshot when the bounded teardown expires. Retain a fresh exit observation on successful teardown.

Add one targeted fixture that starts a background observation, enters teardown while it is active, and lets it complete after more than two but less than five seconds; the valid case must complete with a forced exit sample. Retain bounded refusal for a genuinely blocked callback and sticky failure/deadline behavior. This does not require any scientific or native workload.

### R6-F2-2 — P2: The qualification receipt does not bind the changed observer implementation or explicitly identify all observed roots

References: `docs/research/e2e-guard-cadence-public-check.py:399`–`:428`; `famjet_poc/resources.py:224`–`:246`.

The follow-up brief requires the qualification receipt to bind all three roots and source hashes. The receipt currently contains the driver hash, E3 hash, study-config hash, three guard-reference hashes, and the old full-scale root. It does not contain the hash of `resources.py` or the actual `pipeline.observe_resources` implementation, nor a complete runner identity that covers them. The individual guard receipts contain no observed-root or implementation identity either. The two new-output roots are only inferable from the driver's code and receipt locations.

Thus the artifact intended to qualify this observer correction does not itself identify the observer source it exercised. A separately recorded source-hash inventory is useful evidence, but the qualification receipt does not reference/bind it. This is a direct gap in the newly requested receipt contract, not a request for a general provenance redesign.

Required correction: add an explicit root map from the three actual guard instances and bind the relevant observer/guard source hashes, or the existing complete executable identity covering them, in the qualification receipt. Preserve the driver hash and public-tree path/size inventory hash. Add a small fixture for the actual receipt-building path so the root and source commitments cannot be omitted while the report still claims them. Keep this within the driver/resources scope; no E3/transfer changes are needed.

## Supported portions of the implementation

- `resources.py:59` sets the operation bound to 5.0 seconds while `:129` keeps the successful completed-sample reuse cutoff at 0.25 seconds. The default is asserted independently by a fixture that accepts a 0.31-second fresh callback after the previous sample is stale. Repeated checks do not extend the age cutoff.
- Process-wide serialization remains in place. A timed-out worker retains the global lock until its own `finally` exits, preventing concurrent launches from other guards. Per-guard sampling-lock waits remain finite. Monotonic checks before sampling and after completed observation, sticky failure, current full-tree RSS/disk accounting and reverified owned-descendant cancellation remain. The new slow-call deadline fixture checks that an operation completing after the scientific wall deadline cannot produce success. The teardown interaction is the exception described above.
- New receipt fields distinguish maximum successful reused-sample age, elapsed completed observer operation, and global observation-lock contention. The previous maximum sample-age field is retained. The report correctly explains that attempted age can exceed 0.25 during refresh and that a 0.1-second background poll delay is not a guarantee of a completed observation every 0.1 seconds. It makes no transient-memory or speedup claim.
- `verified_public_scale_tree` at driver `:235` confines scanning to exactly the supplied old public `development_k16` subtree, rejects traversal and symlink ancestors/members, uses metadata inspection without reading file contents, requires at least 1,000 regular files, and records count, byte total and a canonical path/size inventory digest. The existing pinned public journal/cache and archived-model admission remain unchanged. The new code does not traverse the whole old run or its private siblings.
- `public_guard_triplet` at driver `:284` retains the existing outer and inner output guards and adds a third default `observe_resources` guard for the verified public tree. Its receipt is written beneath the new output root. Only the input-tree disk ceiling becomes 512 MiB; new output remains 128 MiB, all guards retain 1.5-GiB RSS, the remaining 180-second work allowance and the 200-second total alarm. Three-guard process serialization is exercised by the synthetic scale fixture.
- The final output-cap check executes after all three guard receipts are written, so those files and the final qualification receipt are counted under the new-output cap. No 350-MB input copy is introduced.
- The 1,100-file fixture verifies the separate public-tree root, 4,400-byte observed total, three callback roots, one-at-a-time operation, a callback above 0.25 seconds and the 512-MiB input cap. Its process fields are synthetic while its disk walk is the production helper; the report accurately discloses that native `ps` was unavailable in the fixture. A separate fixture rejects a public-tree symlink to a private sibling.
- The driver retains all eight methods, 16 public 2048-event histories, complete 128-row-per-method scientific projections, surplus/duplicate rejection, selected configuration labels, the corrected public training seed and unchanged coordinate diagnostics. No protected factory or real private dataset is introduced.
- Production modifications are confined to `resources.py`. Full runner binding, strict policy values, reserve, fresh cohort prefix and roots, all numerical/scientific modules, E3, transfer and locks remain unchanged. Run05 remains failed and cannot be resumed under the new complete executable identity.

## Recorded evidence audit

All raw log byte counts and SHA-256 values in `fixround2/commands.json`, `commands-source-final.json` and `red-new-contracts.json` independently matched their committed logs. The captured RED has exit 1, 3,591 bytes and SHA-256 `448ffbfa78e601491b56c02e1d23661223933a6836308560cceb04560503a7f2`. The uncaptured intermediate stale-age fixture failure is disclosed in the report; no raw receipt is invented for it.

The final affected-suite log states **89 passed in 12.14s**. Its receipt records exit 0, UTC `2026-10-25T03:58:07.470269+00:00` to `2026-10-25T03:58:19.876638+00:00`, elapsed 12.406298750000133 seconds, 180 raw bytes and SHA-256 `53fc74f456837641cde3bc311d352480d0a5a8e558bae3ac110108b85a1295b6`. These are verified recorded results, not rerun tests.

Recorded compile, source diff check, driver help and preserved-source diff all have exit 0 and matching raw logs. All four changed-file and all preserved-file size/hash records match current source. An independent read-only range diff for the preserved tree/files, additionally including `pipeline.py`, returned exit 0 with zero output. The committed baseline and dated execution policy hashes match the unchanged inventory. No scientific byte-preservation regression was found.

## Limits and next step

No new native performance/parity result exists from this review. The actual full-scale third-observer cost, contention, current RSS, exact rows and completion under the qualification budget remain unverified. The supplied run05 failure remains evidence of a failed public-only attempt, not accepted stage evidence.

Apply only the two corrections above, capture their targeted checks and refreshed source evidence, and obtain scoped re-review before Root's bounded native qualification. A successful native gate and the mandatory six-model/normalization reproduction gate remain prerequisites for the fresh run06 path. Final full-run coverage, inference/report and copied scientific replay remain separate later gates. Old outputs and clocks must remain untouched.
