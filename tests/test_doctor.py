"""Lightweight environment contracts; discovery runs without third-party packages."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class DiscoveryTests(unittest.TestCase):
    def test_discovery_partial_failure_is_explicit(self):
        from famjet.doctor import discover
        real_run = subprocess.run

        def run(args, **kwargs):
            if args[0] == "sysctl":
                raise FileNotFoundError("sysctl unavailable in fixture")
            return real_run(args, **kwargs)

        with patch("subprocess.run", side_effect=run):
            report = discover()
        field = report["commands"]["memory_bytes"]
        self.assertEqual(field["status"], "unavailable")
        self.assertIn("sysctl", field["reason"])
        self.assertTrue(field["observed_at_utc"].endswith("+00:00"))
        self.assertEqual(report["commands"]["architecture"]["status"], "ok")
        self.assertEqual(report["schema_version"], 1)

    def test_zero_exit_thermal_error_is_unavailable(self):
        from famjet.doctor import command_record
        with patch("subprocess.run", return_value=subprocess.CompletedProcess(["pmset"], 0, "Error: Failed to get thermal warning level", "")):
            report = command_record(["pmset", "-g", "therm"])
        self.assertEqual(report["status"], "unavailable")
        self.assertIn("thermal", report["reason"])

    def test_battery_identifiers_are_redacted(self):
        from famjet.doctor import command_record
        with patch("subprocess.run", return_value=subprocess.CompletedProcess(["pmset"], 0, "AC Power\n -InternalBattery-0 (id=123456) 100% charged", "")):
            report = command_record(["pmset", "-g", "batt"])
        self.assertNotIn("123456", report["value"])
        self.assertIn("100% charged", report["value"])

    def test_resource_envelope_reserves_memory_and_requires_observations(self):
        from famjet.doctor import derive_resource_policy
        commands = {
            "vm_stat": {"status": "ok", "value": "page size of 16384 bytes\nPages free: 65536.\nPages speculative: 0."},
            "memory_pressure": {"status": "ok", "value": "System-wide memory free percentage: 73%"},
        }
        policy = derive_resource_policy(commands, {})
        self.assertEqual(policy["derived_available_bytes"], 1073741824)
        self.assertEqual(policy["smoke_additional_allocation_limit_bytes"], 201326592)
        self.assertIsNone(policy["training_envelope_bytes"])
        unavailable = derive_resource_policy({}, {})
        self.assertIsNone(unavailable["smoke_additional_allocation_limit_bytes"])
        self.assertEqual(unavailable["status"], "uncalibrated")

    def test_discovery_does_not_import_torch(self):
        result = subprocess.run(
            [sys.executable, "-c", "from famjet.doctor import discover; import sys; discover(); assert 'torch' not in sys.modules"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_doctor_rejects_disabled_allocator_protection(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-m", "famjet.doctor", "--out", directory],
                                    env=dict(os.environ, PYTORCH_MPS_HIGH_WATERMARK_RATIO="0"),
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("allocator", result.stderr)

    def test_discover_only_writes_versioned_hardware(self):
        from famjet.doctor import main
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["--discover-only", "--out", directory]), 0)
            report = json.loads((Path(directory) / "hardware.json").read_text())
            self.assertEqual(report["schema_version"], 1)
            self.assertIn("disk", report["commands"])
            self.assertFalse((Path(directory) / "op_support.json").exists())


@unittest.skipUnless(importlib.util.find_spec("torch"), "torch not installed; discovery remains testable")
class OperationTests(unittest.TestCase):
    def test_missing_core_dependency_is_explicit(self):
        import importlib.metadata
        from famjet.doctor import main
        version = importlib.metadata.version
        def installed(name):
            if name == "scipy":
                raise importlib.metadata.PackageNotFoundError("scipy")
            return version(name)
        with tempfile.TemporaryDirectory() as directory, patch("importlib.metadata.version", side_effect=installed):
            self.assertEqual(main(["--out", directory]), 1)
            self.assertTrue((Path(directory) / "hardware.json").exists())
            report = json.loads((Path(directory) / "op_support.json").read_text())
        self.assertEqual(report["status"], "unavailable")
        self.assertIn("scipy", report["reason"])

    def test_mps_unavailable_keeps_cpu_path(self):
        import torch
        from famjet.ops import probe_ops
        with patch.object(torch.backends.mps, "is_available", return_value=False):
            report = probe_ops("mps", [{"name": "tiny", "batch": 1, "heads": 1, "J": 4, "K": 16, "V": 8, "length": 8}])
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["elapsed_seconds"])
        self.assertTrue(report["reason"])
        cpu = probe_ops("cpu", [{"name": "tiny", "batch": 1, "heads": 1, "J": 4, "K": 16, "V": 8, "length": 8}])
        self.assertEqual(cpu["status"], "ok", cpu)
        self.assertTrue(all(cell["status"] == "ok" for cell in cpu["cells"]))

    def test_cpu_matrix_checks_forward_gradients_and_restore(self):
        from famjet.ops import probe_ops
        report = probe_ops("cpu", [{"name": "tiny", "batch": 1, "heads": 1, "J": 4, "K": 16, "V": 8, "length": 8}])
        names = {cell["operation"] for cell in report["cells"]}
        self.assertTrue({"exp_arithmetic_reduction", "matmul", "einsum", "activations", "normalization", "index_gather_mask", "mlp_backward", "rates_backward", "checkpoint_backward", "short_convolution_backward", "serialization", "rng_restore"}.issubset(names))
        self.assertEqual({cell["dtype"] for cell in report["cells"]}, {"float64", "float32"})
        self.assertTrue(all(cell["status"] == "ok" for cell in report["cells"]), report)
        for cell in report["cells"]:
            self.assertGreaterEqual(cell["max_abs_error"], 0)
            self.assertGreaterEqual(cell["elapsed_seconds"], 0)

    def test_shape_guard_covers_rate_and_mlp_workspaces(self):
        from famjet.ops import probe_ops
        for shape in [
            {"name": "large_rates", "batch": 1, "heads": 1, "J": 10000, "K": 1, "V": 1, "length": 10000},
            {"name": "large_mlp", "batch": 1, "heads": 1, "J": 1, "K": 1, "V": 100000, "length": 1},
        ]:
            # Never allocate the deliberately unsafe fixture while checking the guard.
            with self.subTest(shape=shape["name"]), patch("famjet.ops._fixture", side_effect=RuntimeError("allocation blocked by test")), self.assertRaises(ValueError):
                probe_ops("cpu", [shape])

    def test_cpu_probe_preserves_existing_mps_rng_stream(self):
        import torch
        from famjet.ops import probe_ops
        if not torch.backends.mps.is_available():
            self.skipTest("native MPS not exposed to this process")
        before = torch.mps.get_rng_state().clone()
        probe_ops("cpu", [{"name": "tiny", "batch": 1, "heads": 1, "J": 4, "K": 16, "V": 8, "length": 8}])
        self.assertTrue(torch.equal(before, torch.mps.get_rng_state()), "CPU probes must preserve the caller's MPS RNG stream")

    def test_invalid_shape_is_rejected_before_allocation(self):
        from famjet.ops import probe_ops
        with self.assertRaises(ValueError):
            probe_ops("cpu", [{"name": "invalid", "batch": -1}])


if __name__ == "__main__":
    unittest.main()
