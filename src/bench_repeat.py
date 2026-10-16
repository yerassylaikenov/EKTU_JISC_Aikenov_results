#!/usr/bin/env python3
"""Run bench.py several times as independent series and report the spread.
Writes results/bench_series.json."""
import json, pathlib, statistics as st, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
K = int(args[0]) if args else 7
WRITE = "--write" in sys.argv     # replace bench.json with the new medians
keys = ["sha256_node_us", "rsa_verify_derive_prime_ms", "rsa_verify_given_prime_ms",
        "bls_verify_ms", "bls_single_pairing_ms", "rsa_full_exponent_ms"]
runs = []
bench = ROOT / "results" / "bench.json"
keep = bench.read_text() if bench.exists() else None
for i in range(K):
    subprocess.run([sys.executable, str(ROOT / "src" / "bench.py")], check=True,
                   capture_output=True)
    runs.append(json.load(open(bench)))
    print(f"series {i+1}/{K} done", flush=True)
if keep is not None and not WRITE:
    bench.write_text(keep)                       # leave the paper's values in place
out = {"series": K, "runs": runs, "summary": {}}
for k in keys:
    v = [r[k] for r in runs]
    out["summary"][k] = {"median": st.median(v), "min": min(v), "max": max(v)}
ratios = [r["rsa_verify_derive_prime_ms"] / r["bls_verify_ms"] for r in runs]
out["summary"]["ratio_tR_tB"] = {"median": st.median(ratios), "min": min(ratios), "max": max(ratios)}
json.dump(out, open(ROOT / "results" / "bench_series.json", "w"), indent=1)
if WRITE:
    med = dict(runs[-1])
    med.update({k: out["summary"][k]["median"] for k in keys})
    med["method"] = f"median of {K} independent series, each >=200 repetitions"
    json.dump(med, open(bench, "w"), indent=1)
    print("results/bench.json replaced with the new medians")
for k, v in out["summary"].items():
    print(f"{k:30s} median {v['median']:.4f}  range {v['min']:.4f} .. {v['max']:.4f}")
