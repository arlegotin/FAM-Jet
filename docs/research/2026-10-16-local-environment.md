# Preliminary local discovery — 16 October 2026

Read-only observations during specification work, approximately 16:56 UTC. This is an environment snapshot, not a completed WP00 compatibility or performance assessment. No packages were installed and no tensors or models were run.

| Observation | Value | Command |
|---|---|---|
| Architecture | `arm64` | `uname -m` |
| OS | macOS 26.7.1, build 25G241 | `sw_vers` |
| Chip | Apple M3 Max | `sysctl -n machdep.cpu.brand_string` |
| Installed unified memory | 38,654,705,664 bytes = 36 GiB | `sysctl -n hw.memsize` |
| Physical CPU count | 14 | `sysctl -n hw.physicalcpu` |
| Available volume storage | 46,663,416 KiB, approximately 44.50 GiB; volume reports 95% used | `df -k .` |
| Swap | total 19,456.00 MiB; used 17,793.69 MiB; free 1,662.31 MiB | `sysctl -n vm.swapusage` |
| Python on PATH | `/opt/homebrew/bin/python3`, Python 3.14.6 | `command -v python3`; `python3 --version` |
| Optional environment manager | `uv 0.11.29` | `uv --version` |
| Developer tools | `/Applications/Xcode.app/Contents/Developer` | `xcode-select -p` |
| Git | 2.49.0 | `git --version` |
| Power configuration | AC configuration lists `powermode 0` | `pmset -g custom` |

`vm_stat` reported 16,384-byte pages, 70,871 free pages, 905,852 active pages, 902,406 inactive pages, 314,068 wired pages, and 103,659 pages occupied by the compressor. These counters are not a safe tensor-allocation budget. Cumulative swap counters do not establish current swap throughput. `pmset -g custom` describes configuration, not a thermal measurement or proof of power-source stability.

The first sandboxed `sysctl` request was denied; the same read-only hardware query succeeded with tool escalation. No system setting was changed. No serial number or hardware UUID was collected.

Execution must rediscover available capacity and pressure, select a compatible native Python/PyTorch pair, and run the operation/gradient matrix. The discovered Python version is not a prescribed dependency floor. No PyTorch version, MPS availability, GPU core count, safe batch size, training duration, or native timing is established here. Existing swap use must be recorded when selecting a working envelope and timing conditions; installed memory alone is insufficient.
