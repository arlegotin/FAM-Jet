# Stage B fixed project launcher correction

**Closed source brief; HOLD.** Correct the unavailable-Torch launch environment only. Preserve binding01, its witness and all failed evidence unchanged. The Git observation/reap-overlap failure remains possible and fail-closed. No runtime probe, import, native invocation, retry, or panel release is authorized here.

## Schema and substitution

No Plan, Runtime, Qualification, ExitWitness, Terminal, or Publication fields change. `Runtime` remains the exact dictionary returned by unchanged `A.authority.runtime()`: `executable` identifies the resolved base binary; `process_image` identifies the sampled loaded image. Neither is the lexical virtualenv launcher.

Let `R=Path(root).resolve(strict=True)` be the canonical repository directory, `V=R/'.venv'`, and `L=V/'bin/python'`. PYTHON substitution becomes **`str(L)`**, without resolving L in argv. ROOT remains `str(R)`; PLAN remains the canonical absolute regular plan path P. No other launcher is eligible.

Keep symbolic worker TEMPLATE exactly `["{PYTHON}","-I","{ROOT}/validation/kernel_stage_b/bootstrap.py","--worker","--seal","{PLAN}"]`. Its existing digest is unchanged; the changed source manifest and amendment bind the new substitution semantics. Concrete vectors are exactly:

- Parent: `[str(L),"-I",str(R/"validation/kernel_stage_b/bootstrap.py"),"--seal",str(P)]`.
- Worker: `[str(L),"-I",str(R/"validation/kernel_stage_b/bootstrap.py"),"--worker","--seal",str(P)]`.

Preserve five/six-element validation and `commands.vector_hash` over each literal vector. Plan/evidence/release/template hashes retain their existing preimages. Do not substitute a resolved executable into either vector. Reader commands already use `sys.executable`; preserve them unchanged.

## Minimal implementation

In `validation/kernel_stage_b/authority.py`, add one stdlib helper `project_launcher(root, runtime) -> str`. Validate canonical R is a directory; V and V/bin are directories resolving to those same lexical paths; V/pyvenv.cfg is a regular file resolving within V; L is a file, `L.resolve(strict=True)` equals `Path(runtime['executable'])`, and SHA256 of its exact target bytes equals `runtime['executable_sha256']`. L may be a symlink to the approved external base binary; that exception applies only to L. Missing files, symlink loops, wrong target/hash or directory escape fail authority. Return the lexical `str(L)`; do not search PATH or inspect/import packages. No new artifact Ref is needed: the existing runtime hash pins the executable and argv pins its lexical location; this does not certify installed dependency bytes.

In `_execution_live`, retain exact current runtime comparison. Use that helper for parent/worker expected argv. Additionally require `sys.executable == str(L)` and `Path(sys.prefix).resolve(strict=True) == V`, with `sys.prefix != sys.base_prefix`, before scientific imports. This confirms the executing interpreter selected the project environment rather than merely accepting a proposed vector. Parent and worker independently enforce the check. Add only the stdlib `sys` import. Preserve all other entry ordering, clocks, admission, monitor calls, baseline, metrics, and counter checks.

In `_qualified_material`, require both bound/current parent and worker argv first elements equal the fixed lexical L, with their existing hash checks. Retain equal material manifests/runtime/bootstrap/template/monitor and full source identities. No binding01 result is reusable; equal template hash alone cannot bridge changed authority source.

## Authority and witness closure

Root must first adopt `docs/amendments/2026-10-21-kernel-stage-b-project-launcher.md`. Add precisely that path to `_source_manifest` required paths and `_compare_material_compatibility` allowed additions. Historical executed-A identity and all protected-byte comparisons remain unchanged; recompute sorted material `changed_paths` against actual A. Do not substitute previous B source as historical A or add wildcard document exceptions. New B authority bytes and amendment enter the current material manifest.

After source acceptance, prepare a **new** root-owned `docs/research/task18-kernel-stage-b-binding02-witness.py`, based on witness01 with fixed PLAN `artifacts/task18-kernel-stage-b-binding-02-prep/plan.json`, binding02 wording, and expected parent argv from `project_launcher(ROOT, execution['runtime'])`. Preserve once marker, actual wait, exit evidence, finalizer and external root Publication boundary. Pin its new exact bytes in the future Plan; witness01 stays unchanged. Witness remains separately Ref-bound, not newly inserted into the material-source set. Output binding02 uses its own fresh directory. No current allocation values are supplied.

## Source-only acceptance and subsequent gate

Controlled stdlib/temp-file tests cover valid symlink launcher, wrong hash/target, missing cfg, directory escape, lexical-versus-resolved argv, wrong prefix/base environment, five/six-element hashes, bound/current launcher mismatch, exact amendment inclusion, and protected-byte preservation. Stub runtime/filesystem as needed; no subprocess, backend import, dependency installation, or native identity sampling. Update existing authority fixture vectors and witness AST assertions. Existing retained `.venv/bin/python` source-test commands provide prior environment evidence, not isolated-binding success.

Only after source review may root separately allocate and release one fresh binding02. It must pass unchanged native predicates, Torch/famjet post-import baseline, zero-science counters, truthful terminal exit and root Publication before any panel qualification. This correction makes no promise to eliminate the independent Git timing failure.
