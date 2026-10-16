#!/usr/bin/env python3
"""Measure the verifier-side cost of each revocation primitive.

Merkle  : one SHA-256 over a 64-byte node (two 32-byte children)
RSA     : membership check  w^e mod N == A,  N 3072-bit, e a 256-bit prime
          (a) prover supplies the prime e  -> verifier runs one primality test
          (b) verifier derives e itself    -> full hash-to-prime search
BLS     : bilinear accumulator check  e(w, g2^(s+x)) == e(A, g2) on BLS12-381
          -> one G2 scalar multiplication + a two-pairing product
Reports medians over many repetitions.
"""
import hashlib
import json
import os
import platform
import statistics as st
import time

import gmpy2
from py_arkworks_bls12381 import G1Point, G2Point, GT, Scalar


def timeit(fn, reps, warm=20):
    for _ in range(warm):
        fn()
    out = []
    for _ in range(reps):
        t0 = time.perf_counter_ns()
        fn()
        out.append(time.perf_counter_ns() - t0)
    return st.median(out) / 1e6          # ms


def sha256_node():
    nodes = [os.urandom(64) for _ in range(1000)]
    sha = hashlib.sha256
    def run():
        for x in nodes:
            sha(x).digest()
    return timeit(run, 200) / 1000


def rsa_setup(bits=3072):
    rs = gmpy2.random_state(20260918)
    p = gmpy2.next_prime(gmpy2.mpz_urandomb(rs, bits // 2) | (1 << (bits // 2 - 1)))
    q = gmpy2.next_prime(gmpy2.mpz_urandomb(rs, bits // 2) | (1 << (bits // 2 - 1)))
    N = p * q
    g = gmpy2.mpz(65537)
    return N, g, rs


def hash_to_prime(data, bits=256):
    ctr = 0
    while True:
        c = int.from_bytes(hashlib.sha256(data + ctr.to_bytes(8, "big"))
                           .digest(), "big") | 1 | (1 << (bits - 1))
        c = gmpy2.mpz(c)
        if gmpy2.is_prime(c, 25):
            return c, ctr
        ctr += 1


def rsa_bench():
    N, g, rs = rsa_setup()
    e, _ = hash_to_prime(b"consent-0001")
    w = gmpy2.powmod(g, gmpy2.mpz_urandomb(rs, 3072), N)
    A = gmpy2.powmod(w, e, N)

    def verify_given_prime():
        assert gmpy2.is_prime(e, 25)
        assert gmpy2.powmod(w, e, N) == A

    ids = [os.urandom(16) for _ in range(3000)]
    it = iter(ids * 2)

    def verify_derive_prime():
        e2, _ = hash_to_prime(next(it))
        gmpy2.powmod(w, e2, N)

    return (timeit(verify_given_prime, 400),
            timeit(verify_derive_prime, 2000, warm=5),
            timeit(lambda: gmpy2.powmod(w, gmpy2.mpz_urandomb(rs, 3072), N), 200))


def bls_bench():
    g1, g2 = G1Point(), G2Point()
    s = Scalar(123456789)                       # trapdoor (setup only)
    x = Scalar(987654321)                       # element
    g2s = g2 * s                                # public parameter
    A = g1 * Scalar(424242)                     # accumulator value
    w = A * Scalar(1)                           # placeholder witness

    def verify():
        lhs_g2 = g2s + g2 * x                   # g2^(s+x): one G2 scalar mult
        GT.multi_pairing([w, -A], [lhs_g2, g2])

    def single_pairing():
        GT.pairing(g1, g2)

    return timeit(verify, 300), timeit(single_pairing, 300)


def main():
    res = {"host": platform.processor() or platform.machine(),
           "python": platform.python_version(),
           "gmp": gmpy2.mp_version(), "openssl_backend": "hashlib"}
    res["sha256_node_us"] = sha256_node() * 1000
    rg, rd, rfull = rsa_bench()
    res["rsa_verify_given_prime_ms"] = rg
    res["rsa_verify_derive_prime_ms"] = rd
    res["rsa_full_exponent_ms"] = rfull
    bv, bp = bls_bench()
    res["bls_verify_ms"] = bv
    res["bls_single_pairing_ms"] = bp
    import pathlib
    out = pathlib.Path(__file__).resolve().parent.parent / "results" / "bench.json"
    json.dump(res, open(out, "w"), indent=1)
    print("written", out)
    for k, v in res.items():
        print(f"{k:32s} {v:.4f}" if isinstance(v, float) else f"{k:32s} {v}")


if __name__ == "__main__":
    main()
