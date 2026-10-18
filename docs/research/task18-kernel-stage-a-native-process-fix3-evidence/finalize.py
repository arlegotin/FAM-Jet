"""Finalize documentary records from retained bytes only; no probe/test execution."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path.cwd(); scratch=Path('/tmp/task18-native-fix3'); dest=ROOT/'docs/research/task18-kernel-stage-a-native-process-fix3-evidence'
v=json.loads((scratch/'verification-draft.json').read_text())
sha=lambda raw:hashlib.sha256(raw).hexdigest()
for entry in v['artifact_status']['pruned_early_specimens']:
    entry['scope']='all transient control output directories under this pytest root; none copied or recreated'
    entry['source_status']='current focused source retains exercised inputs/logic; raw RED traces retain failing function text; no byte-exact early whole-file snapshot claimed'
logtable='\n'.join(f"| `{a['log']}` | {a['exit_code']} | {a['summary']} |" for a in v['attempts'])
specrows=[]
for name,spec in v['specimens'].items():
    if not name.startswith('final/'): continue
    summary=spec['summary']; authority=summary.get('authority_full_rss_peak_bytes','emergency omitted')
    specrows.append(f"| `{name.removeprefix('final/')}` | {spec['directory_bytes']} | {spec['verdict_bytes']} | {summary['status']} | {authority} | {summary['incremental_worker_peak_bytes']} |")
whitespace=scratch/'packaging-whitespace.txt'
packaging=f"The evidence-index whitespace check returned exit2 for unmodified raw pytest output and fixed-reservation padding; its exact {whitespace.stat().st_size}-byte diagnostic is retained as `packaging-whitespace.txt`. It ran before adding that diagnostic and this final documentary update. Authored source/report/JSON checks are separate exit0 checks." if whitespace.exists() else 'Evidence-index whitespace check pending packaging; authored source checks exit0.'
report=f'''# Task18 native process fix ROUND3 — N1 phase attribution

Source implementation submitted for scoped review; no source self-acceptance or scientific release. BASE `1b0bb18aed81bcb88a0faec5f6d56397fb2de5d7`; source commit `{v['source_commit']}` on current `main`. Final relevant covering: **64 passed, 24 deselected, 2.93 s**, exit0. Native functional attempts0, scientific factor constructions0, scientific/model reads0. This is synthetic accounting evidence, not native memory measurement, a full Stage A pass, ordinary-reader viability or release.

## Binding scope and final behavior

Read the complete root fix3 brief and fix2 review before writing source. Both exact inputs are retained in `task18-kernel-stage-a-native-process-fix3-evidence/contract/`. F1/F2 remain closed; this round addresses only N1 and the specifically authorized adjacent authority-root charge branch. Lifetime work remains HELD. No authority/commands/production/source-admission or numeric request/response change.

Early numeric recovery now updates only raw RSS maxima, per-PID numerical totals, parent/native markers and an explicitly unresolved initial label. It neither reads the mutable semantic authority flag nor performs ordinary role-based charging. Source byte/deadline bounds and separate completeness/identity labels remain unchanged. Semantic copying still validates the ordered start/end events, and settled/pending reconciliation uses the actual sample interval against those boundaries. A root sample attributed to authority retains its own RSS in `authority_phase_peak_bytes`; that value supplies the full authority charge. An interval spanning authority end is conservatively included in full.

The necessary adjacent correction is explicit: `charge()` formerly used the root's whole-lifetime maximum for `authority_worker`. Raw recovery may already have observed a later post-end sample before an earlier authority sample is reconciled, so that exact branch must instead use the interval-attributed authority peak. The new no-baseline control retains authority RSS80 alongside later post-end raw RSS500: authority stays80, while missing-baseline/final conservative charging remains500. This branch is not a cap relaxation or broad resource-model redesign.

Failed copying of an authority boundary/witness does not supply phase attribution or identity from raw data. The raw known per-PID peak sum is charged conservatively even for a bounded `_MonitorStop` copy failure. Thus the post-end source RSS500 remains charged in full on failure while authority stays at its genuinely established0 or60. Newly seen raw-only PIDs retain an unresolved role even if final copying fails before normal charging; an intermediate regression omitting that label was observed and corrected without weakening the preserved F1 test.

The monitor adds one root RSS integer to each already-retained pending sample batch, using the sampled numeric reading rather than requiring an RSS field in the explicit synthetic identity seam. It adds no journal/file, raw duplicate, whole-history scan, generic observer mechanism or identity cache. Existing source/event/evidence bytes, bounded final reservation and collection/reconciliation/encoding time remain inside the original launch budget. Control directory byte counts below include original source journal, accepted copied evidence, logs, padding, finish sentinel and reserved verdict.

## Exact commands, RED/GREEN and covering evidence

All raw logs are retained byte-for-byte in `docs/research/task18-kernel-stage-a-native-process-fix3-evidence/`:

| Log | Exit | Actual result |
|---|---:|---|
{logtable}

RED command (before implementation):

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix3.py
```

RED produced four failures: post-end RSS500 wrongly became authority500, both without a previously settled authority root (expected0) and with earlier genuine authority60 (expected60), including refused authority-end copying. The positive overlap control passed on BASE. First GREEN attempt and corrected focused GREEN used:

```sh
.venv/bin/python -m pytest -q tests/test_kernel_stage_a_native_process_fix3.py tests/test_kernel_stage_a_native_process_fix2.py
```

The first attempt passed the five new cases but failed two preserved F1 controls with a missing unresolved `role` key (10 passed,2 failed). Restoring the explicit unresolved initial label yielded12 passed. Initial relevant covering yielded63 passed/24 deselected. Self-review then added one adjacent-branch control for an authority-overlap80 sample and later unbaselined500 sample. Its focused command was the RED command above, yielding6 passed; this new control justified the final covering repeat:

```sh
{v['focused_command']}
```

Final output is preserved exactly in `final-focused.txt`:64 passed/24 deselected in2.93s. The full repository suite was not run. Additional exit0 checks:

```sh
.venv/bin/python -m py_compile validation/kernel_stage_a/monitor.py tests/test_kernel_stage_a_native_process_fix3.py
git diff --check
git diff --cached --check
.venv/bin/python /tmp/task18-native-fix3/audit.py
```

The staged source check preceded the source commit. `py-compile.txt` and `source-whitespace.txt` retain exit0. `audit.py`, its exact output and `prior-byte-inventory.json` retain the pure-file verification body/results. A read-only initial `sed` attempt used a nonexistent `tools/.../monitor.py` path (exit1); an exploratory glob for nonexistent prior evidence `*.py` was rejected by zsh. Both were corrected by locating/reading the actual paths; neither changed source or executed a probe.

{packaging}

## Actual final controlled specimens

These are real retained outputs from final pytest root `pytest-4359`, copied with original→durable SHA256/byte mappings. Every returned verdict matched its durable JSON in the controls. Source rows in the principal N1 tests are ordered `authority_start → authority_end → observer_sample → baseline`; the sample's start is strictly after authority_end. The start is ingested in an earlier monitor poll. The four variants independently cover no prior settled authority RSS versus prior60, and successful versus refused boundary copying.

| Final specimen | Directory bytes | Verdict bytes | Status | Authority RSS | Conservative/incremental RSS |
|---|---:|---:|---|---:|---:|
{chr(10).join(specrows)}

Successful post-end baselines500 contribute raw absolute/peak-sum500 without authority inflation or false cap100 stop; worker baseline500/increment0. Actual authority80 overlap remains charged80. The unbaselined post-end500 control stops conservatively, preserving authority80. The cap/encoding cases retain full980 (root80 + inner observer900), numerical COMPLETE/identity incomplete. Deadline/storage/partial/truncation controls retain only known70 and explicitly FAILED/incomplete accounting; no unavailable900 bound is invented. The512B emergency retains its explicit raw-refusal flags/count/RSS. Existing strict later-Python-ESRCH, exact helper identity, deadline, cleanup, settled/pending, output and initialized exact-five-file controls remain in the passing covering set.

## Packaging status and limitations

All six raw attempt logs were saved immediately and are durably retained. Actual surviving specimens are copied from `pytest-4357` (initial covering), `pytest-4358` (adjacent focused GREEN) and `pytest-4359` (final covering): **33 selected actual output directories**, with all files copied exactly. `specimens.json` records summaries and actual bytes; the verification JSON records each original→durable mapping and a full durable artifact hash/byte inventory. Original surviving files were not moved or rewritten.

Pytest automatically pruned the entire transient roots `pytest-4354` (RED), `pytest-4355` (failed first GREEN) and `pytest-4356` (corrected focused GREEN) before packaging. **Their output specimens are missing and are not claimed byte-preserved.** None was recreated and no test was rerun for packaging. RED's five transient control directories were the four `test_post_authority_baseline_b0..b3` directories and `test_source_sample_overlapping0`; each focused12 run additionally included the three `test_late_inner_rss_survives_f0..f2`, `test_unscanned_complete_source0`, and three `test_unrecoverable_source_jour0..jour2` controls. This is a packaging limitation, not scientific evidence. Raw logs and current deterministic test inputs/logic remain; the raw RED traces retain failing function text. No byte-exact earlier whole-test-file snapshot is claimed. Artifact-status fields explicitly distinguish those missing outputs from retained final specimens.

Source-only checks and reports are distinct from raw-padding whitespace. Prior reports/verifications/evidence were left untouched. The173-file inventory compares all tracked `famjet/` bytes, prior native/fix1/fix2 evidence/reports/verifications, frozen metadata/seal/descriptors/lock, authority/commands/production/entrypoint and preflight source acceptance against BASE. Package remains `{v['package_sha256']}`. The source commit has exactly monitor, README and new focused test paths. Documentary packaging postdates that source commit and all test specimens; it makes no new runtime claim.

Required report `.superpowers/sdd/2026-10-16-famjet/task-18-native-process-fix3-report.md` is equal to the durable `docs/research/task18-kernel-stage-a-native-process-fix3-report.md`. Verification is `docs/research/task18-kernel-stage-a-native-process-fix3-verification.json`. Limits remain600s outer/90s candidate/201326592B net/67108864B output/4294967296B free/CPU64/at most4 numerical threads. Runtime/helper identities here are deliberately synthetic test values; prior native observations remain bound to their earlier snapshot.

Scientific nulls remain `implementation_review`, `represented_rate_records`, `static_exports`, `resource_measurement_boundary_seal`, `fresh_launch_snapshot`, `output_directory`, `root_stage_A_release`. Conservative Python ESRCH policy is unchanged: every applicable sample needs its own successful proof, so an exited never-proved process and an earlier-proved process with a later ESRCH still fail the mandated unresolved later-sample check. No proof cache/generation protocol was added. Existing sampled-RSS/allocator-peak, path-file/mapped-image and both-final-writes-storage-failure limitations remain. Root owns scoped review/acceptance, future viability/lifetime decisions and any scientific release.
'''
original=ROOT/'.superpowers/sdd/2026-10-16-famjet/task-18-native-process-fix3-report.md'
durable=ROOT/'docs/research/task18-kernel-stage-a-native-process-fix3-report.md'
original.write_text(report); shutil.copyfile(original,durable)
v['mappings'].append(dict(original=str(original),durable=str(durable.relative_to(ROOT)),sha256=sha(durable.read_bytes()),bytes=durable.stat().st_size))
# Preserve this documentary construction body; excluded from its own contents/hash.
for src in [scratch/'finalize.py',whitespace]:
    if src.exists():
        dst=dest/src.name; shutil.copyfile(src,dst)
        v['mappings'].append(dict(original=str(src),durable=str(dst.relative_to(ROOT)),sha256=sha(src.read_bytes()),bytes=src.stat().st_size))
v['checks']=dict(py_compile_exit=0,source_diff_check_exit=0,source_staged_diff_check_exit=0,byte_audit_exit=0,
 evidence_staged_diff_check_exit=2 if whitespace.exists() else None,raw_whitespace_preserved=True)
v['artifacts']={str(p.relative_to(ROOT)):dict(sha256=sha(p.read_bytes()),bytes=p.stat().st_size) for p in sorted(dest.rglob('*')) if p.is_file()}
v['artifacts'][str(durable.relative_to(ROOT))]=dict(sha256=sha(durable.read_bytes()),bytes=durable.stat().st_size)
(ROOT/'docs/research/task18-kernel-stage-a-native-process-fix3-verification.json').write_text(json.dumps(v,indent=2)+'\n')
print(f'Wrote equal report copies; {len(v["artifacts"])} artifacts, {len(v["mappings"])} mappings')
