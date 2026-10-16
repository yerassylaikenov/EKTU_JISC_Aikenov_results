#!/usr/bin/env python3
"""
Revocation primitives for consent withdrawal in a hybrid-blockchain medical
service: Merkle tree vs RSA accumulator vs bilinear (pairing) accumulator.

Metrics per non-revocation check:
    |w|      witness size                    bytes
    t_ver    verification time               seconds
    T        total check time = 8|w|/B + t_ver
Design question: which primitive minimises T, and how does the answer move
with the size of the revocation set n and the client link bandwidth B?
"""
import json
from math import ceil, log2

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
_B = json.load(open(ROOT / "results" / "bench.json"))

P = {
    # timing parameters come from results/bench.json (produced by bench.py)
    "hash_us": round(_B["sha256_node_us"], 2),          # SHA-256, 64-byte node
    "rsa_bits": 3072,                                   # 128-bit security
    "rsa_exp_ms": round(_B["rsa_verify_derive_prime_ms"], 2),   # verifier derives prime
    "rsa_exp_ms_given": round(_B["rsa_verify_given_prime_ms"], 2),  # prover supplies prime
    "bls_bits": 384,                                    # compressed G1, BLS12-381
    "bls_pair_ms": round(_B["bls_verify_ms"], 2),       # G2 mult + two-pairing product
    "acc_root_bytes": 32,
    "checks_per_day": 1_000_000,
}

NS = [10**2, 10**3, 10**4, 10**5, 10**6, 10**7]
BWS = [0.1, 0.5, 1, 2, 5, 10, 50, 100]      # Mbit/s


def merkle(n):
    d = ceil(log2(n))
    return 32 * d, d * P["hash_us"] / 1e6


def rsa(n):
    return P["rsa_bits"] // 8, P["rsa_exp_ms"] / 1e3


def rsa_given(n):
    return P["rsa_bits"] // 8, P["rsa_exp_ms_given"] / 1e3


def bls(n):
    return P["bls_bits"] // 8, P["bls_pair_ms"] / 1e3


SCHEMES = {"Merkle": merkle, "RSA": rsa, "BLS": bls}


def total(w_bytes, t_ver, bw_mbit):
    return 8 * w_bytes / (bw_mbit * 1e6) + t_ver


def main():
    out = {"params": P, "ns": NS, "bws": BWS, "rows": [], "grid": [],
           "bandwidth_threshold": []}

    for n in NS:
        for name, f in SCHEMES.items():
            w, t = f(n)
            out["rows"].append({"n": n, "scheme": name, "w_bytes": w,
                                "t_ver_ms": t * 1e3,
                                "depth": ceil(log2(n)) if name == "Merkle" else None})

    # crossover: Merkle witness exceeds a constant-size witness
    out["crossover"] = {
        "RSA": 2 ** (P["rsa_bits"] // 8 / 32),
        "BLS": 2 ** (P["bls_bits"] // 8 / 32),
    }

    # decision grid: which scheme minimises total check time
    order = list(SCHEMES)
    for bw in BWS:
        row = []
        for n in NS:
            best, bt = None, 1e9
            for name, f in SCHEMES.items():
                w, t = f(n)
                T = total(w, t, bw)
                if T < bt:
                    best, bt = name, T
            row.append(order.index(best))
            out["grid"].append({"bw": bw, "n": n, "winner": best,
                                "T_ms": bt * 1e3})
        out.setdefault("grid_matrix", []).append(row)

    # bandwidth at which Merkle stops winning, per n
    for n in NS:
        wm, tm = merkle(n)
        wb, tb = bls(n)
        lo, hi = 0.01, 1000.0
        for _ in range(200):
            mid = (lo * hi) ** 0.5
            if total(wm, tm, mid) < total(wb, tb, mid):
                hi = mid
            else:
                lo = mid
        out["bandwidth_threshold"].append({"n": n, "bw_mbit": (lo * hi) ** 0.5})

    # RSA sensitivity: does the prover-supplied-prime variant win anywhere?
    rsa_cells = []
    for bw in [x / 10 for x in range(1, 1001)]:
        for n in NS:
            ts = {"Merkle": total(*merkle(n), bw), "BLS": total(*bls(n), bw),
                  "RSA_derive": total(*rsa(n), bw),
                  "RSA_given": total(*rsa_given(n), bw)}
            best_wo = min(ts["Merkle"], ts["BLS"])
            if ts["RSA_given"] < best_wo:
                rsa_cells.append((n, bw))
            if ts["RSA_derive"] < best_wo:
                out.setdefault("rsa_derive_wins", []).append((n, bw))
    out["rsa_given_wins"] = rsa_cells
    json.dump(out, open(ROOT / "results" / "model_results.json", "w"), indent=1)

    print(f"{'n':>9} {'Merkle w':>9} {'t,ms':>7} {'RSA w':>7} {'t,ms':>7}"
          f" {'BLS w':>7} {'t,ms':>7}")
    for n in NS:
        wm, tm = merkle(n); wr, tr = rsa(n); wb, tb = bls(n)
        print(f"{n:>9} {wm:>9} {tm*1e3:>7.3f} {wr:>7} {tr*1e3:>7.3f}"
              f" {wb:>7} {tb*1e3:>7.3f}")
    print("\ncrossover (Merkle witness = constant witness):",
          {k: round(v) for k, v in out["crossover"].items()})
    print("\nbandwidth threshold (Merkle loses below, Mbit/s):")
    for r in out["bandwidth_threshold"]:
        print(f"  n = {r['n']:>9}: {r['bw_mbit']:.3f}")
    figures(out)


def figures(out):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.grid": True, "grid.alpha": 0.3,
                         "legend.frameon": False, "figure.dpi": 200,
                         "savefig.bbox": "tight"})
    COL = {"Merkle": "#1B6CA8", "RSA": "#C8102E", "BLS": "#0F9D58"}
    LAB = {"Merkle": "Меркле ағашы", "RSA": "RSA аккумуляторы",
           "BLS": "билинеарлы аккумулятор"}

    # Fig 1: witness size
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    for name, f in SCHEMES.items():
        ax.plot(NS, [f(n)[0] for n in NS], marker="o", ms=5, lw=2,
                color=COL[name], label=LAB[name])
    ax.set_xscale("log")
    ax.set_xlabel("кері қайтарылған келісімдер саны, n")
    ax.set_ylabel("куәлік көлемі, байт")
    ax.legend(loc="upper left")
    fig.savefig(ROOT / "figures" / "fig1.png"); plt.close(fig)

    # Fig 2: verification time
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    for name, f in SCHEMES.items():
        ax.plot(NS, [f(n)[1] * 1e3 for n in NS], marker="s", ms=5, lw=2,
                color=COL[name], label=LAB[name])
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("кері қайтарылған келісімдер саны, n")
    ax.set_ylabel("тексеру уақыты, мс")
    ax.legend(loc="center left")
    fig.savefig(ROOT / "figures" / "fig2.png"); plt.close(fig)

    # Fig 3: total check time at three bandwidths
    fig, axes = plt.subplots(1, 3, figsize=(8.2, 2.9), sharey=True)
    for ax, bw in zip(axes, (0.5, 2, 50)):
        for name, f in SCHEMES.items():
            w_t = [total(*f(n), bw) * 1e3 for n in NS]
            ax.plot(NS, w_t, marker="o", ms=4, lw=1.8, color=COL[name],
                    label=LAB[name])
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_title(f"B = {str(bw).replace('.', ',')} Мбит/с", fontsize=9, color="0.3", pad=4)
        ax.set_xlabel("n")
    axes[0].set_ylabel("толық тексеру уақыты, мс")
    axes[2].legend(loc="upper left", fontsize=7.5)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(ROOT / "figures" / "fig3.png"); plt.close(fig)

    # Fig 4: decision map
    M = np.array(out["grid_matrix"])
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    cmap = ListedColormap([COL["Merkle"], COL["RSA"], COL["BLS"]])
    ax.imshow(M, origin="lower", aspect="auto", cmap=cmap, vmin=0, vmax=2)
    ax.set_xticks(range(len(NS)))
    ax.set_xticklabels([f"10{'⁰¹²³⁴⁵⁶⁷⁸⁹'[int(log2(n)/log2(10)+0.5)]}"
                        for n in NS])
    ax.set_yticks(range(len(BWS))); ax.set_yticklabels(BWS)
    ax.set_xlabel("кері қайтарылған келісімдер саны, n")
    ax.set_ylabel("клиент арнасының жылдамдығы, Мбит/с")
    ax.grid(False)
    import matplotlib.patches as mp
    ax.legend(handles=[mp.Patch(facecolor=COL[k], label=LAB[k])
                       for k in ("Merkle", "BLS")],
              loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=2,
              fontsize=8.5)
    fig.savefig(ROOT / "figures" / "fig4.png"); plt.close(fig)
    print("figures written")


if __name__ == "__main__":
    main()
