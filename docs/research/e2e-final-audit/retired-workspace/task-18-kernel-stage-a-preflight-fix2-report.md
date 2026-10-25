# Task18 external Stage A preflight — fix2 implementation report

Status: implementation and focused verification complete; independent review and execution authority remain pending. This report addresses only fix1 review F2/N1, live authority-helper RSS enforcement. It does not self-accept the source or release Stage A.

Base: `dd0b33927cce8abe254adc06e652263d835d20bf`. Source commit: `288ffa33ac0477f65c19bde4b0138b8b4e9ccbf3`. The controlling [fix2 brief](task-18-kernel-stage-a-preflight-fix2-brief.md) and full [fix1 review](task-18-kernel-stage-a-preflight-fix1-review.md) were read. Earlier evidence and reports remain unchanged, except the original report receives a link to this record.

## Exact change and authority boundary

Only `validation/kernel_stage_a/monitor.py` and the new focused test file change executable/test source. The same contemporaneous exact classifier result used to enforce foreign-process rejection now records `sampled_authority_helper` for an observed, admitted helper. Reconciliation charges that retained helper's absolute peak at baseline zero immediately, together with full authority-Python RSS. The charge persists if completion or group termination precedes a helper-end event. Existing completed-helper reconciliation remains in force.

The retained charge is resource evidence, not permission to remain alive. Historical/final identity classification is unchanged; a missing required completion/declaration still fails closed. Later foreign identity samples still stop immediately. No historical helper is globally marked active, and no executable, parent, argument, phase or lifetime exception is broadened. The existing conservative sum of retained peaks is preserved; these tests do not establish real process-tree peaks between samples.

The selected authority design remains the reviewed distinct monitored pre-backend child phase: full live HEAD/clean-source/runtime/helper verification finishes before backend entry; the parent performs schema/null/deadline entry checks. Only the two source-defined exact read-only Git commands are eligible during that phase. Authority Python and admitted Git helpers have baseline zero; later numerical Python workers still require post-import/pre-allocation baselines. The original shared 600s deadline, 90s candidate limit, 201326592-byte incremental cap, 67108864-byte output cap and 4294967296-byte free-disk prerequisite are unchanged. No helper subsystem or protocol was added.

## Actual RED/GREEN and covering evidence

All pytest invocations used `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest -q`. The targeted selection was `tests/test_kernel_stage_a_preflight_fix2.py`.

| Evidence | Exit | Actual outcome |
| --- | --- | --- |
| `live-helper-red.log` against original monitor | 1 | 2 failed in 0.49s: the live cap case reached outer timeout; foreign-stop reconciliation retained only 60 rather than 130 bytes |
| `live-helper-green.log`, first post-fix check | 1 | 2 failed in 0.04s solely at direct returned-dict versus JSON-dict equality; all preceding charging/cap assertions passed |
| `live-helper-green-final.log` | 0 | 2 passed in 0.03s after comparing JSON semantics, accounting for existing integer PID keys becoming JSON string keys |
| `cover.log` | 0 | 15 passed in 1.64s |

The new controls use a real owned sleeping Python process and synthetic exact Git identity/RSS records; they do not launch Git. Python RSS60 and helper RSS70 each fit the synthetic100-byte cap, but their sum130 stops for the memory cap before any helper-end event, within the asserted0.2s bound. A second case stops for a definitively foreign identity under a higher cap and still retains130. Both assert killed owned process, empty completed-helper ledger, absence of helper-end, helper baseline0/increment70, full authority/increment peak130, and durable/returned JSON-semantic equality. All values are controlled test data, not native measurements or feasibility estimates.

The covering selection retains exact authority/foreign checks, late/completed-helper reconciliation, final report-overflow parity, bounded hung observer/Git cleanup, baseline deadline propagation, full simulated source verification through authority-end/backend gate, wrong Python argv rejection, process-group/output cap behavior and exact observer identity checks. The existing full authority-launch control uses a temporary Git simulator and a nonnumerical callback. Exact command vectors, selected node IDs, exit codes, file hashes and log sizes are recorded in [fix2 verification JSON](../../../docs/research/task18-kernel-stage-a-preflight-fix2-verification.json). No broad suite was run.

Fresh compile, `git diff --check`, and `git diff --exit-code dd0b33927cce8abe254adc06e652263d835d20bf -- famjet/ requirements.lock validation/kernel_stage_a/descriptors.py validation/kernel_stage_a/fixture-descriptors.json validation/kernel_stage_a/frozen-training-metadata.json` all exited0 with empty stdout/stderr; their command/output records are preserved beside pytest logs. Git source-control inspection/commits were performed; the native runtime authority/monitor integration was not invoked.

## Exact identities

Accepted whole-package SHA256 was recomputed from the canonical sorted path-to-Python-file-hash mapping using the standard library, without importing production code: `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. Lock SHA256 remains `2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1`.

Current monitor SHA256: `6f30f22772777858791cc30ad2b72f908311591005a6a923f03ddc6257e049c5`. Prior monitor SHA256 and every current helper/test/input hash are in the verification JSON. AST-extracted source text for `classify`, `process_tree`, and `record_baseline` matches the base exactly; their SHA256s are retained there. The prospective seal is unchanged and remains non-authorizing; it must not be used as a fresh launch identity.

Raw log SHA256s:

| File | SHA256 |
| --- | --- |
| `live-helper-red.log` | `7fdf4d3501416fa4f7bedbbc9abaefac6b22cec05c076f570f5319117825dab2` |
| `live-helper-green.log` | `13373a39be01c47b5479b1a02d01d48959e926df1be0453a57024a20ee382b00` |
| `live-helper-green-final.log` | `149e983c325e1215d8fe411fd58fb9c0fa38bc5dfa119c4a6a92d44ee61e3e10` |
| `cover.log` | `c14a58c874335cdf5a2c5b3673f456c1ad4d0b7da65f61be9706a2b668cb7d34` |

Logs live under `docs/research/task18-kernel-stage-a-preflight-fix2-logs/`. The initial RED test snapshot was not separately hashed; the retained raw failure log shows the executed source/assertion locations. The final test hash and source commit are recorded exactly. The intermediate test adjustment changes only JSON-semantic equality and its explanatory comment, not resource assertions or production behavior.

## Remaining fields and limits

`implementation_review`, `represented_rate_records`, `static_exports`, `resource_measurement_boundary_seal`, `fresh_launch_snapshot`, `output_directory`, and `root_stage_A_release` remain null. No actual factor/rate export, fixture snapshot, production fixture read, Decimal fixture grid, scientific/model backend, training/refit/panel/corpus/protected execution or native numerical profile occurred in fix2. No dependency, cache, frozen statistic, fixture descriptor or `famjet/` file changed.

Root's separate own-Python OS-format observation found truncated `comm` and a framework-launcher display. Native executable/display/parser policy was not changed here. Exact native stage/reader identity integration and monitoring context remain prerequisites; controlled sampler evidence does not resolve them. Actual setup of six factors, the shared original preparation/deadline boundary, native monitoring and final scientific authority remain root-owned pending work. F1/F3/F4/F5/F6 and the identity/phase portions of F2 were not reopened. No policy ambiguity or additional scope request arose in this round.
