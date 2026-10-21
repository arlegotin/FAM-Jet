# Stage B implementation brief — 21 October 2026

DESIGN ONLY / HOLD. Read companion `task-18-kernel-stage-b-full-design.md` and binding21October amendment first. This closes the full adapter contract, not an implementation or execution release. Preserve famjet, lock, Stage A sources/fixtures/evidence. No generic factory/trainer/central-metrics edits and no fake STUB experiment CLI.

## Minimal files and interfaces

Create only after root source release: `validation/kernel_stage_b/{__init__,__main__,bootstrap,authority,driver,production}.py`, `README.md`, prospective plan and small tests. `__init__` is empty. `authority.py` is stdlib: `validate_plan(plan)`, `read_verified(root,ref)`, `validate_evidence(evidence,root)`, `entry(plan,root)`, `verify_worker(plan,root,event_path)`. `driver.py` owns record schemas, counts, scoring composition, costs and `execute(plan,backend,checkpoint)`; backend is a concrete object with controlled test double, not a registry. `production.py` supplies `Backend(plan,root)` with `prepare()`, `encode(family,entry)`, `read(candidate,entry,snapshot)`, `score(candidate,entry,numeric,trigger)`; import only after complete worker authority. `__main__.py` exposes `main()`. Static `bootstrap.py` inserts `Path(__file__).resolve().parents[2]` into sys.path, imports B main, and exits with its result. Its source contains no allocation paths/deadlines. `--help` and null-plan refusal work without scientific imports/native calls. Accepted production path performs actual operations; qualification scope returns after imports/baseline with zero model construction, encode, read or factor.

Use these existing signatures verbatim:

```
# famjet/eval/isolation.py
_reconstruct(spec, *, freeze_rates=False)
export_method(method)
_query_record(query)
result_json(result)
# famjet/models/kernel_read_model.py
KernelReadModel(kernel,ridge,fit_provenance,target_statistics,*,prior_scale=5224.)
# famjet/readers/kernel_projection.py
KernelProjection(rates,family,t_ref,*,prior_scale=5224.,ridge=1e-6)
# famjet/data/synthetic.py / eval/runner.py / eval/metrics.py
generate_episode(config: RunConfig,split_seed: int,episode_id: str) -> Episode
episode_policy(episodes)
score_predictions(predictions: PredictionBatch, statistics: dict, policy: dict) -> list[dict]
aggregate_scores(rows: list[dict]) -> dict
# famjet/config.py
load_config(path: Path) -> RunConfig
validate_config(config: RunConfig) -> None
# validation/kernel_stage_a/commands.py / production.py
reader_command(root,event_path,deadline)
owned_reader_dispatch(vector,*,input,stdout,stderr,cwd,env,deadline,event_path,runtime_identity=None)
# validation/kernel_stage_a/monitor.py
record_baseline(path,*,deadline=None)
supervise(command,output,*,outer_seconds=600,output_bytes=67108864,free_disk_bytes=4294967296,
 incremental_bytes=201326592,sampler=process_tree,preparation_output=None,authority_root=None,deadline=None,
 outer_ceiling_seconds=600,candidate_seconds=90)
```

Do not construct new `KernelProjection`: reconstruct sealed exports with `freeze_rates=True`, using existing `from_statics` path. `PredictionBatch` fields are `(history_ids,query_ids,prediction,target,supported,failure,abstained,metadata,schema_version=1)`. Construct numeric B1/Q8/V8 and exact `scoring_v2` context copied semantically from `score_episode`; labels/support remain outside inference. Preserve complete central numeric row schema and aggregate outputs, including null metrics/statuses, policies, provenance and fallback reasons.

Supported execution scopes are exactly binding and panel. Binding imports/baselines only; panel processes every original entry with Q8. Reject feasibility, subsets and Q1 modes. Resource forecasts confer no authority. A later feasibility component needs its own closed subset/shape/count/component contract and release.

Rematerialization uses the exact config/producer/manifest/exposure references pinned in companion design, never an inferred RunConfig. After verified authority and baseline, load the pinned YAML with unchanged `load_config`; preserve full resolved `asdict(base)` in the run artifacts. Its model.precision=float32, training and resource fields are historical generator-validation inputs, not the kernel model or current resource allocation. Do not follow calibration/cache/checkpoint paths in this config.

Define `panel_base=replace(base,development=replace(base.development,eval_histories_per_cell=8))`. For each original manifest entry, in existing order, `g=replace(panel_base.data.generator,namespace='development_fit',regime=entry['regime'])`, `c=replace(panel_base,data=replace(panel_base.data,length=entry['length'],generator=g))`. No other replacement is allowed, including base.seed. RunConfig.__post_init__ and generate_episode._check_exploratory invoke existing validate_config. Require base.data equals manifest.data and each substituted data object equals that base with only these three changes. Require entry.seed=development_fit.root=3626995086544026198 and equals `derive_seed(base.development.data_seed,'task18_development_v2','shared')`; base.development.data_seed stays20261017018. Call `generate_episode(c,entry['seed'],entry['episode_id'])`; verify complete event/query/oracle hashes. This constructs no new history identity and grants no present generation permission.

## Exact transport contract

Request keys: `{method,state,queries,operation:"read",model_hash,source_hash}`. Method/state/query schemas are the existing versioned export/snapshot/query schemas validated by isolation/state_io; freeze ordered query record bytes. Use separate stdout/stderr files and fresh temporary cwd under output. Pass verified runtime explicitly to unchanged dispatch. Hash saved state before/after read, require equality, and check its writer hash against the exact candidate; no source events/labels/auxiliary history enter the request. Set reader deadline=`min(original_deadline,candidate_start+candidate_seconds)` and pass that identical value to command, dispatch and worker, preserving the monitor's candidate-range recognition.

Response exact keys: `{numeric,counts,windows,coefficients,window_vectors,seconds}`. Numeric exact keys: `{prediction,logits,support,failure,diagnostics,schema_version}`; schema1, prediction[1,8,8], logits=null, support[1,8], failure boolean[1,8]. Diagnostics exact keys: numerical_eligible,prediction_valid,numeric_supported,factual_support_available,quarantined boolean[1,8]; failure_code integer[1,8,2] code0–7; reconstructed_mass,cancellation_bound numeric-or-null[1,8,2]. Numeric leaves permit finite numbers/null only; decode null to nonfinite only in numeric tensor positions. Missing fields/wrong types stop. Preserve unavailable support and unused-window nulls, never replace by zero. `_result_from_record` remains worker-internal.

Counts is a map over exactly the worker Trace counter-name allowset (`coefficients,window_vector,snapshot_record,snapshot_from_record,_advance_payload,_reconstruct,read,tensor_clone,factor`), absent means zero; nonnegative integers, emitted counters exactly reconcile, read1/factor0. Require one final result, no trailing records, exit0 and empty stderr. seconds finite/nonnegative.

Window `{code,prediction,mass,bound,raw,reached}`: code0–7; prediction/raw nullable8-vectors; mass/bound nullable numbers; reached exactly five booleans `{coefficients,mass,bound,raw,prediction}`. coefficients is nullable8-vector per executed window; window_vectors is an8-vector per window, or empty where profiling has no preceding vector; retain source short-circuit behavior. Three lists have equal length. Map windows to query order using mean one/contrast up to two windows, code/early-return applicability and saved-state validity; never assume sixteen windows. Validate reached/null consistency. Preserve raw bytes even on failure.

Encode quarantine `Trigger={reason:"nonfinite_stored_state",fields:S[],event_offset:N,parameter_hash:H,input_hash:H,state_hash:H,input:{event_id:N,timestamp:F,key_id:N,values:F[8],observed:bool[8],key_features:F[16],auxiliary:{}},history_id:S}` for this fixed primary panel. Inspect payload+last_time after every event; offset starts1. Retain serialized state and state_ledger logical bytes. Skip transport and create eight NaN raw rows, failure=true, prediction_valid=false,numeric_supported=false,quarantined=true. Central scorer supplies task training mean; no fabricated reader response. Reader/transport/schema failures instead stop with unscored inventory preserved.

The fixed panel has finite validated timestamp metadata. Preserve snapshot serialization/ledger exceptions as infrastructure failures exactly as `score_episode`; never bypass metadata validation to make a malformed state scoreable. Quarantine covers numerical stored payload failure; no later event, advance or reader may run for that family/history. At completion, scored rows equal eight times completed requests plus eight times the number of candidate/history quarantine outcomes; quarantined_histories counts unique family/history triggers. All six candidates still require768 score rows each for selection.

## Source-bound native reuse

Current monitor SHA256=`3c7e4aa237173895245444e1cb66a017275507398a6446133020ad509a00d30e`. Bind commands=`01f1c14f53f5e31cd87640867a730080999c7dc12e5d5bcda2013428514658a0`, production=`20940f1e27702a04e857dc18187a782f223b4f64482a80a81d8c8f7fb2c1c5ab`, reader_worker=`918cd1a6a1b17144dfbc80ac39ee428a05b97ef57dc62a3c87c270ce77085a0b`; manifest binds authority/source_lifecycles and every other source too. Mismatch blocks pending root review; no whitelist or replacement identity algorithm.

Parent stdlib gate verifies nonnull authority, original clock, exact own bootstrap/argv, runtime artifacts and fresh output. Invoke unchanged supervise with explicit `outer_seconds=deadline-now`, `outer_ceiling_seconds=limits.outer_seconds`, `candidate_seconds=limits.candidate_seconds`, allocated output/incremental caps, disk4GiB, preparation_output, authority_root, deadline; leave sampler default. Its bounded finalization remains inside original allocation.

Construct argv only from the frozen template in companion design, with resolved root/bootstrap and plan paths; hash literal argv separately. Source/template hashes remain stable across binding/panel output paths and allocation times. Qualification records its own full Git; later HEAD is separately verified. Root compatibility may bridge nonmaterial archival/document commits only with equal material manifests, never by asserting unequal commits equal.

Use companion C/D definitions for every new content hash. Request bytes=C(request); Ref hashes cover these exact bytes and raw response files. Candidate config hash=request.model_hash=D(original exported method). Writer SHA uses the unchanged kernel preimage: Jet `{kernel:'jet-v1-fixed-shared',rates:represented_cpu_rates.tolist(),key_dim:16,value_dim:8}`; Bank changes kernel to expbank-v1-fixed-shared and adds no_decay:false. Snapshot hash=D(snapshot_record(state)); serialized snapshot checksum=D(body) under existing state_io format. Trigger input_hash/state_hash and manifest event/query/oracle hashes use unchanged synthetic.batch_hash: exclude validation, replace tensors with `{dtype,shape,sha256:SHA256(contiguous_cpu_numpy_bytes)}`, process tensor-valued dictionaries with batch_hash_tensor, then D(record). Statistics/policy hashes=D(exact statistics/policy objects). Package source_hash=D(sorted relative famjet Python path→raw-byte-SHA map). Preserve existing inherited identities; never confuse a semantic hash with a Ref byte hash.

Owned worker emits authority_start; calls unchanged A low-level `git(root,'rev-parse','HEAD',deadline=...,event_path=...)` and `git(root,'status','--porcelain',...)` exactly once each, verifies source/authority, then authority_end(success). Both helpers must complete/reap successfully inside that phase. No A entry/verify, additional Git command or backend import in phase. After success import Torch/famjet/production, set one thread, call unchanged record_baseline before allocation. Use candidate_start/end around each candidate's work including first-family encoding; preserve reader launch/end, observer and owner cleanup events through unchanged code. Qualification uses identical authority/import/baseline branch and no candidate/scientific operation. Inherit existing unknown-child proof by exact byte binding; do not repeat old native control suites.

## Durable outputs

All added records have version1. Append attempt before dispatch; persist completed records atomically within output cap. Hash refs after close; interrupted tails remain raw failure evidence. Types use companion aliases; `Score`/`Summary` are unchanged central numeric-v2 outputs, validated against sealed metrics source, never a replacement schema.

Prelaunch refusal writes only diagnostic stderr and returns2, creating no experimental run. After monitor initialization, an authority failure can create empty score/request/snapshot journals plus the infrastructure failure record using stdlib only; required references then resolve even with zero work. Check ceilings/deadline before each attempt and never retry. Finalization is reserved within the original allocation; preserve partial journals if the process is killed before a full Run can be committed.

```
Snapshot={version,family,history_id,writer_sha256,snapshot:Ref<snapshot>,snapshot_hash:H,
 logical_bytes:N,trigger:Trigger?,event_count:N,encoding_seconds:F}
Request={version,ordinal:N,candidate:S,history_id:S,query_ids:N[8],
 request:Ref<request>,stdout:Ref<bytes>?,stderr:Ref<bytes>?,returncode:int?,
 status:"attempted"|"completed"|"failed",reader_seconds:F?,failure:Failure?}
QueryScore={version,candidate:S,length:N,snapshot_hash:H,request_ordinal:N?,score:Score}
Counts={snapshots_attempted:N,snapshots_completed:N,requests_attempted:N,requests_completed:N,
 worker_reads:N,worker_factors:N,predictions_scored:N,quarantined_histories:N,fallback_rows:N}
Failure={phase:"authority"|"prepare"|"encode"|"transport"|"decode"|"score"|"finalize",
 candidate:S?,history_id:S?,ordinal:N?,exception_type:S,message:S,monotonic:F,
 raw:Ref<bytes>[],remaining:{candidate:S,history_id:S,query_ids:N[]}[]}
Interval={start:F,end:F,owner:"common"|"jet"|"bank"|CandidateID,operation:S,status:"completed"|"failed"}
Cost={candidate:S,complete:bool,direct_seconds:F,family_encoding_seconds:F,
 common_seconds:F,standalone_total_seconds:F,intervals:N[]}
Combined={candidate:S,status:"ok"|"infinite_loss"|"undefined_loss"|"incomplete",loss:F?,
 infinite_loss_count:N,has_infinite:bool,has_undefined:bool,query_count:N,complete:bool}
Run={version,plan_sha256:H,status:"COMPLETED"|"INFRA_STOP",counts:Counts,
 resolved_panel_config:Ref<resolved_run_config>?,
 snapshots:Ref<jsonl>,requests:Ref<jsonl>,scores:Ref<jsonl>,failure:Failure?,
 summaries:{candidate:S,length:N,summary:Summary}[],combined:Combined[6],costs:Cost[6],intervals:Interval[],
 campaign_seconds:F,selection:{jet:S?,bank:S?},exclusions:{candidate:S,reason:S}[],
 start_monotonic:F,end_monotonic:F,source_manifest:Ref<source_manifest>}
BindingReport={version,status:"PASS"|"FAILED",plan_sha256:H,source_full_git:G,
 source_manifest:Ref<source_manifest>,template_sha256:H,argv_sha256:H,
 monitor:Ref<A_monitor>,events:Ref<jsonl>,journal:Ref<jsonl>,external:Ref<A_external>,
 counts:{constructions:0,encodes:0,reads:0,factors:0,predictions:0},failure:Failure?}
```

Final wrapper retains run and monitor separately, plus external elapsed/returncode through commit; never synthesize monitor success. No selection on infrastructure stop. Disjoint measured intervals partition entire allocated wall time, including startup, verification, rematerialization, scoring and finalization. Charge common intervals fully to each standalone configuration, family encoding fully to each matching configuration, direct intervals only to their candidate; campaign charges each interval once. Failed costs persist; incomplete candidates cannot win. Binding costs stay separately visible. resolved_panel_config stores C(asdict(base)) with every RunConfig field, null only if stopped before config load; its Ref hash=D(asdict(base)).

Length policies explicitly contain `{version:2,primary_tasks:["contrast","mean"],support_calibration:null,expected_inventory,task_weights:{contrast:0.5,mean:0.5},regime_weights}`; inventory cells are `{history_id,replicate:0,regime,tasks:{contrast:N[],mean:N[]}}`, with exactly the original query IDs. Regime weights are0.25 each. Context exact keys are version,output_convention,present,tasks,target_valid,numeric_supported,prediction_valid,quarantined,quarantine_trigger,method,replicate,regime,target_semantics,manifest_hash,statistics_hash. Set output_convention=numeric and target_semantics=observed_event_targets_v2; derive actual masks from recorded response/episode, abstained=false. Never derive support from numerical eligibility.

`Summary` has central keys status,loss,infinite_loss_count,query_count,fallback_count,native_by_task,categorical_by_task,coverage,selective_risk,coverage_weighting,history_order,replicate_order,history_weights; numeric mean/contrast yields empty categorical_by_task. Keep native task status/nullable metrics verbatim. Central Score includes its full version2 policy and provenance, target/raw/final prediction, support/validity/failure/quarantine/fallback/abstention flags/reasons, loss_status/infinite_loss and native metric flags; do not project it down to loss alone. Validate complete inventory before aggregate_scores. Combine finite length losses as an overflow-safe equal-third mean, preserving undefined-first then infinite precedence and both evidence flags. Partial rows cannot produce a partial-loss winner. Terminal request/scoring errors retain attempted ordinal and all remaining identities; no fallback rows are invented for missing work.

## Source acceptance checks

TDD only with small controlled stubs, AST and stdlib fixture metadata: null refusal/import order, exact bootstrap/Git lifecycle, tamper/path escape, candidate/inventory mapping and all24 dispositions, exact config reference/substitutions, canonical hash vectors including Unicode argv, rejection of feasibility/subsets/Q1, response order/shapes/nulls, quarantine skips reads/eight scores, infrastructure stop, counters/caps/deadline, finite/infinite/undefined composition, exact ties/cost charging. Small central-API unit fixtures may run after source authorization; no actual panel/materialization, large campaign, native processes, models or factors. Source acceptance includes independent review and preservation hashes. Root separately releases and assesses one empty native binding; full96/Q8 panel release is last. HOLD.
