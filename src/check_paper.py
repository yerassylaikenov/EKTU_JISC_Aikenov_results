#!/usr/bin/env python3
"""Compare every number printed in the paper with the current results.

Run after model.py and robustness.py. Exit code 0 means all values match
(rounded as they are printed in the paper).
"""
import json
import pathlib
import sys
from math import ceil, log2

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = json.load(open(ROOT / "results" / "bench.json"))
M = json.load(open(ROOT / "results" / "model_results.json"))
R = json.load(open(ROOT / "results" / "robustness.json"))
TH = {r["n"]: r["bw_mbit"] for r in M["bandwidth_threshold"]}
H, TR, TB = B["sha256_node_us"] * 1e-6, B["rsa_verify_derive_prime_ms"] * 1e-3, B["bls_verify_ms"] * 1e-3


def total(wbytes, tver, mbit):
    return (8 * wbytes / (mbit * 1e6) + tver) * 1e3      # ms


def merkle(n):
    d = ceil(log2(n)); return 32 * d, d * H


W = {}
for n, bw in M.get("rsa_given_wins", []):
    W.setdefault(n, []).append(bw)

S = json.load(open(ROOT / "results" / "bench_series.json"))["summary"]
D = 20                                                    # depth at n = 1e6

PAPER = [   # (where in the paper, printed value, computed value, decimals)
    ("Table 1  t_h (us)", 0.86, B["sha256_node_us"], 2),
    ("Table 1  t_R (ms)", 1.23, B["rsa_verify_derive_prime_ms"], 2),
    ("Table 1  t_B (ms)", 2.11, B["bls_verify_ms"], 2),
    ("Sec 3    t_R series min (ms)", 1.18, S["rsa_verify_derive_prime_ms"]["min"], 2),
    ("Sec 3    t_R series max (ms)", 1.40, S["rsa_verify_derive_prime_ms"]["max"], 2),
    ("Sec 3    t_B series min (ms)", 2.04, S["bls_verify_ms"]["min"], 2),
    ("Sec 3    t_B series max (ms)", 2.15, S["bls_verify_ms"]["max"], 2),
    ("Sec 3    full 3072-bit exponent (ms)", 8.67, B["rsa_full_exponent_ms"], 2),
    ("Sec 3    single pairing (ms)", 1.50, B["bls_single_pairing_ms"], 2),
    ("Table 2  n=1e2 (Mbit/s)", 0.67, TH[10**2], 2),
    ("Table 2  n=1e3", 1.04, TH[10**3], 2),
    ("Table 2  n=1e4", 1.53, TH[10**4], 2),
    ("Table 2  n=1e5", 1.89, TH[10**5], 2),
    ("Table 2  n=1e6", 2.26, TH[10**6], 2),
    ("Table 2  n=1e7", 2.76, TH[10**7], 2),
    ("Eq (5)   RSA crossover n*", 4096, M["crossover"]["RSA"], 0),
    ("Sec 4    Merkle verify at n=1e6 (us)", 17, D * H * 1e6, 0),
    ("Sec 4    RSA / Merkle verify ratio (x10)", 70, TR / (D * H), -1),
    ("Sec 4    BLS / Merkle verify ratio (x10)", 120, TB / (D * H), -1),
    ("Sec 4    BLS / RSA verify ratio", 1.7, TB / TR, 1),
    ("Sec 4    worked ex. B=50 Merkle (ms)", 0.12, total(*merkle(10**6), 50), 2),
    ("Sec 4    worked ex. B=50 BLS (ms)", 2.12, total(48, TB, 50), 2),
    ("Sec 4    worked ex. B=0.5 Merkle (ms)", 10.3, total(*merkle(10**6), 0.5), 1),
    ("Sec 4    worked ex. B=0.5 BLS (ms)", 2.9, total(48, TB, 0.5), 1),
    ("Sec 4    RSA winning cells (verifier derives prime)", 0, len(M.get("rsa_derive_wins", [])), 0),
    ("Sec 4    RSA window n=1e6, lower (Mbit/s)", 2.2, min(W.get(10**6, [0])), 1),
    ("Sec 4    RSA window n=1e6, upper (Mbit/s)", 2.4, max(W.get(10**6, [0])), 1),
    ("Sec 4    RSA window n=1e7, lower (Mbit/s)", 2.2, min(W.get(10**7, [0])), 1),
    ("Sec 4    RSA window n=1e7, upper (Mbit/s)", 3.6, max(W.get(10**7, [0])), 1),
    ("Sec 3    robustness: all x0.5, n=1e6", 4.52, R["cases"]["all x0.5"]["boundary_n1e6"], 2),
    ("Sec 3    robustness: all x2, n=1e6", 1.13, R["cases"]["all x2"]["boundary_n1e6"], 2),
    ("Sec 3/5  critical ratio t_R/t_B", 0.53, R["critical_ratio_tR_over_tB"], 2),
    ("Sec 3/5  measured ratio", 0.58, R["measured_ratio"], 2),
    ("Sec 3    prover-supplied ratio", 0.41, R["prover_supplied_ratio"], 2),
    ("Sec 3/5  ratio across series, min", 0.56, S["ratio_tR_tB"]["min"], 2),
    ("Sec 3/5  ratio across series, max", 0.66, S["ratio_tR_tB"]["max"], 2),
]


def main():
    ok = True
    for name, want, got, dec in PAPER:
        good = round(got, dec) == round(want, dec)
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name:48s} paper {want:<8} run {got:.4g}")
    print("ALL PASS" if ok else "MISMATCH - see FAIL lines "
          "(expected if you re-ran bench.py on different hardware)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
