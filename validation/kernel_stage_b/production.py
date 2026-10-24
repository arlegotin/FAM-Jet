"""Scientific backend imported only after a complete worker authority phase."""
from dataclasses import replace
import math


COUNTERS = {"coefficients", "window_vector", "snapshot_record", "snapshot_from_record",
            "_advance_payload", "_reconstruct", "read", "tensor_clone", "factor"}


class DecodeError(ValueError):
    """The guarded reader returned a malformed or mismatched numeric record."""


def panel_config_for_entry(base, entry):
    """Preserve the original resolved config except three closed substitutions."""
    if entry["length"] not in (128, 512, 2048) or entry["regime"] not in (
            "piecewise_stationary", "trend_reset", "periodic_impulses", "irregular_revisions"):
        raise ValueError("unsupported panel cell")
    development = replace(base.development, eval_histories_per_cell=8)
    generator = replace(base.data.generator, namespace="development_fit", regime=entry["regime"])
    data = replace(base.data, length=entry["length"], generator=generator)
    return replace(base, development=development, data=data)


def _keys(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(label + " schema mismatch")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _shape(value, outer, inner, leaf):
    return (type(value) is list and len(value) == outer and
            all(type(row) is list and len(row) == inner and all(leaf(v) for v in row)
                for row in value))


def decode_response(response):
    """Validate the unchanged Q8 reader wire format without replacing nulls."""
    _keys(response, ("numeric", "counts", "windows", "coefficients", "window_vectors", "seconds"),
          "reader response")
    n = response["numeric"]
    _keys(n, ("prediction", "logits", "support", "failure", "diagnostics", "schema_version"),
          "numeric")
    if type(n["schema_version"]) is not int or n["schema_version"] != 1 or n["logits"] is not None:
        raise ValueError("numeric version/logits")
    nullable = lambda x: x is None or _number(x)
    boolean = lambda x: type(x) is bool
    if not _shape(n["prediction"], 1, 8, lambda row: type(row) is list and len(row) == 8 and all(nullable(x) for x in row)):
        raise ValueError("Q8 prediction shape")
    if not _shape(n["support"], 1, 8, nullable) or not _shape(n["failure"], 1, 8, boolean):
        raise ValueError("Q8 support/failure shape")
    d = n["diagnostics"]
    booleans = ("numerical_eligible", "prediction_valid", "numeric_supported",
                "factual_support_available", "quarantined")
    _keys(d, (*booleans, "failure_code", "reconstructed_mass", "cancellation_bound"), "diagnostics")
    if any(not _shape(d[k], 1, 8, boolean) for k in booleans):
        raise ValueError("Q8 diagnostics shape")
    pair = lambda x: type(x) is list and len(x) == 2
    if not _shape(d["failure_code"], 1, 8,
                  lambda x: pair(x) and all(type(v) is int and 0 <= v <= 7 for v in x)):
        raise ValueError("Q8 failure codes")
    for key in ("reconstructed_mass", "cancellation_bound"):
        if not _shape(d[key], 1, 8, lambda x: pair(x) and all(nullable(v) for v in x)):
            raise ValueError("Q8 " + key)
    counts = response["counts"]
    if type(counts) is not dict or not set(counts) <= COUNTERS or any(type(v) is not int or v < 0 for v in counts.values()):
        raise ValueError("reader counters")
    if counts.get("read", 0) != 1 or counts.get("factor", 0) != 0:
        raise ValueError("reader operation/factor count")
    if not _number(response["seconds"]) or response["seconds"] < 0:
        raise ValueError("reader time")
    windows, coefficients, vectors = (response[k] for k in ("windows", "coefficients", "window_vectors"))
    if (type(windows) is not list or type(coefficients) is not list or type(vectors) is not list or
            len(windows) != len(coefficients) or len(windows) != len(vectors) or len(windows) > 16):
        raise ValueError("reader window lists")
    vector = lambda x: type(x) is list and len(x) == 8 and all(nullable(v) for v in x)
    for window, coeff, vec in zip(windows, coefficients, vectors):
        _keys(window, ("code", "prediction", "mass", "bound", "raw", "reached"), "window")
        if type(window["code"]) is not int or not 0 <= window["code"] <= 7:
            raise ValueError("window code")
        _keys(window["reached"], ("coefficients", "mass", "bound", "raw", "prediction"), "reached")
        if any(type(v) is not bool for v in window["reached"].values()):
            raise ValueError("reached flags")
        if coeff is not None and not vector(coeff) or not (vec == [] or vector(vec)):
            raise ValueError("window vectors")
        if any((window[key] is None) == window["reached"][key] for key in ("mass", "bound", "raw", "prediction")):
            raise ValueError("window reached/null mismatch")
        if (coeff is None) == window["reached"]["coefficients"]:
            raise ValueError("coefficient reached/null mismatch")
        if (window["prediction"] is not None and not vector(window["prediction"]) or
                window["raw"] is not None and not vector(window["raw"])):
            raise ValueError("window prediction/raw")
        if (window["mass"] is not None and not _number(window["mass"]) or
                window["bound"] is not None and not _number(window["bound"])):
            raise ValueError("window mass/bound")
    return response


def validate_window_order(response, tasks, state_valid, intervals=None):
    """Bind each reached window to its Q8 position and short-circuit path."""
    if type(tasks) not in (tuple, list) or len(tasks) != 8 or any(t not in ("mean", "contrast") for t in tasks):
        raise ValueError("Q8 task order")
    d = response["numeric"]["diagnostics"]
    windows = response["windows"]
    position = 0
    for j, task in enumerate(tasks):
        codes = d["failure_code"][0][j]
        def unused(k):
            if (codes[k] != 0 or d["reconstructed_mass"][0][j][k] is not None or
                    d["cancellation_bound"][0][j][k] is not None):
                raise ValueError("unused diagnostic slot must retain producer null")
        if not state_valid:
            if codes != [5, 0] or d["quarantined"][0][j]:
                raise ValueError("empty-state short circuit")
            if d["reconstructed_mass"][0][j] != [None, None] or d["cancellation_bound"][0][j] != [None, None]:
                raise ValueError("unused empty-state diagnostics")
            continue
        if d["quarantined"][0][j]:
            raise ValueError("unexpected reader quarantine after finite encoding")
        for k in range(1 if task == "mean" else 2):
            if k == 1 and codes[0] != 0:
                break
            if intervals is not None:
                lower, upper = intervals[j][k]
                if not math.isfinite(lower) or not math.isfinite(upper) or not lower < upper:
                    if codes[k] != 7:
                        raise ValueError("invalid interval code")
                    if (d["reconstructed_mass"][0][j][k] is not None or
                            d["cancellation_bound"][0][j][k] is not None):
                        raise ValueError("unexecuted invalid interval diagnostics must remain null")
                    break
            if position >= len(windows):
                raise ValueError("missing reached window")
            window = windows[position]
            position += 1
            final_contrast_overflow = task == "contrast" and k == 1 and codes[k] == 7 and window["code"] == 0
            if codes[k] != window["code"] and not final_contrast_overflow:
                raise ValueError("window query/code order")
            if (d["reconstructed_mass"][0][j][k] != window["mass"] or
                    d["cancellation_bound"][0][j][k] != window["bound"]):
                raise ValueError("window diagnostic position")
            if window["code"] != 0:
                break
        if task == "mean" or task == "contrast" and codes[0] != 0:
            unused(1)
    if position != len(windows):
        raise ValueError("extra reader window")


def score_numeric(candidate_id, episode, statistics, policy, manifest_hash, numeric, trigger):
    """Use the unchanged v2 scorer for actual numeric results or quarantine."""
    import torch
    from famjet.eval.metrics import score_predictions
    from famjet.provenance import canonical_hash
    from famjet.types import PredictionBatch

    q = episode.queries
    if tuple(q.query_ids.shape) != (1, 8) or tuple(episode.labels.shape) != (1, 8, 8):
        raise ValueError("fixed B1/Q8/V8 scoring shape required")
    if trigger is not None:
        raw = torch.full((1, 8, 8), float("nan"), dtype=torch.float64)
        valid = [[False] * 8]; supported = [[False] * 8]; failed = [[True] * 8]
    else:
        if numeric is None:
            raise ValueError("missing numeric reader response")
        raw = torch.tensor([[[float("nan") if v is None else v for v in row]
                             for row in numeric["prediction"][0]]], dtype=torch.float64)
        d = numeric["diagnostics"]
        valid = d["prediction_valid"]
        supported = d["numeric_supported"]
        failed = numeric["failure"]
    context = dict(version=2, output_convention="numeric", present=q.present.cpu().tolist(),
                   tasks=q.tasks, target_valid=episode.metadata["target_valid"],
                   numeric_supported=supported, prediction_valid=valid,
                   quarantined=[[trigger is not None] * 8], quarantine_trigger=trigger,
                   method=candidate_id, replicate=0, regime=episode.metadata["regime"],
                   target_semantics="observed_event_targets_v2", manifest_hash=manifest_hash,
                   statistics_hash=canonical_hash(statistics))
    batch = PredictionBatch(q.history_ids, q.query_ids.cpu(), raw, episode.labels.cpu(),
                            episode.supported.cpu(), torch.tensor(failed, dtype=torch.bool),
                            torch.zeros((1, 8), dtype=torch.bool), {"scoring_v2": context})
    return score_predictions(batch, statistics, policy)


class Backend:
    """The sole released scientific path; construction itself performs no work."""

    def __init__(self, plan, root):
        from pathlib import Path
        from .authority import read_verified, strict_json
        self.plan = plan
        self.root = Path(root)
        self.out = Path(plan["execution"]["output"])
        self.models = {}
        self.specs = {}
        self.episodes = {}
        self.policies = {}
        self.read_ordinal = 0
        self.candidate_deadline = None
        source = strict_json(read_verified(self.root, plan["panel"]))
        self.entries = [dict(entry, query_ids=list(range(8))) for entry in
                        source["splits"]["development_fit"]["episodes"]]

    def prepare(self):
        from dataclasses import asdict
        import hashlib
        from famjet.config import load_config, validate_config
        from famjet.data.synthetic import generate_episode
        from famjet.eval import isolation
        from famjet.eval.runner import episode_policy
        from famjet.provenance import derive_seed
        from .authority import canonical, digest, read_verified, strict_json

        manifest = strict_json(read_verified(self.root, self.plan["panel"]))
        base = load_config(self.root / self.plan["panel_config"]["path"])
        validate_config(base)
        if asdict(base.data) != manifest["data"] or base.development.data_seed != 20261017018:
            raise ValueError("original resolved generator config mismatch")
        if derive_seed(base.development.data_seed, "task18_development_v2", "shared") != 3626995086544026198:
            raise ValueError("original panel seed derivation mismatch")
        base_raw = canonical(asdict(base))
        resolved = self.out / "resolved-panel-config.json"
        resolved.write_bytes(base_raw)
        self.resolved_ref = self._ref(resolved, "resolved_run_config")
        training = strict_json(read_verified(self.root, self.plan["training"]))
        package = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((self.root / "famjet").rglob("*.py"))}
        self.source_hash = digest(package)
        if self.source_hash != "15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050":
            raise ValueError("sealed famjet package changed")
        for candidate in self.plan["candidates"]:
            spec = strict_json(read_verified(self.root, candidate["static"]))
            if digest(spec) != candidate["config_sha256"]:
                raise ValueError("candidate export identity mismatch")
            model = isolation._reconstruct(spec, freeze_rates=True)
            if model.reader.family != candidate["family"] or model.reader.ridge.hex() != candidate["ridge_hex"]:
                raise ValueError("static family/ridge mismatch")
            if isolation.export_method(model) != spec:
                raise ValueError("export round trip mismatch")
            family = candidate["family"]
            frozen = training[family]
            if model.fit_provenance != frozen["fit_provenance"] or model.target_statistics != frozen["target_statistics"]:
                raise ValueError("frozen fallback identity mismatch")
            rates = strict_json(read_verified(self.root, candidate["rates"]))
            if rates != [x.hex() for x in model.kernel.rates[0].tolist()]:
                raise ValueError("represented rate bits mismatch")
            if model._parameter_hash() != candidate["writer_sha256"]:
                raise ValueError("writer identity mismatch")
            self.models[candidate["id"]] = model
            self.specs[candidate["id"]] = spec
        for family in ("jet", "bank"):
            ids = [c["id"] for c in self.plan["candidates"] if c["family"] == family]
            if len({self.models[cid]._parameter_hash() for cid in ids}) != 1:
                raise ValueError("family writer identity mismatch")
        entries = []
        from famjet.data.synthetic import batch_hash
        for source in manifest["splits"]["development_fit"]["episodes"]:
            c = panel_config_for_entry(base, source)
            validate_config(c)
            ep = generate_episode(c, source["seed"], source["episode_id"])
            hashes = {"events": batch_hash(ep.events), "queries": batch_hash(ep.queries),
                      "oracle": ep.metadata["hashes"]["oracle"]}
            if hashes != source["hashes"] or ep.metadata["hashes"] != source["hashes"]:
                raise ValueError("rematerialized panel identity mismatch")
            if tuple(ep.queries.query_ids.shape) != (1, 8) or tuple(ep.labels.shape) != (1, 8, 8):
                raise ValueError("full Q8 panel required")
            query_ids = ep.queries.query_ids[0].cpu().tolist()
            if query_ids != list(range(8)):
                raise ValueError("original stateless Q8 query IDs changed")
            entry = dict(source, query_ids=query_ids)
            entries.append(entry)
            self.episodes[source["episode_id"]] = ep
        for length in (128, 512, 2048):
            policy = episode_policy([self.episodes[e["episode_id"]] for e in entries if e["length"] == length])
            if (policy["primary_tasks"] != ["contrast", "mean"] or policy["task_weights"] !=
                    {"contrast": 0.5, "mean": 0.5} or policy["regime_weights"] !=
                    {r: 0.25 for r in ("piecewise_stationary", "trend_reset",
                                       "periodic_impulses", "irregular_revisions")}):
                raise ValueError("fixed length policy mismatch")
            self.policies[length] = policy
        self.manifest_hash = manifest["manifest_hash"]
        return dict(entries=entries, resolved_panel_config=self.resolved_ref)

    def _ref(self, path, kind):
        import hashlib
        raw = path.read_bytes()
        return dict(kind=kind, path=str(path.relative_to(self.out)),
                    sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))

    def encode(self, family, entry):
        from dataclasses import replace
        import torch
        import time
        from famjet.data.schema import validate_events, validate_queries
        from famjet.data.synthetic import batch_hash
        from famjet.eval.budgets import state_ledger
        from famjet.eval.state_io import snapshot_hash, state_bytes

        ep = self.episodes[entry["episode_id"]]
        validate_events(ep.events); validate_queries(ep.queries)
        events = ep.events; queries = ep.queries
        count = int(events.lengths[0])
        if count and bool((queries.T[queries.present.cpu()] < events.timestamps[0, count - 1]).any()):
            raise ValueError("queries precede completed history")
        candidate = next(c for c in self.plan["candidates"] if c["family"] == family)
        model = self.models[candidate["id"]]
        state = None; trigger = None; start = time.monotonic()
        reference = model.kernel.reference_tensor
        writer_events = replace(events,
                                key_features=events.key_features.to(reference),
                                values=events.values.to(reference),
                                present=events.present.to(reference.device),
                                observed=events.observed.to(reference.device),
                                auxiliary={k: v.to(reference.device) for k, v in events.auxiliary.items()})
        with torch.no_grad():
            for offset in range(count):
                event = replace(writer_events, **{k: getattr(writer_events, k)[:, offset:offset + 1]
                                                  for k in ("event_ids", "timestamps", "key_ids",
                                                            "key_features", "values", "present", "observed")},
                                lengths=torch.ones_like(writer_events.lengths),
                                auxiliary={k: v[:, offset:offset + 1] for k, v in writer_events.auxiliary.items()})
                state = model.encode(event, state, mode="stream")
                fields = {**state.payload, "last_time": state.last_time}
                bad = [name for name, value in fields.items()
                       if value.is_floating_point() and not bool(torch.isfinite(value).all())]
                if bad:
                    if events.auxiliary:
                        raise ValueError("primary panel auxiliary fields unexpected")
                    raw_event = replace(events, **{k: getattr(events, k)[:, offset:offset + 1]
                                                   for k in ("event_ids", "timestamps", "key_ids",
                                                             "key_features", "values", "present", "observed")},
                                        lengths=torch.ones_like(events.lengths),
                                        auxiliary={k: v[:, offset:offset + 1] for k, v in events.auxiliary.items()})
                    trigger = dict(reason="nonfinite_stored_state", fields=bad,
                                   event_offset=offset + 1, parameter_hash=state.parameter_hash,
                                   input_hash=batch_hash(raw_event), state_hash=batch_hash(state),
                                   input=dict(event_id=int(events.event_ids[0, offset]),
                                              timestamp=events.timestamps[0, offset].item(),
                                              key_id=int(events.key_ids[0, offset]),
                                              values=events.values[0, offset].cpu().tolist(),
                                              observed=events.observed[0, offset].cpu().tolist(),
                                              key_features=events.key_features[0, offset].cpu().tolist(),
                                              auxiliary={}), history_id=entry["episode_id"])
                    break
            if state is None:
                state = model.encode(writer_events, mode="stream")
        if state.parameter_hash != candidate["writer_sha256"]:
            raise ValueError("encoded writer changed")
        logical_bytes = (model.persistent_nbytes(state) if trigger is None else
                         state_ledger(state)["logical_bytes"])
        raw = state_bytes(state)
        path = self.out / f"snapshot-{family}-{entry['episode_id']}.json"
        path.write_bytes(raw)
        record = dict(version=1, family=family, history_id=entry["episode_id"],
                      writer_sha256=state.parameter_hash, snapshot=self._ref(path, "snapshot"),
                      snapshot_hash=snapshot_hash(state), logical_bytes=logical_bytes,
                      trigger=trigger, event_count=int(state.event_offset[0]),
                      encoding_seconds=time.monotonic() - start)
        return dict(state=state, record=record)

    def read(self, candidate, entry, snapshot):
        from dataclasses import replace
        import json
        import os
        import tempfile
        import time
        from famjet.eval import isolation
        from famjet.eval.state_io import snapshot_hash, snapshot_record
        from validation.kernel_stage_a import commands
        from validation.kernel_stage_a.production import owned_reader_dispatch
        from .authority import canonical, digest, strict_json

        if self.candidate_deadline is None or time.monotonic() >= self.candidate_deadline:
            raise TimeoutError("candidate/original deadline before read")
        state = snapshot["state"]
        before = snapshot_hash(state)
        if before != snapshot["record"]["snapshot_hash"] or state.parameter_hash != candidate["writer_sha256"]:
            raise ValueError("saved state identity mismatch")
        ep = self.episodes[entry["episode_id"]]
        if ep.queries.query_ids[0].cpu().tolist() != entry["query_ids"]:
            raise ValueError("ordered query IDs changed")
        from famjet.data.synthetic import batch_hash
        if batch_hash(ep.queries) != entry["hashes"]["queries"]:
            raise ValueError("ordered query bytes changed")
        spec = self.specs[candidate["id"]]
        model = self.models[candidate["id"]]
        reader_queries = replace(ep.queries,
                                 key_features=ep.queries.key_features.to(model.kernel.reference_tensor))
        request = dict(method=spec, state=snapshot_record(state),
                       queries=isolation._query_record(reader_queries), operation="read",
                       model_hash=digest(spec), source_hash=self.source_hash)
        raw = canonical(request)
        index = self.read_ordinal
        req_path = self.out / f"request-{index:03}.json"
        stdout_path = self.out / f"reader-{index:03}.jsonl"
        stderr_path = self.out / f"reader-{index:03}.stderr"
        req_path.write_bytes(raw)
        self.on_attempt(self._ref(req_path, "request"))
        env = {k: "1" for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                 "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}
        env.update(PYTORCH_ENABLE_MPS_FALLBACK="0", PYTORCH_MPS_FAST_MATH="0")
        vector = commands.reader_command(self.root, self.out / "monitor-events.jsonl",
                                         self.candidate_deadline)
        if vector[0] != self.plan["execution"]["runtime"]["executable"]:
            raise ValueError("reader Python image mismatch")
        with (tempfile.TemporaryDirectory(prefix="reader-", dir=self.out) as work,
              stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr):
            result = owned_reader_dispatch(vector, input=raw, stdout=stdout, stderr=stderr,
                                           cwd=work, env=env, deadline=self.candidate_deadline,
                                           event_path=self.out / "monitor-events.jsonl",
                                           runtime_identity=self.plan["execution"]["runtime"])
        self.read_ordinal += 1
        if result.returncode != 0 or stderr_path.read_bytes() != b"":
            raise ValueError("reader engine/transport failure")
        try:
            lines = stdout_path.read_bytes().splitlines()
            if not lines:
                raise ValueError("missing reader result")
            observed = {k: 0 for k in COUNTERS}
            for line in lines[:-1]:
                item = strict_json(line)
                _keys(item, ("counter",), "reader counter")
                if item["counter"] not in COUNTERS:
                    raise ValueError("unknown reader counter")
                observed[item["counter"]] += 1
            response = decode_response(strict_json(lines[-1]))
            if any(response["counts"].get(k, 0) != count for k, count in observed.items()):
                raise ValueError("reader emitted count mismatch")
            intervals = []
            for j, task in enumerate(ep.queries.tasks[0]):
                lower = ep.queries.age_start[0, j].item() / model.kernel.t_ref
                upper = ep.queries.age_end[0, j].item() / model.kernel.t_ref
                intervals.append([(lower, upper)] +
                                 ([(upper, upper + (upper - lower))] if task == "contrast" else []))
            validate_window_order(response, ep.queries.tasks[0], bool(state.valid[0]), intervals)
        except ValueError as exc:
            raise DecodeError(str(exc)) from exc
        if snapshot_hash(state) != before:
            raise ValueError("saved state mutated by read")
        return dict(numeric=response["numeric"], counts=response["counts"],
                    seconds=response["seconds"], request=self._ref(req_path, "request"),
                    stdout=self._ref(stdout_path, "bytes"), stderr=self._ref(stderr_path, "bytes"))

    def score(self, candidate, entry, numeric, trigger):
        ep = self.episodes[entry["episode_id"]]
        model = self.models[candidate["id"]]
        return score_numeric(candidate["id"], ep, model.target_statistics,
                             self.policies[entry["length"]], self.manifest_hash,
                             numeric, trigger)
