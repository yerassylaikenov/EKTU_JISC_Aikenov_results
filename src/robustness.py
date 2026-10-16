#!/usr/bin/env python3
"""Robustness of the conclusions to the timing parameters (Section 3 of the
paper, paragraph after the measurement description).

1. Scales every operation, or only one, by x0.5 and x2 and reports the
   Merkle/bilinear bandwidth boundary and whether RSA wins anywhere.
2. Finds the critical ratio t_R / t_B below which RSA gains a winning window.
Reads results/bench.json; writes results/robustness.json.
"""
import json
import pathlib
from math import ceil, log2

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = json.load(open(ROOT / "results" / "bench.json"))
H = B["sha256_node_us"] * 1e-6
TR = B["rsa_verify_derive_prime_ms"] * 1e-3
TB = B["bls_verify_ms"] * 1e-3
NS = [10 ** k for k in range(2, 8)]
BWS = [k / 10 * 1e6 for k in range(1, 1001)]          # 0.1 .. 100 Mbit/s


def boundary(n, h, tb):
    d = ceil(log2(n))
    return 8 * (32 * d - 48) / (tb - d * h) / 1e6


def rsa_cells(h, tr, tb):
    c = 0
    for n in NS:
        d = ceil(log2(n))
        for bw in BWS:
            tm = 8 * 32 * d / bw + d * h
            tbls = 8 * 48 / bw + tb
            trsa = 8 * 384 / bw + tr
            c += trsa < min(tm, tbls)
    return c


def critical_ratio():
    lo, hi = 0.05 * TB, TR
    for _ in range(50):
        mid = (lo + hi) / 2
        if rsa_cells(H, mid, TB) > 0:
            lo = mid
        else:
            hi = mid
    return hi / TB


def main():
    cases = {"measured": (1, 1, 1), "all x0.5": (.5, .5, .5),
             "all x2": (2, 2, 2), "pairing x0.5": (1, 1, .5),
             "pairing x2": (1, 1, 2), "RSA x0.5": (1, .5, 1)}
    out = {"cases": {}}
    for name, (fh, fr, fb) in cases.items():
        h, tr, tb = H * fh, TR * fr, TB * fb
        out["cases"][name] = {
            "boundary_n1e2": round(boundary(10 ** 2, h, tb), 2),
            "boundary_n1e6": round(boundary(10 ** 6, h, tb), 2),
            "boundary_n1e7": round(boundary(10 ** 7, h, tb), 2),
            "rsa_winning_cells": rsa_cells(h, tr, tb)}
        print(f"{name:14s}", out["cases"][name])
    out["critical_ratio_tR_over_tB"] = round(critical_ratio(), 3)
    out["measured_ratio"] = round(TR / TB, 3)
    out["prover_supplied_ratio"] = round(B["rsa_verify_given_prime_ms"] / B["bls_verify_ms"], 3)
    print("critical t_R/t_B:", out["critical_ratio_tR_over_tB"],
          "| measured:", out["measured_ratio"],
          "| prover-supplied prime:", out["prover_supplied_ratio"])
    json.dump(out, open(ROOT / "results" / "robustness.json", "w"), indent=1)


if __name__ == "__main__":
    main()
