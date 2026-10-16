#!/usr/bin/env python3
"""Reproduce the paper.

    python run_all.py            # use the shipped measurements (reproduces the paper exactly)
    python run_all.py --measure  # re-measure on this machine first (numbers will differ)
"""
import subprocess
import sys

steps = (["src/bench_repeat.py"] if "--measure" in sys.argv else []) + \
        ["src/model.py", "src/robustness.py", "src/check_paper.py"]
for s in steps:
    print(f"\n=== {s} ===", flush=True)
    extra = ["7", "--write"] if s.endswith("bench_repeat.py") else []
    r = subprocess.run([sys.executable, s] + extra)
    if r.returncode and s != "src/check_paper.py":
        sys.exit(r.returncode)
if "--measure" in sys.argv:
    print("\nRe-measured on this machine: differences from the paper are expected.")
    sys.exit(0)
sys.exit(r.returncode)
