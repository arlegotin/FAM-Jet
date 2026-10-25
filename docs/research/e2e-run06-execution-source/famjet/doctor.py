"""Read-only discovery and native operation gate: python -m famjet.doctor."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def utc_now():
    return datetime.now(timezone.utc).isoformat()


COMMANDS = {
    "architecture": ["uname", "-m"],
    "os": ["sw_vers"],
    "chip": ["sysctl", "-n", "machdep.cpu.brand_string"],
    "memory_bytes": ["sysctl", "-n", "hw.memsize"],
    "physical_cpus": ["sysctl", "-n", "hw.physicalcpu"],
    "gpu": ["system_profiler", "SPDisplaysDataType", "-json"],
    "disk": ["df", "-k", "."],
    "swap": ["sysctl", "-n", "vm.swapusage"],
    "vm_stat": ["vm_stat"],
    "memory_pressure": ["memory_pressure", "-Q"],
    "power_source": ["pmset", "-g", "batt"],
    "power_configuration": ["pmset", "-g", "custom"],
    "thermal": ["pmset", "-g", "therm"],
    "developer_tools": ["xcode-select", "-p"],
    "git": ["git", "--version"],
}


def command_record(args):
    record = {"command": args, "observed_at_utc": utc_now()}
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=30, check=False)
        if result.returncode:
            return dict(record, status="unavailable", reason=(result.stderr or result.stdout).strip() or f"exit {result.returncode}", value=None)
        # Display profile includes monitor serials/UUIDs; retain only hardware capabilities.
        value = result.stdout.strip()
        if args == ["pmset", "-g", "therm"] and "error" in value.lower():
            return dict(record, status="unavailable", reason=value, value=None)
        if args == ["pmset", "-g", "batt"]:
            value = re.sub(r"\(id=\d+\)", "(id=redacted)", value)
        if args[0] == "system_profiler":
            devices = json.loads(value).get("SPDisplaysDataType", [])
            value = [{key: device[key] for key in ("sppci_model", "sppci_cores", "spdisplays_metal") if key in device} for device in devices]
        return dict(record, status="ok", reason=None, value=value)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        return dict(record, status="unavailable", reason=f"{type(error).__name__}: {error}", value=None)


def discover() -> dict:
    """Discover each field independently; no torch or optional dependencies required."""
    return {
        "schema_version": 1,
        "observed_at_utc": utc_now(),
        "python": {"version": sys.version, "executable": sys.executable, "machine": platform.machine(), "build": platform.python_build()},
        "commands": {name: command_record(args) for name, args in COMMANDS.items()},
        "notes": ["Read-only commands; no private hardware identifiers retained.", "vm_stat counters and installed RAM are not allocation budgets; swap usage is not swap throughput."],
    }


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def derive_resource_policy(commands, device_reports):
    """Conservative additional smoke allocation only; never a training guarantee.

    Count currently free/speculative pages, not inactive/compressed RAM. Cap the
    observation at 256 MiB, then reserve 25%. Metal's recommendation is a further
    bound on the same unified pool; it is never added to system availability.
    """
    policy = {"status": "uncalibrated", "microbatch": 1, "effective_batch": 1,
              "reserved_fraction_of_derived_envelope": 0.25,
              "derived_available_bytes": None, "smoke_additional_allocation_limit_bytes": None,
              "training_envelope_bytes": None, "disk_asset_budget_bytes": 0,
              "reason": "Missing usable current free-page/pressure observations; smoke only, no training headroom claim."}
    vm = commands.get("vm_stat", {})
    pressure = commands.get("memory_pressure", {})
    if vm.get("status") != "ok" or pressure.get("status") != "ok":
        return policy
    page_size = re.search(r"page size of (\d+) bytes", vm["value"])
    free = re.search(r"Pages free:\s+(\d+)", vm["value"])
    speculative = re.search(r"Pages speculative:\s+(\d+)", vm["value"])
    if not page_size or not free:
        return policy
    available = int(page_size[1]) * (int(free[1]) + (int(speculative[1]) if speculative else 0))
    mps_memory = device_reports.get("mps", {}).get("memory_after_warm_probes", {})
    recommendation = mps_memory.get("recommended_max_memory_bytes")
    driver = mps_memory.get("driver_allocated_memory_bytes")
    if recommendation is not None and driver is not None:
        available = min(available, max(0, recommendation - driver))
    envelope = min(available, 256 * 1024 * 1024)
    policy.update(status="smoke_only", derived_available_bytes=available,
                  smoke_additional_allocation_limit_bytes=int(envelope * 0.75),
                  reason="Fresh free+speculative pages bounded by Metal headroom if available; cap 256 MiB and reserve 25%. Full training peaks/sustained pressure remain uncalibrated.")
    return policy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("artifacts/environment"))
    parser.add_argument("--discover-only", action="store_true", help="stdlib-only read-only discovery; never imports torch")
    args = parser.parse_args(argv)
    hardware = discover()
    write_json(args.out / "hardware.json", hardware)
    if args.discover_only:
        return 0
    # These flags must precede the first torch import; fail closed on conflicting caller flags.
    flags = {"PYTORCH_ENABLE_MPS_FALLBACK": "0", "PYTORCH_MPS_FAST_MATH": "0"}
    for name, value in flags.items():
        if os.environ.get(name, value) != value:
            print(f"Refusing native reference probe: {name} must equal {value}", file=sys.stderr)
            return 2
        os.environ[name] = value
    for name in ("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "PYTORCH_MPS_LOW_WATERMARK_RATIO"):
        value = os.environ.get(name)
        if value is not None:
            try:
                protective = float(value) > 0
            except ValueError:
                protective = False
            if not protective:
                print(f"Refusing probe: allocator protection {name} must remain positive or unset", file=sys.stderr)
                return 2
    try:
        import torch
        from .ops import DEFAULT_SHAPES, probe_ops
    except ImportError as error:
        write_json(args.out / "op_support.json", {"schema_version": 1, "status": "unavailable", "reason": str(error), "observed_at_utc": utc_now()})
        return 1
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    try:
        packages = {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "torch", "pytest", "PyYAML", "pip")
        }
    except importlib.metadata.PackageNotFoundError as error:
        write_json(args.out / "op_support.json", {
            "schema_version": 1, "status": "unavailable",
            "reason": str(error), "observed_at_utc": utc_now(),
        })
        return 1
    hardware["dependencies"] = packages
    hardware["pip_freeze"] = command_record([sys.executable, "-m", "pip", "freeze"])
    hardware["torch_build_config"] = torch.__config__.show()
    hardware["mps_flags"] = {name: os.environ.get(name) for name in ("PYTORCH_ENABLE_MPS_FALLBACK", "PYTORCH_MPS_FAST_MATH", "PYTORCH_MPS_HIGH_WATERMARK_RATIO", "PYTORCH_MPS_LOW_WATERMARK_RATIO", "PYTORCH_MPS_PREFER_METAL", "PYTORCH_MPS_LOG_PROFILE_INFO", "PYTORCH_MPS_TRACE_SIGNPOSTS", "PYTORCH_DEBUG_MPS_ALLOCATOR")}
    hardware["mps"] = {"built": torch.backends.mps.is_built(), "available": torch.backends.mps.is_available(), "apis": {name: hasattr(torch.mps, name) for name in ("synchronize", "current_allocated_memory", "driver_allocated_memory", "recommended_max_memory", "get_rng_state", "set_rng_state", "empty_cache")}}
    reports = {device: probe_ops(device, DEFAULT_SHAPES) for device in ("cpu", "mps")}
    hardware["post_probe_commands"] = {name: command_record(COMMANDS[name]) for name in ("disk", "swap", "vm_stat", "memory_pressure", "power_source", "thermal")}
    hardware["resource_policy"] = derive_resource_policy(hardware["post_probe_commands"], reports)
    hardware["resource_policy"]["cpu_threads"] = torch.get_num_threads()
    write_json(args.out / "hardware.json", hardware)
    write_json(args.out / "op_support.json", {
        "schema_version": 1,
        "observed_at_utc": utc_now(),
        "devices": reports,
        "timing_scope": "One warmed operation/gradient fixture per cell; diagnostic wall times include input construction, device transfers, serialization or backward as applicable; numerical comparisons are outside the timer. No scientific benchmark or model throughput is measured.",
    })
    lock = Path("requirements.lock")
    provenance_paths = (
        Path("docs/research/2026-10-16-native-wheels.json"),
        Path("docs/research/2026-10-16-source-verification.md"),
    )
    write_json(args.out / "assets.json", {
        "schema_version": 1,
        "observed_at_utc": utc_now(),
        "assets": [],
        "status": "no_dataset_or_model_downloads",
        "dependency_lock": {
            "path": str(lock),
            "sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None,
        },
        "dependencies": packages,
        "documentation": {
            "torch": f"https://docs.pytorch.org/docs/{'.'.join(torch.__version__.split('.')[:2])}/",
            "numpy": f"https://numpy.org/doc/{'.'.join(packages['numpy'].split('.')[:2])}/",
            "scipy": f"https://docs.scipy.org/doc/scipy-{packages['scipy']}/",
            "pytest": f"https://docs.pytest.org/en/{'.'.join(packages['pytest'].split('.')[:2])}.x/",
            "PyYAML": "https://pyyaml.org/wiki/PyYAMLDocumentation",
        },
        "provenance_records": [
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in provenance_paths if path.exists()
        ],
        "note": "Dependency wheels are pinned by hashes in requirements.lock; scientific sources were inspected read-only in the provenance record, with no dataset/model download here. Documentation URLs name installed versions; access verification is recorded separately in the environment-gate report.",
    })
    return 0 if reports["cpu"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
