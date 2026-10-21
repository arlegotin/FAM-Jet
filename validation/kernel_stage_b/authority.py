"""Standard-library authority for the fixed external Stage B panel."""
import hashlib
import json
import math
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
import platform
import re
import shutil
import time


class AuthorityError(ValueError):
    """A sealed precondition, identity, or evidence record did not match."""


H = re.compile(r"[0-9a-f]{64}\Z")
G = re.compile(r"[0-9a-f]{40}\Z")
SCOPE = "Task18 descriptive actual-state Stage B"
TEMPLATE = ["{PYTHON}", "-I", "{ROOT}/validation/kernel_stage_b/bootstrap.py",
            "--worker", "--seal", "{PLAN}"]
FAMILIES = (("jet", "0x1.b7cdfd9d7bdbbp-34"),
            ("bank", "0x1.b7cdfd9d7bdbbp-34"),
            ("bank", "0x1.0c6f7a0b5ed8dp-20"),
            ("jet", "0x1.0c6f7a0b5ed8dp-20"),
            ("jet", "0x1.47ae147ae147bp-7"),
            ("bank", "0x1.47ae147ae147bp-7"))
CEILINGS = dict(histories=96, queries=8, snapshots=192, requests=576,
                predictions=4608, factors=0)
PINS = {
    "panel": ("artifacts/task18/finite-nested96/manifest.json", 37234,
              "0617dab2f992fb6c9adfd44bb588ee6d8c0418f1c03d8e9f496e097427d28013"),
    "panel_config": ("configs/development/jet_finite_raw_32768.yaml", 2732,
                     "a0dd6ecdcdda0464c4ec32e36c2b3f3533e75871369666c05192869b4c8b0708"),
    "panel_producer": ("artifacts/task18-evidence/procedure-scripts/task18_nested96_evaluation.py", 6870,
                       "a8fc50b1a2f09ebb14699d55f53514ca015f5d2e741ac73630d0d2ea1ebca67d"),
    "exposure": ("docs/amendments/2026-10-21-kernel-actual-state-panel-design.md", 4781,
                 "c0df1dee7cd73b26def8ca948405f50aef2f2079186fe52ec3e0b5ad61458d00"),
}


def _need(condition, message):
    if not condition:
        raise AuthorityError(message)


def canonical(value):
    """The one Stage B content encoding; JSON special floats are forbidden."""
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float:
            _need(math.isfinite(item), "nonfinite canonical number")
            return
        if type(item) in (list, tuple):
            for child in item:
                check(child)
            return
        if type(item) is dict:
            for key, child in item.items():
                _need(type(key) is str, "nonstring canonical key")
                check(child)
            return
        raise TypeError("unsupported canonical value")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        _need(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def strict_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_need(False, "nonfinite JSON literal")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityError("invalid JSON") from exc


def _keys(value, names, label):
    _need(type(value) is dict and set(value) == set(names), label + " schema mismatch")


def _str(value):
    return type(value) is str and bool(value)


def _hash(value, pattern=H):
    return type(value) is str and pattern.fullmatch(value) is not None


def _integer(value):
    return type(value) is int and value >= 0


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _ref(ref, kind=None):
    _keys(ref, ("kind", "path", "sha256", "bytes"), "reference")
    _need(_str(ref["kind"]) and (kind is None or ref["kind"] == kind), "reference kind")
    _need(_str(ref["path"]) and _hash(ref["sha256"]) and _integer(ref["bytes"]),
          "reference value")


def read_verified(root, ref):
    """Read exact bytes from a regular, contained file after validating the ref."""
    _ref(ref)
    root = Path(root).resolve(strict=True)
    rel = Path(ref["path"])
    _need(not rel.is_absolute() and ".." not in rel.parts, "reference path escape")
    path = (root / rel).resolve(strict=True)
    _need(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
          "reference file escape/type")
    raw = path.read_bytes()
    _need(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
          "reference bytes changed")
    return raw


def _candidate(record, expected):
    _keys(record, ("id", "family", "ridge_hex", "config_sha256", "writer_sha256", "static", "rates"), "candidate")
    family, ridge = expected
    _need(record["family"] == family and record["ridge_hex"] == ridge and
          record["id"] == family + ":" + ridge, "candidate order/identity")
    _need(_hash(record["config_sha256"]) and _hash(record["writer_sha256"]), "candidate hashes")
    _ref(record["static"], "existing_export")
    _ref(record["rates"], "represented_rates")


def _manifest(value):
    _keys(value, ("artifact_kind", "data", "feature_version", "generator_version",
                  "length_weights", "manifest_hash", "manifest_version", "regime_weights",
                  "seed_version", "splits", "target_semantics"), "panel manifest")
    _need(value["manifest_version"] == 1 and
          value["artifact_kind"] == "task18_pooled_development_inventory" and
          value["generator_version"] == "initial_spec_v2_targets" and
          value["target_semantics"] == "observed_event_targets_v2" and
          value["seed_version"] == "sha256_named_v1" and
          value["feature_version"] == "squared_gaussian.pcg64_box_muller_v1", "panel version")
    _need(value["manifest_hash"] == "90d0808a5410a8a2efe09bab823be3de798b03886e957ca77dc88fb68db98056" and
          digest({k: v for k, v in value.items() if k != "manifest_hash"}) == value["manifest_hash"],
          "panel internal hash")
    splits = value["splits"]
    _need(type(splits) is dict and set(splits) ==
          {"training", "development_fit", "development_calibration", "pilot", "confirmation", "replication"},
          "panel splits")
    fit = splits["development_fit"]
    _keys(fit, ("episodes", "root", "status"), "development fit")
    _need(fit["root"] == 3626995086544026198 and fit["status"] == "exploratory" and
          type(fit["episodes"]) is list and len(fit["episodes"]) == 96, "panel inventory")
    for split, data in splits.items():
        _need(type(data) is dict and set(data) == {"episodes", "root", "status"}, "split schema")
        if split != "development_fit":
            _need(data["episodes"] == [], "other split must be empty")
    regimes = ("piecewise_stationary", "trend_reset", "periodic_impulses", "irregular_revisions")
    expected = [(length, regime, ordinal) for length in (128, 512, 2048)
                for regime in regimes for ordinal in range(8)]
    for item, (length, regime, ordinal) in zip(fit["episodes"], expected):
        _keys(item, ("length", "regime", "episode_id", "seed", "hashes"), "panel entry")
        _keys(item["hashes"], ("events", "queries", "oracle"), "panel entry hashes")
        _need(item["length"] == length and item["regime"] == regime and
              item["episode_id"] == f"task18-dev-N{length}-{regime}-{ordinal:012d}" and
              item["seed"] == fit["root"] and all(_hash(h) for h in item["hashes"].values()),
              "panel entry identity/order")


TRACE_COUNTERS = {"coefficients", "window_vector", "snapshot_record", "snapshot_from_record",
                  "_advance_payload", "_reconstruct", "read", "tensor_clone", "factor"}


def parse_reader_stream(raw):
    """Check the archived B1/Q1 trace without importing scientific code."""
    lines = raw.splitlines()
    _need(bool(lines), "empty A reader stream")
    observed = {name: 0 for name in TRACE_COUNTERS}
    for line in lines[:-1]:
        item = strict_json(line)
        _keys(item, ("counter",), "A counter")
        _need(item["counter"] in TRACE_COUNTERS, "A counter name")
        observed[item["counter"]] += 1
    response = strict_json(lines[-1])
    _keys(response, ("numeric", "counts", "windows", "coefficients", "window_vectors", "seconds"),
          "A reader result")
    counts = response["counts"]
    _need(type(counts) is dict and set(counts) <= TRACE_COUNTERS and
          all(_integer(v) for v in counts.values()) and
          all(counts.get(k, 0) == n for k, n in observed.items()) and
          counts.get("read", 0) == 1 and counts.get("factor", 0) == 0, "A reader trace counts")
    n = response["numeric"]
    _keys(n, ("prediction", "logits", "support", "failure", "diagnostics", "schema_version"),
          "A numeric")
    _need(n["schema_version"] == 1 and n["logits"] is None and
          type(n["prediction"]) is list and len(n["prediction"]) == 1 and
          type(n["prediction"][0]) is list and len(n["prediction"][0]) == 1 and
          type(n["prediction"][0][0]) is list and len(n["prediction"][0][0]) == 8 and
          all(x is None or _finite(x) for x in n["prediction"][0][0]) and
          type(n["failure"]) is list and len(n["failure"]) == 1 and
          type(n["failure"][0]) is list and len(n["failure"][0]) == 1 and
          type(n["failure"][0][0]) is bool, "A numeric B1/Q1/V8")
    _keys(n["diagnostics"], ("numerical_eligible", "prediction_valid", "numeric_supported",
                             "factual_support_available", "quarantined", "failure_code",
                             "reconstructed_mass", "cancellation_bound"), "A diagnostics")
    _need(type(response["windows"]) is list and type(response["coefficients"]) is list and
          type(response["window_vectors"]) is list and
          len(response["windows"]) == len(response["coefficients"]) == len(response["window_vectors"]) <= 2 and
          _finite(response["seconds"]) and response["seconds"] >= 0,
          "A reader windows/seconds")
    return response


def _role_shape(role, reference):
    names = ("code", "coefficients", "path", "prediction", "task", "window_vectors", "windows")
    _keys(role, (*names, "residuals") if reference else names, "A role")
    _need(type(role["code"]) is int and 0 <= role["code"] <= 7 and
          role["path"] in ("decoded", "empty", "quarantined") and
          role["task"] in ("mean", "contrast"), "A role code/path/task")
    def number(value):
        if not reference:
            return _finite(value)
        if not _str(value):
            return False
        try:
            return Decimal(value).is_finite()
        except InvalidOperation:
            return False
    def vector(value):
        return type(value) is list and len(value) == 8 and all(number(x) for x in value)
    _need(vector(role["prediction"]) and type(role["windows"]) is list and
          type(role["coefficients"]) is list and type(role["window_vectors"]) is list and
          len(role["windows"]) == len(role["coefficients"]) == len(role["window_vectors"]) <= 2,
          "A role vector/window shape")
    for coefficient, vector_value, window in zip(role["coefficients"], role["window_vectors"], role["windows"]):
        _need((coefficient is None or vector(coefficient)) and
              (vector_value == [] or vector(vector_value)), "A role coefficients/window vectors")
        keys = ("code", "prediction", "mass", "bound", "raw", "reached")
        _keys(window, (*keys, "margins") if reference else keys, "A window")
        _keys(window["reached"], ("coefficients", "mass", "bound", "raw", "prediction"),
              "A reached flags")
        _need(type(window["code"]) is int and 0 <= window["code"] <= 7 and
              all(type(x) is bool for x in window["reached"].values()), "A reached types")
        for key in ("prediction", "raw"):
            _need((window[key] is None) != window["reached"][key] and
                  (window[key] is None or vector(window[key])), "A window vector applicability")
        for key in ("mass", "bound"):
            _need((window[key] is None) != window["reached"][key] and
                  (window[key] is None or number(window[key])), "A window scalar applicability")
        _need((coefficient is None) != window["reached"]["coefficients"],
              "A coefficient applicability")
        if reference:
            margins = window["margins"]
            _need(type(margins) is dict and set(margins) <=
                  {"nonnegative_mass", "floor", "cancellation"} and
                  all(number(value) for value in margins.values()), "A reference margins")


def validate_plan(plan):
    """Validate closed plan shape and reject every unallocated or unsupported release."""
    _keys(plan, ("version", "scope", "panel", "panel_config", "panel_producer", "exposure",
                 "training", "candidates", "ceilings", "evidence", "approval", "execution", "release"), "plan")
    _need(type(plan["version"]) is int and plan["version"] == 2 and
          plan["scope"] == SCOPE and plan["ceilings"] == CEILINGS and
          type(plan["ceilings"]) is dict and all(_integer(v) for v in plan["ceilings"].values()),
          "plan scope/ceilings")
    kinds = dict(panel="existing_manifest", panel_config="run_config_yaml",
                 panel_producer="python_source", exposure="markdown")
    for name, (path, size, sha) in PINS.items():
        _ref(plan[name], kinds[name]); _need((plan[name]["path"], plan[name]["bytes"], plan[name]["sha256"]) ==
                                (path, size, sha), "historical pin mismatch: " + name)
    _ref(plan["training"], "frozen_training")
    _need(type(plan["candidates"]) is list and len(plan["candidates"]) == 6, "six candidates required")
    for record, expected in zip(plan["candidates"], FAMILIES):
        _candidate(record, expected)
    _need(type(plan["evidence"]) is dict, "evidence schema")
    if plan["release"] is not None:
        _keys(plan["release"], ("approved", "scope", "payload_sha256", "ruling"), "release")
        _need(plan["release"]["approved"] is True and
              plan["release"]["scope"] in ("binding", "panel"), "unsupported release scope")
    if plan["approval"] is None or plan["execution"] is None or plan["release"] is None:
        raise AuthorityError("null execution authority blocks work")
    _ref(plan["release"]["ruling"], "markdown")
    _need(plan["release"]["payload_sha256"] == digest({k: v for k, v in plan.items() if k != "release"}),
          "release payload hash")
    _keys(plan["approval"], ("ruling", "approved", "scope", "evidence_sha256", "failures",
                              "source_review", "compatibility"), "approval")
    approval = plan["approval"]
    _need(approval["approved"] is True and approval["scope"] == "descriptive_actual_state_only" and
          approval["evidence_sha256"] == digest(plan["evidence"]), "approval identity")
    _ref(approval["ruling"], "markdown"); _ref(approval["source_review"], "markdown")
    _need(type(approval["failures"]) is list and len(approval["failures"]) == 24,
          "all 24 source failures require manual dispositions")
    _keys(approval["compatibility"], ("old_source", "new_source", "old_manifest", "new_manifest",
                                    "changed_paths", "decision"), "compatibility")
    compat = approval["compatibility"]
    _need(_hash(compat["old_source"], G) and _hash(compat["new_source"], G) and
          compat["decision"] == "external_adapter_only" and type(compat["changed_paths"]) is list and
          all(_str(x) for x in compat["changed_paths"]), "manual source compatibility")
    _ref(compat["old_manifest"], "source_manifest")
    _ref(compat["new_manifest"], "source_manifest")
    for disposition in approval["failures"]:
        _keys(disposition, ("candidate", "row", "transform", "source_status", "strict_status",
                            "failed_fields", "contraction_indices", "decision", "ruling"), "disposition")
        _need(disposition["row"] == 30 and disposition["transform"] in ("I", "O", "U", "R") and
              disposition["source_status"] == disposition["strict_status"] == "FAILED" and
              disposition["decision"] == "retain_and_score_actual_state" and
              type(disposition["failed_fields"]) is list and
              disposition["contraction_indices"] == list(range(8, 72)), "manual failure disposition")
        _ref(disposition["ruling"], "markdown")
    _execution_shape(plan["execution"], plan["release"]["scope"])
    return plan


def _observation(value):
    _keys(value, ("argv", "returncode", "stdout", "stderr"), "observation")
    _need(type(value["argv"]) is list and value["argv"] and all(_str(x) for x in value["argv"]) and
          value["returncode"] == 0, "observation command/result")
    _ref(value["stdout"], "bytes"); _ref(value["stderr"], "bytes")


def _execution_shape(execution, scope):
    _keys(execution, ("source_full_git", "source_manifest", "runtime", "host", "admission", "limits",
                      "boundary", "launch", "qualification", "preparation_output", "output"), "execution")
    _need(_hash(execution["source_full_git"], G), "source Git identity")
    _ref(execution["source_manifest"], "source_manifest")
    _keys(execution["host"], ("node", "system", "release", "machine"), "host")
    _need(all(_str(v) for v in execution["host"].values()), "host identity")
    runtime = execution["runtime"]
    _keys(runtime, ("python", "executable", "executable_sha256", "implementation", "process_image",
                    "helpers", "decimal_version", "libmpdec_version", "decimal_extension",
                    "decimal_extension_sha256", "byteorder", "machine", "context"), "runtime")
    _keys(runtime["process_image"], ("method", "path", "sha256"), "runtime image")
    _keys(runtime["helpers"], ("ps", "git"), "runtime helpers")
    for helper in runtime["helpers"].values():
        _keys(helper, ("path", "sha256"), "runtime helper")
    limits = execution["limits"]
    _keys(limits, ("outer_seconds", "candidate_seconds", "incremental_bytes", "output_bytes",
                   "free_disk_bytes", "numerical_threads"), "limits")
    _need(all(_finite(limits[k]) and limits[k] > 0 for k in ("outer_seconds", "candidate_seconds")) and
          all(_integer(limits[k]) and limits[k] > 0 for k in ("incremental_bytes", "output_bytes")) and
          limits["free_disk_bytes"] == 4294967296 and limits["numerical_threads"] == 1,
          "unallocated/invalid limits")
    boundary = execution["boundary"]
    _keys(boundary, ("allocation_start_monotonic", "allocation_start_utc_epoch", "deadline_monotonic",
                     "baseline", "absolute_rss", "process_tree_rss", "sequential_workers",
                     "outputs_include_temporaries"), "boundary")
    _need(all(_finite(boundary[k]) and boundary[k] > 0 for k in
              ("allocation_start_monotonic", "allocation_start_utc_epoch", "deadline_monotonic")) and
          boundary["deadline_monotonic"] == boundary["allocation_start_monotonic"] + limits["outer_seconds"] and
          boundary["baseline"] == "post-import/pre-allocation per worker" and
          all(boundary[k] is True for k in ("absolute_rss", "process_tree_rss", "sequential_workers",
                                            "outputs_include_temporaries")), "original resource boundary")
    admission = execution["admission"]
    _keys(admission, ("utc_epoch", "host", "vm_stat", "memory_pressure", "power", "page_size",
                      "free_pages", "speculative_pages", "available_bytes", "reserve_bytes",
                      "planning_envelope_bytes", "free_disk_bytes"), "admission")
    _need(_finite(admission["utc_epoch"]) and admission["utc_epoch"] > 0 and
          admission["host"] == execution["host"], "admission clock/host")
    for key in ("vm_stat", "memory_pressure", "power"):
        _observation(admission[key])
    _need(all(_integer(admission[k]) for k in ("page_size", "free_pages", "speculative_pages",
                                               "available_bytes", "reserve_bytes", "planning_envelope_bytes",
                                               "free_disk_bytes")), "admission values")
    launch = execution["launch"]
    _keys(launch, ("bootstrap", "template_sha256", "argv", "argv_sha256", "monitor", "environment",
                   "fresh_utc_epoch", "free_disk_bytes", "power"), "launch")
    _ref(launch["bootstrap"], "python_source"); _ref(launch["monitor"], "python_source")
    _observation(launch["power"])
    _need(_finite(launch["fresh_utc_epoch"]) and launch["fresh_utc_epoch"] > 0 and
          _integer(launch["free_disk_bytes"]) and type(launch["argv"]) is list and
          len(launch["argv"]) == 6 and all(_str(x) for x in launch["argv"]), "launch values")
    expected_env = {k: "1" for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                   "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}
    expected_env.update(PYTORCH_ENABLE_MPS_FALLBACK="0", PYTORCH_MPS_FAST_MATH="0")
    _need(launch["environment"] == expected_env, "numerical environment")
    qualification = execution["qualification"]
    _need((qualification is None) == (scope == "binding"), "binding qualification sequence")
    if qualification is not None:
        _keys(qualification, ("release", "report", "source_full_git", "source_manifest",
                              "template_sha256", "runtime", "monitor", "unknown_child_guard",
                              "compatibility"), "qualification")
        for key, kind in (("release", "binding_plan"), ("report", "binding_report"),
                          ("source_manifest", "source_manifest"), ("monitor", "python_source"),
                          ("unknown_child_guard", "existing_guard_proof")):
            _ref(qualification[key], kind)
        _need(_hash(qualification["source_full_git"], G) and
              qualification["template_sha256"] == launch["template_sha256"] and
              qualification["runtime"] == runtime and qualification["monitor"] == launch["monitor"],
              "qualified runtime/template")
    _need(_str(execution["output"]) and Path(execution["output"]).is_absolute() and
          (execution["preparation_output"] is None or
           (_str(execution["preparation_output"]) and Path(execution["preparation_output"]).is_absolute())),
          "absolute output paths")


def validate_evidence(evidence, root):
    """Validate raw A inventory and every explicitly referenced source failure."""
    names = ("audit", "acceptance", "custody", "mapping", "seal", "setup", "inventory",
             "monitor", "events", "journal", "external", "slots", "statics", "source")
    _keys(evidence, names, "evidence")
    kinds = dict(audit="markdown", acceptance="scoped_acceptance", custody="root_custody",
                 mapping="archive_mapping", seal="A_seal", setup="A_setup", inventory="A_stage",
                 monitor="A_monitor", events="jsonl", journal="jsonl", external="A_external",
                 source="source_manifest")
    for name in names:
        if name in ("slots", "statics"):
            continue
        _ref(evidence[name], kinds[name])
        read_verified(root, evidence[name])
    _need(type(evidence["statics"]) is list and len(evidence["statics"]) == 6, "six statics")
    for ref in evidence["statics"]:
        raw = strict_json(read_verified(root, ref))
        _keys(raw, ("factor_diagnostics", "gram_gate", "ownership", "unit_ownership", "unit_transport"), "static")
        diag = raw["factor_diagnostics"]
        _need(all(_finite(diag[k]) and diag[k] > 0 for k in
                  ("condition_estimate", "minimum_eigenvalue")) and
              _finite(diag["factor_residual"]) and diag["factor_residual"] >= 0 and
              raw["gram_gate"]["status"] == "PASS" and
              raw["gram_gate"]["failed_fields"] == [] and
              all(type(raw["gram_gate"][k]) is list and len(raw["gram_gate"][k]) == 8 and
                  all(type(row) is list and len(row) == 8 for row in raw["gram_gate"][k])
                  for k in ("production_gram", "reference_gram")) and
              raw["ownership"]["additional_persistent_history_bytes"] == 0 and
              raw["unit_ownership"]["additional_persistent_history_bytes"] == 0 and
              raw["unit_transport"]["kind"] == "DERIVED unit transport", "static Gram/ownership gate")
    stage = strict_json(read_verified(root, evidence["inventory"]))
    _keys(stage, ("counts", "events", "failure", "groups", "inventory", "outer_seconds",
                  "seconds", "status"), "A inventory")
    _need(stage["status"] == "FAILED" and stage["failure"] is None and
          len(stage["groups"]) == 24 and len(stage["inventory"]) == 768,
          "A status/inventory")
    _need(stage["counts"].get("read") == 744 and stage["counts"].get("read_dispatch") == 744 and
          stage["counts"].get("result_serialization") == 720 and
          stage["counts"].get("reference_setup") == 12 and
          stage["counts"].get("reference_solve") == 3360 and
          all(_integer(v) for v in stage["counts"].values()) and
          all(_finite(v) and v >= 0 for v in stage["seconds"].values()) and
          _finite(stage["outer_seconds"]), "A actual inventory counts")
    training = strict_json((Path(root) / "validation/kernel_stage_a/frozen-training-metadata.json").read_bytes())
    from validation.kernel_stage_a.descriptors import slots as a_slots
    expected = list(a_slots())
    _need(type(evidence["slots"]) is list and len(evidence["slots"]) == 768, "A slots")
    ordinal = 0
    for ci, pair in enumerate(FAMILIES):
        for si, slot in enumerate(expected):
            listed = evidence["slots"][ci * 128 + si]
            _keys(listed, ("candidate", "row", "transform", "ordinal", "detail", "stdout", "stderr", "input"), "slot")
            row = stage["inventory"][ci * 128 + si]
            _need(listed["candidate"] == pair[0] + ":" + pair[1] and
                  (listed["row"], listed["transform"]) == (slot.row, slot.transform) and
                  row["candidate"] == list(pair) and row["row"] == slot.row and
                  row["transform"] == slot.transform, "slot mapping")
            if not slot.applicable:
                _keys(row, ("candidate", "row", "transform", "status"), "A nonapplicable")
                _need(listed["ordinal"] is None and all(listed[k] is None for k in
                      ("detail", "stdout", "stderr", "input")) and row["status"] == "NONAPPLICABLE",
                      "nonapplicable slot")
                continue
            _need(listed["ordinal"] == ordinal and row["status"] == "EXECUTED", "executed ordinal")
            _keys(row, ("candidate", "row", "transform", "status", "seconds", "outcome"),
                  "A executed row")
            _need(_finite(row["seconds"]) and row["seconds"] >= 0, "A executed seconds")
            ordinal += 1
            for name in ("stdout", "stderr", "input"):
                _need(listed[name] is not None, "missing executed raw slot")
                _ref(listed[name], {"stdout": "A_reader", "stderr": "bytes", "input": "snapshot"}[name])
                read_verified(root, listed[name])
            _need(read_verified(root, listed["stderr"]) == b"", "A reader stderr")
            response = parse_reader_stream(read_verified(root, listed["stdout"]))
            state = strict_json(read_verified(root, listed["input"]))
            _keys(state, ("body", "checksum"), "A saved state")
            _need(state["checksum"] == digest(state["body"]), "A state checksum")
            body = state["body"]
            _need(body["format"] == "famjet.snapshot" and body["format_version"] == 1,
                  "A snapshot format")
            state_hash = digest({k: v for k, v in body.items() if k not in ("format", "format_version")})
            outcome = row["outcome"]
            if slot.row == 32:
                _need(listed["detail"] is None, "sentinel has invented detail")
                _keys(outcome, ("end_to_end_gate", "reader_arithmetic", "snapshot_sha256",
                                "source_state_fidelity", "strict_end_to_end", "stop", "worker_counts"),
                      "A sentinel outcome")
                _need(outcome["snapshot_sha256"] == state_hash and
                      outcome["worker_counts"] == response["counts"] and
                      outcome["end_to_end_gate"] == outcome["reader_arithmetic"] == "PASS" and
                      outcome["stop"] == "continue" and
                      outcome["source_state_fidelity"] == "NONFINITE_POLICY_SENTINEL" and
                      outcome["strict_end_to_end"] == "NONFINITE_POLICY_SENTINEL" and
                      response["numeric"]["diagnostics"]["quarantined"] == [[True]] and
                      response["numeric"]["diagnostics"]["failure_code"][0][0][0] == 1 and
                      response["numeric"]["failure"] == [[True]] and
                      response["numeric"]["prediction"][0][0] ==
                      training[pair[0]]["target_statistics"]["tasks"]["mean"]["mean"],
                      "A sentinel policy")
            else:
                finite_keys = ("comparisons", "end_to_end_gate", "reader_arithmetic",
                               "source_contractions", "source_state_fidelity", "strict_end_to_end", "stop")
                _keys(outcome, (*finite_keys, "transform_checks") if slot.transform != "I"
                      else finite_keys, "A finite outcome")
                _need(listed["detail"] is not None, "missing finite detail")
                _ref(listed["detail"], "A_detail")
                detail = strict_json(read_verified(root, listed["detail"]))
                _keys(detail, ("P", "A", "B", "counts", "outcome", "snapshot_sha256"), "A detail")
                _need(detail["outcome"] == outcome and detail["counts"] == response["counts"] and
                      detail["snapshot_sha256"] == state_hash, "detail/inventory/stream mismatch")
                p = detail["P"]
                _role_shape(p, False)
                _need(p["prediction"] == response["numeric"]["prediction"][0][0] and
                      p["windows"] == response["windows"] and
                      p["coefficients"] == response["coefficients"] and
                      p["window_vectors"] == response["window_vectors"] and
                      p["task"] in ("mean", "contrast"), "A P profile")
                for role in ("A", "B"):
                    reference = detail[role]
                    _role_shape(reference, True)
                    _need(reference["task"] == p["task"] and
                          type(reference["residuals"]) is list, "A reference task/residuals")
                    for value in reference["residuals"]:
                        _need(_str(value), "A reference residual decimal")
                        try:
                            residual = Decimal(value)
                        except (InvalidOperation, TypeError):
                            raise AuthorityError("A reference residual decimal")
                        _need(residual.is_finite() and abs(residual) < Decimal("1e-50"),
                              "A reference residual bound")
                _need(outcome["comparisons"]["P_A"]["status"] == "PASS", "P-A failure")
                _keys(outcome["comparisons"], ("P_A", "A_B", "P_B"), "A comparisons")
                _need(outcome["reader_arithmetic"] == "PASS" and outcome["stop"] == "continue",
                      "A reader arithmetic/stop")
                if slot.row == 30:
                    _need(outcome["end_to_end_gate"] == outcome["source_state_fidelity"] ==
                          outcome["strict_end_to_end"] == "FAILED", "row30 failure status")
                    expected_fields = ([f"prediction[{i}]" for i in range(8)] +
                                       [f"windows[0].prediction[{i}]" for i in range(8)] +
                                       [f"windows[0].raw[{i}]" for i in range(8)])
                    for side in ("A_B", "P_B"):
                        _need(outcome["comparisons"][side] ==
                              {"status": "FAILED", "failed_fields": expected_fields}, "row30 source failure")
                    _need(outcome["source_contractions"] ==
                          {"status": "FAILED", "failed_fields": [f"prediction[{i}]" for i in range(8, 72)]},
                          "row30 contraction failure")
                else:
                    _need(outcome["end_to_end_gate"] == outcome["source_state_fidelity"] ==
                          outcome["strict_end_to_end"] == "PASS", "unexpected finite failure status")
                    _need(all(outcome["comparisons"][side] == {"status": "PASS", "failed_fields": []}
                              for side in ("A_B", "P_B")) and
                          outcome["source_contractions"] == {"status": "PASS", "failed_fields": []},
                          "unexpected source failure")
                if slot.transform != "I":
                    _need(len(outcome["transform_checks"]) == 3 and
                          all(x == {"status": "PASS", "failed_fields": []}
                              for x in outcome["transform_checks"]), "transform check")
                else:
                    _need("transform_checks" not in outcome, "invented I transform check")
    _need(ordinal == 744, "A executed count")
    setup = strict_json(read_verified(root, evidence["setup"]))
    seal = strict_json(read_verified(root, evidence["seal"]))
    _need(setup["actual_completed_top_level_exports"] == 6 and
          setup["actual_factor_constructions"] == 6 and
          setup["actual_rate_grid_constructions"] == 2 and setup["actual_reads"] == 0 and
          setup["static_exports"] == seal["pending"]["static_exports"] and
          setup["represented_rate_records"] == seal["pending"]["represented_rate_records"] and
          seal["observed"]["package_hash"] ==
          "15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050" and
          seal["observed"]["dependency_lock_hash"] ==
          "2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1" and
          len(seal["observed"]["files"]) == 26, "A setup/sealed source")
    for path, sha in seal["observed"]["files"].items():
        _need(hashlib.sha256((Path(root) / path).read_bytes()).hexdigest() == sha,
              "preserved A sealed source: " + path)
    mapping = strict_json(read_verified(root, evidence["mapping"]))
    _need(type(mapping["files"]) is list and len(mapping["files"]) == 3064,
          "A custody mapping count")
    for item in mapping["files"]:
        _keys(item, ("original", "archive", "bytes", "sha256"), "A custody row")
        read_verified(root, dict(kind="bytes", path=item["archive"],
                                 bytes=item["bytes"], sha256=item["sha256"]))
    custody = strict_json(read_verified(root, evidence["custody"]))
    acceptance = strict_json(read_verified(root, evidence["acceptance"]))
    _need(custody["status"] == "CUSTODY_SOURCE_PASS_ONLY" and
          custody["original_files"] == 3064 and
          acceptance["global_stage_a_status"] == "FAILED" and
          acceptance["raw_monitor_status"] == "STOPPED" and
          acceptance["counts"] == {"executed": 744, "nonapplicable": 24,
                                   "finite_detail_pass_P_A": 720, "policy_sentinel_pass": 24,
                                   "finite_source_pass": 696, "finite_source_failed": 24} and
          acceptance["audit"] == {k: evidence["audit"][k] for k in ("path", "sha256")} and
          acceptance["failed_source_slots"]["row"] == 30 and
          acceptance["failed_source_slots"]["transforms"] == ["I", "O", "U", "R"],
          "accepted scoped A custody")
    monitor = strict_json(read_verified(root, evidence["monitor"]))
    _need(monitor["status"] == "STOPPED" and monitor["returncode"] == 1 and
          monitor["source_event_accounting"]["status"] == "COMPLETE" and
          monitor["source_event_accounting"]["complete"] is True and
          monitor["source_event_accounting"]["identity_complete"] is True and
          monitor["missing_worker_baselines"] == [] and monitor["cleanup_diagnostics"] == [] and
          monitor["reason"] is None and monitor["monitor_failure"] is None and
          monitor["evidence"]["rejected_observations"] == 0 and
          monitor["unresolved_worker_count"] == 0, "A native accounting/STOPPED")
    phase = monitor["authority_phase"]
    _need(phase["started"] is True and phase["success"] is True and
          phase["helper_count"] == phase["completed_count"] == 2 and
          len(phase["declarations"]) == 2 and len(phase["commands"]) == 2 and
          all(v["reaped"] is True and v["returncode"] == 0
              for v in phase["declarations"].values()), "A exact successful Git phase")
    events = [strict_json(line) for line in read_verified(root, evidence["events"]).splitlines()]
    kinds = {k: sum(x["event"] == k for x in events) for k in
             ("authority_start", "authority_end", "authority_helper", "authority_helper_end",
              "python_worker_launch", "python_worker_end", "candidate_start")}
    _need(kinds == {"authority_start": 1, "authority_end": 1,
                    "authority_helper": 2, "authority_helper_end": 2,
                    "python_worker_launch": 744, "python_worker_end": 744,
                    "candidate_start": 6} and
          all(x["reaped"] is True and x["returncode"] == 0
              for x in events if x["event"] == "authority_helper_end"),
          "A raw authority/reader lifecycle")
    journal = read_verified(root, evidence["journal"])
    _need(len(journal.splitlines()) == monitor["evidence"]["accepted_records"] and
          monitor["evidence"]["bytes"] == len(journal), "A monitor journal accounting")
    external = strict_json(read_verified(root, evidence["external"]))
    deadline = seal["pending"]["resource_measurement_boundary_seal"]["deadline_monotonic"]
    _need(external["exit"] == 1 and external["parent_invocations"] == 1 and
          external["monotonic_before"] < external["monotonic_after"] < deadline and
          _finite(external["elapsed_seconds"]), "A external end before original deadline")
    return stage


def _source_manifest(root, ref):
    rows = strict_json(read_verified(root, ref))
    _need(type(rows) is list and rows == sorted(rows, key=lambda row: row["path"]),
          "source manifest order")
    paths = set()
    for row in rows:
        _keys(row, ("path", "sha256", "bytes"), "source manifest row")
        _need(row["path"] not in paths, "duplicate source path")
        paths.add(row["path"])
        read_verified(root, dict(kind="bytes", **row))
    root = Path(root)
    required = {str(p.relative_to(root)) for p in (root / "famjet").rglob("*.py")}
    required.update(str(p.relative_to(root)) for p in (root / "validation/kernel_stage_a").glob("*.py"))
    required.update(str(p.relative_to(root)) for p in (root / "validation/kernel_stage_b").glob("*.py"))
    required.update(("requirements.lock", PINS["panel_config"][0],
                     "docs/amendments/2026-10-21-kernel-stage-b-external-adapter-source.md"))
    _need(required <= paths and "validation/kernel_stage_b/bootstrap.py" in paths,
          "source manifest missing material paths")
    return rows


def _execution_live(plan, root, worker):
    from validation.kernel_stage_a import authority as a_authority
    from validation.kernel_stage_a.commands import vector_hash

    execution = plan["execution"]
    current = a_authority.runtime()
    _need(execution["runtime"] == current, "runtime image/helper/decimal mismatch")
    host = dict(node=platform.node(), system=platform.system(), release=platform.release(),
                machine=platform.machine())
    _need(execution["host"] == host, "current host changed")
    _source_manifest(root, execution["source_manifest"])
    _need(plan["approval"]["compatibility"]["new_manifest"] == execution["source_manifest"] and
          plan["approval"]["compatibility"]["new_source"] == execution["source_full_git"],
          "current source compatibility mismatch")
    admission = execution["admission"]
    now = time.time()
    _need(0 <= now - admission["utc_epoch"] <= 60, "admission expired")
    commands = {"vm_stat": ("vm_stat",), "memory_pressure": ("memory_pressure", "-Q"),
                "power": ("pmset", "-g", "batt")}
    for name, suffix in commands.items():
        obs = admission[name]
        _need(tuple(Path(v).name if i == 0 else v for i, v in enumerate(obs["argv"])) == suffix,
              "admission command mismatch: " + name)
        _need(read_verified(root, obs["stderr"]) == b"", "admission stderr")
    vm = read_verified(root, admission["vm_stat"]["stdout"]).decode("utf-8")
    page = re.search(r"page size of (\d+) bytes", vm)
    free = re.search(r"Pages free:\s+(\d+)\.", vm)
    speculative = re.search(r"Pages speculative:\s+(\d+)\.", vm)
    _need(page is not None and free is not None and speculative is not None and
          int(page[1]) == admission["page_size"] and
          int(free[1]) == admission["free_pages"] and
          int(speculative[1]) == admission["speculative_pages"], "printed vm_stat mismatch")
    available = (admission["free_pages"] + admission["speculative_pages"]) * admission["page_size"]
    _need(available == admission["available_bytes"] and available >= 2**30 and
          admission["reserve_bytes"] >= available / 4 and
          admission["planning_envelope_bytes"] == available - admission["reserve_bytes"] and
          admission["planning_envelope_bytes"] > execution["limits"]["incremental_bytes"],
          "admission memory envelope")
    _need(read_verified(root, admission["memory_pressure"]["stdout"]) and
          read_verified(root, admission["power"]["stdout"]), "admission observations missing")
    launch = execution["launch"]
    _need(0 <= now - launch["fresh_utc_epoch"] <= 60, "fresh launch expired")
    _need(tuple(Path(v).name if i == 0 else v for i, v in enumerate(launch["power"]["argv"])) ==
          ("pmset", "-g", "batt"), "fresh power command")
    _need(read_verified(root, launch["power"]["stdout"]) and
          read_verified(root, launch["power"]["stderr"]) == b"", "fresh power observation")
    _need(launch["template_sha256"] == digest(TEMPLATE), "bootstrap template identity")
    bootstrap = (Path(root) / "validation/kernel_stage_b/bootstrap.py").resolve()
    _need(launch["bootstrap"]["path"] == "validation/kernel_stage_b/bootstrap.py" and
          read_verified(root, launch["bootstrap"]) == bootstrap.read_bytes(), "bootstrap identity")
    monitor = "validation/kernel_stage_a/monitor.py"
    _need(launch["monitor"]["path"] == monitor and
          launch["monitor"]["sha256"] ==
          "3c7e4aa237173895245444e1cb66a017275507398a6446133020ad509a00d30e" and
          read_verified(root, launch["monitor"]) == (Path(root) / monitor).read_bytes(),
          "unchanged monitor identity")
    argv = launch["argv"]
    _need(argv[:5] == [current["executable"], "-I", str(bootstrap), "--worker", "--seal"] and
          Path(argv[5]).is_absolute() and Path(argv[5]).is_file() and
          launch["argv_sha256"] == vector_hash(argv), "literal worker argv")
    boundary = execution["boundary"]
    _need(boundary["allocation_start_monotonic"] <= time.monotonic() <
          boundary["deadline_monotonic"], "original allocation clock")
    out = Path(execution["output"])
    _need(out.parent.is_dir() and out.parent.resolve() == out.parent and
          out.parent != Path(execution["preparation_output"] or "/"), "output parent")
    initialized = {"stdout.log", "stderr.log", "monitor-events.jsonl",
                   "monitor-evidence.jsonl", "monitor.json"}
    if worker:
        _need(out.is_dir() and {p.name for p in out.iterdir()} == initialized,
              "monitor-initialized output boundary")
    else:
        _need(not out.exists(), "fresh output required")
    _need(admission["free_disk_bytes"] >= 4294967296 and launch["free_disk_bytes"] >= 4294967296 and
          shutil.disk_usage(out.parent).free >= 4294967296, "disk floor")
    if plan["release"]["scope"] == "panel":
        q = execution["qualification"]
        report = strict_json(read_verified(root, q["report"]))
        binding = strict_json(read_verified(root, q["release"]))
        read_verified(root, q["unknown_child_guard"])
        _need(report["status"] == "PASS" and report["counts"] ==
              {"constructions": 0, "encodes": 0, "reads": 0, "factors": 0, "predictions": 0} and
              report["failure"] is None and
              report["template_sha256"] == launch["template_sha256"] and
              report["source_full_git"] == q["source_full_git"] and
              report["source_manifest"] == q["source_manifest"] and
              report["plan_sha256"] == digest(binding) and
              binding["release"]["scope"] == "binding" and
              binding["execution"]["source_full_git"] == q["source_full_git"],
              "binding qualification")
        report_root = Path(root) / Path(q["report"]["path"]).parent
        native = strict_json(read_verified(report_root, report["monitor"]))
        external = strict_json(read_verified(report_root, report["external"]))
        read_verified(report_root, report["events"])
        read_verified(report_root, report["journal"])
        _need(native["status"] == "COMPLETED" and native["returncode"] == 0 and
              native["source_event_accounting"]["complete"] is True and
              native["source_event_accounting"]["identity_complete"] is True and
              native["missing_worker_baselines"] == [] and
              native["unresolved_worker_count"] == 0 and
              external["monitor_status"] == "COMPLETED" and
              external["monitor_returncode"] == 0 and external["same_plan_bytes"] is True and
              external["commit_monotonic"] < binding["execution"]["boundary"]["deadline_monotonic"],
              "accepted zero-science native binding")
        _need(q["source_manifest"] == execution["source_manifest"] or
              (q["compatibility"] is not None and q["compatibility"]["material_manifest_equal"] is True),
              "qualified material source")
        if q["compatibility"] is not None:
            compat = q["compatibility"]
            _keys(compat, ("qualified_source", "current_source", "material_manifest_equal", "ruling"),
                  "qualification compatibility")
            _ref(compat["ruling"], "markdown")
            read_verified(root, compat["ruling"])
            _need(compat["qualified_source"] == q["source_full_git"] and
                  compat["current_source"] == execution["source_full_git"] and
                  compat["material_manifest_equal"] is True, "qualified/current source ruling")
    return boundary["deadline_monotonic"]


def _entry(plan, root, worker):
    validate_plan(plan)
    for name in PINS:
        read_verified(root, plan[name])
    _manifest(strict_json(read_verified(root, plan["panel"])))
    stage = validate_evidence(plan["evidence"], root)
    _need(plan["evidence"]["source"] == plan["execution"]["source_manifest"],
          "evidence/current source manifest mismatch")
    read_verified(root, plan["training"])
    setup = strict_json(read_verified(root, plan["evidence"]["setup"]))
    for candidate in plan["candidates"]:
        cid = candidate["id"]
        spec = strict_json(read_verified(root, candidate["static"]))
        read_verified(root, candidate["rates"])
        _need(candidate["static"]["sha256"] == setup["static_exports"][cid]["sha256"] and
              candidate["rates"]["sha256"] ==
              setup["represented_rate_records"][candidate["family"]]["sha256"] and
              candidate["config_sha256"] == digest(spec) and
              candidate["writer_sha256"] == spec["schema"]["fit_provenance"]["writer_hash"],
              "sealed candidate export/rate identity")
    dispositions = {(d["candidate"], d["transform"]): d for d in plan["approval"]["failures"]}
    _need(len(dispositions) == 24, "duplicate source dispositions")
    for row in stage["inventory"]:
        if row["row"] != 30:
            continue
        key = (row["candidate"][0] + ":" + row["candidate"][1], row["transform"])
        d = dispositions[key]
        _need(d["failed_fields"] == row["outcome"]["comparisons"]["A_B"]["failed_fields"],
              "manual disposition differs from raw A failure")
        read_verified(root, d["ruling"])
    for name in ("ruling", "source_review"):
        read_verified(root, plan["approval"][name])
    read_verified(root, plan["release"]["ruling"])
    compat = plan["approval"]["compatibility"]
    new_rows = _source_manifest(root, compat["new_manifest"])
    old_rows = strict_json(read_verified(root, compat["old_manifest"]))
    _need(type(old_rows) is list and old_rows == sorted(old_rows, key=lambda row: row["path"]),
          "historical source manifest order")
    old = {row["path"]: row for row in old_rows}
    new = {row["path"]: row for row in new_rows}
    _need(len(old) == len(old_rows), "duplicate historical material source")
    changed = sorted(path for path in old.keys() | new.keys() if old.get(path) != new.get(path))
    _need(compat["changed_paths"] == changed and
          all(old.get(path) == new.get(path) for path in old.keys() & new.keys()
              if path.startswith("famjet/") or path.startswith("validation/kernel_stage_a/") or
              path == "requirements.lock"), "material source compatibility inventory")
    return _execution_live(plan, root, worker)


def entry(plan, root):
    return _entry(plan, root, False)


def verify_worker(plan, root, event_path):
    """Single bounded authority Git phase, before importing scientific code."""
    import os
    from validation.kernel_stage_a import authority as a_authority

    plan_bytes = Path(plan["execution"]["launch"]["argv"][5]).read_bytes()
    _need(strict_json(plan_bytes) == plan, "worker Plan bytes changed")
    a_authority.event(event_path, "authority_start", pid=os.getpid(),
                      plan_file_sha256=hashlib.sha256(plan_bytes).hexdigest())
    success = False
    try:
        deadline = _entry(plan, root, True)
        _need(time.monotonic() < deadline, "original deadline expired")
        head = a_authority.git(root, "rev-parse", "HEAD", deadline=deadline, event_path=event_path)
        status = a_authority.git(root, "status", "--porcelain", deadline=deadline, event_path=event_path)
        _need(head == plan["execution"]["source_full_git"] and status == "", "source Git identity")
        success = True
    finally:
        a_authority.event(event_path, "authority_end", pid=os.getpid(), success=success)
    return deadline
