# R6 fix round 3 — independent scoped re-review

Reviewed 2026-10-25. **SPEC: YES. QUALITY: APPROVED** for the scoped source gate before the next bounded native public qualification. **R6-F2-1: ADDRESSED. R6-F2-2: ADDRESSED.** No new blocking defect was found in the correction diff. This is not approval of native parity/performance, fresh protected execution or scientific completion.

## Scope and boundary

This review covers exactly the two open findings from `e2e-measured-execution-fix2-review.md`, their correction, and directly introduced regressions. The observer follow-up brief and previously accepted mathematical, policy, cohort, public-input and scientific-projection constraints remain in force.

Reviewed range: `1e627d84a08fc5c48f1d32a77936d2cd24a25dd7..4f90cd2a`, implementation `c8e48a088239c7af39616acdc3709be99e6ab837`, appended fix-round-3 report, and recorded RED/final evidence. The supplied review package is 47,370 bytes, SHA-256 `830f52ab0c13b124fe9e39494d246f9fde31d02b0d7f9732358e55d25690000e`.

No tests, native qualification, fitting, benchmark, protected/scientific work or experiment were run. No private artifacts, old private ledger, private results or private data were opened. Inspection used source, committed reports/logs, stdlib hashing and read-only Git comparisons. No tracked source or Git state was written; only this ignored review file was created.

## R6-F2-1 — ADDRESSED

References: `famjet_poc/resources.py:63`, `:67`, `:111`, `:146`, `:194`, `:228`, `:291`; `tests/test_measured_execution.py:214`.

The fixed two-second sampler join is replaced by a bounded wait that accounts for the existing five-second serialization wait and five-second callback allowance. The join does not restart the running observation's own timeout. A successful sampler stop is followed by the required fresh exit observation. The newly added deadline parameter flows through exit sampling, global-lock acquisition, callback join, and cancellation re-verification; those teardown operations share the remaining 18-second monotonic deadline for that guard rather than each receiving a fresh full allowance.

The new targeted fixture begins a background callback, exits the context while it is active, allows it to finish after 2.2 seconds, then checks completed status, two forced observations, at least three samples and the measured operation duration. Its recorded RED demonstrates the previous two-second failure. The captured final suite includes this fixture and the existing short-timeout blocked/stale, deadline, serialization and owned-cancellation fixtures.

Receipt construction now copies sample dictionaries under the sample lock and captures the violation/cancelled set before serialization. The sample count and summed observer cost are derived from that copied list. If the sampler misses its bounded join, failure is latched before this snapshot; a later detached callback cannot append into the receipt's copied list or turn it into successful completion.

The 0.25-second successful-sample reuse cutoff, five-second host-operation bound, 0.1-second background poll delay, sticky failure and scientific wall deadline remain intact. No mathematical or stage budget was extended.

Operational limit: the 18-second deadline is **per guard**, and receipt filesystem I/O is outside that wait deadline. It is not a proof that three nested guards finish cooperative teardown plus I/O within 20 seconds. The unchanged 200-second native alarm and independent owner witness must continue enforcing the total qualification/shutdown limit; a hard-stop or incomplete receipt remains failure. This is consistent with the explicitly retained external hard-stop boundary and must not be described as a guaranteed aggregate 18-second shutdown.

## R6-F2-2 — ADDRESSED

References: `docs/research/e2e-guard-cadence-public-check.py:324`, `:418`, `:434`; `tests/test_guard_cadence_public_check.py:232`.

The actual qualification receipt-building path now calls `qualification_guard_evidence` with the three guard instances after they exit. It resolves and records the actual outer, inner and full-scale roots, checks the expected output-root/`runs` mapping, verifies the three guard-reference byte hashes, and records their references. It also embeds `execution_source_sha256()`, using the existing complete executable inventory that includes both `resources.py` and the real `pipeline.py` observer implementation.

The existing driver hash, E3 hash, study-config hash and old public full-scale tree/count/bytes/path-size inventory commitment remain. The final new-output cap check includes the expanded qualification receipt. The new fixture constructs three guard instances and compares the emitted root map, reference inventory and source identity with their actual values. The actual run path merges that helper's output into the final receipt, closing the former omission.

## Regression and preservation assessment

The production changes remain confined to `resources.py`; the driver and its focused fixtures are the other changed executable/test paths. The patch does not alter numerical/evaluator modules, archived models, E1/E2/E3/transfer, locks, complete runner binding, dated policy values, finalization reserve, cohort prefix/roots/counts, public control seed, all-eight-method projection requirements or public-only path admission. The third full-scale observer and its 512-MiB input-tree cap remain; the two output guards retain the 128-MiB new-output cap and all three retain 1.5-GiB RSS. Run05 stays failed and source-bound; no old-run resume compatibility path was added.

An independent read-only preserved-source range comparison returned exit 0 and zero bytes. All four changed-file and all preserved-file sizes/hashes in the fix-round-3 inventory match current files. The unchanged baseline remains 6,593 bytes with SHA-256 `dd49488b03f78fb7b0818ed837fd53b6272304c0f8497030b4a239c78c5abe43`. The source inventory records complete executable identity `b994b3ef7b770fb50db7adba3a9125f75c7c5dc1a4cd3dc3d85843d3177e1260` and unchanged E3 identity `e25b63ee60f51ed511fc7af5d3f713c9a404301f51178283c0a2066d940e68ba`.

## Recorded evidence audit

Every raw log byte count and SHA-256 in `fixround3/commands-source-final.json` and `red-review-findings.json` independently matched its log. The RED receipt has exit 1, 3,693 bytes and SHA-256 `a69b13f9d365b93f8b8350378d1d416b402094a0f2c5066dfb2133ff66e401aa`.

The final targeted log states **42 passed in 7.39s**. Its receipt records exit 0, UTC `2026-10-25T04:06:59.526742+00:00` to `2026-10-25T04:07:07.197647+00:00`, elapsed 7.670835249999072 seconds, 99 bytes and SHA-256 `e0d8349621d3448ccd1fc412a674bd0a989922cde4fd145d0110722e74d15b8c`. Recorded compile, source diff check, driver help and preserved-source diff all have exit 0 and matching logs. These are verified recorded outcomes, not tests rerun by this reviewer.

## Cannot verify at this gate

Actual native exact row parity, full-scale observer duration/contention, sampled RSS/output, and completion within the qualification allowance remain unverified. The unit fixture establishes the corrected 2.2-second background teardown case; it does not establish native performance or aggregate worst-case nested shutdown timing.

Root's next step is the single bounded native public qualification under its independent hard witness. It must yield complete all-eight-method 128-row matches, all three verified guard receipts and appropriate resource/cadence evidence. Any timeout, failed guard or incomplete receipt remains a failed qualification. Fresh full-run work still requires that gate, continuous new-run policy/source binding, and the six-model/normalization reproduction gate before freeze. Full protected coverage, inference/report, scientific copied replay and final whole-branch review remain later gates. Preserve every old output and clock unchanged.
