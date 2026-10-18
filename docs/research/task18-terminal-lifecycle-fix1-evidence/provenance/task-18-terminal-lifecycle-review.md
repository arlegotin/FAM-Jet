# Task18 terminal lifecycle: fresh SPEC and QUALITY review

Review date: 18 October 2026. Scope: BASE `1bc005abe7b323c7cc76358adecc6e71346296d2` through delivered HEAD `4815000fef3060f88518a8577713a0085aebb1f4`; production source `3044f3ca0cd935b4e3e53863cbe259fdcacd4c38` and input correction `9550cf38f12915ff81a261ff5372febf26d294d4`.

**SPEC verdict: NEEDS CHANGES / native acceptance gate incomplete.** The main ownership, proof and terminal ordering implements the adopted design, and the input-only correction respects its boundary. Two failure paths below remain inconsistent with the required helper cleanup and first-failure guarantees. Independently, required native compatibility is not established: both attempted controls remain NEEDS_CONTEXT and both survivor cases are NOT RUN.

**QUALITY verdict: NEEDS CHANGES.** Two Important findings, no Critical findings. The numerical helper is narrowly scoped and the ordering is substantially clearer, but helper termination after a wait error and preservation of the primary reason through emergency finalization need correction. This is a source review, not root acceptance, scientific release, or authorization to rerun native controls.

## Findings

### Important R1: a helper wait failure after clean EOF never triggers helper termination

Location: `validation/kernel_stage_a/monitor.py:365`, especially lines 367–371; direct caller at line 815.

The cleanup helper is killed only when `errors` is already nonempty **before** its owning wait. If stdout and stderr both reach EOF without a read error, `errors` is empty, so the code skips `probe.kill()` and calls `probe.wait(...)`. If that wait raises while `probe.returncode` remains None, the exception is added to the error list, the streams are closed and an unsuccessful observation is returned. There is no subsequent kill or owning wait attempt for that helper.

EOF is not an exit/reap certificate. The process can close its pipes and remain alive, or be delayed/stopped after closing them. A timeout from the owning wait is precisely the case in which teardown must not assume exit. The actual helper is launched in the supervisor's group, whereas the worker root is launched with `start_new_session=True`; the later `killpg(process.pid, ...)` therefore cannot clean up this helper. The result honestly stays incomplete, but the supervisor can return with a still-live source-owned helper for which it never attempted termination.

This violates the adopted helper requirement to always attempt helper cleanup/reap. It is a defect in the new helper, separate from root lifecycle and defunct-row policy. The existing helper timeout control keeps a pipe open, so its timeout occurs during the drain and exercises the earlier kill branch; it does not cover this post-EOF wait failure.

Smallest correction: on an unsuccessful owning wait, retain the original error and, while the helper remains unreaped, attempt its nonblocking termination and an independently protected owning wait with only the remaining original helper/deadline allowance. Preserve actual kill/wait errors, actual elapsed time and reaped false if cleanup cannot finish. Grant no new grace interval and do not fabricate a helper completion. Add the focused EOF-then-wait-failure regression.

Evidence: the single reviewer control below extracts only the two new functions into an isolated namespace, supplies EOF on both fake pipes, and makes the fake owning wait fail with returncode None. It records **one wait, zero kill calls, reaped false**. No real child/native observation was used.

### Important R2: emergency finalization still replaces an established first violation

Location: `validation/kernel_stage_a/monitor.py:987`–988, with `emergency()` at line 870 and the changed first-failure handling at lines 753–767.

The new `failure()` correctly preserves an existing reason, and the changed deadline branches also preserve it. However, if the final JSON encoding or `_commit_monitor()` fails, the final exception handler builds its durable result with `emergency(str(exc) ... else 'monitor serialization/write failure')`. `emergency()` writes that supplied string as the sole reason; the already-established `reason` is ignored.

Concrete failure path: reconciliation establishes `incremental worker memory cap`; cleanup records an additional error while preserving that cap; final `_commit_monitor()` raises an OSError; the fallback succeeds and returns a STOPPED verdict whose reason is only `monitor serialization/write failure`. The primary cap and separate cleanup diagnostics disappear from that returned/durable verdict. The same loss occurs on a final encoding/output-cap exception, which substitutes the later `_MonitorStop` text. A final write/encoding failure is already an explicit supported seam in `tests/test_kernel_stage_a_native_process_fix1.py`; its existing coverage does not combine that failure with a pre-existing primary violation.

This final writer is inherited code, but it is a direct terminal dependency of the newly required first-failure guarantee. The change updates failure handling and final timeout reason selection while leaving this final replacement path intact. This finding does not reopen the old identity/lifetime review.

Smallest correction: when a primary reason already exists, preserve it in the emergency verdict and retain a bounded secondary finalization-failure indicator within the existing reservation. Use the emergency failure as primary only if no earlier violation exists. Verify a primary cap followed by final encoding/write failure; preserve one durable returned verdict and all existing byte/deadline constraints. This finding is established by the source path; no second reviewer test was run.

## Scope and evidence checked

Read the review brief first; all four task/clarification briefs; the binding numeric-only lifecycle adoption; the stopped01 diagnosis and initial/addendum design documents; both implementer reports in full; and both independent root verification records. The adoption overrides the older full-argument helper proposal. No unadopted defunct-state proposal was used as a requirement.

Read the complete nine-path authored-source supplement once, rather than scanning the 10.7 MB archival diff. Checked the corresponding current source, line-numbered helper/supervisor/accounting boundaries, and the directly used authority launch and unchanged Python lifetime proof/end methods. The exhaustive source hashes, byte preservation, worker-body equivalence and package digest remain grounded in the supplied independent root audits; this review did not duplicate their archival inventory.

Read selected actual native journals/results from both attempts, including the ordinary raw root rows, numeric query rows, helper source/image/completion witnesses, ownership boundary, signal/poll/wait/end and terminal resolutions. Also checked retained focused02, failure-followup and launch-green test outputs against report claims. No Git mutation, source change, native control, scientific operation, suite repeat, project import, subagent or archival crawl occurred. The only new execution was the isolated synthetic check described below. This report is the sole review artifact written.

## Source behavior that satisfies the binding design

- Ordinary `PS_ARGV` remains unchanged. The extra exact four-column vector is private to supervisor cleanup; worker classification does not gain admission for it. Numeric rows never supply Python image proof or invented raw comm/args.
- The helper bounds combined captured stdout/stderr to min(1 MiB, remaining allowance), uses nonblocking bounded reads, retains an overflow detection byte count, validates the full numeric table before claiming completeness, and rejects duplicate/malformed/truncated/nonzero/denied/incomplete output. Selected rows cover the owned PGID regardless of PPID plus the actual helper. The captured raw bytes, parse outcome and interval are journaled under the existing output accounting.
- Existing authority utilities verify the helper executable hash immediately before launch. Distinct source launch and completion witnesses retain PID, parent, exact vector/hash and launch ID. Native helper image lookup must match the expected image, or use the narrow real ESRCH plus actual source-owned completion route; other errors/contradictions do not admit it.
- Known selected RSS is recorded numerically before a cleanup journal append can refuse it. Refusal forces conservative known costs. Helpers are charged as overhead only with admissible evidence; surviving non-root numeric members are not silently treated as Python workers.
- Native loop headers no longer poll/reap. Valid current root proof is preserved while owned, subject to generation, failed-PID and identity-completeness guards. Terminal/absent-root observations enter cleanup before the retained terminal row is reconciled.
- Membership precedes root release and required group signal. Complete empty membership skips the nonexistent-group signal; survivors require cancellation under retained ownership; root-only terminal membership permits the bounded nonblocking owning poll. Poll None retains unsuccessful conservative treatment. All group signal paths check the owning returncode before signaling; they do not signal a released numeric PGID.
- Root wait and truthful end bookkeeping are nested independently of observation and signal success. Integer owning returncode is mandatory. Idempotence prevents duplicate actual ends; terminal reconciliation follows successful end publication. Earlier identity/resource failures remain sticky through ordinary cleanup and final deadline checks, subject to R2's emergency path.
- The deadline clarification is implemented: a budget check cannot prevent the immediate signal required for an already-owned group. Waits consume only the original remainder; exhausted cleanup cannot manufacture end or successful completion.
- Changed synthetic reader seams now supply explicit root lifecycle rows and explicit membership, retain reader sample counts and failed-provenance/identity/cap expectations, and do not claim native compatibility. The behind-owner reap seam now correctly expects unsuccessful ownership-supported cleanup. The baseline assertion selects the reader PID instead of the newly present root baseline.
- The file correction changes the committed control inputs only: exact old worker body, file-based isolated vector, adjusted repository root and pre-spawn input hashes/AST checks. Strengthened survivor assertions require natural root status 0, no selected root membership, queried child reparenting/correct PGID, owned signal and sole-descendant EOF. These assertions remain unexercised natively.

## Verification and native gate: accepted limits

Historical broad cover remains **121 passed, 12 failed out of 133**. The targeted followup remains **43 passed, 1 failed**; its failed assertion selected the new root baseline instead of the reader baseline, followed by a retained one-node pass. The refused-launch initializer regression has retained RED/GREEN evidence. Focused02 reports 31 passing controls. There is no new all-pass 133-test result, and this review makes no aggregate rerun claim.

The first native attempt (`t18n-0zr5z837`) failed the exact multiline display check: actual ps escaped source newlines. Its raw evidence nevertheless records a complete numeric query under ownership, live root plus helper, successful group signal, actual owning wait -9 and one truthful matching end. That is failed-case cancellation evidence, not successful natural exit or survivor validation. Overall NEEDS_CONTEXT; survivor NOT RUN.

The corrected attempt (`t18f-ot0owjzs`) has real live exact file-vector/kernel-image proof. The later ordinary row is literally `raw_comm='<defunct>'`, `raw_args='<defunct>'`, RSS 0, same PID/parent, and native lookup errno ESRCH. Numeric cleanup is complete and selects the root's RSS0 row plus the actual helper: it is **root-only membership, not empty membership**. Actual root poll returns 0; journal index 9 contains the one truthful end, before terminal resolution index 12. The owning wait also returns 0. No signal, cleanup denial or peer-close fallback occurs. The unchanged strict classifier still marks the tombstone unaccounted, yielding STOPPED / foreign process identity. Overall NEEDS_CONTEXT; survivor NOT RUN.

These actual rows corroborate the reported ordering improvement while establishing that the required native compatibility objective is **unfulfilled**. The strict classifier/unchanged PythonLifetimes terminal-state limitation is inherited and is being handled as a separate architecture question. This review neither proposes a defunct admission policy nor treats any unadopted policy as binding. Root acceptance remains pending independently of R1/R2.

Package digest remains the root-verified `15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050`. Original failed setup/factors remain failed evidence. No protected/scientific allocation is reopened. Sampled trusted-source monitoring does not certify continuous process identity, OS birth tokens, containment, allocator peak, unsampled spikes, parent/supervisor RSS or scientific resource feasibility. CPU64 means CPU float64 arithmetic, not a 64-CPU host.

## Single reviewer synthetic check

Reason for execution was announced before running it: retained tests cover drain timeout, but not clean EOF followed by owning wait failure. Command: `.venv/bin/python -B -` with the following stdin. Exit 0; no filesystem outputs or project imports, real child launches or native syscalls. AST extraction executes only the two named function definitions with isolated fake dependencies.

```python
import ast, errno, json, types
from pathlib import Path
path=Path('validation/kernel_stage_a/monitor.py')
tree=ast.parse(path.read_text())
body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_parse_cleanup_numeric','_cleanup_observation')]
calls=[]
class Clock:
    value=100.
    def monotonic(self):
        self.value+=.001
        return self.value
clock=Clock()
class Stream:
    def __init__(self,fd): self.fd=fd
    def fileno(self): return self.fd
    def close(self): calls.append(['close',self.fd])
class Probe:
    pid=42
    returncode=None
    stdout=Stream(10)
    stderr=Stream(11)
    def kill(self): calls.append(['kill'])
    def wait(self,timeout):
        calls.append(['wait',timeout])
        raise TimeoutError('helper remains alive after both pipes closed')
probe=Probe()
class Selector:
    def __enter__(self): self.keys={}; return self
    def __exit__(self,*args): pass
    def register(self,stream,event,name): self.keys[stream.fd]=types.SimpleNamespace(fd=stream.fd,fileobj=stream,data=name)
    def get_map(self): return self.keys
    def select(self,timeout): return [(key,1) for key in list(self.keys.values())]
    def unregister(self,stream): del self.keys[stream.fd]
reads={10:[b'1 0 1 3\n42 7 7 2\n',b''],11:[b'']}
artifact={'path':'/bin/ps','sha256':'x'}
def launch(argv,expected):
    return dict(parent=7,argv=argv,launch_id='one',launch_start=clock.monotonic(),reaped=False)
def image(pid):
    return dict(status='ok',**artifact,lookup_start=clock.monotonic(),lookup_end=clock.monotonic())
ns=dict(time=clock,os=types.SimpleNamespace(set_blocking=lambda *a:None,read=lambda fd,n:reads[fd].pop(0),getpid=lambda:7),
        selectors=types.SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1),
        subprocess=types.SimpleNamespace(Popen=lambda *a,**k:probe,PIPE=-1),
        authority=types.SimpleNamespace(helper_launch=launch,process_image=image),
        _MonitorStop=RuntimeError,_CLEANUP_ARGV=['/bin/ps','-axo','pid=,ppid=,pgid=,rss='],errno=errno)
exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),ns)
result=ns['_cleanup_observation'](1,{'helpers':{'ps':artifact}},deadline=101.,output_limit=1024)
assert result['complete'] is False
assert probe.returncode is None
assert not any(call[0]=='kill' for call in calls)
assert len([call for call in calls if call[0]=='wait'])==1
print(json.dumps(dict(case='helper EOF followed by owning wait failure',calls=calls,
    complete=result['complete'],reaped=result['helper']['witness']['reaped'],
    returncode=result['helper']['witness']['returncode'],error=result['error']),indent=2))
```

Full output:

```json
{
  "case": "helper EOF followed by owning wait failure",
  "calls": [
    [
      "wait",
      0.9919999999999618
    ],
    [
      "close",
      10
    ],
    [
      "close",
      11
    ]
  ],
  "complete": false,
  "reaped": false,
  "returncode": null,
  "error": "helper wait: helper remains alive after both pipes closed; cleanup observer unsuccessful returncode; cleanup helper identity/lifetime unavailable"
}
```

The synthetic TimeoutError reaches the same generic wait-exception handler as Popen's TimeoutExpired. This check proves the missing cleanup call in that branch; it is not evidence that an actual native ps leaked in either archived attempt.
