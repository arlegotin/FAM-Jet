"""Independent prospective protocol check; imports no scientific project code."""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from pathlib import Path
import platform
import time

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[variable] = "1"
import numpy as np

ROOT_SEED = 2026101619
FIXTURES = [
    ("gaussian_history", (0.90, 0.05, 0.05), False),
    ("gaussian_balanced", (0.45, 0.45, 0.10), False),
    ("gaussian_seed", (0.05, 0.90, 0.05), False),
    ("gaussian_residual", (0.05, 0.05, 0.90), False),
    ("skewed_seed", (0.05, 0.90, 0.05), True),
    ("gaussian_pure_history", (1.0, 0.0, 0.0), False),
    ("gaussian_pure_residual", (0.0, 0.0, 1.0), False),
]


def rng(*key):
    return np.random.default_rng(np.random.SeedSequence([ROOT_SEED, *key]))


def matrix(generator, h, s, variances, skewed):
    vh, vs, ve = variances
    a = generator.standard_normal(h) * math.sqrt(vh)
    z = generator.standard_normal(s)
    b = ((np.exp(z) - math.exp(0.5)) / math.sqrt(math.e * (math.e - 1))) if skewed else z
    b *= math.sqrt(vs)
    e = generator.standard_normal((h, s)) * math.sqrt(ve)
    return a[:, None] + b[None, :] + e


def resample(d, generator, draws, chunk=1000):
    h, s = d.shape
    values = np.empty(draws)
    for start in range(0, draws, chunk):
        n = min(chunk, draws - start)
        wh = generator.multinomial(h, np.full(h, 1 / h), size=n)
        ws = generator.multinomial(s, np.full(s, 1 / s), size=n)
        values[start:start+n] = np.sum((wh @ d) * ws, axis=1) / (h*s)
    return values


def conditional_variance(d):
    h, s = d.shape
    mean = d.mean()
    a, b = d.mean(1) - mean, d.mean(0) - mean
    c = d - mean - a[:, None] - b[None, :]
    return float(np.mean(a*a)/h + np.mean(b*b)/s + np.mean(c*c)/(h*s))


def wilson(k, n, z=1.959963984540054):
    p = k/n
    center = (p + z*z/(2*n))/(1 + z*z/n)
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/(1 + z*z/n)
    return [center-half, center+half]


def summarize_event(values):
    n, k = len(values), int(np.sum(values))
    return {"count": k, "n": n, "rate": k/n, "wilson95": wilson(k, n)}


def self_check():
    d = np.array([[1., 3.], [7., -2.]])
    seq = list(itertools.product(range(2), repeat=2))
    enumerated = np.array([d[np.ix_(hh, ss)].mean() for hh in seq for ss in seq])
    assert np.isclose(enumerated.var(), conditional_variance(d), atol=1e-14)
    hh, ss = [1, 1], [0, 1]
    wh, ws = np.bincount(hh, minlength=2), np.bincount(ss, minlength=2)
    assert (wh @ d @ ws)/4 == d[np.ix_(hh, ss)].mean()
    assert np.array_equal(resample(d, rng(999), 30)+2, resample(d+2, rng(999), 30))
    assert np.all(resample(np.zeros((2, 3)), rng(998), 30) == 0)


def coverage(args):
    start = time.monotonic()
    output = {"root_seed": ROOT_SEED, "python": platform.python_version(), "numpy": np.__version__,
              "h": args.histories, "draws": args.draws, "requested_outer": args.outer,
              "max_seconds": args.max_seconds, "scenarios": []}
    for fi, (name, variances, skewed) in enumerate(FIXTURES):
        selected = args.fixture or [item[0] for item in FIXTURES[:5]]
        if name not in selected:
            continue
        for s in (4, 8, 16):
            h = args.histories
            vh, vs, ve = variances
            truth_v = vh/h + vs/s + ve/(h*s)
            expected_boot_v = (h-1)/h*vh/h + (s-1)/s*vs/s + ((h-1)/h + (s-1)/s + (h-1)*(s-1)/(h*s))*ve/(h*s)
            delta = 2.8*math.sqrt(truth_v)
            records = []
            for rep in range(args.outer):
                if time.monotonic() - start > args.max_seconds:
                    break
                d = matrix(rng(10, fi, s, rep), h, s, variances, skewed)
                observed = float(d.mean())
                boot = resample(d, rng(20, fi, s, rep), args.draws)
                lo, hi = np.quantile(boot, [0.025, 0.975], method="linear")
                null = boot - observed
                p0 = (1 + int(np.sum(np.abs(null) >= abs(observed))))/(args.draws+1)
                p1 = (1 + int(np.sum(np.abs(null) >= abs(observed+delta))))/(args.draws+1)
                oracle = 1.959963984540054*math.sqrt(truth_v)
                records.append({"rep": rep, "observed": observed, "lo": float(lo), "hi": float(hi),
                                "p_null": p0, "p_mde": p1, "conditional_boot_variance": conditional_variance(d),
                                "sample_boot_variance": float(boot.var(ddof=1)),
                                "covers": bool(lo <= 0 <= hi), "primary_power": bool(lo+delta > 0 or hi+delta < 0),
                                "oracle_covers": bool(abs(observed) <= oracle),
                                "oracle_power": bool(abs(observed+delta) > oracle)})
            if not records:
                break
            scenario = {"fixture": name, "fixture_index": fi, "s": s, "variances": variances,
                        "true_mean": 0., "true_variance": truth_v, "mde_shift": delta,
                        "expected_boot_variance": expected_boot_v, "expected_variance_ratio": expected_boot_v/truth_v,
                        "coverage": summarize_event([r["covers"] for r in records]),
                        "primary_type_i": summarize_event([not r["covers"] for r in records]),
                        "primary_power": summarize_event([r["primary_power"] for r in records]),
                        "secondary_type_i": summarize_event([r["p_null"] <= .05 for r in records]),
                        "secondary_power": summarize_event([r["p_mde"] <= .05 for r in records]),
                        "oracle_coverage": summarize_event([r["oracle_covers"] for r in records]),
                        "oracle_power": summarize_event([r["oracle_power"] for r in records]),
                        "mean_conditional_variance_ratio": float(np.mean([r["conditional_boot_variance"] for r in records])/truth_v),
                        "mean_simulated_boot_variance_ratio": float(np.mean([r["sample_boot_variance"] for r in records])/truth_v),
                        "records": records}
            output["scenarios"].append(scenario)
            output["elapsed_seconds"] = time.monotonic()-start
            args.output.write_text(json.dumps(output, indent=2)+"\n")
            print(name, s, "n", len(records), "coverage", scenario["coverage"], "elapsed", round(output["elapsed_seconds"], 1), flush=True)
        if time.monotonic()-start > args.max_seconds:
            break


def endpoint(args):
    start = time.monotonic()
    output = {"root_seed": ROOT_SEED, "fixed_fixture_rep": 0, "runs": []}
    # Independent repeats on fixed matrices: evidence on endpoint MC only.
    for fi, s in ((0, 4), (2, 4), (2, 16), (4, 4)):
        name, variances, skewed = FIXTURES[fi]
        d = matrix(rng(10, fi, s, 0), 128, s, variances, skewed)
        for repeat in range(4):
            generators = [rng(30, fi, s, repeat, b) for b in range(4)]
            batches = [np.empty(0) for _ in range(4)]
            trail = []
            for total in (2000, 4000, 8000, 16000, 32000, 64000, 128000):
                for b in range(4):
                    batches[b] = np.concatenate((batches[b], resample(d, generators[b], total//4-len(batches[b]))))
                estimates = np.array([np.quantile(x, [.025, .975], method="linear") for x in batches])
                pooled = np.quantile(np.concatenate(batches), [.025, .975], method="linear")
                se = estimates.std(axis=0, ddof=1)/2
                ratios = se/(pooled[1]-pooled[0])
                passed = bool(np.all(ratios < .01))
                trail.append({"draws": total, "endpoints": pooled.tolist(), "endpoint_se": se.tolist(),
                              "se_over_width": ratios.tolist(), "passed": passed})
                if passed:
                    break
            output["runs"].append({"fixture": name, "s": s, "repeat": repeat, "trail": trail,
                                   "cap_failure": not trail[-1]["passed"]})
            output["elapsed_seconds"] = time.monotonic()-start
            args.output.write_text(json.dumps(output, indent=2)+"\n")
            print(name, s, repeat, "draws", trail[-1]["draws"], "ratios", trail[-1]["se_over_width"], flush=True)
            if time.monotonic()-start > args.max_seconds:
                return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("coverage", "endpoint"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--histories", type=int, default=128)
    parser.add_argument("--outer", type=int, default=256)
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--max-seconds", type=float, default=120.)
    parser.add_argument("--fixture", action="append", choices=[x[0] for x in FIXTURES])
    args = parser.parse_args()
    self_check()
    (coverage if args.mode == "coverage" else endpoint)(args)
