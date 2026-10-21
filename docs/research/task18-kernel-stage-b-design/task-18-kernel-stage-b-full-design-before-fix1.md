# Stage B full external adapter design — 21 October 2026

DESIGN ONLY / HOLD. Binding authority: `docs/amendments/2026-10-21-kernel-actual-state-panel-design.md`. This document and its companion `task-18-kernel-stage-b-full-design-brief.md` jointly specify the minimum production adapter. Neither releases implementation, native qualification or panel work. Preserve all 53 famjet files/package `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`, lock `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`, and every Stage A file/artifact.

## Fixed experiment

Descriptive predictions from actual saved states; no source-fidelity, information-ceiling or baseline-convergence claim. Historical source is `81204796ade55ce9e7202bc9253b1b61db6a65a3`. Global A FAILED and raw STOPPED/returncode1 remain. All 720 finite P–A checks and 24 policy sentinels pass; 696 source comparisons pass, exactly 24 row30 source failures remain included. Six static Gram gates and 1602 transform comparisons pass; recorded identity/accounting/cleanup are complete.

Ordered candidates are `(jet,1e-10),(bank,1e-10),(bank,1e-6),(jet,1e-6),(jet,1e-2),(bank,1e-2)`. Ridge hex values are `0x1.b7cdfd9d7bdbbp-34`, `0x1.0c6f7a0b5ed8dp-20`, `0x1.47ae147ae147bp-7`. Keep Jet4/Bank8, CPU64, 9345 logical state bytes, prior5224, epsilon1e-8, floor/cancellation guards, original writer identities and frozen training metadata. Config SHA is the canonical exported method SHA, with exact export round-trip required.

Only EXPOSED manifest `90d0808a5410a8a2efe09bab823be3de798b03886e957ca77dc88fb68db98056`: original ordered 96 histories, eight queries each, lengths128/512/2048, four original regimes. Hash-check events, queries and observed-event targets against each original entry. Never call `development_inventory`, fit, train or refresh 6144 histories. Exact rematerialization requires later explicit allocation. Ceilings:192 new family/history snapshots,576 guarded eight-query requests,4608 scored predictions; no retries/replacements.

## Closed authority schema

All objects below have exactly listed keys. Reject duplicates, unknown keys, booleans-as-numbers, malformed hashes and JSON NaN/Infinity. `H`=64 lowercase hex; `G`=40 lowercase hex; `N`=nonnegative integer; `F`=finite number; `S`=nonempty string; `?`=nullable; lists retain order. Authority numbers are nonnegative, time/caps positive. `Ref<T>={kind:T,path:S,sha256:H,bytes:N}`: exact bytes/hash, regular-file containment under declared root, no symlink escape; parse T and validate semantics after hashing. No executable deserialization. Path-specific historical references resolve through the hash-bound original/archive mapping.

```
Plan={version:2,scope:"Task18 descriptive actual-state Stage B",
 panel:Ref<existing_manifest>,training:Ref<frozen_training>,
 candidates:Candidate[6],ceilings:{histories:96,queries:8,snapshots:192,requests:576,predictions:4608,factors:0},
 evidence:Evidence,approval:Approval?,execution:Execution?,release:Release?}
Candidate={id:S,family:"jet"|"bank",ridge_hex:S,config_sha256:H,writer_sha256:H,
 static:Ref<existing_export>,rates:Ref<represented_rates>}
Evidence={audit:Ref<markdown>,acceptance:Ref<scoped_acceptance>,custody:Ref<root_custody>,
 mapping:Ref<archive_mapping>,seal:Ref<A_seal>,setup:Ref<A_setup>,
 inventory:Ref<A_stage>,monitor:Ref<A_monitor>,events:Ref<jsonl>,journal:Ref<jsonl>,
 external:Ref<A_external>,slots:Slot[768],statics:Ref<A_static>[6],source:Ref<source_manifest>}
Slot={candidate:S,row:N,transform:"I"|"O"|"U"|"R",ordinal:N?,
 detail:Ref<A_detail>?,stdout:Ref<A_reader>?,stderr:Ref<bytes>?,input:Ref<snapshot>?}
Approval={ruling:Ref<markdown>,approved:true,scope:"descriptive_actual_state_only",
 evidence_sha256:H,failures:Disposition[24],source_review:Ref<markdown>,
 compatibility:{old_source:G,new_source:G,old_manifest:Ref<source_manifest>,
 new_manifest:Ref<source_manifest>,changed_paths:S[],decision:"external_adapter_only"}}
Disposition={candidate:S,row:30,transform:"I"|"O"|"U"|"R",
 source_status:"FAILED",strict_status:"FAILED",failed_fields:S[],
 contraction_indices:N[],decision:"retain_and_score_actual_state",ruling:Ref<markdown>}
Release={approved:true,scope:"binding"|"feasibility"|"panel",payload_sha256:H,ruling:Ref<markdown>}
```

Approval requires explicit manual root adoption of every failure, never inferred from hashes or row number. Missing dispositions block. Canonical payload hash excludes only `release`; ruling references payload hash without embedding its own hash. Source manifests are sorted `{path,sha256,bytes}` lists excluding generated manifests/reviews/seals/output, preventing cycles. Include every current B source, all reused A sources, all famjet sources, lock, bootstrap and binding amendment. Approval/release values and actual Execution remain null in prospective files.

Candidate ID is `family+":"+ridge_hex`. `existing_manifest` retains its existing sealed internal manifest hash as well as the independent Ref raw-byte hash; they are different identities. Validate existing manifest version, EXPOSED provenance, generator/seed/feature versions, data configuration and exact ordered development entries `{length,regime,episode_id,seed,hashes:{events,queries,oracle}}`. Regimes are irregular_revisions,periodic_impulses,piecewise_stationary,trend_reset, eight histories per length/regime. Reconstruct configuration only from those sealed fields and original seed/episode ID. Never substitute an equivalent-looking manifest.

Raw A schemas are fixed by the actual archived producer bytes, with these explicit semantic types; reject unexpected variants rather than silently accepting extensions:

```
Comparison={status:"PASS"|"FAILED",failed_fields:S[]}
FiniteOutcome={comparisons:{P_A:Comparison,A_B:Comparison,P_B:Comparison},
 end_to_end_gate:"PASS"|"FAILED",reader_arithmetic:"PASS"|"FAILED",
 source_contractions:Comparison,source_state_fidelity:"PASS"|"FAILED",
 strict_end_to_end:"PASS"|"FAILED",stop:"continue"|"candidate"}
# Only transformed finite outcomes additionally require transform_checks:Comparison[3].
SentinelOutcome={end_to_end_gate:"PASS",reader_arithmetic:"PASS",snapshot_sha256:H,
 source_state_fidelity:"NONFINITE_POLICY_SENTINEL",strict_end_to_end:"NONFINITE_POLICY_SENTINEL",
 stop:"continue",worker_counts:TraceCounts}
Executed={candidate:[family,ridge_hex],row:N,transform:S,status:"EXECUTED",seconds:F,
 outcome:FiniteOutcome|SentinelOutcome}
Nonapplicable={candidate:[family,ridge_hex],row:N,transform:"O",status:"NONAPPLICABLE"}
A_detail={P:Role,A:ReferenceRole,B:ReferenceRole,counts:TraceCounts,outcome:FiniteOutcome,snapshot_sha256:H}
Role={code:N,coefficients:(Number[8]|null)[],path:"decoded"|"empty"|"quarantined",
 prediction:Number[8],task:"mean"|"contrast",window_vectors:Number[8][],windows:Window[]}
ReferenceRole=Role+{residuals:DecimalString[]}
# Reference windows additionally contain margins:{nonnegative_mass?:DecimalString,
# floor?:DecimalString,cancellation?:DecimalString}; optionality follows executed reached/code path.
```

Here Number is a finite JSON number for P, finite decimal string for A/B; nullable applicability is permitted only as actual reference output requires. `Window`/`TraceCounts` are specified in brief; historical worker numeric shape is B1/Q1/V8, future panel shape B1/Q8/V8. A_stage exact top-level keys are counts,events,failure,groups,inventory,outer_seconds,seconds,status. Counts/events/seconds use the finite allowsets of sealed driver/production; verify actual inventory-derived counts,24 groups and failure=null. Check all26 sealed source hashes, six exports and two rates against setup and seal maps, then archived mapping raw bytes against original custody. Existing static/frozen-training/snapshot/export schemas remain their existing source-validated schemas, with no newly admitted fields.

Evidence validator checks raw records, not merely a signed summary: exact descriptor candidate/slot order,744 executed/24 predefined O11/12/13/15 NONAPPLICABLE; ordinal000–743 bijection;720 details exactly equal inventory outcomes;24 row32 early-return outcomes have no detail. Every raw stream has one final numeric result, one read, zero factorization, empty stderr, matching detailed P/counts/snapshot. Sentinels have quarantine/failure/code1 and exact training fallback. Require all P_A PASS; only row30 A_B/P_B failures, exactly prediction[0–7], windows[0].prediction[0–7], windows[0].raw[0–7]; contraction failures exactly8–71. Other failed fields/slots block. Require534 transformed finite records × three PASS checks against I; no invented sentinel detail/candidate_end.

Check six statics: passing materialized8×8 Gram gate, finite positive minimum eigenvalue/condition estimate, finite residual, correct factor arrays/exports, zero additional persistent history bytes, DERIVED unit metadata. Reference proof binds executed production/reference source,12 setups/3360 solves, completed details, stored A/B residuals <1e-50, valid reached/margin/code applicability, and audit acceptance of executed80/160 agreement/resolved decisions. Low/high arrays were not all archived: never invent independently replayed gates. Common validator checks COMPLETE source accounting, identity_complete, zero unresolved/missing baselines/rejected observations, empty diagnostics, null reason/monitor_failure, exact successful Git phase, real reap1 and external end before original deadline. Preserve sampled-proof limitations and raw STOPPED.

## Runtime/allocation types

```
Execution={source_full_git:G,source_manifest:Ref<source_manifest>,runtime:Runtime,
 host:{node:S,system:S,release:S,machine:S},admission:Admission,
 limits:{outer_seconds:F,candidate_seconds:F,incremental_bytes:N,output_bytes:N,
 free_disk_bytes:4294967296,numerical_threads:1},boundary:Boundary,launch:Launch,
 qualification:Qualification?,preparation_output:S?,output:S}
Runtime={python:S,executable:S,executable_sha256:H,implementation:S,
 process_image:{method:"macos.proc_pidpath",path:S,sha256:H},
 helpers:{ps:{path:S,sha256:H},git:{path:S,sha256:H}},
 decimal_version:S,libmpdec_version:S,decimal_extension:S,decimal_extension_sha256:H,
 byteorder:S,machine:S,context:S}
Observation={argv:S[],returncode:0,stdout:Ref<bytes>,stderr:Ref<bytes>}
Admission={utc_epoch:F,host:{node:S,system:S,release:S,machine:S},
 vm_stat:Observation,memory_pressure:Observation,power:Observation,
 page_size:N,free_pages:N,speculative_pages:N,available_bytes:N,reserve_bytes:N,
 planning_envelope_bytes:N,free_disk_bytes:N}
Boundary={allocation_start_monotonic:F,allocation_start_utc_epoch:F,deadline_monotonic:F,
 baseline:"post-import/pre-allocation per worker",absolute_rss:true,process_tree_rss:true,
 sequential_workers:true,outputs_include_temporaries:true}
Launch={bootstrap:Ref<python_source>,template_sha256:H,argv:S[],argv_sha256:H,monitor:Ref<python_source>,
 environment:{OMP_NUM_THREADS:"1",MKL_NUM_THREADS:"1",OPENBLAS_NUM_THREADS:"1",
 VECLIB_MAXIMUM_THREADS:"1",NUMEXPR_NUM_THREADS:"1",PYTORCH_ENABLE_MPS_FALLBACK:"0",PYTORCH_MPS_FAST_MATH:"0"},
 fresh_utc_epoch:F,free_disk_bytes:N,power:Observation}
Qualification={release:Ref<binding_plan>,report:Ref<binding_report>,source_full_git:G,
 source_manifest:Ref<source_manifest>,template_sha256:H,
 runtime:Runtime,monitor:Ref<python_source>,unknown_child_guard:Ref<existing_guard_proof>,
 compatibility:{qualified_source:G,current_source:G,material_manifest_equal:true,ruling:Ref<markdown>}?}
```

Runtime compares exactly to current unchanged `A.authority.runtime()`; this reuses low-level identity, never A `entry/verify/observe` scope. Exact current B Git/source manifest differs legitimately from historical executed A: manual compatibility review must confirm only the external adapter was introduced and all preserved bytes match. `changed_paths` enumerates material source/lock/bootstrap deltas, excluding archival evidence/document churn; retain both full Git identities. No compatibility waiver is inferred.

Qualification=null is permitted only for the separately released binding scope; panel/feasibility require PASS binding with identical material source/runtime/bootstrap/monitor/template. The source manifest includes static B bootstrap.py, never generated output/seal paths or literal invocation vectors. Template binds `[runtime.executable,"-I",ROOT/validation/kernel_stage_b/bootstrap.py,"--worker","--seal",PLAN]`; ROOT/PLAN are typed absolute substitutions checked per invocation. Each fresh literal vector gets its own hash; deadline stays in the plan. Qualification proves this source/template class, not equality of historical argv. Binding counts are all zero regardless of scientific ceilings. A binding report cannot authorize science. Different qualification/current full Git requires the explicit compatibility ruling above and equal material manifests; any material drift blocks reuse. Never repeat qualification automatically. Future feasibility needs its own frozen ordered subset, counts and release, charged separately without silently consuming/replacing panel attempts.

Admission verifies raw same-snapshot printed `(free+speculative)*page_size>=1GiB`, reserve≥25%, remaining envelope strictly exceeds allocated incremental cap; unchanged4GiB disk floor. Require exact observational `vm_stat`, `memory_pressure -Q`, power results; no polling/pressure generation. Admission and launch age≤60s, same host, fresh disk recheck. Future caps, clock, runtime, paths and current B full Git are unallocated, not borrowed from A.

Set original deadline=start+outer_seconds before allocated work; never reset after inspection/import/encoding. Parent requires absent output under existing parent; worker accepts exactly monitor-initialized stdout/stderr/events/evidence/monitor files. Include preparation directory, temporary files, failure artifacts, helpers, startup and final commit in accounting. Monitor invocation and lifecycle are fixed in the brief.

## Scientific path and selection

After verified authority and Torch/famjet baseline, reconstruct six statics without factorization; validate frozen rates/statistics/export/writer identity. Encode each family/history once, eventwise, inspecting all floating payload fields and last_time after each event. First nonfinite field stops encoding; retain trigger/saved state/logical bytes, skip read, score all eight fallback rows exactly as `score_episode`. Shared states require identical writer hashes. No history rescue, clipping, repairs or exclusions.

Normal inference receives only existing closed numeric request. Hash ordered query IDs against manifest before dispatch; bind response bytes to request hash. No response query IDs exist. Decode `numeric=result_json`, preserving null/nonfinite semantics and positional B1/Q8/V8 shapes. Transport, counters, schema or reader exceptions cause infrastructure STOP, not fabricated fallback.

Use unchanged `score_predictions`/`aggregate_scores` v2 separately per length, equal task/regime/history weights; combine three equal length losses. Undefined dominates; otherwise infinite dominates; retain counts and both flags. Only complete finite configurations are selectable. Per family minimize loss; exact ties(tolerance0) minimize standalone total seconds then config SHA. Charge family encoding fully to each configuration, once to campaign. Keep failed/excluded costs. Never call `select_family` or fabricate baseline acceptance.

## Gates

Source acceptance first; separately release ONE zero-read/zero-factor native empty binding with unchanged unknown-child guard proof; then separately bounded feasibility/batch-equivalence smoke only if needed; actual panel allocation last. No protocol is released here. Root still must accept source/compatibility and manual dispositions, accept binding evidence, choose measured caps/paths/clock and issue each release. HOLD.
