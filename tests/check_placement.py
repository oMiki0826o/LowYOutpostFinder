"""File: check_placement.py
Modification: 2026-10-12 — compare C output with JDK Random oracle.
"""
import csv
import io
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
exe = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'bin' / 'lowyoutpost'
subprocess.run(['javac', str(root / 'tests' / 'PlacementOracle.java')], check=True)
for seed in ('0', '123', '-1', '-9223372036854775808', '9223372036854775807'):
    radius = '4096'
    c = subprocess.run([str(exe), '--seed', seed, '--radius', radius,
                        '--candidates-only', '--top', '100000'], check=True,
                       text=True, capture_output=True).stdout
    j = subprocess.run(['java', '-cp', str(root / 'tests'), 'PlacementOracle', seed, radius],
                       check=True, text=True, capture_output=True).stdout
    a = list(csv.DictReader(io.StringIO(c)))
    b = list(csv.DictReader(io.StringIO(j)))
    assert a == b, f'placement mismatch on seed={seed}: C={len(a)} vs Java={len(b)}'
    print(f'seed={seed:>21}  checked={len(a):>3} PASS')
