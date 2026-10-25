"""Small native-operation/gradient fixtures, checked against CPU FP64.

Timings are diagnostics for these fixtures, never writer/reader/training claims.
General fallback is disabled by doctor; built-in CPU fallback registrations may
still exist. Successful cells prove API/numerical support, not kernel residency.
"""
import io
import os
import random
import resource
import time

DEFAULT_SHAPES = [
    {"name": "tiny", "batch": 1, "heads": 1, "J": 4, "K": 16, "V": 8, "length": 8},
    {"name": "smoke", "batch": 1, "heads": 1, "J": 4, "K": 16, "V": 8, "length": 128},
    {"name": "initial_scientific", "batch": 1, "heads": 1, "J": 8, "K": 32, "V": 64, "length": 2048},
]
OPERATIONS = (
    "exp_arithmetic_reduction", "matmul", "einsum", "activations",
    "normalization", "index_gather_mask", "mlp_backward", "rates_backward",
    "checkpoint_backward", "short_convolution_backward", "serialization", "rng_restore",
)


def _fixture(torch, operation, shape, device, dtype):
    import numpy as np
    import torch.nn.functional as F
    from torch.utils.checkpoint import checkpoint

    b, h, j, k, v, length = (shape[key] for key in ("batch", "heads", "J", "K", "V", "length"))

    def bounded(dims, start=-0.25, end=0.25, grad=False):
        count = 1
        for dim in dims:
            count *= dim
        # Generate fixture values in FP64 then cast, identically on every device.
        return torch.linspace(start, end, count, dtype=torch.float64, device="cpu").reshape(dims).to(device=device, dtype=dtype).requires_grad_(grad)

    x = bounded((b, h, j, k, v + 1))
    if operation == "exp_arithmetic_reduction":
        decay = torch.exp(-x.abs())
        return [(x * decay + 0.1).sum(dim=-1), decay.mean(dim=-2)]
    if operation == "matmul":
        return [x @ bounded((v + 1, 8))]
    if operation == "einsum":
        return [torch.einsum("bhjkv,bk->bhjv", x, bounded((b, k), 0.1, 0.5))]
    if operation == "activations":
        return [F.silu(x), torch.sigmoid(x), torch.tanh(x), F.relu(x)]
    if operation == "normalization":
        # Spread values along the normalized axis. A global state linspace makes
        # each channel group almost constant and tests cancellation conditioning
        # instead of the ordinary bounded-input gate (see initial failed report).
        normalized_input = bounded((v + 1,), -0.25, 0.5).expand_as(x)
        return [F.layer_norm(normalized_input, (v + 1,)), normalized_input / (normalized_input.square().sum(dim=-1, keepdim=True) + 1e-8).sqrt()]
    if operation == "index_gather_mask":
        indices = torch.tensor([0, v], device=device).expand(b, h, j, k, 2)
        return [torch.gather(x, -1, indices), torch.where(x > 0, x, torch.zeros_like(x)), x[..., [0, v]]]
    if operation in ("mlp_backward", "checkpoint_backward"):
        features = bounded((b * h * j, v + 1), grad=True)
        w1 = bounded((v + 1, 128), -0.05, 0.05, grad=True)
        w2 = bounded((128, 128), -0.02, 0.02, grad=True)
        w3 = bounded((128, v), -0.05, 0.05, grad=True)
        def mlp(inputs):
            return F.silu(F.silu(inputs @ w1) @ w2) @ w3
        output = checkpoint(mlp, features, use_reentrant=False) if operation == "checkpoint_backward" else mlp(features)
        output.square().mean().backward()
        return [output, features.grad, w1.grad, w2.grad, w3.grad]
    if operation == "rates_backward":
        logits = bounded((j,), -1, 1, grad=True)
        rates = torch.exp(-6.907755278982137 + 6.907755278982137 * torch.sigmoid(logits))
        gaps = bounded((length,), 0, 1)
        output = torch.exp(-gaps[:, None] * rates[None, :]).mean(dim=0)
        output.sum().backward()
        return [output, logits.grad]
    if operation == "short_convolution_backward":
        stream = bounded((b, v, length), grad=True)
        kernel = bounded((v, 1, 3), -0.1, 0.1, grad=True)
        output = F.conv1d(stream, kernel, padding=1, groups=v)
        output.square().mean().backward()
        return [output, stream.grad, kernel.grad]
    if operation == "serialization":
        buffer = io.BytesIO()
        torch.save({"schema_version": 1, "state": x.detach().cpu()}, buffer)
        buffer.seek(0)
        restored = torch.load(buffer, weights_only=True)["state"].to(device)
        if not torch.equal(x, restored):
            raise AssertionError("serialization did not preserve tensor exactly")
        return [restored]
    if operation == "rng_restore":
        py_state, np_state, cpu_state = random.getstate(), np.random.get_state(), torch.get_rng_state()
        gpu_state = torch.mps.get_rng_state() if device == "mps" else None
        try:
            random.seed(20261013)
            np.random.seed(20261013)
            torch.default_generator.manual_seed(20261013)
            if device == "mps":
                torch.mps.manual_seed(20261013)
            saved = (random.getstate(), np.random.get_state(), torch.get_rng_state(), torch.mps.get_rng_state() if device == "mps" else None)
            first = (random.random(), np.random.random(), torch.rand((4,), device=device, dtype=dtype))
            random.setstate(saved[0])
            np.random.set_state(saved[1])
            torch.set_rng_state(saved[2])
            if device == "mps":
                torch.mps.set_rng_state(saved[3])
            second = (random.random(), np.random.random(), torch.rand((4,), device=device, dtype=dtype))
            if first[:2] != second[:2] or not torch.equal(first[2], second[2]):
                raise AssertionError("RNG state restore failed exact replay")
            # CPU/device RNG streams need not match; this fixture checks within-device replay.
            return [torch.ones((1,), device=device, dtype=dtype)]
        finally:
            random.setstate(py_state)
            np.random.set_state(np_state)
            torch.set_rng_state(cpu_state)
            if gpu_state is not None:
                torch.mps.set_rng_state(gpu_state)
    raise ValueError(f"Unknown operation {operation}")


def _memory(torch, device):
    result = {"process_lifetime_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    # macOS reports bytes; Linux reports KiB.
    import sys
    if sys.platform != "darwin":
        result["process_lifetime_peak_rss_bytes"] *= 1024
    if device == "mps":
        for name in ("current_allocated_memory", "driver_allocated_memory", "recommended_max_memory"):
            try:
                result[name + "_bytes"] = getattr(torch.mps, name)()
            except (AttributeError, RuntimeError) as error:
                result[name + "_unavailable_reason"] = str(error)
    return result


def probe_ops(device: str, shapes: list[dict]) -> dict:
    """Report explicit numerical/gradient support for bounded fixtures.

    A failed MPS cell never invalidates a passing CPU path. MPS tests require
    fallback and fast math off before torch import (the doctor enforces this).
    """
    import torch
    if device not in ("cpu", "mps"):
        raise ValueError("device must be cpu or mps")
    for shape in shapes:
        if not isinstance(shape.get("name"), str) or any(type(shape.get(key)) is not int or shape[key] < 1 for key in ("batch", "heads", "J", "K", "V", "length")):
            raise ValueError("Each named shape requires positive integer batch/heads/J/K/V/length")
        state_elements = shape["batch"] * shape["heads"] * shape["J"] * shape["K"] * (shape["V"] + 1)
        stream_elements = shape["batch"] * shape["V"] * shape["length"]
        rate_elements = shape["length"] * shape["J"]
        mlp_elements = (shape["V"] + 1) * 128 + 128 * 128 + 128 * shape["V"] + shape["batch"] * shape["heads"] * shape["J"] * (shape["V"] + 257)
        if max(state_elements, stream_elements, rate_elements, mlp_elements) > 2_000_000:
            raise ValueError("Doctor fixture exceeds bounded smoke allocation; calibrate separately")
    report = {"schema_version": 1, "device": device, "status": "ok", "reason": None, "elapsed_seconds": None, "rtol": 1e-5, "atol": 1e-6, "cells": [], "shapes": shapes, "precision_policy": "CPU float64 oracle; CPU float64 and float32; MPS float32 only", "native_kernel_profiling": "not_performed; general fallback disabled does not rule out built-in CPU fallback registrations"}
    if device == "mps":
        if not torch.backends.mps.is_available():
            return dict(report, status="unavailable", reason=f"MPS unavailable (built={torch.backends.mps.is_built()}); CPU remains supported", memory=None)
        if any(os.environ.get(name) != "0" for name in ("PYTORCH_ENABLE_MPS_FALLBACK", "PYTORCH_MPS_FAST_MATH")):
            return dict(report, status="unavailable", reason="Native MPS requires fallback=0 and fast_math=0 set before torch import", memory=None)
    def sync():
        if device == "mps":
            torch.mps.synchronize()
    begin = time.perf_counter()
    report["memory_before"] = _memory(torch, device)
    report["sampled_memory_maxima"] = {}
    report["memory_notes"] = "Process RSS is the process-lifetime high-water mark. Metal values are samples with fixture outputs live, not allocator peak tracking; never add RSS and driver bytes as independent unified pools."
    for shape in shapes:
        for operation in OPERATIONS:
            try:
                reference = _fixture(torch, operation, shape, "cpu", torch.float64)
            except Exception as error:
                reference = error
            for dtype in ((torch.float64, torch.float32) if device == "cpu" else (torch.float32,)):
                cell = {"shape": shape["name"], "operation": operation, "dtype": str(dtype).removeprefix("torch."), "status": "unsupported", "reason": None, "elapsed_seconds": None, "max_abs_error": None}
                try:
                    if isinstance(reference, Exception):
                        raise RuntimeError(f"CPU FP64 oracle failed: {reference}")
                    _fixture(torch, operation, shape, device, dtype)  # one warmup
                    sync()
                    start = time.perf_counter()
                    actual = _fixture(torch, operation, shape, device, dtype)
                    sync()
                    elapsed = time.perf_counter() - start
                    cell["elapsed_seconds"] = elapsed
                    cell["memory_after_fixture"] = _memory(torch, device)
                    for name, value in cell["memory_after_fixture"].items():
                        if isinstance(value, int):
                            report["sampled_memory_maxima"][name] = max(value, report["sampled_memory_maxima"].get(name, 0))
                    max_error = 0.0
                    for got, want in zip(actual, reference, strict=True):
                        if got is None or want is None:
                            raise AssertionError("Missing expected backward gradient")
                        got = got.detach().cpu().to(torch.float64)
                        want = want.detach().cpu()
                        if not torch.isfinite(got).all() or not torch.isfinite(want).all():
                            raise AssertionError("Nonfinite output/gradient")
                        max_error = max(max_error, (got - want).abs().max().item())
                        cell["max_abs_error"] = max_error
                        torch.testing.assert_close(got, want, rtol=1e-5, atol=1e-6)
                    cell.update(status="ok", elapsed_seconds=elapsed, max_abs_error=max_error)
                except Exception as error:
                    cell["reason"] = f"{type(error).__name__}: {error}"
                    report["status"] = "partial"
                report["cells"].append(cell)
    sync()
    report["elapsed_seconds"] = time.perf_counter() - begin
    report["memory_after_warm_probes"] = _memory(torch, device)
    if report["status"] == "partial":
        report["reason"] = "One or more cells unsupported or outside fixed tolerance; accelerated claims require every relevant native cell."
    return report
